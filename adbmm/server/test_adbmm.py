"""Offline tests for adbmm: pure parsing/matching functions on inline UI-dump fixtures."""

import asyncio
import inspect
import io
import sys
from pathlib import Path

import pytest
from PIL import Image as PILImage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adbmm  # noqa: E402

APP = "es.example.app"
LAUNCHER = "com.android.launcher3"


def node(text="", desc="", rid="", pkg=APP, clickable=False, bounds="[0,0][100,100]",
         password=False, children=""):
    """One uiautomator <node> element with the given attributes and child XML."""
    return (
        f'<node text="{text}" resource-id="{rid}" class="android.view.View" package="{pkg}" '
        f'content-desc="{desc}" clickable="{str(clickable).lower()}" long-clickable="false" '
        f'scrollable="false" checkable="false" focusable="false" '
        f'password="{str(password).lower()}" bounds="{bounds}">{children}</node>'
    )


def parse(*top_nodes):
    """Parse a hierarchy made of the given top-level node XML fragments."""
    return adbmm._parse_ui_tree_nodes(f'<hierarchy rotation="0">{"".join(top_nodes)}</hierarchy>')


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
    assert result.startswith("Error: JAVA_HOME is not set") and "settings.json" in result


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
