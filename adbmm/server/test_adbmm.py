"""Offline tests for adbmm: pure parsing/matching functions on inline UI-dump fixtures."""

import asyncio
import inspect
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image as PILImage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adbmm  # noqa: E402

APP = "es.example.app"
LAUNCHER = "com.android.launcher3"


def node(text="", desc="", rid="", pkg=APP, clickable=False, bounds="[0,0][100,100]",
         password=False, children="", scrollable=False, focusable=False, checkable=False,
         checked=False, selected=False, enabled=True):
    """One uiautomator <node> element with the given attributes and child XML."""
    flags = {
        "clickable": clickable, "scrollable": scrollable, "checkable": checkable,
        "checked": checked, "focusable": focusable, "selected": selected,
        "enabled": enabled, "password": password,
    }
    attrs = " ".join(f'{key}="{str(value).lower()}"' for key, value in flags.items())
    return (
        f'<node text="{text}" resource-id="{rid}" class="android.view.View" package="{pkg}" '
        f'content-desc="{desc}" long-clickable="false" {attrs} bounds="{bounds}">{children}</node>'
    )


def hierarchy(*top_nodes):
    return f'<hierarchy rotation="0">{"".join(top_nodes)}</hierarchy>'


def parse(*top_nodes):
    """Parse a hierarchy made of the given top-level node XML fragments."""
    return adbmm._parse_ui_tree_nodes(hierarchy(*top_nodes))


def test_compose_parent_gets_label_from_child_and_matches():
    nodes = parse(node(
        clickable=True, bounds="[0,1000][540,1200]",
        children=node(text="ORDER NOW!", bounds="[10,1010][500,1100]")
        + node(desc="Ir al menu", bounds="[10,1100][500,1190]"),
    ))
    assert nodes[0]["label"] == "ORDER NOW! Ir al menu"

    tier, hits = adbmm._find_candidates(nodes, None, "order now!", None, None)
    assert tier == 1 and hits == [nodes[0]]  # child match collapses into the clickable parent

    x, y, label, pkg = adbmm._pick_target(nodes, None, "order now", None, None)
    assert (x, y, pkg) == (270, 1100, APP)
    assert label == "ORDER NOW! Ir al menu"


def test_nested_clickable_child_is_not_merged_into_parent_label():
    nodes = parse(node(
        clickable=True,
        children=node(text="Total", bounds="[0,0][50,50]")
        + node(text="Pagar", clickable=True, bounds="[50,0][100,50]"),
    ))
    assert nodes[0]["label"] == "Total"
    assert nodes[2]["label"] == "Pagar"


def test_merged_label_is_full_but_display_is_cut_per_mode():
    nodes = parse(node(clickable=True, children=node(text="x" * 200)))
    assert nodes[0]["label"] == "x" * 200  # matching sees the full label
    assert '"' + "x" * 79 + '…"' in adbmm._node_line(nodes[0])
    assert '"' + "x" * 200 + '"' in adbmm._node_line(nodes[0], max_chars=None)


@pytest.mark.parametrize("space", [" ", " ", " ", " "])
def test_normalization_handles_unicode_spaces_and_euro(space):
    nodes = parse(node(text=f"Pagar pedido |{space}19,32{space}€", clickable=True))
    tier, hits = adbmm._find_candidates(nodes, None, "Pagar pedido | 19,32 €", None, None)
    assert tier == 1 and len(hits) == 1


def test_normalize_function():
    assert adbmm._normalize("  Ａbc  DEF  ") == "abc def"


def test_substring_tier_taps_single_hit():
    nodes = parse(node(text="Pagar pedido | 19,32 €", clickable=True, bounds="[0,0][200,100]"))
    tier, hits = adbmm._find_candidates(nodes, None, "pagar pedido", None, None)
    assert tier == 2 and len(hits) == 1
    assert adbmm._pick_target(nodes, None, "pagar pedido", None, None)[:2] == (100, 50)


def test_resource_id_exact_and_suffix():
    nodes = parse(node(text="OK", rid=f"{APP}:id/btn_ok", clickable=True))
    assert adbmm._find_candidates(nodes, "btn_ok", None, None, None)[0] == 1
    assert adbmm._find_candidates(nodes, f"{APP}:id/btn_ok", None, None, None)[0] == 1


def test_launcher_vs_app_package_filter_and_pkg_reporting():
    launcher = node(desc="Home", pkg=LAUNCHER, clickable=True, bounds="[0,0][1080,2400]")
    app = node(desc="Home", pkg=APP, clickable=True, bounds="[100,2200][170,2240]")
    nodes = parse(launcher, app)

    with pytest.raises(ValueError, match="2 elements matched"):
        adbmm._pick_target(nodes, None, None, "Home", None)

    x, y, _, pkg = adbmm._pick_target(nodes, None, None, "Home", APP)
    assert (x, y, pkg) == (135, 2220, APP)

    _, _, _, pkg = adbmm._pick_target(nodes, None, None, "Home", LAUNCHER)
    assert pkg == LAUNCHER

    with pytest.raises(ValueError, match="packages on screen"):
        adbmm._pick_target(nodes, None, None, "Home", "no.such.pkg")


def test_ambiguous_duplicates_return_candidates_and_never_tap():
    nodes = parse(
        node(text="Add", clickable=True, bounds="[0,0][100,100]"),
        node(text="Add", clickable=True, bounds="[0,200][100,300]"),
    )
    with pytest.raises(ValueError) as err:
        adbmm._pick_target(nodes, None, "Add", None, None)
    message = str(err.value)
    assert "refusing to guess" in message and "nothing tapped" in message
    assert f'[1] "Add" pkg={APP} center=(50,50)' in message
    assert f'[2] "Add" pkg={APP} center=(50,250)' in message


def test_tier3_fuzzy_hit_is_never_tapped():
    nodes = parse(node(text="Pagar pedido | 19,32 €", clickable=True))
    tier, hits = adbmm._find_candidates(nodes, None, "Pagar pedido 19,32", None, None)
    assert tier == 3 and len(hits) == 1
    with pytest.raises(ValueError, match="nothing tapped"):
        adbmm._pick_target(nodes, None, "Pagar pedido 19,32", None, None)


def test_no_match_still_lists_closest_candidates():
    nodes = parse(node(text="Recompensas", clickable=True), node(text="Perfil", clickable=True))
    tier, hits = adbmm._find_candidates(nodes, None, "zzzz", None, None)
    assert tier == 0 and len(hits) == 2
    with pytest.raises(ValueError, match="closest"):
        adbmm._pick_target(nodes, None, "zzzz", None, None)


def test_empty_screen_is_the_only_no_match():
    with pytest.raises(ValueError, match="No UI nodes on screen"):
        adbmm._pick_target([], None, "x", None, None)


def test_redacted_card_field_never_leaks_value():
    card = node(text="4242 4242 4242 4242", rid=f"{APP}:id/card_number", clickable=True,
                bounds="[0,0][500,100]")
    nodes = parse(card)
    assert nodes[0]["text"] == adbmm.REDACTED_PLACEHOLDER
    assert nodes[0]["label"] == adbmm.REDACTED_PLACEHOLDER
    assert adbmm._sensitive_regions(nodes)
    assert "4242" not in adbmm._node_line(nodes[0])
    assert adbmm._find_candidates(nodes, None, "4242", None, None)[0] == 0


def test_sensitive_parent_redacts_merged_child_values():
    nodes = parse(node(
        rid=f"{APP}:id/cvc_field", clickable=True,
        children=node(text="123"),
    ))
    assert nodes[0]["label"] == adbmm.REDACTED_PLACEHOLDER


@pytest.mark.parametrize("label", ["card_number", "cc_num", "cvc", "cvv", "expiry_date", "iban"])
def test_payment_labels_are_sensitive(label):
    assert adbmm._is_sensitive({"resource-id": f"{APP}:id/{label}"})


def test_password_attribute_is_redacted():
    nodes = parse(node(text="hunter2", password=True))
    assert nodes[0]["text"] == adbmm.REDACTED_PLACEHOLDER


def test_node_line_is_compact_and_omits_empty_fields():
    nodes = parse(node(text="Hi", rid=f"{APP}:id/greet", desc="Greeting", clickable=True,
                       bounds="[0,0][10,20]"))
    assert adbmm._node_line(nodes[0]) == '"Hi" id=greet desc="Greeting" center=(5,10)'
    assert adbmm._node_line(parse(node(bounds="[0,0][10,20]"))[0]) == "center=(5,10)"


def test_downscale_png_by_integer_scale():
    buffer = io.BytesIO()
    PILImage.new("RGB", (100, 200), (255, 0, 0)).save(buffer, format="PNG")
    png, width, height = adbmm._downscale_png(buffer.getvalue(), 2)
    assert (width, height) == (100, 200)
    assert PILImage.open(io.BytesIO(png)).size == (50, 100)


def test_returns_errors_decorator_converts_value_error():
    assert asyncio.run(adbmm.dumpsys("nope")).startswith("Error: 'nope' not in allowlist")


def test_fastmcp_introspection_after_decorator():
    tools = {tool.name: tool for tool in asyncio.run(adbmm.mcp.list_tools())}
    tap_props = tools["tap"].inputSchema["properties"]
    assert {"resource_id", "text", "content_desc", "x", "y", "package", "device"} <= set(tap_props)
    assert "include_screenshot" not in tools["get_state"].inputSchema["properties"]
    assert "scale" in tools["screenshot"].inputSchema["properties"]
    assert "max_edge" not in tools["screenshot"].inputSchema["properties"]
    assert tools["tap"].description.startswith("Tap a UI element")
    assert {"network", "wait_for", "run_steps"} <= set(tools)
    assert "steps" in tools["run_steps"].inputSchema["properties"]


def test_screen_text_lists_static_text_not_in_labels():
    nodes = parse(
        node(text="Mi pedido"),
        node(text="nº pedido: 2632"),
        node(text="nº pedido: 2632"),  # duplicate dropped
        node(clickable=True, children=node(text="Ver detalles")),  # already in a label
    )
    assert adbmm._screen_text(nodes, *adbmm.SCREEN_TEXT_MODES["optimal"]) == "Mi pedido · nº pedido: 2632"


def test_screen_text_optimal_mode_cuts_and_caps_at_10():
    nodes = parse(node(text="x" * 200), *(node(text=f"t{i}") for i in range(25)))
    text = adbmm._screen_text(nodes, *adbmm.SCREEN_TEXT_MODES["optimal"])
    assert text.startswith("x" * 79 + "…")
    assert text.endswith("· … (+16 more)")


def test_screen_text_full_mode_keeps_text_and_caps_at_20():
    nodes = parse(node(text="x" * 200), *(node(text=f"t{i}") for i in range(25)))
    text = adbmm._screen_text(nodes, *adbmm.SCREEN_TEXT_MODES["full"])
    assert text.startswith("x" * 200 + " · ")
    assert text.endswith("· … (+6 more)")


def test_get_state_rejects_unknown_mode():
    assert asyncio.run(adbmm.get_state(mode="verbose")).startswith("Error: mode must be one of")


def test_normalize_strips_diacritics():
    assert adbmm._normalize("Café  Ñandú") == "cafe nandu"


def test_accentless_query_matches_exact_and_substring_tiers():
    nodes = parse(node(text="Añadir café", clickable=True))
    assert adbmm._find_candidates(nodes, None, "anadir cafe", None, None)[0] == 1
    assert adbmm._find_candidates(nodes, None, "anadir", None, None)[0] == 2


def test_scrollable_container_merges_at_most_three_labels():
    nodes = parse(node(clickable=True, scrollable=True,
                       children="".join(node(text=f"item {i}") for i in range(6))))
    assert nodes[0]["label"] == "item 0 item 1 item 2 …"
    texts = adbmm._screen_text(nodes, *adbmm.SCREEN_TEXT_MODES["optimal"])
    assert texts == "item 3 · item 4 · item 5"  # not merged, so still visible


def test_unlabelled_button_gets_nearest_labelled_ancestor_as_context():
    nodes = parse(node(
        clickable=True, children=node(text="Item name")
        + node(rid=f"{APP}:id/button_add", clickable=True, bounds="[0,0][10,10]"),
    ))
    button = nodes[2]
    assert button["label"] == "" and button["context"] == "Item name"
    assert adbmm._node_line(button) == 'id=button_add in "Item name" center=(5,5)'
    # Context is display-only: the row is the only text match.
    tier, hits = adbmm._find_candidates(nodes, None, "Item name", None, None)
    assert tier == 1 and hits == [nodes[0]]


def test_node_line_shows_widget_state_flags():
    nodes = parse(
        node(text="Terms", checkable=True, checked=True, bounds="[0,0][10,10]"),
        node(text="Tab", clickable=True, selected=True, bounds="[0,0][10,10]"),
        node(text="Pay", clickable=True, enabled=False, bounds="[0,0][10,10]"),
        node(text="Off", checkable=True, bounds="[0,0][10,10]"),
    )
    assert adbmm._node_line(nodes[0]) == '"Terms" [checked] center=(5,5)'
    assert adbmm._node_line(nodes[1]) == '"Tab" [selected] center=(5,5)'
    assert adbmm._node_line(nodes[2]) == '"Pay" [disabled] center=(5,5)'
    assert adbmm._node_line(nodes[3]) == '"Off" center=(5,5)'


def test_screen_text_keeps_non_consecutive_duplicates_and_amounts_next_to_labels():
    nodes = parse(
        node(text="19,32 €"),
        node(text="Envío"),
        node(text="19,32 €"),  # same amount, different row: kept
        node(text="Total", clickable=True),
        node(text="Tot"),  # substring of a label: kept
        node(text="Total"),  # exact label: dropped
    )
    text = adbmm._screen_text(nodes, *adbmm.SCREEN_TEXT_MODES["optimal"])
    assert text == "19,32 € · Envío · 19,32 € · Tot"


def test_sensitive_merged_child_value_stays_out_of_text_line():
    nodes = parse(node(rid=f"{APP}:id/cvc_field", clickable=True, children=node(text="123")))
    assert "123" not in adbmm._screen_text(nodes, *adbmm.SCREEN_TEXT_MODES["full"])


FOCUS_APP = f"  mCurrentFocus=Window{{abc u0 {APP}/.MainActivity}}\n"
FOCUS_LAUNCHER = f"  mCurrentFocus=Window{{abc u0 {LAUNCHER}/.Launcher}}\n"


@pytest.fixture
def state(monkeypatch):
    """get_state against canned dumpsys/uiautomator output: state(xml, window=..., mode=...)."""
    async def fake_resolve_device(device):
        return "emulator-5554"

    def run(xml, window=FOCUS_APP + "    isKeyguardShowing=false\n", mode="optimal"):
        async def fake_window(serial):
            return window

        async def fake_dump(serial):
            return xml

        monkeypatch.setattr(adbmm, "_resolve_device", fake_resolve_device)
        monkeypatch.setattr(adbmm, "_dumpsys_window", fake_window)
        monkeypatch.setattr(adbmm, "_dump_ui_tree", fake_dump)
        return asyncio.run(adbmm.get_state(mode=mode))

    return run


def element_lines(output):
    return [line for line in output.splitlines() if line.startswith("- ")]


def test_get_state_header_and_text_line(state):
    out = state(hierarchy(node(text="Mi pedido"), node(text="OK", clickable=True)))
    assert out.splitlines()[:5] == [
        "Device: emulator-5554",
        f"Package: {APP}",
        f"Activity: {APP}/.MainActivity",
        "",
        "1 interactive element(s):",
    ]
    assert out.endswith("\n\nText: Mi pedido")
    assert "Text:" not in state(hierarchy(node(text="OK", clickable=True)))


def test_get_state_reports_locked_screen(state):
    out = state(hierarchy(node(text="OK", clickable=True)), window=FOCUS_APP + WINDOW_LOCKED)
    assert "Screen: locked (keyguard showing) — call unlock" in out


@pytest.mark.parametrize("mode, shown, more", [("optimal", 10, 15), ("full", 20, 5)])
def test_get_state_caps_element_list_per_mode(state, mode, shown, more):
    out = state(hierarchy(*(node(text=f"b{i}", clickable=True) for i in range(25))), mode=mode)
    lines = element_lines(out)
    assert "25 interactive element(s):" in out
    assert len(lines) == shown + 1
    assert lines[-1] == f"- … (+{more} more)"
    assert lines[0].startswith('- "b0"')


def test_get_state_no_overflow_line_at_cap(state):
    out = state(hierarchy(*(node(text=f"b{i}", clickable=True) for i in range(10))))
    assert "more)" not in out and len(element_lines(out)) == 10


def test_get_state_lists_layout_noise_after_real_elements(state):
    noise = [node(scrollable=True), node(focusable=True)] * 6
    real = [node(text=f"b{i}", clickable=True) for i in range(3)]
    disabled = node(text="Pay", clickable=True, enabled=False)
    lines = element_lines(state(hierarchy(*noise, *real, disabled)))
    assert [line.split()[1] for line in lines[:4]] == ['"b0"', '"b1"', '"b2"', '"Pay"']
    assert "[disabled]" in lines[3]
    assert lines[-1] == "- … (+6 more)"


def test_get_state_package_from_dump_flags_focus_lag(state):
    out = state(hierarchy(node(text="OK", clickable=True)), window=FOCUS_LAUNCHER)
    assert f"Package: {APP}" in out
    assert f"Activity: {LAUNCHER}/.Launcher (window focus differs from screen package)" in out


# Trimmed from a real API 35 `dumpsys window` capture (locked); screen-off is the AOSP form.
WINDOW_LOCKED = (
    "      screenState=SCREEN_STATE_ON\n"
    "    mAwake=true mScreenOnEarly=true mScreenOnFully=true\n"
    "    isKeyguardShowing=true\n"
)
WINDOW_SCREEN_OFF = (
    "      screenState=SCREEN_STATE_OFF\n"
    "    mAwake=false mScreenOnEarly=false mScreenOnFully=false\n"
    "    isKeyguardShowing=true\n"
)
WINDOW_UNLOCKED = (
    "      screenState=SCREEN_STATE_ON\n"
    "    mAwake=true mScreenOnEarly=true mScreenOnFully=true\n"
    "    isKeyguardShowing=false\n"
)


def test_screen_state_off_locked_unlocked():
    assert adbmm._screen_state(WINDOW_SCREEN_OFF) == "off"
    assert adbmm._screen_state(WINDOW_LOCKED) == "locked"
    assert adbmm._screen_state(WINDOW_UNLOCKED) is None


def test_unlock_rejects_non_digit_pin():
    for bad in ("12ab", "123", "1234; reboot", ""):
        assert asyncio.run(adbmm.unlock(pin=bad)).startswith("Error: invalid pin")


def test_press_key_allowlist_wakeup_yes_power_no():
    assert adbmm.PRESS_KEY_ALLOWLIST["WAKEUP"] == "KEYCODE_WAKEUP"
    assert asyncio.run(adbmm.press_key("POWER")).startswith("Error: 'POWER' not in allowlist")


DEVICES_HEADER = "List of devices attached\n"


def test_free_emulator_port_empty_gap_and_offline():
    assert adbmm._free_emulator_port(DEVICES_HEADER) == 5554
    assert adbmm._free_emulator_port(DEVICES_HEADER + "emulator-5554\tdevice\n") == 5556
    gap = "emulator-5554\tdevice\nemulator-5558\tdevice\n"
    assert adbmm._free_emulator_port(DEVICES_HEADER + gap) == 5556
    assert adbmm._free_emulator_port(DEVICES_HEADER + "emulator-5554\toffline\n") == 5556


def test_free_emulator_port_all_taken_raises():
    raw = "".join(f"emulator-{port}\tdevice\n" for port in range(5554, 5585, 2))
    with pytest.raises(ValueError):
        adbmm._free_emulator_port(raw)


def test_emulator_argv_headless_flags():
    assert adbmm._emulator_argv("Pixel", 5556, False) == ["-avd", "Pixel", "-port", "5556"]
    assert adbmm._emulator_argv("Pixel", 5556, True) == [
        "-avd", "Pixel", "-port", "5556", "-no-window", "-no-audio", "-no-boot-anim",
    ]


def test_parse_avds_drops_noise_lines():
    raw = "INFO    | Storing crashdata\nAPI_35_16kb\n\nWARNING | something\nAPI_36_16kb\n"
    assert adbmm._parse_avds(raw) == ["API_35_16kb", "API_36_16kb"]


def test_stop_emulator_refuses_unspawned_serial(monkeypatch):
    monkeypatch.setattr(adbmm, "_spawned", {})
    result = asyncio.run(adbmm.stop_emulator("emulator-5554"))
    assert result.startswith("Error: Refused: emulator-5554 was not started by this server")


def test_kill_emulator_refuses_non_emulator_serial():
    result = asyncio.run(adbmm.kill_emulator("R58M123ABC", force=True))
    assert result.startswith("Error: 'R58M123ABC' is not an emulator serial")


@pytest.fixture
def project(monkeypatch, tmp_path):
    (tmp_path / "gradlew").write_text("#!/bin/sh\n")
    monkeypatch.setattr(adbmm, "PROJECT_ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize("bad", ["release", "devRelease", "Debug", "debug;rm", "dev Debug", "debug && ls", ""])
def test_build_install_rejects_non_debug_variant(project, bad):
    result = asyncio.run(adbmm.build_install(bad, device="emulator-5554"))
    assert result.startswith("Error: variant must be debug or end with Debug")


@pytest.mark.parametrize("bad", ["app;rm", ":app", "app:", "a b", ""])
def test_build_install_rejects_bad_module(project, bad):
    result = asyncio.run(adbmm.build_install("debug", module=bad, device="emulator-5554"))
    assert result.startswith("Error: module must be a Gradle module path")


def test_build_install_requires_gradlew(monkeypatch, tmp_path):
    monkeypatch.setattr(adbmm, "PROJECT_ROOT", tmp_path)
    result = asyncio.run(adbmm.build_install("debug", device="emulator-5554"))
    assert result.startswith("Error: No gradlew in") and "Android project root" in result


def test_build_install_refuses_non_emulator_serial(project):
    result = asyncio.run(adbmm.build_install("devDebug", device="R58M123ABC"))
    assert result.startswith("Error: Refused: 'R58M123ABC' is not an emulator serial")


def test_build_install_requires_java_home(monkeypatch, project):
    monkeypatch.delenv("JAVA_HOME", raising=False)
    result = asyncio.run(adbmm.build_install("devDebug", device="emulator-5554"))
    assert result.startswith("Error: JAVA_HOME is not set") and "settings.local.json" in result


def test_build_install_failure_policy(monkeypatch, project, tmp_path):
    monkeypatch.setenv("JAVA_HOME", "/jdk")
    monkeypatch.setattr(adbmm, "_build_failures", 0)
    monkeypatch.setattr(adbmm.tempfile, "gettempdir", lambda: str(tmp_path))
    outcomes = iter([1, 1, 0])
    calls = []

    async def fake_run_process(binary, args, timeout, *, cwd=None, env=None, log_path=None):
        calls.append((binary, args, cwd, env))
        log_path.write_text("\n".join(f"line {n}" for n in range(30)))
        return next(outcomes), b"", b""

    monkeypatch.setattr(adbmm, "_run_process", fake_run_process)

    first = asyncio.run(adbmm.build_install("devDebug", device="emulator-5554"))
    assert first.startswith("Build failed (exit 1).")
    assert "line 29" in first and "line 10" in first and "line 9\n" not in first
    assert "Stop:" not in first
    binary, args, cwd, env = calls[0]
    assert binary == str(project / "gradlew")
    assert args == [":app:installDevDebug"] and cwd == project
    assert env["ANDROID_SERIAL"] == "emulator-5554"

    second = asyncio.run(adbmm.build_install("devDebug", device="emulator-5554"))
    assert "Stop: report this log path to the user." in second and "line 29" not in second

    ok = asyncio.run(adbmm.build_install("debug", device="emulator-5554"))
    assert ok.startswith("Built and installed :app:installDebug on emulator-5554 in ")
    assert adbmm._build_failures == 0


def test_uninstall_app_rejects_invalid_package():
    result = asyncio.run(adbmm.uninstall_app("bad pkg;rm", device="emulator-5554"))
    assert result.startswith("Error: invalid package name")


def test_uninstall_app_refuses_non_emulator_serial():
    result = asyncio.run(adbmm.uninstall_app("es.example.app", device="R58M123ABC"))
    assert result.startswith("Error: Refused: 'R58M123ABC' is not an emulator serial")


def test_uninstall_app_success_and_failure(monkeypatch):
    calls = []
    outputs = iter([(0, b"Success\n", b""), (0, b"Failure [DELETE_FAILED_INTERNAL_ERROR]\n", b"")])

    async def fake_run_adb(args, timeout=adbmm.DEFAULT_TIMEOUT):
        calls.append(args)
        return next(outputs)

    monkeypatch.setattr(adbmm, "_run_adb", fake_run_adb)

    ok = asyncio.run(adbmm.uninstall_app("es.example.app", device="emulator-5554"))
    assert ok == "Uninstalled es.example.app."
    assert calls[0] == ["-s", "emulator-5554", "uninstall", "es.example.app"]

    failed = asyncio.run(adbmm.uninstall_app("es.example.app", device="emulator-5554"))
    assert failed.startswith("Error: could not uninstall") and "DELETE_FAILED_INTERNAL_ERROR" in failed


# --- trace ---


class FakeProc:
    """Stand-in for subprocess.Popen: alive until terminate() is called."""

    def __init__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True


@pytest.fixture
def traces(monkeypatch, tmp_path):
    """Fresh flow state, temp dir = tmp_path, adb, device clock and Popen faked; returns spawns."""
    spawned = []

    def fake_popen(argv, **kwargs):
        proc = FakeProc(argv, **kwargs)
        spawned.append(proc)
        return proc

    async def fake_adb_shell(serial, shell_args, timeout=0):
        return 0, b"1763288430\n", b""

    async def fake_resolve_device(device):
        return device or "emulator-5554"

    monkeypatch.setattr(adbmm, "_traces", {})
    monkeypatch.setattr(adbmm, "_flow_logs", [])
    monkeypatch.setattr(adbmm.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(adbmm, "_resolve_adb", lambda: "/fake/adb")
    monkeypatch.setattr(adbmm, "_adb_shell", fake_adb_shell)
    monkeypatch.setattr(adbmm, "_resolve_device", fake_resolve_device)
    monkeypatch.setattr(adbmm.subprocess, "Popen", fake_popen)
    return spawned


def test_trace_flow_starts_stream_from_device_time_and_names_file(traces, tmp_path):
    result = asyncio.run(adbmm.trace_flow("Checkout: Delivery!", str(tmp_path)))
    path = tmp_path / "logcat-checkout-delivery.log"
    assert result == str(path) and path.exists()
    assert [proc.argv for proc in traces] == [
        ["/fake/adb", "-s", "emulator-5554", "logcat", "-v", "threadtime",
         "-T", "1763288430.000"],
    ]
    assert asyncio.run(adbmm.trace_flow("  !! ", str(tmp_path))).startswith("Error:")


def test_trace_flow_ends_previous_flow_and_never_overwrites(traces, tmp_path):
    asyncio.run(adbmm.trace_flow("login", str(tmp_path)))
    second = asyncio.run(adbmm.trace_flow("login", str(tmp_path)))
    assert traces[0].terminated and not traces[1].terminated
    assert second == str(tmp_path / "logcat-login-2.log")
    assert asyncio.run(adbmm.trace_flow("login", str(tmp_path))).endswith("logcat-login-3.log")


def test_validate_trace_dir_refuses_relative_missing_and_outside(traces, tmp_path):
    assert adbmm._validate_trace_dir(str(tmp_path)) == tmp_path
    for bad in ("relative/dir", str(tmp_path / "missing"), str(Path.home())):
        with pytest.raises(ValueError, match="Refused|not an existing"):
            adbmm._validate_trace_dir(bad)


def test_mask_secrets_bearer_json_and_form():
    line, count = adbmm._mask_secrets("Authorization: Bearer abc.def.ghi")
    assert (line, count) == ("Authorization: Bearer ***", 1)
    line, count = adbmm._mask_secrets('{"email":"a@b.c","password":"hunter2","token":"sekret"}')
    assert line == '{"email":"a@b.c","password":"***","token":"***"}' and count == 2
    line, count = adbmm._mask_secrets("grant_type=password&refresh_token=sekret&client_secret=hunter2")
    assert line == "grant_type=password&refresh_token=***&client_secret=***" and count == 2
    assert adbmm._mask_secrets("D/Request: GET users/me/") == ("D/Request: GET users/me/", 0)


def test_trace_save_masks_all_flows_filters_by_title_and_never_overwrites(traces, tmp_path):
    asyncio.run(adbmm.trace_flow("login", str(tmp_path)))
    (tmp_path / "logcat-login.log").write_text("Authorization: Bearer abc.def.ghi\nplain line\n")
    asyncio.run(adbmm.trace_flow("checkout", str(tmp_path)))
    (tmp_path / "logcat-checkout.log").write_text('{"password":"hunter2"}\n')
    dest = tmp_path / "evidence"

    only = asyncio.run(adbmm.trace_save(str(dest), title="Login"))
    assert "Masked values: 1" in only and not (dest / "logcat-checkout.log").exists()
    assert (dest / "logcat-login.log").read_text() == "Authorization: Bearer ***\nplain line\n"

    clash = asyncio.run(adbmm.trace_save(str(dest)))
    assert clash.startswith("Error: Refused:") and "already exists" in clash

    other = tmp_path / "all"
    result = asyncio.run(adbmm.trace_save(str(other)))
    assert "Masked values: 2" in result
    assert (other / "logcat-checkout.log").read_text() == '{"password":"***"}\n'
    # raw scratchpad copy untouched
    assert "abc.def.ghi" in (tmp_path / "logcat-login.log").read_text()


def test_trace_save_refuses_relative_dest_and_no_match(traces, tmp_path):
    assert asyncio.run(adbmm.trace_save(str(tmp_path / "x"))).startswith("Error: No matching")
    asyncio.run(adbmm.trace_flow("login", str(tmp_path)))
    relative = asyncio.run(adbmm.trace_save("evidence"))
    assert relative.startswith("Error: Refused: dest_dir must be an absolute path")
    assert asyncio.run(adbmm.trace_save(str(tmp_path / "x"), title="nope")).startswith("Error: No matching")


def test_trace_end_terminates_stream_keeps_log_and_status(traces, tmp_path):
    asyncio.run(adbmm.trace_flow("login", str(tmp_path)))
    status = asyncio.run(adbmm.trace_status())
    assert "recording" in status
    result = asyncio.run(adbmm.trace_end())
    assert result.startswith(str(tmp_path / "logcat-login.log")) and traces[0].terminated
    assert adbmm._flow_logs == [tmp_path / "logcat-login.log"]
    assert "finished" in asyncio.run(adbmm.trace_status())
    assert asyncio.run(adbmm.trace_end()).startswith("Error: No live flow")
    assert asyncio.run(adbmm._end_trace("emulator-5556")) is None


def test_start_emulator_takes_no_trace_dir():
    assert "trace_dir" not in inspect.signature(adbmm.start_emulator).parameters


@pytest.mark.parametrize("variant,module,task", [
    ("debug", "app", ":app:installDebug"),
    ("devDebug", "app", ":app:installDevDebug"),
    ("debug", "feature:shop", ":feature:shop:installDebug"),
])
def test_build_install_runs_expected_task(monkeypatch, project, tmp_path, variant, module, task):
    monkeypatch.setenv("JAVA_HOME", "/jdk")
    monkeypatch.setattr(adbmm, "_build_failures", 0)
    monkeypatch.setattr(adbmm.tempfile, "gettempdir", lambda: str(tmp_path))
    calls = []

    async def fake_run_process(binary, args, timeout, *, cwd=None, env=None, log_path=None):
        calls.append(args)
        return 0, b"", b""

    monkeypatch.setattr(adbmm, "_run_process", fake_run_process)
    result = asyncio.run(adbmm.build_install(variant, module=module, device="emulator-5554"))
    assert calls == [[task]] and result.startswith(f"Built and installed {task} on emulator-5554")


# --- SDK binary resolution ---

def _fake_sdk(root, subdir, name):
    binary = root / subdir / name
    binary.parent.mkdir(parents=True)
    binary.write_text("")
    return binary


@pytest.fixture
def sdk_env(monkeypatch, tmp_path):
    """Clean env: no SDK vars, fake home, nothing on PATH."""
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(adbmm.shutil, "which", lambda name: None)
    return tmp_path


def test_resolve_env_var_wins_over_default(sdk_env, monkeypatch):
    monkeypatch.setattr(adbmm.sys, "platform", "darwin")
    _fake_sdk(sdk_env / "home" / "Library" / "Android" / "sdk", "emulator", "emulator")
    env_binary = _fake_sdk(sdk_env / "custom", "emulator", "emulator")
    monkeypatch.setenv("ANDROID_HOME", str(sdk_env / "custom"))
    assert adbmm._resolve_emulator() == str(env_binary)


@pytest.mark.parametrize("platform,parts", [
    ("darwin", ("Library", "Android", "sdk")),
    ("linux", ("Android", "Sdk")),
])
def test_resolve_falls_back_to_os_default(sdk_env, monkeypatch, platform, parts):
    monkeypatch.setattr(adbmm.sys, "platform", platform)
    binary = _fake_sdk(sdk_env.joinpath("home", *parts), "emulator", "emulator")
    assert adbmm._resolve_emulator() == str(binary)


def test_resolve_expands_tilde_in_env_var(sdk_env, monkeypatch):
    binary = _fake_sdk(sdk_env / "home" / "mysdk", "platform-tools", "adb")
    monkeypatch.setenv("ANDROID_HOME", "~/mysdk")
    assert adbmm._resolve_adb() == str(binary)


def test_resolve_error_lists_tried_paths(sdk_env, monkeypatch):
    monkeypatch.setattr(adbmm.sys, "platform", "darwin")
    monkeypatch.setenv("ANDROID_HOME", str(sdk_env / "x"))
    with pytest.raises(ValueError) as exc:
        adbmm._resolve_emulator()
    msg = str(exc.value)
    assert str(sdk_env / "x" / "emulator" / "emulator") in msg
    assert str(sdk_env / "home" / "Library" / "Android" / "sdk" / "emulator" / "emulator") in msg
    assert "PATH" in msg


class FakeShell:
    """Records adb shell argv; answers `settings get global <key>` from a dict."""

    def __init__(self, settings=None, fail=None):
        self.calls, self.settings, self.fail = [], settings or {}, fail

    async def __call__(self, serial, args, timeout=adbmm.DEFAULT_TIMEOUT):
        self.calls.append(args)
        if self.fail and args[:len(self.fail)] == self.fail:
            return 1, b"", b"boom"
        if args[:3] == ["settings", "get", "global"]:
            return 0, self.settings.get(args[3], "0").encode() + b"\n", b""
        return 0, b"", b""


@pytest.fixture
def emulator(monkeypatch):
    monkeypatch.setattr(adbmm, "_session_device", "emulator-5554")


def test_network_query_only_reads_states(monkeypatch, emulator):
    shell = FakeShell({"airplane_mode_on": "0", "wifi_on": "2", "mobile_data": "1"})
    monkeypatch.setattr(adbmm, "_adb_shell", shell)
    assert asyncio.run(adbmm.network()) == "Network: airplane=off wifi=on data=on"
    assert all(call[:2] == ["settings", "get"] for call in shell.calls)


def test_network_applies_airplane_first_then_others(monkeypatch, emulator):
    shell = FakeShell({"airplane_mode_on": "1", "wifi_on": "3", "mobile_data": "0"})
    monkeypatch.setattr(adbmm, "_adb_shell", shell)
    result = asyncio.run(adbmm.network(data=False, airplane=True))
    assert shell.calls[:2] == [
        ["cmd", "connectivity", "airplane-mode", "enable"],
        ["svc", "data", "disable"],
    ]
    assert result == "Network: airplane=on wifi=off data=off"


def test_network_reports_toggle_failure(monkeypatch, emulator):
    monkeypatch.setattr(adbmm, "_adb_shell", FakeShell(fail=["svc", "wifi"]))
    assert asyncio.run(adbmm.network(wifi=True)).startswith("Error: wifi enable failed (exit 1)")


def fake_screens(monkeypatch, *screens):
    """_dump_ui_tree returns the given hierarchies in turn, repeating the last one."""
    xml = [f'<?xml version="1.0"?><hierarchy rotation="0">{s}</hierarchy>' for s in screens]
    calls = {"n": 0}

    async def dump(serial):
        calls["n"] += 1
        return xml[min(calls["n"], len(xml)) - 1]

    monkeypatch.setattr(adbmm, "_dump_ui_tree", dump)
    monkeypatch.setattr(adbmm, "WAIT_FOR_POLL_S", 0)
    return calls


def test_wait_for_polls_until_element_appears(monkeypatch, emulator):
    calls = fake_screens(monkeypatch, node(text="Loading"), node(text="Welcome back"))
    result = asyncio.run(adbmm.wait_for(text="welcome", timeout_s=5))
    assert result.startswith('Found 1 match(es): "Welcome back"')
    assert calls["n"] == 2


def test_wait_for_timeout_zero_is_a_single_check(monkeypatch, emulator):
    calls = fake_screens(monkeypatch, node(text="Loading", clickable=True))
    result = asyncio.run(adbmm.wait_for(text="Welcome", timeout_s=0))
    assert result.startswith("Error: 'Welcome' not found after 0.0s; closest:")
    assert calls["n"] == 1


def test_wait_for_gone(monkeypatch, emulator):
    fake_screens(monkeypatch, node(text="Loading"), node(text="Done"))
    assert asyncio.run(adbmm.wait_for(text="Loading", gone=True)) == "Gone."


def test_wait_for_requires_selector():
    assert asyncio.run(adbmm.wait_for()).startswith("Error: Provide a selector")


def test_run_steps_validates_all_steps_before_running(monkeypatch, emulator):
    shell = FakeShell()
    monkeypatch.setattr(adbmm, "_adb_shell", shell)
    bad = [
        ([{"action": "press_key", "key": "BACK"}, {"action": "uninstall_app", "package": "x"}],
         "Error: step 2: action must be one of"),
        ([{"action": "tap", "text": "a", "device": "emulator-5556"}], "Error: step 1: 'device' is set once"),
        ([{"action": "tap", "txt": "a"}], "Error: step 1 (tap): invalid args"),
        (["tap"], "Error: step 1: expected an object"),
        ([], "Error: steps is empty"),
        ([{"action": "wait", "seconds": 0}] * 51, "Error: too many steps (51)"),
    ]
    for steps, expected in bad:
        assert asyncio.run(adbmm.run_steps(steps)).startswith(expected)
    assert shell.calls == []


def test_run_steps_runs_in_order_and_stops_at_first_failure(monkeypatch, emulator):
    shell = FakeShell(fail=["input", "keyevent", "KEYCODE_HOME"])
    monkeypatch.setattr(adbmm, "_adb_shell", shell)

    async def state(device=None, mode="optimal"):
        return "Device: emulator-5554"

    monkeypatch.setattr(adbmm, "get_state", state)
    result = asyncio.run(adbmm.run_steps([
        {"action": "press_key", "key": "BACK"},
        {"action": "wait", "seconds": 0},
        {"action": "press_key", "key": "HOME"},
        {"action": "press_key", "key": "ENTER"},
    ]))
    assert result.splitlines() == [
        "1 ok press_key: Pressed BACK.",
        "2 ok wait: Waited 0.0s.",
        "3 FAIL press_key: press_key failed (exit 1): boom",
        "Stopped at step 3/4.",
        "",
        "Screen at failure:",
        "Device: emulator-5554",
    ]
    assert ["input", "keyevent", "KEYCODE_ENTER"] not in shell.calls


def test_run_steps_all_passed(monkeypatch, emulator):
    monkeypatch.setattr(adbmm, "_adb_shell", FakeShell())
    result = asyncio.run(adbmm.run_steps([{"action": "launch_activity", "component": "a.b/.Main"}]))
    assert result.splitlines() == ["1 ok launch_activity: Launched a.b/.Main.", "All 1 step(s) passed."]


# --- capture filters and http_calls ---


def test_logcat_filterspec_validates_tags():
    assert adbmm._logcat_filterspec(["OkHttp", "NAV_PATH"]) == ["OkHttp:V", "NAV_PATH:V", "*:S"]
    assert adbmm._logcat_filterspec(["OkHttp"], "I") == ["OkHttp:I", "*:S"]
    with pytest.raises(ValueError):
        adbmm._logcat_filterspec(["bad tag"])


def test_trace_flow_filters_by_tags_and_package_uid(traces, tmp_path, monkeypatch):
    async def fake_adb_shell(serial, shell_args, timeout=0):
        if shell_args[:2] == ["pm", "list"]:
            return 0, b"package:es.example.app.debug uid:10200\npackage:es.example.app uid:10123\n", b""
        return 0, b"1763288430\n", b""

    monkeypatch.setattr(adbmm, "_adb_shell", fake_adb_shell)
    asyncio.run(adbmm.trace_flow("login", str(tmp_path), tags=["OkHttp", "NAV"], package=APP))
    assert traces[0].argv[-4:] == ["--uid=10123", "OkHttp:V", "NAV:V", "*:S"]
    missing = asyncio.run(adbmm.trace_flow("x", str(tmp_path), package="com.missing"))
    assert missing.startswith("Error:") and "not installed" in missing
    bad = asyncio.run(adbmm.trace_flow("x", str(tmp_path), tags=["a b"]))
    assert bad.startswith("Error:") and not traces[0].terminated  # live flow kept on bad input


def tt(time, tid, tag, message):
    """One `-v threadtime` line."""
    return f"01-19 {time} 12006 {tid:>5} I {tag:<8}: {message}\n"


OKHTTP_LOG = "".join([
    tt("09:52:50.000", 1, "NAV_PATH", "home -> plp"),
    tt("09:52:53.100", 10, "OkHttp", "--> GET https://api.x.com/v1/products?page=1&token=abc"),
    tt("09:52:53.101", 11, "OkHttp", "--> POST https://api.x.com/v1/cart http/1.1"),
    tt("09:52:53.102", 11, "OkHttp", "Content-Type: application/json"),
    tt("09:52:53.103", 11, "OkHttp", '{"password":"hunter2"}'),
    tt("09:52:53.104", 11, "OkHttp", "--> END POST (22-byte body)"),
    tt("09:52:53.300", 10, "OkHttp", "<-- 200 OK https://api.x.com/v1/products?page=1&token=abc (200ms)"),
    tt("09:52:53.301", 10, "OkHttp", "<-- END HTTP (2048-byte body)"),
    tt("09:52:55.000", 11, "OkHttp", "<-- 404 Not Found https://api.x.com/v1/cart (1900ms, 10-byte body)"),
    tt("09:52:56.000", 1, "NAV_PATH", "plp -> pdp"),
    tt("09:52:56.100", 12, "OkHttp", "--> GET https://www.google-analytics.com/collect"),
    tt("09:52:56.200", 12, "OkHttp", "<-- 204 https://www.google-analytics.com/collect (5ms, 0-byte body)"),
    tt("09:52:57.000", 13, "OkHttp", "--> GET https://api.x.com/v1/pdp/1"),
    tt("09:52:58.000", 13, "OkHttp", "<-- HTTP FAILED: java.net.SocketTimeoutException: timeout"),
    tt("09:52:59.000", 14, "OkHttp", "--> GET https://api.x.com/v1/reviews"),
    "--------- beginning of main\n",
    tt("09:53:00.000", 2, "Other", "--> GET https://ignored.com/x"),
])


def write_tmp(directory, name, text):
    path = directory / name
    path.write_text(text)
    return path


def test_pair_http_calls_threadtime(tmp_path):
    entries = adbmm._read_log_entries(write_tmp(tmp_path, "flow.log", OKHTTP_LOG))
    calls = adbmm._pair_http_calls(entries)
    got = [(c.method, c.url.split("?")[0], c.status, c.ok, c.ms, c.req_bytes, c.resp_bytes) for c in calls]
    assert got == [
        ("GET", "https://api.x.com/v1/products", "200", True, 200, 0, 2048),
        ("POST", "https://api.x.com/v1/cart", "404", False, 1900, 22, 10),
        ("GET", "https://www.google-analytics.com/collect", "204", True, 5, 0, 0),
        ("GET", "https://api.x.com/v1/pdp/1", "FAILED: java.net.SocketTimeoutException: timeout",
         False, None, 0, 0),
        ("GET", "https://api.x.com/v1/reviews", "no response", False, None, 0, 0),
    ]


def test_http_report_markers_masking_and_summary(tmp_path):
    entries = adbmm._read_log_entries(write_tmp(tmp_path, "flow.log", OKHTTP_LOG))
    report = adbmm._http_report(entries, adbmm._pair_http_calls(entries), 1500, ["NAV_PATH"])
    lines = report.splitlines()
    assert lines[0] == "Base URL: https://api.x.com"
    assert lines[1] == "Hosts: https://api.x.com (4), https://www.google-analytics.com (1)"
    assert lines[2] == "09:52:50.000 [NAV_PATH] home -> plp"
    assert lines[3] == "09:52:53.100 GET /v1/products?page=1&token=*** 200 200ms 2.00 KiB"
    assert lines[4] == "09:52:53.101 POST /v1/cart 404 1900ms 0.03 KiB SLOW"
    assert lines[5] == "09:52:56.000 [NAV_PATH] plp -> pdp"
    assert lines[6].startswith("09:52:56.100 GET https://www.google-analytics.com/collect 204 5ms")
    assert "FAILED: java.net.SocketTimeoutException" in lines[7]
    assert lines[8].endswith("/v1/reviews no response 0.00 KiB")
    assert lines[9] == ("Calls: 5 (ok 2, failed 2, no response 1) | total 2105 ms | "
                        "total 2.03 KiB | slow (>1500 ms) 1")
    assert "hunter2" not in report and "ignored.com" not in report


def test_read_logcat_json_export_feeds_same_pairing(tmp_path):
    export = {
        "metadata": {"device": {}},
        "logcatMessages": [
            {"header": {"tid": 7, "tag": "OkHttp", "timestamp": {"seconds": 1768811563, "nanos": 852000000}},
             "message": "--> GET https://api.x.com/a"},
            {"header": {"tid": 7, "tag": "OkHttp", "timestamp": {"seconds": 1768811564, "nanos": 0}},
             "message": "<-- 200 OK https://api.x.com/a (30ms, 1024-byte body)"},
        ],
    }
    entries = adbmm._read_log_entries(write_tmp(tmp_path, "flow.logcat", json.dumps(export)))
    assert entries[0].time.endswith(".852")
    (call,) = adbmm._pair_http_calls(entries)
    assert (call.status, call.ms, call.resp_bytes) == ("200", 30, 1024)
    with pytest.raises(ValueError, match="not an Android Studio"):
        adbmm._read_log_entries(write_tmp(tmp_path, "bad.logcat", "[]"))


def test_http_calls_resolves_flow_title_and_refuses_paths(traces, tmp_path, monkeypatch):
    asyncio.run(adbmm.trace_flow("checkout", str(tmp_path)))
    (tmp_path / "logcat-checkout.log").write_text(OKHTTP_LOG)
    result = asyncio.run(adbmm.http_calls("Checkout"))
    assert result.startswith("Base URL: https://api.x.com") and "Calls: 5" in result
    assert asyncio.run(adbmm.http_calls(str(tmp_path / "logcat-checkout.log"))) == result
    assert "No flow log titled" in asyncio.run(adbmm.http_calls("nope"))
    assert "must end in" in asyncio.run(adbmm.http_calls(str(tmp_path / "x.json")))
    monkeypatch.setattr(adbmm, "PROJECT_ROOT", tmp_path / "project")
    assert "Refused" in asyncio.run(adbmm.http_calls("/etc/hosts.txt"))
    assert asyncio.run(adbmm.http_calls("Checkout", marker_tags=["a b"])).startswith("Error:")
    assert asyncio.run(adbmm.http_calls("Checkout", slow_ms=100)).count("SLOW") == 2



@pytest.fixture
def idle(monkeypatch, traces):
    """Two spawned emulators (headless 5554, windowed 5556), adb faked, last call 10 min ago."""
    async def fake_run_adb(args, timeout=0):
        for serial, (proc, _, _) in adbmm._spawned.items():
            if serial in args:
                proc.terminate()
        return 0, b"", b""

    spawned = {
        "emulator-5554": (FakeProc(["emu"]), True, "API_35"),
        "emulator-5556": (FakeProc(["emu"]), False, "API_36"),
    }
    monkeypatch.setattr(adbmm, "_spawned", spawned)
    monkeypatch.setattr(adbmm, "_pending_notes", [])
    monkeypatch.setattr(adbmm, "_inflight", 0)
    monkeypatch.setattr(adbmm, "_last_activity", adbmm.time.monotonic() - 600)
    monkeypatch.setattr(adbmm, "_run_adb", fake_run_adb)
    monkeypatch.setattr(adbmm, "_notify", lambda message: None)
    return spawned


def test_idle_stop_ends_flow_stops_only_headless_and_notes_next_result(idle, tmp_path):
    asyncio.run(adbmm.trace_flow("login", str(tmp_path)))
    adbmm._last_activity = adbmm.time.monotonic() - 600
    asyncio.run(adbmm._stop_idle_headless())
    assert list(adbmm._spawned) == ["emulator-5556"]
    assert adbmm._traces["emulator-5554"].proc.terminated
    result = asyncio.run(adbmm.trace_status())
    assert result.startswith("Headless API_35 (emulator-5554) stopped after 5 min idle. "
                             f"Flow log: {tmp_path / 'logcat-login.log'}\n")
    assert adbmm._pending_notes == []


def test_idle_stop_waits_for_running_call_and_recent_activity(idle, monkeypatch):
    monkeypatch.setattr(adbmm, "_inflight", 1)
    asyncio.run(adbmm._stop_idle_headless())
    monkeypatch.setattr(adbmm, "_inflight", 0)
    monkeypatch.setattr(adbmm, "_last_activity", adbmm.time.monotonic())
    asyncio.run(adbmm._stop_idle_headless())
    assert len(adbmm._spawned) == 2 and adbmm._pending_notes == []


def test_idle_watchdog_off_when_minutes_zero(monkeypatch):
    monkeypatch.setattr(adbmm, "IDLE_SHUTDOWN_MIN", 0)
    monkeypatch.setattr(adbmm, "_watchdog_task", None)
    adbmm._start_idle_watchdog()
    assert adbmm._watchdog_task is None
