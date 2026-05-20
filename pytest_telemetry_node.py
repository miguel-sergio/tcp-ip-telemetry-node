"""
Target tests for tcp-ip-telemetry-node firmware.
Uses pytest-embedded (esp,idf services) per the ESP-IDF testing standard.

Quick-start
-----------
1. Build the firmware (include sdkconfig.ci for Wi-Fi credentials):

       idf.py -DSDKCONFIG_DEFAULTS='sdkconfig.defaults;sdkconfig.ci' \\
              set-target esp32 build

2. Flash and run all tests:

       pytest --target esp32

3. Skip re-flashing on repeated runs (useful while iterating on the script):

       pytest --target esp32 --skip-autoflash y

Test-case IDs produced by this file (target.config.function):
  esp32.default.test_boot_message
  esp32.default.test_wifi_connects
  esp32.default.test_telemetry_is_sent
  esp32.default.test_telemetry_json_fields
  esp32.default.test_telemetry_json_values
"""

import json
import pytest
from pytest_embedded_idf.dut import IdfDut

# ── Timeouts (seconds) ────────────────────────────────────────────────────────
BOOT_TIMEOUT = 10   # time to see the startup banner after reset
WIFI_TIMEOUT = 30   # time to obtain an IP address (includes retries)
TCP_TIMEOUT  = 20   # time for the first telemetry send after Wi-Fi is up

# ── Helpers ───────────────────────────────────────────────────────────────────

def _wait_for_boot(dut: IdfDut) -> None:
    """Shared preamble: wait for the boot banner."""
    dut.expect_exact("tcp-ip-telemetry-node starting...", timeout=BOOT_TIMEOUT)


def _wait_for_wifi(dut: IdfDut) -> None:
    """Shared preamble: wait for boot then a valid IP address."""
    _wait_for_boot(dut)
    dut.expect(r"got IP: \d+\.\d+\.\d+\.\d+", timeout=WIFI_TIMEOUT)


# ── Test cases ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("target", ["esp32"], indirect=True)
def test_boot_message(dut: IdfDut) -> None:
    """Device prints the startup banner immediately after reset."""
    _wait_for_boot(dut)


@pytest.mark.parametrize("target", ["esp32"], indirect=True)
def test_wifi_connects(dut: IdfDut) -> None:
    """Device connects to the configured AP and obtains an IP address."""
    _wait_for_wifi(dut)


@pytest.mark.parametrize("target", ["esp32"], indirect=True)
def test_telemetry_is_sent(dut: IdfDut) -> None:
    """Device sends at least one telemetry frame over TCP within the expected window."""
    _wait_for_wifi(dut)
    dut.expect_exact("telemetry:", timeout=TCP_TIMEOUT)


@pytest.mark.parametrize("target", ["esp32"], indirect=True)
def test_telemetry_json_fields(dut: IdfDut) -> None:
    """The telemetry JSON logged by the TCP client contains all required fields."""
    _wait_for_wifi(dut)

    match = dut.expect(r"telemetry: (\{[^\n]+\})", timeout=TCP_TIMEOUT)
    payload = json.loads(match.group(1))

    required_fields = (
        "machine_id", "state", "temp", "vibration",
        "fault_code", "uptime", "ts",
    )
    for field in required_fields:
        assert field in payload, f"Missing field in telemetry JSON: '{field}'"


@pytest.mark.parametrize("target", ["esp32"], indirect=True)
def test_telemetry_json_values(dut: IdfDut) -> None:
    """The telemetry payload carries valid, in-range values for the simulated node."""
    _wait_for_wifi(dut)

    match = dut.expect(r"telemetry: (\{[^\n]+\})", timeout=TCP_TIMEOUT)
    payload = json.loads(match.group(1))

    assert payload["machine_id"] == "NODE_01", \
        f"Unexpected machine_id: {payload['machine_id']}"

    assert payload["state"] == 1, \
        f"Expected MACHINE_STATE_RUNNING (1), got {payload['state']}"

    assert payload["fault_code"] == 0, \
        f"Expected no active fault (0), got {payload['fault_code']}"

    # telemetry_simulate() adds up to 10 °C to the 68 °C base value
    assert 68.0 <= payload["temp"] <= 80.0, \
        f"Temperature {payload['temp']} out of expected range [68, 80]"

    assert payload["vibration"] >= 0.0, \
        f"Vibration must be non-negative, got {payload['vibration']}"

    assert payload["uptime"] >= 0, \
        f"Uptime must be non-negative, got {payload['uptime']}"

    assert payload["ts"] > 0, \
        f"Timestamp must be positive, got {payload['ts']}"
