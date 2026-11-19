# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp==1.28.1", "pillow>=10,<12"]
# ///
"""adbmm MCP stdio server — emulator control for Claude.

Spawned by the Claude Code CLI as a normal child process, so it reaches the
adb server on 127.0.0.1:5037 even though the Bash tool (sandboxed) cannot.

No wildcard shell tool: every tool builds a fixed argv. Emulator-only serials
(^emulator-\\d+$) — a plugged-in physical phone can never be driven, because
logcat/screenshots can carry credentials and customer data into model context.
Credential values are redacted when the UI dump is parsed, and screenshots
refuse (or mask) screens that show credential fields.
"""

import asyncio
import atexit
import functools
import inspect
import io
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage, ImageDraw

INSTRUCTIONS = """\
adb emulator control.

Rules:
- NEVER run `adb` or `emulator` from Bash, even when it looks like fewer turns. The Bash \
sandbox cannot reach the adb server (127.0.0.1:5037), and the CLI bypasses the emulator-only \
guard. Use list_devices (not `adb devices`), get_state/ui_tree (not `uiautomator dump`), \
network (not `cmd connectivity`/`svc`), run_steps to batch several actions in one call.
- If no tool covers a need, tell the user. Do not fall back to the CLI.

Roles: get_state is the primary observation (text). screenshot is orientative only \
(downscaled by `scale`). Actions (tap, long_press) are selector-first.

Dependencies:
- A selector tap/long_press takes its own fresh UI dump: no get_state needed first.
- Coordinates are device pixels: image coords x scale, or `center` from get_state/ui_tree.
- screenshot refuses when credential fields are visible: use screenshot_masked.
- A tap result reports `pkg`: verify it is the target app, not a launcher or other app.

Edge cases:
- Compose labels sit on non-clickable child nodes; they are merged into the clickable \
parent's `label`.
- Matching is normalized (Unicode, accents, whitespace, case): exact, then substring. One hit \
taps. Several hits, or only fuzzy hits, return candidates and tap nothing.
- get_state ends with a `Text:` line: static text not already in an element label \
(titles, status, empty-state and error messages).
- Element lines carry widget state flags: [checked], [selected], [disabled]. An unlabelled \
button shows its nearest labelled ancestor as `in "..."` (display only, not matchable).
- get_state `Package:` is the dumped screen's package. An `Activity:` line flagged "window \
focus differs" means focus lags the screen or a dialog/overlay is on top: trust the elements.
- get_state modes apply to both lists (elements and Text): mode="optimal" (default) shows \
max 10 entries per list and cuts lines at 80 chars; mode="full" shows max 20 per list, \
uncut. Overflow ends with "+N more". Hidden elements stay tappable by selector. Use full \
when a cut line or hidden entry matters (dialog questions, order summaries, long lists).
- A `Screen: off` or `Screen: locked` line in get_state means call unlock(pin=...) before \
anything else. launch_app fails with "No activities found" on a device never unlocked since boot.
- Loading placeholders (shimmer) appear as empty nodes: observe again before acting.
- Limit: Compose input fields without resource-id or content-desc cannot be detected \
as sensitive.

Emulator lifecycle:
- start_emulator (normal mode) reuses an emulator that is already running and spawns only \
if none is up. Headless mode always spawns its own emulator. reuse=False spawns a second \
windowed emulator next to a running one (different AVD).
- A headless emulator started by this server is killed when the server exits. A windowed \
one is left running.
- stop_emulator stops only emulators started by this server.
- kill_emulator shuts down any emulator, including Android Studio's: ALWAYS ask the user \
for confirmation before every call. Use force=True only after a normal kill left it running.

Build and deploy:
- Order: start_emulator (headless unless the user asks for a window), build_install, \
launch_app, current_activity. If the app is not in the foreground, read logcat.
- build_install builds and installs a debug variant (for example debug, devDebug) on the emulator only.
- After the first build failure you may fix the cause and retry once. After the second \
failure stop and report the log path to the user.
- uninstall_app deletes the app and its data. Call it without asking only when build_install \
failed with INSTALL_FAILED_UPDATE_INCOMPATIBLE (signature mismatch), then retry build_install. \
Any other uninstall: ask the user first.

Trace:
- At the start of every QA flow call trace_flow(title, trace_dir) with a short flow title and the \
session scratchpad as trace_dir. It records the device logcat from that moment into \
logcat-<title>.log. One call per flow. Call trace_end when the flow is done. A flow also ends on \
the next trace_flow, stop_emulator, kill_emulator and server exit.
- Backend HTTP calls may appear in the logcat if the app logs them. For live inspection, suggest \
Android Studio's Network Inspector to the user.
- The raw logs can contain tokens and passwords. Never paste those values into replies or docs.
- After the run, ask the user whether to keep the logs as evidence and where. If yes, call \
trace_save with that path.
"""

mcp = FastMCP("adbmm", instructions=INSTRUCTIONS)

DEFAULT_TIMEOUT = 20.0
MAX_TEXT_CHARS = 60000
MAX_LABEL_CHARS = 80
# get_state limits per mode, for both the element list and `Text:`:
# (max entries per list, max chars per line or None for no cut).
SCREEN_TEXT_MODES = {"optimal": (10, MAX_LABEL_CHARS), "full": (20, None)}
# A clickable scrollable container merges at most this many child labels (a list is not a label).
MERGE_SCROLLABLE_MAX_PARTS = 3
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
# Only debug install tasks are reachable, so release/signing tasks cannot run.
BUILD_VARIANT_RE = re.compile(r"^[a-z][A-Za-z0-9]*Debug$|^debug$")
BUILD_MODULE_RE = re.compile(r"^[A-Za-z0-9_-]+(:[A-Za-z0-9_-]+)*$")
BUILD_LOG_TAIL_LINES = 20

EMULATOR_SERIAL_RE = re.compile(r"^emulator-\d+$")
COMPONENT_RE = re.compile(r"^[A-Za-z0-9_.]+/\.?[A-Za-z0-9_.$]+$")
PACKAGE_RE = re.compile(r"^[A-Za-z0-9_.]+$")
SAVE_AS_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
TAG_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
FOCUS_RE = re.compile(r"mCurrentFocus=.*?\s([\w.]+/[\w.$]+)\}")
FOCUSED_APP_RE = re.compile(r"mFocusedApp=.*?\s([\w.]+/[\w.$]+)")
AWAKE_OFF_RE = re.compile(r"\bmAwake=false\b")
SCREEN_OFF_RE = re.compile(r"\bscreenState=SCREEN_STATE_OFF\b")
KEYGUARD_SHOWING_RE = re.compile(r"\bisKeyguardShowing=true\b")
PIN_RE = re.compile(r"^\d{4,16}$")
UNLOCK_BOUNCER_DELAY_S = 1.0
UNLOCK_POLLS = 6
UNLOCK_POLL_INTERVAL_S = 0.5
WM_SIZE_RE = re.compile(r"(\d+)x(\d+)")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Credential fields must never reach the model context. Matched against a node's
# resource-id and content-desc; password="true" nodes are redacted regardless.
SENSITIVE_LABEL_RE = re.compile(
    r"secret|password|passwd|token|client_id|clientid|api_?key|credential|auth"
    r"|card_?number|cc_?num|cvc|cvv|expir|iban",
    re.IGNORECASE,
)
REDACTED_PLACEHOLDER = "<redacted>"

DUMPSYS_ALLOWLIST = {"window", "activity", "package", "display", "battery", "input_method"}
LOGCAT_PRIORITIES = {"V", "D", "I", "W", "E", "F", "S"}
SCROLL_DIRECTIONS = {"up", "down", "left", "right"}
PRESS_KEY_ALLOWLIST = {
    "BACK": "KEYCODE_BACK",
    "HOME": "KEYCODE_HOME",
    "ENTER": "KEYCODE_ENTER",
    "TAB": "KEYCODE_TAB",
    "DEL": "KEYCODE_DEL",
    "APP_SWITCH": "KEYCODE_APP_SWITCH",
    "MENU": "KEYCODE_MENU",
    "SEARCH": "KEYCODE_SEARCH",
    "DPAD_UP": "KEYCODE_DPAD_UP",
    "DPAD_DOWN": "KEYCODE_DPAD_DOWN",
    "DPAD_LEFT": "KEYCODE_DPAD_LEFT",
    "DPAD_RIGHT": "KEYCODE_DPAD_RIGHT",
    "VOLUME_UP": "KEYCODE_VOLUME_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN",
    # WAKEUP is idempotent; POWER is deliberately absent (it toggles the screen off).
    "WAKEUP": "KEYCODE_WAKEUP",
}
WAIT_FOR_MAX_S = 15.0
WAIT_FOR_POLL_S = 0.5
# network(): toggle name -> (shell argv, completed with enable/disable; global setting with its state).
NETWORK_TOGGLES = {
    "airplane": (["cmd", "connectivity", "airplane-mode"], "airplane_mode_on"),
    "wifi": (["svc", "wifi"], "wifi_on"),
    "data": (["svc", "data"], "mobile_data"),
}
# wifi_on: 1 on, 2 on despite airplane mode, 3 off because of airplane mode.
NETWORK_ON_VALUES = {"1", "2"}
RUN_STEPS_MAX = 50

# Session default target device, set by use_device().
_session_device: str | None = None
# Emulators this server started: serial -> (process, headless, avd name).
_spawned: dict[str, tuple[subprocess.Popen, bool, str]] = {}
# Consecutive build_install failures; reset on success.
_build_failures = 0


@dataclass
class Trace:
    """One QA flow: its logcat file and the adb logcat stream writing into it."""

    path: Path
    proc: subprocess.Popen


# Latest flow stream by serial.
_traces: dict[str, Trace] = {}
# Every flow log recorded by this server, kept after the flow ends for trace_status/trace_save.
_flow_logs: list[Path] = []


# --------------------------------------------------------------------------
# adb resolution and process execution — the ONLY subprocess path for adb
# (plus `emulator -list-avds`); the emulator itself is spawned by start_emulator.
# --------------------------------------------------------------------------

def _default_sdk_root() -> str | None:
    """Android Studio's default SDK location for this OS, or None if unknown."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Android/sdk")
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        return os.path.join(local_app_data, "Android", "Sdk") if local_app_data else None
    return os.path.expanduser("~/Android/Sdk")


def _resolve_sdk_binary(subdir: str, name: str) -> str:
    """Resolve an SDK binary: $ANDROID_HOME -> $ANDROID_SDK_ROOT -> OS default SDK root -> PATH.

    A leading `~` in the env vars is expanded. Raises ValueError, listing every path tried,
    if the binary cannot be found.
    """
    file_name = name + ".exe" if sys.platform == "win32" else name
    roots = [os.environ.get(var) for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT")]
    roots.append(_default_sdk_root())
    tried = []
    for sdk_root in filter(None, roots):
        candidate = os.path.join(os.path.expanduser(sdk_root), subdir, file_name)
        if os.path.isfile(candidate):
            return candidate
        tried.append(candidate)

    which_result = shutil.which(name)
    if which_result:
        return which_result
    tried.append("PATH")

    raise ValueError(
        f"Could not resolve {name}. Tried: {', '.join(tried)}. "
        "Set ANDROID_HOME in the project's .claude/settings.local.json env (absolute path)."
    )


def _resolve_adb() -> str:
    return _resolve_sdk_binary("platform-tools", "adb")


def _resolve_emulator() -> str:
    return _resolve_sdk_binary("emulator", "emulator")


async def _run_process(
    binary: str,
    args: list[str],
    timeout: float,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    log_path: Path | None = None,
) -> tuple[int, bytes, bytes]:
    """Run a binary with the given argv (no shell), capturing raw stdout/stderr, with a timeout.

    Kills the child and raises ValueError on timeout, never hangs the event loop.
    With log_path, stdout and stderr (merged) go to that file and the returned bytes are empty.
    """
    log_file = open(log_path, "wb") if log_path else None
    try:
        process = await asyncio.create_subprocess_exec(
            binary,
            *args,
            cwd=cwd,
            env=env,
            stdout=log_file or asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT if log_file else asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ValueError(
                f"{os.path.basename(binary)} {' '.join(args)} timed out after {timeout}s."
            )
    finally:
        if log_file:
            log_file.close()

    return process.returncode, stdout_bytes or b"", stderr_bytes or b""


async def _run_adb(args: list[str], timeout: float = DEFAULT_TIMEOUT) -> tuple[int, bytes, bytes]:
    return await _run_process(_resolve_adb(), args, timeout)


async def _adb_shell(
    serial: str, shell_args: list[str], timeout: float = DEFAULT_TIMEOUT
) -> tuple[int, bytes, bytes]:
    return await _run_adb(["-s", serial, "shell", *shell_args], timeout=timeout)


async def _adb_exec_out(
    serial: str, args: list[str], timeout: float = DEFAULT_TIMEOUT
) -> tuple[int, bytes, bytes]:
    return await _run_adb(["-s", serial, "exec-out", *args], timeout=timeout)


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _check(returncode: int, stderr_bytes: bytes, what: str) -> None:
    """Raise ValueError('<what> failed (exit N): stderr') when an adb command exited non-zero."""
    if returncode != 0:
        raise ValueError(f"{what} failed (exit {returncode}): {_decode(stderr_bytes).strip()}")


def _returns_errors(func):
    """Decorator: turn a ValueError raised by a tool into an 'Error: ...' string result."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValueError as e:
            return f"Error: {e}"

    return wrapper


def _truncate(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    if len(text) <= limit:
        return text
    kept, rest = text[:limit], text[limit:]
    dropped_bytes = len(rest.encode("utf-8", errors="replace"))
    return f"{kept}\n[truncated {dropped_bytes} bytes]"


def _parse_devices(raw_output: str) -> list[tuple[str, str]]:
    """Parse `adb devices -l` output into (serial, rest_of_line) pairs, state == 'device' only."""
    devices: list[tuple[str, str]] = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if state != "device":
            continue
        rest = parts[2] if len(parts) > 2 else ""
        devices.append((serial, rest))
    return devices


async def _resolve_device(device: str | None) -> str:
    """Resolve target serial: explicit arg -> session default -> sole connected device.

    Only emulator serials (^emulator-\\d+$) are ever accepted.
    """
    candidate = device or _session_device
    if candidate:
        if not EMULATOR_SERIAL_RE.match(candidate):
            raise ValueError(
                f"Refused: '{candidate}' is not an emulator serial (must match ^emulator-\\d+$)."
            )
        return candidate

    returncode, stdout_bytes, stderr_bytes = await _run_adb(["devices", "-l"])
    _check(returncode, stderr_bytes, "adb devices -l")
    devices = _parse_devices(_decode(stdout_bytes))
    if not devices:
        raise ValueError("No devices found (state == 'device'); call start_emulator.")
    if len(devices) > 1:
        serials = ", ".join(serial for serial, _ in devices)
        raise ValueError(f"Multiple devices connected, no target set: {serials}. Call use_device() first.")
    serial = devices[0][0]
    if not EMULATOR_SERIAL_RE.match(serial):
        raise ValueError(f"Refused: sole connected device '{serial}' is not an emulator serial.")
    return serial


async def _get_screen_size(serial: str) -> tuple[int, int]:
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, ["wm", "size"])
    _check(returncode, stderr_bytes, "wm size")
    text = _decode(stdout_bytes)
    match = None
    for line in text.splitlines():
        if "Override size" in line:
            match = WM_SIZE_RE.search(line)
            break
    if not match:
        for line in text.splitlines():
            if "Physical size" in line:
                match = WM_SIZE_RE.search(line)
                break
    if not match:
        raise ValueError(f"Could not parse 'wm size' output: {text.strip()!r}")
    return int(match.group(1)), int(match.group(2))


async def _dumpsys_window(serial: str) -> str:
    """Raw `dumpsys window` text (focus and screen state are both parsed from it)."""
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, ["dumpsys", "window"])
    _check(returncode, stderr_bytes, "dumpsys window")
    return _decode(stdout_bytes)


def _screen_state(dumpsys_window_text: str) -> str | None:
    """'off' (screen asleep), 'locked' (keyguard showing) or None (awake and unlocked)."""
    if AWAKE_OFF_RE.search(dumpsys_window_text) or SCREEN_OFF_RE.search(dumpsys_window_text):
        return "off"
    if KEYGUARD_SHOWING_RE.search(dumpsys_window_text):
        return "locked"
    return None


async def _current_activity(serial: str, text: str | None = None) -> str:
    if text is None:
        text = await _dumpsys_window(serial)
    match = FOCUS_RE.search(text) or FOCUSED_APP_RE.search(text)
    if match:
        return match.group(1)
    raise ValueError("Could not determine current focused activity from dumpsys window.")


def _package_of(activity: str) -> str:
    """Package part of a 'package/.Activity' component string."""
    return activity.split("/", 1)[0]


# --------------------------------------------------------------------------
# UI tree — parsing and selector matching (tap/long_press are selector-first).
# --------------------------------------------------------------------------

async def _dump_ui_tree(serial: str) -> str:
    returncode, stdout_bytes, stderr_bytes = await _adb_exec_out(
        serial, ["uiautomator", "dump", "/dev/tty"]
    )
    _check(returncode, stderr_bytes, "uiautomator dump")
    text = _decode(stdout_bytes)
    start = text.find("<?xml")
    if start == -1:
        raise ValueError("uiautomator dump did not return XML.")
    end = text.rfind(">")
    return text[start:end + 1] if end != -1 else text[start:]


def _is_sensitive(attrib: dict) -> bool:
    """True if a node's value must never leave the server.

    Two independent triggers:
      - password="true" in the uiautomator dump, i.e. inputType="textPassword".
      - resource-id or content-desc naming a credential (secret, token, client_id, ...).
    """
    if attrib.get("password") == "true":
        return True
    label = f"{attrib.get('resource-id', '')} {attrib.get('content-desc', '')}"
    return bool(SENSITIVE_LABEL_RE.search(label))


def _redact_node(attrib: dict) -> dict:
    """Replace a sensitive node's text with a placeholder, preserving structure.

    Marks the node with _redacted so the screenshot masker can find the same
    regions without re-deriving sensitivity — one source of truth.
    """
    if attrib.get("text") and _is_sensitive(attrib):
        attrib["text"] = REDACTED_PLACEHOLDER
        attrib["_redacted"] = "true"
    return attrib


def _sensitive_regions(nodes: list[dict]) -> list[tuple[str, tuple[int, int, int, int]]]:
    """(label, rect) for every node whose on-screen value was redacted."""
    regions: list[tuple[str, tuple[int, int, int, int]]] = []
    for n in nodes:
        if n.get("_redacted") != "true":
            continue
        match = BOUNDS_RE.search(n.get("bounds", ""))
        if not match:
            continue
        left, top, right, bottom = (int(g) for g in match.groups())
        if right <= left or bottom <= top:
            continue
        label = n.get("resource-id") or n.get("content-desc") or "field"
        regions.append((label, (left, top, right, bottom)))
    return regions


def _mask_regions(png_bytes: bytes, regions: list[tuple[str, tuple[int, int, int, int]]]) -> bytes:
    """Paint opaque bars over sensitive regions at full resolution.

    Solid fill, not blur: blurred text is frequently recoverable, a filled rect is not.
    Runs before downscaling so device bounds need no rescaling.
    """
    with PILImage.open(io.BytesIO(png_bytes)) as img:
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size
        for _, (left, top, right, bottom) in regions:
            draw.rectangle(
                [max(0, left), max(0, top), min(width, right), min(height, bottom)],
                fill=(0, 0, 0),
            )
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()


def _is_interactive(node: dict) -> bool:
    return any(
        node.get(flag) == "true"
        for flag in ("clickable", "long-clickable", "scrollable", "checkable", "focusable")
    )


def _is_clickable(node: dict) -> bool:
    return node.get("clickable") == "true" or node.get("long-clickable") == "true"


def _is_layout_noise(node: dict) -> bool:
    """Unlabelled, id-less node that is only scrollable or focusable (a layout container)."""
    return not (
        node.get("label") or node.get("resource-id")
        or _is_clickable(node) or node.get("checkable") == "true"
    )


def _merge_label(nodes: list[dict], idx: int) -> str:
    """Join the non-empty text/content-desc of a node's descendants (Compose child labels).

    Nested clickable subtrees are skipped (they carry their own label). A scrollable
    container keeps at most MERGE_SCROLLABLE_MAX_PARTS parts, ending in "…". Children whose
    value went into the label are marked `_merged` (get_state's Text: line skips them).
    A sensitive node never exposes its descendants' values.
    """
    node = nodes[idx]
    max_parts = MERGE_SCROLLABLE_MAX_PARTS if node.get("scrollable") == "true" else None
    parts: list[str] = []
    capped = False
    i, end = idx + 1, node["_end"]
    while i < end and not capped:
        child = nodes[i]
        if _is_clickable(child):
            i = child["_end"]
            continue
        for value in (child.get("text", ""), child.get("content-desc", "")):
            value = " ".join(value.split())
            if not value or value in parts[-1:]:
                continue
            if max_parts is not None and len(parts) == max_parts:
                capped = True
                break
            parts.append(value)
            child["_merged"] = True
        i += 1
    if parts and _is_sensitive(node):
        return REDACTED_PLACEHOLDER
    return " ".join(parts) + (" …" if capped else "")


def _parse_ui_tree_nodes(xml_text: str) -> list[dict]:
    """Parse the UI dump into node dicts, redacting credential values at the source.

    Every consumer (ui_tree, get_state, selector matching) goes through this
    function, so a sensitive value cannot reach the caller by any path. Nodes are in
    document order and carry `_parent` (index or -1), `_end` (end of subtree) and `label`.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"Could not parse UI tree XML: {e}")

    nodes: list[dict] = []

    def walk(elements: list[ET.Element], parent: int) -> None:
        for element in elements:
            if element.tag != "node":
                continue
            idx = len(nodes)
            node = _redact_node(dict(element.attrib))
            node["_parent"] = parent
            nodes.append(node)
            walk(list(element), idx)
            node["_end"] = len(nodes)

    walk([root] if root.tag == "node" else list(root), -1)

    # Document order: ancestors are labelled before their descendants look them up.
    for idx, node in enumerate(nodes):
        label = " ".join((node.get("text") or node.get("content-desc") or "").split())
        if not label and _is_clickable(node):
            label = _merge_label(nodes, idx)
        node["label"] = label
        if not label and _is_clickable(node):
            parent = node["_parent"]
            while parent != -1 and not nodes[parent]["label"]:
                parent = nodes[parent]["_parent"]
            if parent != -1:
                node["context"] = nodes[parent]["label"]  # display only, never matched
    return nodes


def _screen_package(nodes: list[dict], activity: str) -> str:
    """Package of the dumped screen (root node), else the focused activity's package."""
    return next((n["package"] for n in nodes if n.get("package")), _package_of(activity))


def _bounds_center(bounds: str) -> tuple[int, int] | None:
    match = BOUNDS_RE.match(bounds)
    if not match:
        return None
    x1, y1, x2, y2 = (int(v) for v in match.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def _normalize(value: str) -> str:
    """NFKD without combining marks (diacritics), collapse every Unicode whitespace (NBSP,
    narrow NBSP, ...) to one space, strip, casefold."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.split()).casefold()


def _short_id(resource_id: str) -> str:
    """Resource id without the 'package:id/' prefix."""
    return resource_id.split(":id/", 1)[-1]


def _node_fields(node: dict) -> list[str]:
    """Normalized, non-empty text / content-desc / label of a node (the matchable fields)."""
    values = (_normalize(node.get(key, "")) for key in ("text", "content-desc", "label"))
    return [value for value in values if value]


def _field_rank(query: str, fields: list[str]) -> tuple[int, float] | None:
    """Best (tier, score) of a normalized query against normalized fields; None if no tier hits.

    Tier 1 exact, tier 2 substring, tier 3 fuzzy (all tokens present, or ratio >= 0.6).
    """
    best: tuple[int, float] | None = None
    tokens = query.split()
    for field in fields:
        if field == query:
            return 1, 1.0
        if query in field:
            rank = (2, len(query) / len(field))
        else:
            ratio = SequenceMatcher(None, query, field[:200]).ratio()
            if not (all(token in field for token in tokens) or ratio >= 0.6):
                continue
            rank = (3, ratio)
        if best is None or rank[0] < best[0] or (rank[0] == best[0] and rank[1] > best[1]):
            best = rank
    return best


def _rank_node(node: dict, resource_id: str | None, queries: list[str]) -> tuple[int, float] | None:
    """(tier, score) of a node against every given selector (AND); None if any selector misses."""
    tier, score = 1, 1.0
    if resource_id:
        node_id = node.get("resource-id", "")
        if node_id != resource_id and not node_id.endswith(":id/" + resource_id):
            ratio = SequenceMatcher(None, resource_id.lower(), _short_id(node_id).lower()).ratio()
            if not node_id or ratio < 0.6:
                return None
            tier, score = 3, ratio
    fields = _node_fields(node)
    for query in queries:
        rank = _field_rank(query, fields)
        if rank is None:
            return None
        tier, score = max(tier, rank[0]), min(score, rank[1])
    return tier, score


def _tap_target(nodes: list[dict], idx: int) -> int:
    """A non-interactive node collapses into its nearest clickable ancestor; others stay."""
    if _is_interactive(nodes[idx]):
        return idx
    parent = nodes[idx]["_parent"]
    while parent != -1:
        if _is_clickable(nodes[parent]):
            return parent
        parent = nodes[parent]["_parent"]
    return idx


def _find_candidates(
    nodes: list[dict],
    resource_id: str | None,
    text: str | None,
    content_desc: str | None,
    package: str | None,
) -> tuple[int, list[dict]]:
    """Find selector matches. Returns (tier, nodes); the first tier with hits wins.

    Tier 0 means nothing matched in any tier: the nodes are the closest guesses.
    """
    queries = [q for q in (_normalize(value) for value in (text, content_desc) if value) if q]
    best: dict[int, tuple[int, float]] = {}
    for idx, node in enumerate(nodes):
        if package and node.get("package") != package:
            continue
        rank = _rank_node(node, resource_id, queries)
        if rank is None:
            continue
        target = _tap_target(nodes, idx)
        if target not in best or (rank[0], -rank[1]) < (best[target][0], -best[target][1]):
            best[target] = rank

    if best:
        tier = min(rank[0] for rank in best.values())
        hits = [idx for idx, rank in best.items() if rank[0] == tier]
        if tier == 3:
            hits.sort(key=lambda idx: -best[idx][1])
            hits = hits[:5]
        else:
            hits.sort()
        return tier, [nodes[idx] for idx in hits]

    needle = _normalize(text or content_desc or resource_id or "")

    def similarity(node: dict) -> float:
        fields = _node_fields(node) + [_normalize(_short_id(node.get("resource-id", "")))]
        return max((SequenceMatcher(None, needle, f[:200]).ratio() for f in fields if f), default=0.0)

    pool = [
        node for node in nodes
        if (not package or node.get("package") == package)
        and _is_interactive(node) and (node.get("label") or node.get("resource-id"))
    ]
    pool.sort(key=similarity, reverse=True)
    return 0, pool[:5]


def _node_line(
    node: dict, with_class: bool = False, with_pkg: bool = False,
    max_chars: int | None = MAX_LABEL_CHARS,
) -> str:
    """Compact node description; empty fields omitted:
    "label" id=… in "context" [checked] [selected] [disabled] desc="…" class=… pkg=… center=(x,y).

    `in "context"` (nearest labelled ancestor) appears only for an unlabelled node. Labels
    are cut to max_chars (None: no cut); matching always uses the full label.
    """
    parts: list[str] = []
    label = node.get("label", "")
    if label:
        parts.append(f'"{_cut(label, max_chars)}"')
    node_id = _short_id(node.get("resource-id", ""))
    if node_id:
        parts.append(f"id={node_id}")
    if not label and node.get("context"):
        parts.append(f'in "{_cut(node["context"], max_chars)}"')
    if node.get("checked") == "true":
        parts.append("[checked]")
    if node.get("selected") == "true":
        parts.append("[selected]")
    if node.get("enabled") == "false":
        parts.append("[disabled]")
    desc = " ".join(node.get("content-desc", "").split())
    if desc and desc != label:
        parts.append(f'desc="{_cut(desc, max_chars)}"')
    if with_class and node.get("class"):
        parts.append(f"class={node['class'].rsplit('.', 1)[-1]}")
    if with_pkg and node.get("package"):
        parts.append(f"pkg={node['package']}")
    center = _bounds_center(node.get("bounds", ""))
    if center:
        parts.append(f"center=({center[0]},{center[1]})")
    return " ".join(parts)


def _candidate_lines(candidates: list[dict]) -> str:
    return "\n".join(f"[{n}] {_node_line(node, with_pkg=True)}" for n, node in enumerate(candidates, 1))


def _pick_target(
    nodes: list[dict],
    resource_id: str | None,
    text: str | None,
    content_desc: str | None,
    package: str | None,
) -> tuple[int, int, str, str]:
    """Pick the single element a selector designates: (x, y, label, pkg).

    Taps only on exactly one tier-1/2 hit. Several hits or any fuzzy hit raise with a
    candidate list; the caller decides what to tap.
    """
    if not nodes:
        raise ValueError("No UI nodes on screen.")
    if package and not any(node.get("package") == package for node in nodes):
        seen = ", ".join(sorted({node.get("package", "") for node in nodes} - {""}))
        raise ValueError(f"No UI nodes from package '{package}'; packages on screen: {seen}.")

    tier, hits = _find_candidates(nodes, resource_id, text, content_desc, package)
    if tier in (1, 2) and len(hits) == 1:
        node = hits[0]
        center = _bounds_center(node.get("bounds", ""))
        if center is None:
            raise ValueError("Matched element has no usable bounds.")
        label = node.get("label") or _short_id(node.get("resource-id", "")) or "element"
        return center[0], center[1], label, node.get("package", "")

    if tier in (1, 2):
        head = f"{len(hits)} elements matched, refusing to guess"
    elif tier == 3:
        head = "No exact match; closest fuzzy candidates"
    else:
        head = "No match; closest elements on screen"
    raise ValueError(f"{head} (nothing tapped):\n{_candidate_lines(hits[:10])}")


async def _resolve_target(
    serial: str,
    resource_id: str | None,
    text: str | None,
    content_desc: str | None,
    x: int | None,
    y: int | None,
    package: str | None,
) -> tuple[int, int, str, str]:
    """Shared by tap/long_press: selector (fresh UI dump) or raw x, y -> (x, y, label, pkg).

    pkg is empty for raw coordinates (no dump is taken to hit-test them).
    """
    if resource_id or text or content_desc:
        nodes = _parse_ui_tree_nodes(await _dump_ui_tree(serial))
        return _pick_target(nodes, resource_id, text, content_desc, package)
    if package:
        raise ValueError("package filter requires a selector (resource_id/text/content_desc).")
    if x is not None and y is not None:
        return x, y, f"({x}, {y})", ""
    raise ValueError("Provide a selector (resource_id/text/content_desc) or x, y.")


# --------------------------------------------------------------------------
# Screenshot — exec-out screencap, integer downscale via Pillow, save_as.
# --------------------------------------------------------------------------

async def _capture_screenshot(serial: str) -> bytes:
    returncode, stdout_bytes, stderr_bytes = await _adb_exec_out(serial, ["screencap", "-p"])
    _check(returncode, stderr_bytes, "screencap")
    if not stdout_bytes.startswith(PNG_MAGIC):
        raise ValueError("screencap output failed PNG magic-byte verification; refusing to return it.")
    return stdout_bytes


def _downscale_png(png_bytes: bytes, scale: int) -> tuple[bytes, int, int]:
    """Downscale a PNG by an integer factor with Pillow. Returns (png, device_width, device_height)."""
    with PILImage.open(io.BytesIO(png_bytes)) as img:
        width, height = img.size
        if scale == 1:
            return png_bytes, width, height
        small = img.convert("RGB").resize(
            (max(1, width // scale), max(1, height // scale)), PILImage.Resampling.LANCZOS
        )
        out = io.BytesIO()
        small.save(out, format="PNG")
        return out.getvalue(), width, height


def _validate_save_as(save_as: str) -> Path:
    """save_as is the only host-write primitive in this server (C3)."""
    if not SAVE_AS_RE.match(save_as) or ".." in save_as or "/" in save_as or "\\" in save_as:
        raise ValueError(
            "Invalid save_as; allowed: letters, digits, '.', '_', '-' (max 64 chars), no separators."
        )
    filename = save_as if save_as.lower().endswith(".png") else f"{save_as}.png"
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    resolved_dir = SCREENSHOTS_DIR.resolve()
    target = (SCREENSHOTS_DIR / filename).resolve()
    if not target.is_relative_to(resolved_dir):
        raise ValueError("Refused: resolved path escapes the screenshots directory.")
    if target.exists():
        raise ValueError(f"Refused: {target.name} already exists; refusing silent overwrite.")
    return target


# --------------------------------------------------------------------------
# Device
# --------------------------------------------------------------------------

@mcp.tool()
@_returns_errors
async def list_devices() -> str:
    """List connected Android devices/emulators whose adb state is exactly 'device'.

    Use this, never `adb devices` in Bash: the Bash sandbox cannot reach the adb server.
    """
    returncode, stdout_bytes, stderr_bytes = await _run_adb(["devices", "-l"])
    _check(returncode, stderr_bytes, "adb devices -l")

    devices = _parse_devices(_decode(stdout_bytes))
    if not devices:
        return "No devices found (state == 'device')."

    lines = [f"{len(devices)} device(s):"]
    for serial, rest in devices:
        lines.append(f"  {serial}  {rest}".rstrip())
    return "\n".join(lines)


@mcp.tool()
@_returns_errors
async def use_device(device_id: str) -> str:
    """Set the session default target device. Emulator serials only (^emulator-\\d+$)."""
    if not EMULATOR_SERIAL_RE.match(device_id):
        raise ValueError(f"'{device_id}' is not an emulator serial (must match ^emulator-\\d+$).")
    returncode, stdout_bytes, stderr_bytes = await _run_adb(["devices", "-l"])
    _check(returncode, stderr_bytes, "adb devices -l")
    known = {serial for serial, _ in _parse_devices(_decode(stdout_bytes))}
    if device_id not in known:
        raise ValueError(f"'{device_id}' not found among connected devices (state == 'device').")

    global _session_device
    _session_device = device_id
    return f"Default device set to {device_id}."


def _free_emulator_port(raw_devices_output: str) -> int:
    """First even port in 5554-5584 with no emulator-<port> in the raw `adb devices` output."""
    taken = {int(port) for port in re.findall(r"emulator-(\d+)", raw_devices_output)}
    for port in range(5554, 5585, 2):
        if port not in taken:
            return port
    raise ValueError("No free emulator port in 5554-5584.")


def _emulator_argv(avd: str, port: int, headless: bool) -> list[str]:
    argv = ["-avd", avd, "-port", str(port)]
    if headless:
        argv += ["-no-window", "-no-audio", "-no-boot-anim"]
    return argv


def _parse_avds(raw: str) -> list[str]:
    """AVD names from `emulator -list-avds`, without INFO/WARNING noise lines."""
    lines = (line.strip() for line in raw.splitlines())
    return [line for line in lines if line and not line.startswith(("INFO", "WARNING"))]


def _emulator_log_path(serial: str) -> Path:
    return Path(tempfile.gettempdir()) / f"adbmm-{serial}.log"


def _drop_exited_emulators() -> None:
    for serial in [s for s, (proc, _, _) in _spawned.items() if proc.poll() is not None]:
        del _spawned[serial]


def _notify(message: str) -> None:
    """Post a macOS notification (fire-and-forget); no-op where osascript is missing."""
    osascript = shutil.which("osascript")
    if not osascript:
        return
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.Popen(
            [osascript, "-e", f'display notification "{escaped}" with title "adb MCP"'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


TRACE_ROOTS = ("/private/tmp", "/tmp")
SECRET_KEYS = r"password|client_secret|refresh_token|access_token|token"
BEARER_RE = re.compile(r"(Bearer\s+)[^\s\"',}]+", re.IGNORECASE)
JSON_SECRET_RE = re.compile(rf'("(?:{SECRET_KEYS})"\s*:\s*")[^"]*(")')
FORM_SECRET_RE = re.compile(rf'(?<!\w)((?:{SECRET_KEYS})=)[^&\s"]+')
MASK = "***"


def _mask_secrets(line: str) -> tuple[str, int]:
    """Mask Bearer tokens and secret JSON/form values in a log line; returns (line, count)."""
    total = 0
    line, count = BEARER_RE.subn(rf"\g<1>{MASK}", line)
    total += count
    line, count = JSON_SECRET_RE.subn(rf"\g<1>{MASK}\g<2>", line)
    total += count
    line, count = FORM_SECRET_RE.subn(rf"\g<1>{MASK}", line)
    return line, total + count


def _validate_trace_dir(trace_dir: str) -> Path:
    """trace_dir must be an existing absolute directory inside a temp root."""
    path = Path(trace_dir)
    if not path.is_absolute():
        raise ValueError("Refused: trace_dir must be an absolute path.")
    if not path.is_dir():
        raise ValueError(f"Refused: trace_dir {trace_dir} is not an existing directory.")
    roots = [Path(root).resolve() for root in (*TRACE_ROOTS, tempfile.gettempdir())]
    if not any(path.resolve().is_relative_to(root) for root in roots):
        raise ValueError("Refused: trace_dir must be inside /tmp or the system temp directory.")
    return path


def _flow_slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


async def _end_trace(serial: str, grace_s: float = 2.0) -> Path | None:
    """End the serial's live flow stream (grace_s to end by itself); returns its log or None."""
    trace = _traces.get(serial)
    if trace is None or trace.proc.poll() is not None:
        return None
    for _ in range(int(grace_s / 0.5)):
        if trace.proc.poll() is not None:
            break
        await asyncio.sleep(0.5)
    if trace.proc.poll() is None:
        trace.proc.terminate()
    return trace.path


def _kill_headless() -> None:
    for trace in _traces.values():
        if trace.proc.poll() is None:
            trace.proc.terminate()
    for serial, (proc, headless, avd) in list(_spawned.items()):
        if headless and proc.poll() is None:
            proc.terminate()
            _notify(f"Headless {avd} ({serial}) stopped: server exit")


atexit.register(_kill_headless)


async def _installed_avds() -> list[str]:
    returncode, stdout_bytes, stderr_bytes = await _run_process(
        _resolve_emulator(), ["-list-avds"], DEFAULT_TIMEOUT
    )
    _check(returncode, stderr_bytes, "emulator -list-avds")
    return _parse_avds(_decode(stdout_bytes))


async def _wait_for_boot(serial: str, timeout_s: int) -> bool:
    """Poll sys.boot_completed every 2 s. True once booted, False on timeout.

    Raises ValueError (with the log tail) if the emulator process exits first.
    """
    proc = _spawned[serial][0]
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        if proc.poll() is not None:
            del _spawned[serial]
            log_tail = "\n".join(
                _decode(_emulator_log_path(serial).read_bytes()).splitlines()[-15:]
            )
            raise ValueError(f"Emulator exited early (code {proc.returncode}). Log tail:\n{log_tail}")
        try:
            returncode, stdout_bytes, _ = await _adb_shell(
                serial, ["getprop", "sys.boot_completed"], timeout=5
            )
            if returncode == 0 and _decode(stdout_bytes).strip() == "1":
                return True
        except ValueError:
            pass  # not booted yet
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(2)


@mcp.tool()
@_returns_errors
async def list_avds() -> str:
    """List the Android Virtual Devices that start_emulator can launch."""
    avds = await _installed_avds()
    return "\n".join(avds) if avds else "No AVDs found."


@mcp.tool()
@_returns_errors
async def start_emulator(
    avd: str | None = None,
    headless: bool = False,
    boot_timeout_s: int = 120,
    reuse: bool = True,
) -> str:
    """Start an emulator and make it the session device; waits until it has booted.

    Normal mode reuses an emulator that is already running and spawns only if none is up;
    reuse=False spawns `avd` anyway (for a second emulator next to a running one).
    headless=True always spawns one without a window; it is killed when this server exits.
    `avd` must be a name from list_avds. If boot_timeout_s (max 300) passes first, call
    start_emulator again with the same avd to keep waiting.
    """
    global _session_device
    boot_timeout_s = max(1, min(300, boot_timeout_s))
    returncode, stdout_bytes, stderr_bytes = await _run_adb(["devices", "-l"])
    _check(returncode, stderr_bytes, "adb devices -l")
    raw_devices = _decode(stdout_bytes)
    _drop_exited_emulators()

    serial = next((s for s, (_, _, name) in _spawned.items() if avd and name == avd), None)
    if serial is None and not headless and reuse:
        up = [s for s, _ in _parse_devices(raw_devices) if EMULATOR_SERIAL_RE.match(s)]
        if up:
            _session_device = _session_device if _session_device in up else up[0]
            others = [s for s in up if s != _session_device]
            return f"Reusing {_session_device}" + (f" (also up: {', '.join(others)})." if others else ".")

    if serial is None:
        avds = await _installed_avds()
        if avd not in avds:
            raise ValueError(f"avd must be one of: {', '.join(avds) or 'none installed'}.")
        # A just-spawned emulator is not in `adb devices` yet: count its port as taken too.
        port = _free_emulator_port(raw_devices + " ".join(_spawned))
        serial = f"emulator-{port}"
        try:
            with open(_emulator_log_path(serial), "wb") as log:
                proc = subprocess.Popen(
                    [_resolve_emulator(), *_emulator_argv(avd, port, headless)],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
        except OSError as e:
            raise ValueError(f"could not start emulator: {e}")
        _spawned[serial] = (proc, headless, avd)

    _, spawned_headless, spawned_avd = _spawned[serial]
    mode = "headless" if spawned_headless else "windowed"
    if not await _wait_for_boot(serial, boot_timeout_s):
        return (
            f"{spawned_avd} ({mode}) still booting as {serial}; "
            f"call start_emulator(avd={spawned_avd!r}) again to keep waiting."
        )
    _session_device = serial
    _notify(f"{mode.capitalize()} {spawned_avd} running as {serial}")
    return f"Started {spawned_avd} ({mode}) as {serial}; default device set."


@mcp.tool()
@_returns_errors
async def build_install(
    variant: str = "debug", module: str = "app", device: str | None = None, timeout_s: int = 900
) -> str:
    """Build the app (debug) with Gradle and install it on the emulator.

    variant is a debug variant such as debug or devDebug; module is the Gradle module
    (default app, nested like feature:shop). Only :<module>:install<Variant> runs, from the
    project root's gradlew. timeout_s is clamped to 60-1800. Output goes to a log file in
    the temp dir. After a failure you may fix the cause and retry once; a second
    consecutive failure means stop.
    """
    global _build_failures
    if not BUILD_VARIANT_RE.fullmatch(variant):
        raise ValueError("variant must be debug or end with Debug, for example devDebug.")
    if not BUILD_MODULE_RE.fullmatch(module):
        raise ValueError("module must be a Gradle module path such as app or feature:shop.")
    gradlew = PROJECT_ROOT / "gradlew"
    if not gradlew.is_file():
        raise ValueError(f"No gradlew in {PROJECT_ROOT}; run Claude Code from the Android project root.")
    task = f":{module}:install{variant[0].upper()}{variant[1:]}"
    serial = await _resolve_device(device)
    if not os.environ.get("JAVA_HOME"):
        raise ValueError(
            "JAVA_HOME is not set: add the project's JDK to .claude/settings.local.json env (absolute path). "
            "On macOS, `/usr/libexec/java_home -V` lists installed JDKs."
        )
    timeout_s = max(60, min(1800, timeout_s))
    log_path = Path(tempfile.gettempdir()) / "adbmm-gradle.log"
    loop = asyncio.get_running_loop()
    started = loop.time()
    returncode, _, _ = await _run_process(
        str(gradlew),
        [task],
        timeout_s,
        cwd=PROJECT_ROOT,
        env={**os.environ, "ANDROID_SERIAL": serial},
        log_path=log_path,
    )
    if returncode == 0:
        _build_failures = 0
        duration = round(loop.time() - started)
        return f"Built and installed {task} on {serial} in {duration}s. Log: {log_path}"

    _build_failures += 1
    if _build_failures == 1:
        tail = "\n".join(_decode(log_path.read_bytes()).splitlines()[-BUILD_LOG_TAIL_LINES:])
        return f"Build failed (exit {returncode}). Log: {log_path}\n{tail}"
    return f"Build failed (exit {returncode}). Log: {log_path}\nStop: report this log path to the user."


@mcp.tool()
@_returns_errors
async def stop_emulator(device: str | None = None) -> str:
    """Stop an emulator started by this server (never one started elsewhere)."""
    global _session_device
    serial = await _resolve_device(device)
    if serial not in _spawned:
        raise ValueError(f"Refused: {serial} was not started by this server.")
    proc = _spawned[serial][0]
    try:
        await _run_adb(["-s", serial, "emu", "kill"])
    except ValueError:
        pass  # fall through to terminate()
    for _ in range(40):
        if proc.poll() is not None:
            break
        await asyncio.sleep(0.5)
    else:
        proc.terminate()
    del _spawned[serial]
    if _session_device == serial:
        _session_device = None
    _notify(f"Emulator {serial} stopped")
    flow_log = await _end_trace(serial)
    return f"Stopped {serial}." + (f"\nFlow log: {flow_log}" if flow_log else "")


async def _emulator_pid(serial: str) -> int:
    """PID of the qemu process listening on the emulator's console port (= serial number)."""
    port = serial.removeprefix("emulator-")
    _, stdout_bytes, _ = await _run_process(
        "lsof", ["-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], DEFAULT_TIMEOUT
    )
    pids = _decode(stdout_bytes).split()
    if not pids:
        raise ValueError(f"No process listens on port {port}.")
    _, comm_bytes, _ = await _run_process("ps", ["-p", pids[0], "-o", "comm="], DEFAULT_TIMEOUT)
    if "qemu" not in _decode(comm_bytes):
        raise ValueError(f"Refused: pid {pids[0]} on port {port} is not an emulator process.")
    return int(pids[0])


@mcp.tool()
@_returns_errors
async def kill_emulator(device: str, force: bool = False) -> str:
    """Shut down any running emulator, including ones not started by this server.

    ALWAYS ask the user for confirmation before calling this tool, every time. force=True
    sends SIGKILL to the emulator process: use it only when a normal kill left it running.
    """
    global _session_device
    if not EMULATOR_SERIAL_RE.match(device):
        raise ValueError(f"'{device}' is not an emulator serial (must match ^emulator-\\d+$).")
    if force:
        try:
            os.kill(await _emulator_pid(device), signal.SIGKILL)
        except OSError as e:
            raise ValueError(f"could not kill {device}: {e}")
    else:
        returncode, _, stderr_bytes = await _run_adb(["-s", device, "emu", "kill"])
        _check(returncode, stderr_bytes, "adb emu kill")

    for _ in range(40):
        await asyncio.sleep(0.5)
        returncode, stdout_bytes, stderr_bytes = await _run_adb(["devices"])
        _check(returncode, stderr_bytes, "adb devices")
        if device not in re.findall(r"emulator-\d+", _decode(stdout_bytes)):
            break
    else:
        raise ValueError(
            f"{device} still up after 20 s" + ("." if force else "; retry with force=True.")
        )
    _drop_exited_emulators()
    if _session_device == device:
        _session_device = None
    _notify(f"Emulator {device} killed")
    flow_log = await _end_trace(device)
    return (
        f"Killed {device}" + (" (forced)." if force else ".")
        + (f"\nFlow log: {flow_log}" if flow_log else "")
    )


@mcp.tool()
@_returns_errors
async def device_info(device: str | None = None) -> str:
    """Report screen size, density, Android version and current package."""
    serial = await _resolve_device(device)
    width, height = await _get_screen_size(serial)
    rc_density, stdout_density, stderr_density = await _adb_shell(serial, ["wm", "density"])
    _check(rc_density, stderr_density, "wm density")
    rc_version, stdout_version, stderr_version = await _adb_shell(
        serial, ["getprop", "ro.build.version.release"]
    )
    _check(rc_version, stderr_version, "getprop")
    focus = await _current_activity(serial)

    return (
        f"Device: {serial}\n"
        f"Screen: {width}x{height}\n"
        f"Density: {_decode(stdout_density).strip()}\n"
        f"Android version: {_decode(stdout_version).strip()}\n"
        f"Current package: {_package_of(focus)}"
    )


# --------------------------------------------------------------------------
# Observe
# --------------------------------------------------------------------------

@mcp.tool()
@_returns_errors
async def get_state(device: str | None = None, mode: str = "optimal") -> str:
    """Primary observe tool: foreground package/activity + interactive elements, one round trip.

    One line per element: "label" id=… [checked] [selected] [disabled] desc="…" center=(x,y).
    Compose labels are merged from child nodes into `label`; an unlabelled button shows its
    nearest labelled ancestor as `in "…"`. `center` is in device pixels (usable for tap x, y).
    Unlabelled layout containers are listed last. A final `Text:` line lists static text not
    already in a label. Modes apply to both lists:
    mode="optimal" (default): max 10 entries per list, lines cut at 80 chars with "…".
    mode="full": max 20 entries per list, never cut. Overflow ends with "+N more"; hidden
    elements stay tappable by selector. Empty entries are usually loading placeholders.
    `Package:` is the package of the dumped screen; `Activity:` comes from window focus and
    is flagged when its package differs (focus lag, dialog or overlay).
    Use this, never `adb shell` in Bash: the Bash sandbox cannot reach the adb server.
    """
    limits = SCREEN_TEXT_MODES.get(mode)
    if limits is None:
        raise ValueError(f"mode must be one of {sorted(SCREEN_TEXT_MODES)}.")
    serial = await _resolve_device(device)
    window_text = await _dumpsys_window(serial)
    activity = await _current_activity(serial, window_text)
    screen_state = _screen_state(window_text)
    all_nodes = _parse_ui_tree_nodes(await _dump_ui_tree(serial))
    nodes = sorted((n for n in all_nodes if _is_interactive(n)), key=_is_layout_noise)
    package = _screen_package(all_nodes, activity)
    activity_note = "" if package == _package_of(activity) else (
        " (window focus differs from screen package)"
    )

    lines = [
        f"Device: {serial}",
        f"Package: {package}",
        f"Activity: {activity}{activity_note}",
    ]
    if screen_state == "off":
        lines.append("Screen: off")
    elif screen_state == "locked":
        lines.append("Screen: locked (keyguard showing) — call unlock")
    lines += [
        "",
        f"{len(nodes)} interactive element(s):",
    ]
    max_entries, max_chars = limits
    lines.extend(f"- {_node_line(n, max_chars=max_chars)}" for n in nodes[:max_entries])
    if len(nodes) > max_entries:
        lines.append(f"- … (+{len(nodes) - max_entries} more)")
    screen_text = _screen_text(all_nodes, *limits)
    if screen_text:
        lines.extend(["", f"Text: {screen_text}"])
    return _truncate("\n".join(lines))


def _cut(text: str, max_chars: int | None) -> str:
    """Cut text to max_chars, ending in "…" when shortened; None keeps it whole."""
    if max_chars is None or len(text) <= max_chars:
        return text
    return text[:max_chars - 1] + "…"


def _screen_text(nodes: list[dict], max_entries: int, max_chars: int | None) -> str:
    """Static text in document order, skipping text already in an interactive label.

    Skips text merged into a label and text equal to a whole label; drops only consecutive
    duplicates. Joined with " · ", at most max_entries entries, each cut to max_chars
    (None: no cut).
    """
    labels = {_normalize(n.get("label", "")) for n in nodes if _is_interactive(n)}
    previous = None
    texts: list[str] = []
    for node in nodes:
        if _is_interactive(node) or node.get("_merged"):
            continue
        text = " ".join((node.get("text") or node.get("content-desc") or "").split())
        key = _normalize(text)
        if not key or key == previous or key in labels:
            continue
        previous = key
        texts.append(_cut(text, max_chars))
    extra = len(texts) - max_entries
    joined = " · ".join(texts[:max_entries])
    return f"{joined} · … (+{extra} more)" if extra > 0 else joined


async def _screenshot_impl(
    device: str | None, save_as: str | None, scale: int, mask_sensitive: bool
) -> list:
    """Shared capture path for screenshot / screenshot_masked."""
    serial = await _resolve_device(device)

    # Inspect the hierarchy first so a credential on screen is known before pixels are returned.
    # If the dump fails the screen exposes no parseable nodes, so no region can be identified;
    # capture proceeds. Use screenshot_masked when in doubt about such a screen.
    regions: list[tuple[str, tuple[int, int, int, int]]] = []
    try:
        regions = _sensitive_regions(_parse_ui_tree_nodes(await _dump_ui_tree(serial)))
    except ValueError:
        pass

    if regions and not mask_sensitive:
        fields = ", ".join(sorted({label for label, _ in regions}))
        raise ValueError(
            f"Refused: {len(regions)} sensitive field(s) visible on screen ({fields}). "
            "These render as plain text and would leak through the image. "
            "Call screenshot_masked to capture with those regions blacked out."
        )

    png_bytes = await _capture_screenshot(serial)
    if regions:
        png_bytes = _mask_regions(png_bytes, regions)

    scale = max(1, min(4, scale))
    png_bytes, device_width, device_height = _downscale_png(png_bytes, scale)

    if save_as is not None:
        target = _validate_save_as(save_as)
        with open(target, "wb") as f:
            f.write(png_bytes)

    note = f"scale={scale} · device = image × {scale} · device {device_width}x{device_height}"
    return [Image(data=png_bytes, format="png"), note]


@mcp.tool()
async def screenshot(device: str | None = None, save_as: str | None = None, scale: int = 2) -> list:
    """Orientative screenshot, downscaled by integer `scale` (1-4, default 2: 1080x2400 -> 540x1200).

    Prefer get_state for text. Returns the image plus a note with the scale and device size;
    device coords = image coords x scale. Refuses if a credential field is visible; use
    screenshot_masked then. Optionally persists to screenshots/<save_as>.png (refuses silent
    overwrite). Errors raise (rather than returning a string) because the return type is fixed.
    """
    return await _screenshot_impl(device, save_as, scale, mask_sensitive=False)


@mcp.tool()
async def screenshot_masked(device: str | None = None, save_as: str | None = None, scale: int = 2) -> list:
    """Capture the screen with every credential field blacked out. Requires user approval.

    Use only after screenshot refused. Sensitive regions are filled with opaque rectangles at
    full resolution before downscaling (same `scale` semantics as screenshot); a filled rect
    cannot be recovered the way a blur can. Keep this tool OUT of the permission allowlist —
    the approval prompt is the consent step.
    """
    return await _screenshot_impl(device, save_as, scale, mask_sensitive=True)


@mcp.tool()
@_returns_errors
async def ui_tree(device: str | None = None, interactive_only: bool = True) -> str:
    """Dump the UI hierarchy: "label" id=… desc="…" class=… center=(x,y) per node.

    interactive_only=False also lists non-interactive nodes (own text only, no merged label).
    Prefer get_state unless the full tree is needed.
    """
    serial = await _resolve_device(device)
    activity = await _current_activity(serial)
    all_nodes = _parse_ui_tree_nodes(await _dump_ui_tree(serial))
    nodes = [n for n in all_nodes if _is_interactive(n)] if interactive_only else all_nodes
    if not nodes:
        return "No UI nodes found."

    lines = [f"Package: {_screen_package(all_nodes, activity)}", f"{len(nodes)} node(s):"]
    lines.extend(f"- {_node_line(n, with_class=True)}" for n in nodes)
    return _truncate("\n".join(lines))


@mcp.tool()
@_returns_errors
async def current_activity(device: str | None = None) -> str:
    """Report the currently focused window/activity component."""
    serial = await _resolve_device(device)
    return await _current_activity(serial)


@mcp.tool()
@_returns_errors
async def notifications(device: str | None = None) -> str:
    """Dump the current notification shade state (dumpsys notification)."""
    serial = await _resolve_device(device)
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, ["dumpsys", "notification"])
    _check(returncode, stderr_bytes, "dumpsys notification")
    return _truncate(_decode(stdout_bytes))


@mcp.tool()
@_returns_errors
async def logcat(
    lines: int = 200,
    priority: str = "V",
    tag: str | None = None,
    clear_first: bool = False,
    device: str | None = None,
) -> str:
    """Dump recent logcat output (never streams — always `-d`). Capped at 500 lines."""
    serial = await _resolve_device(device)

    lines = max(1, min(500, lines))
    priority = priority.upper()
    if priority not in LOGCAT_PRIORITIES:
        raise ValueError(f"priority must be one of {sorted(LOGCAT_PRIORITIES)}.")

    if clear_first:
        rc, _, err = await _adb_shell(serial, ["logcat", "-c"])
        _check(rc, err, "logcat -c")

    if tag is not None:
        if not TAG_RE.match(tag):
            raise ValueError("invalid tag; allowed: letters, digits, '.', '_', '-' (max 64 chars).")
        filterspec = [f"{tag}:{priority}", "*:S"]
    else:
        filterspec = [f"*:{priority}"]

    args = ["logcat", "-d", "-t", str(lines), "-v", "threadtime", *filterspec]
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, args)
    _check(returncode, stderr_bytes, "logcat")
    return _truncate(_decode(stdout_bytes))


@mcp.tool()
@_returns_errors
async def trace_flow(title: str, trace_dir: str, device: str | None = None) -> str:
    """Start recording the device logcat of one QA flow into trace_dir/logcat-<title>.log.

    Call it at the start of every QA test/flow, once per flow, with a short flow title and the
    session scratchpad as trace_dir (absolute, inside /tmp or the system temp dir). The file holds
    only this flow. It ends on trace_end, the next trace_flow, stop_emulator, kill_emulator or
    server exit. An existing file is never overwritten: a -2, -3, ... suffix is added.
    """
    base_dir = _validate_trace_dir(trace_dir)
    slug = _flow_slug(title)
    if not slug:
        raise ValueError("title must contain letters or digits.")
    serial = await _resolve_device(device)
    await _end_trace(serial, grace_s=0)
    path = base_dir / f"logcat-{slug}.log"
    number = 2
    while path.exists():
        path = base_dir / f"logcat-{slug}-{number}.log"
        number += 1
    # Epoch seconds: adb joins args into one device shell line, so the value must hold no space.
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, ["date", "+%s"])
    _check(returncode, stderr_bytes, "date")
    start = f"{_decode(stdout_bytes).strip()}.000"
    try:
        with open(path, "wb") as out:
            proc = subprocess.Popen(
                [_resolve_adb(), "-s", serial, "logcat", "-v", "threadtime", "-T", start],
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except OSError as e:
        raise ValueError(f"could not start flow log: {e}")
    _traces[serial] = Trace(path, proc)
    _flow_logs.append(path)
    return str(path)


@mcp.tool()
@_returns_errors
async def trace_end(device: str | None = None) -> str:
    """End the live QA flow recording; returns the log path and size."""
    serial = await _resolve_device(device)
    path = await _end_trace(serial, grace_s=0)
    if path is None:
        raise ValueError(f"No live flow on {serial}.")
    return f"{path} ({path.stat().st_size} bytes)"


@mcp.tool()
@_returns_errors
async def trace_status() -> str:
    """List every flow log of this server: path, recording or finished, size."""
    if not _flow_logs:
        return "No flow logs."
    live = {trace.path for trace in _traces.values() if trace.proc.poll() is None}
    return "\n".join(
        f"{path} ({'recording' if path in live else 'finished'}; "
        f"{path.stat().st_size if path.exists() else 0} bytes)"
        for path in _flow_logs
    )


@mcp.tool()
@_returns_errors
async def trace_save(dest_dir: str, title: str | None = None) -> str:
    """Copy every flow log (or only the one matching `title`) to dest_dir, secrets masked as `***`.

    dest_dir must be absolute; it is created if missing and existing files there are never
    overwritten. Works on live and finished flows.
    """
    logs = _flow_logs
    if title is not None:
        pattern = re.compile(rf"logcat-{re.escape(_flow_slug(title))}(-\d+)?\.log")
        logs = [path for path in logs if pattern.fullmatch(path.name)]
    if not logs:
        raise ValueError("No matching flow logs.")
    dest = Path(dest_dir)
    if not dest.is_absolute():
        raise ValueError("Refused: dest_dir must be an absolute path.")
    for path in logs:
        if (dest / path.name).exists():
            raise ValueError(f"Refused: {dest / path.name} already exists; refusing silent overwrite.")
    dest.mkdir(parents=True, exist_ok=True)
    masked = 0
    for path in logs:
        with open(path, encoding="utf-8", errors="replace") as source, \
                open(dest / path.name, "x", encoding="utf-8") as target:
            for line in source:
                clean, count = _mask_secrets(line)
                masked += count
                target.write(clean)
    return "Saved " + ", ".join(str(dest / path.name) for path in logs) + f"\nMasked values: {masked}"


@mcp.tool()
@_returns_errors
async def dumpsys(service: str, device: str | None = None) -> str:
    """Dump a fixed Android system service. Allowlisted bare service names only, no args."""
    service = service.strip().lower()
    if service not in DUMPSYS_ALLOWLIST:
        raise ValueError(f"'{service}' not in allowlist: {sorted(DUMPSYS_ALLOWLIST)}.")
    serial = await _resolve_device(device)
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, ["dumpsys", service])
    _check(returncode, stderr_bytes, f"dumpsys {service}")
    return _truncate(_decode(stdout_bytes))


# --------------------------------------------------------------------------
# Interact — tap/long_press are selector-first (fresh ui_tree, click center).
# --------------------------------------------------------------------------

@mcp.tool()
@_returns_errors
async def tap(
    resource_id: str | None = None,
    text: str | None = None,
    content_desc: str | None = None,
    x: int | None = None,
    y: int | None = None,
    package: str | None = None,
    device: str | None = None,
) -> str:
    """Tap a UI element: selector (fresh UI dump, no get_state needed first) or raw x, y.

    Selectors match text, content-desc and merged label, normalized: exact, then substring.
    resource_id matches exactly or by suffix after ':id/'. Exactly one hit is tapped; several
    hits or only fuzzy hits return candidates and tap nothing. `package` limits the match to one
    app (e.g. to exclude a launcher). The result reports the target's pkg: verify it. x, y are
    device pixels (image x scale, or `center`); raw coordinates are not hit-tested, no pkg.
    """
    serial = await _resolve_device(device)
    cx, cy, label, pkg = await _resolve_target(serial, resource_id, text, content_desc, x, y, package)
    returncode, _, stderr_bytes = await _adb_shell(serial, ["input", "tap", str(cx), str(cy)])
    _check(returncode, stderr_bytes, "tap")
    return f"Tapped {label!r}{f' pkg={pkg}' if pkg else ''} at ({cx}, {cy})."


@mcp.tool()
@_returns_errors
async def long_press(
    resource_id: str | None = None,
    text: str | None = None,
    content_desc: str | None = None,
    x: int | None = None,
    y: int | None = None,
    duration_ms: int = 800,
    package: str | None = None,
    device: str | None = None,
) -> str:
    """Long-press a UI element; same selector, `package` and coordinate rules as tap."""
    serial = await _resolve_device(device)
    cx, cy, label, pkg = await _resolve_target(serial, resource_id, text, content_desc, x, y, package)
    returncode, _, stderr_bytes = await _adb_shell(
        serial, ["input", "swipe", str(cx), str(cy), str(cx), str(cy), str(duration_ms)]
    )
    _check(returncode, stderr_bytes, "long_press")
    return f"Long-pressed {label!r}{f' pkg={pkg}' if pkg else ''} at ({cx}, {cy}) for {duration_ms}ms."


@mcp.tool()
@_returns_errors
async def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, device: str | None = None) -> str:
    """Swipe from (x1, y1) to (x2, y2), in device pixels."""
    serial = await _resolve_device(device)
    returncode, _, stderr_bytes = await _adb_shell(
        serial, ["input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)]
    )
    _check(returncode, stderr_bytes, "swipe")
    return f"Swiped ({x1}, {y1}) -> ({x2}, {y2}) over {duration_ms}ms."


@mcp.tool()
@_returns_errors
async def scroll(direction: str, amount: float = 0.6, device: str | None = None) -> str:
    """Scroll the screen up/down/left/right by a fraction (0.1-1.0) of the screen size."""
    direction = direction.lower()
    if direction not in SCROLL_DIRECTIONS:
        raise ValueError(f"direction must be one of {sorted(SCROLL_DIRECTIONS)}.")
    amount = max(0.1, min(1.0, amount))
    serial = await _resolve_device(device)
    width, height = await _get_screen_size(serial)

    cx, cy = width // 2, height // 2
    span_x = int(width * amount / 2)
    span_y = int(height * amount / 2)
    if direction == "down":
        x1, y1, x2, y2 = cx, cy + span_y, cx, cy - span_y
    elif direction == "up":
        x1, y1, x2, y2 = cx, cy - span_y, cx, cy + span_y
    elif direction == "left":
        x1, y1, x2, y2 = cx + span_x, cy, cx - span_x, cy
    else:  # right
        x1, y1, x2, y2 = cx - span_x, cy, cx + span_x, cy
    x1, x2 = max(0, min(width - 1, x1)), max(0, min(width - 1, x2))
    y1, y2 = max(0, min(height - 1, y1)), max(0, min(height - 1, y2))

    returncode, _, stderr_bytes = await _adb_shell(
        serial, ["input", "swipe", str(x1), str(y1), str(x2), str(y2), "300"]
    )
    _check(returncode, stderr_bytes, "scroll")
    return f"Scrolled {direction} by {amount:.1f}."


@mcp.tool()
@_returns_errors
async def input_text(text: str, device: str | None = None) -> str:
    """Type text into the currently focused field. Spaces/special characters are preserved."""
    serial = await _resolve_device(device)
    quoted = shlex.quote(text)
    returncode, _, stderr_bytes = await _adb_shell(serial, ["input", "text", quoted])
    _check(returncode, stderr_bytes, "input_text")
    return f"Typed {len(text)} character(s)."


@mcp.tool()
@_returns_errors
async def clear_text(device: str | None = None) -> str:
    """Clear the currently focused text field (move to end, then delete backward)."""
    serial = await _resolve_device(device)
    keys = ["KEYCODE_MOVE_END"] + ["KEYCODE_DEL"] * 60
    returncode, _, stderr_bytes = await _adb_shell(serial, ["input", "keyevent", *keys])
    _check(returncode, stderr_bytes, "clear_text")
    return "Cleared focused text field."


@mcp.tool()
@_returns_errors
async def press_key(key: str, device: str | None = None) -> str:
    """Press a key by name (allowlisted). No numeric keycodes accepted."""
    keycode = PRESS_KEY_ALLOWLIST.get(key.upper())
    if keycode is None:
        raise ValueError(f"'{key}' not in allowlist: {sorted(PRESS_KEY_ALLOWLIST)}.")
    serial = await _resolve_device(device)
    returncode, _, stderr_bytes = await _adb_shell(serial, ["input", "keyevent", keycode])
    _check(returncode, stderr_bytes, "press_key")
    return f"Pressed {key.upper()}."


@mcp.tool()
@_returns_errors
async def unlock(pin: str | None = None, device: str | None = None) -> str:
    """Wake the screen and dismiss the keyguard; enters `pin` (digits only) if given."""
    if pin is not None and not PIN_RE.match(pin):
        raise ValueError("invalid pin (4-16 digits only).")
    serial = await _resolve_device(device)
    returncode, _, stderr_bytes = await _adb_shell(serial, ["input", "keyevent", "KEYCODE_WAKEUP"])
    _check(returncode, stderr_bytes, "wake")
    returncode, _, stderr_bytes = await _adb_shell(serial, ["wm", "dismiss-keyguard"])
    _check(returncode, stderr_bytes, "dismiss-keyguard")
    if pin is not None:
        # Digits typed before the PIN bouncer finishes appearing are dropped.
        await asyncio.sleep(UNLOCK_BOUNCER_DELAY_S)
        returncode, _, stderr_bytes = await _adb_shell(serial, ["input", "text", pin])
        _check(returncode, b"", "enter pin")
        returncode, _, stderr_bytes = await _adb_shell(serial, ["input", "keyevent", "KEYCODE_ENTER"])
        _check(returncode, stderr_bytes, "confirm pin")
    # The keyguard takes a moment to go away after ENTER: poll instead of reading once.
    for _ in range(UNLOCK_POLLS):
        if not _screen_state(await _dumpsys_window(serial)):
            return "Unlocked."
        await asyncio.sleep(UNLOCK_POLL_INTERVAL_S)
    raise ValueError("device still locked (keyguard showing): wrong or missing pin.")


@mcp.tool()
async def wait(seconds: float) -> str:
    """Sleep for up to 10 seconds (capped)."""
    seconds = max(0.0, min(10.0, seconds))
    await asyncio.sleep(seconds)
    return f"Waited {seconds}s."


@mcp.tool()
@_returns_errors
async def wait_for(
    text: str | None = None,
    resource_id: str | None = None,
    content_desc: str | None = None,
    package: str | None = None,
    gone: bool = False,
    timeout_s: float = 5.0,
    device: str | None = None,
) -> str:
    """Wait until an element matching the selector is on screen (gone=True: until none is).

    Same matching as tap (exact, then substring; fuzzy hits do not count), but any number of
    hits is fine. Polls fresh UI dumps for up to timeout_s (max 15). timeout_s=0 checks once:
    use it as an assertion. On timeout returns an error with the closest elements.
    """
    if not (resource_id or text or content_desc):
        raise ValueError("Provide a selector (resource_id/text/content_desc).")
    timeout_s = max(0.0, min(WAIT_FOR_MAX_S, timeout_s))
    serial = await _resolve_device(device)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while True:
        nodes = _parse_ui_tree_nodes(await _dump_ui_tree(serial))
        tier, hits = _find_candidates(nodes, resource_id, text, content_desc, package)
        found = tier in (1, 2)
        if found and not gone:
            return f"Found {len(hits)} match(es): {_node_line(hits[0], with_pkg=True)}"
        if gone and not found:
            return "Gone."
        if loop.time() >= deadline:
            break
        await asyncio.sleep(WAIT_FOR_POLL_S)
    selector = text or content_desc or resource_id
    head = f"{selector!r} still on screen" if gone else f"{selector!r} not found"
    closest = _candidate_lines(hits[:5]) or "(no elements)"
    raise ValueError(f"{head} after {timeout_s}s; closest:\n{closest}")


@mcp.tool()
@_returns_errors
async def network(
    airplane: bool | None = None,
    wifi: bool | None = None,
    data: bool | None = None,
    device: str | None = None,
) -> str:
    """Turn airplane mode, wifi and mobile data on/off, then report all three states.

    Omitted toggles are left as they are; no args only reports. Airplane is applied first.
    States come from global settings and can lag a second behind a toggle: call again to confirm.
    """
    serial = await _resolve_device(device)
    wanted = {"airplane": airplane, "wifi": wifi, "data": data}
    for name, enabled in wanted.items():
        if enabled is None:
            continue
        argv, _ = NETWORK_TOGGLES[name]
        returncode, _, stderr_bytes = await _adb_shell(serial, [*argv, "enable" if enabled else "disable"])
        _check(returncode, stderr_bytes, f"{name} {'enable' if enabled else 'disable'}")
    states = []
    for name, (_, setting) in NETWORK_TOGGLES.items():
        returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, ["settings", "get", "global", setting])
        _check(returncode, stderr_bytes, f"read {setting}")
        states.append(f"{name}={'on' if _decode(stdout_bytes).strip() in NETWORK_ON_VALUES else 'off'}")
    return "Network: " + " ".join(states)


# --------------------------------------------------------------------------
# App lifecycle
# --------------------------------------------------------------------------

@mcp.tool()
@_returns_errors
async def list_app_activities(package: str, device: str | None = None) -> str:
    """List activity components declared in the given package (from dumpsys package)."""
    if not PACKAGE_RE.match(package):
        raise ValueError("invalid package name (letters, digits, '.', '_' only).")
    serial = await _resolve_device(device)
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, ["dumpsys", "package", package])
    _check(returncode, stderr_bytes, "dumpsys package")
    text = _decode(stdout_bytes)
    if "Unable to find package" in text or not text.strip():
        raise ValueError(f"package '{package}' not found on device.")

    pattern = re.compile(rf"{re.escape(package)}/([A-Za-z0-9_.$]+)")
    activities = sorted(set(pattern.findall(text)))
    if not activities:
        return f"No activities found for package '{package}'."
    lines = [f"{len(activities)} activit(y/ies) for {package}:"]
    lines.extend(f"  {package}/{a}" for a in activities)
    return _truncate("\n".join(lines))


@mcp.tool()
@_returns_errors
async def launch_app(package: str, device: str | None = None) -> str:
    """Launch a package's launcher activity (adb monkey, LAUNCHER category, 1 event)."""
    if not PACKAGE_RE.match(package):
        raise ValueError("invalid package name (letters, digits, '.', '_' only).")
    serial = await _resolve_device(device)
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(
        serial, ["monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"]
    )
    output = _decode(stdout_bytes) + _decode(stderr_bytes)
    if returncode != 0 or "No activities found" in output:
        message = f"could not launch '{package}' (exit {returncode}): {output.strip()}"
        if _screen_state(await _dumpsys_window(serial)):
            message += (
                " Device is locked/screen off: call unlock first "
                "(apps are not launchable before first unlock)."
            )
        raise ValueError(message)
    return f"Launched {package}."


@mcp.tool()
@_returns_errors
async def launch_activity(component: str, device: str | None = None, force_stop: bool = False) -> str:
    """Launch an explicit activity component ('package/.Activity'). force_stop discards app state."""
    if not COMPONENT_RE.match(component):
        raise ValueError("invalid component; expected 'package/.Activity' or 'package/package.Activity'.")
    serial = await _resolve_device(device)
    args = ["am", "start", "-S", "-n", component] if force_stop else ["am", "start", "-n", component]
    returncode, stdout_bytes, stderr_bytes = await _adb_shell(serial, args)
    output = _decode(stdout_bytes) + _decode(stderr_bytes)
    if returncode != 0 or "Error" in output:
        raise ValueError(f"could not launch '{component}': {output.strip()}")
    return f"Launched {component}" + (" (force-stopped first)." if force_stop else ".")


@mcp.tool()
@_returns_errors
async def stop_app(package: str, device: str | None = None) -> str:
    """Force-stop a package. Destructive: discards all in-memory app state."""
    if not PACKAGE_RE.match(package):
        raise ValueError("invalid package name (letters, digits, '.', '_' only).")
    serial = await _resolve_device(device)
    returncode, _, stderr_bytes = await _adb_shell(serial, ["am", "force-stop", package])
    _check(returncode, stderr_bytes, "force-stop")
    return f"Force-stopped {package}."


@mcp.tool()
@_returns_errors
async def uninstall_app(package: str, device: str | None = None) -> str:
    """Uninstall a package from the emulator. Destructive: deletes the app and all its data."""
    if not PACKAGE_RE.match(package):
        raise ValueError("invalid package name (letters, digits, '.', '_' only).")
    serial = await _resolve_device(device)
    returncode, stdout_bytes, stderr_bytes = await _run_adb(["-s", serial, "uninstall", package], timeout=60)
    output = (_decode(stdout_bytes) + _decode(stderr_bytes)).strip()
    if returncode != 0 or "Success" not in output:
        raise ValueError(f"could not uninstall '{package}' (exit {returncode}): {output}")
    return f"Uninstalled {package}."


# --------------------------------------------------------------------------
# Scripted steps — a batch of allowlisted tool calls, stops at the first failure.
# --------------------------------------------------------------------------

# Non-destructive actions only: no uninstall, build, emulator lifecycle, screenshots or trace.
STEP_ACTIONS = {
    fn.__name__: getattr(fn, "__wrapped__", fn)
    for fn in (
        tap, long_press, swipe, scroll, input_text, clear_text, press_key, wait, wait_for,
        network, launch_app, launch_activity, stop_app,
    )
}


def _bind_step(n: int, step: object) -> tuple[str, dict]:
    """Validate step n (1-based) against its action's signature: (action, kwargs)."""
    if not isinstance(step, dict):
        raise ValueError(f"step {n}: expected an object, got {type(step).__name__}.")
    kwargs = dict(step)
    action = kwargs.pop("action", None)
    if action not in STEP_ACTIONS:
        raise ValueError(f"step {n}: action must be one of {sorted(STEP_ACTIONS)}, got {action!r}.")
    if "device" in kwargs:
        raise ValueError(f"step {n}: 'device' is set once on run_steps, not per step.")
    try:
        inspect.signature(STEP_ACTIONS[action]).bind(**kwargs)
    except TypeError as e:
        raise ValueError(f"step {n} ({action}): invalid args: {e}.")
    return action, kwargs


@mcp.tool()
@_returns_errors
async def run_steps(steps: list[dict], device: str | None = None) -> str:
    """Run a scripted test: a list of actions in one call, stopping at the first failure.

    Each step is {"action": <tool name>, ...that tool's args}, without `device`. Actions: tap,
    long_press, swipe, scroll, input_text, clear_text, press_key, wait, wait_for, network,
    launch_app, launch_activity, stop_app. Use wait_for as an assertion (timeout_s=0 checks once).
    All steps are validated before any runs. Max 50 steps. Reports one line per step; on failure
    appends the get_state view of the screen. Example:
    [{"action": "launch_app", "package": "com.example"},
     {"action": "wait_for", "text": "Log in", "timeout_s": 10},
     {"action": "tap", "text": "Log in"},
     {"action": "wait_for", "text": "Welcome"}]
    """
    if not steps:
        raise ValueError("steps is empty.")
    if len(steps) > RUN_STEPS_MAX:
        raise ValueError(f"too many steps ({len(steps)}); max {RUN_STEPS_MAX}.")
    bound = [_bind_step(n, step) for n, step in enumerate(steps, 1)]
    serial = await _resolve_device(device)

    lines = []
    for n, (action, kwargs) in enumerate(bound, 1):
        fn = STEP_ACTIONS[action]
        if "device" in inspect.signature(fn).parameters:
            kwargs["device"] = serial
        try:
            result = await fn(**kwargs)
        except ValueError as e:
            lines += [
                f"{n} FAIL {action}: {e}",
                f"Stopped at step {n}/{len(bound)}.",
                "",
                "Screen at failure:",
                await get_state(device=serial),
            ]
            return _truncate("\n".join(lines))
        lines.append(f"{n} ok {action}: {result}")
    lines.append(f"All {len(bound)} step(s) passed.")
    return _truncate("\n".join(lines))


if __name__ == "__main__":
    # Turn SIGTERM into a normal exit so the atexit handler stops headless emulators.
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    mcp.run()
