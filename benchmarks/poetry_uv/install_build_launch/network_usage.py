"""Measure the network traffic received while a benchmark command runs.

Poetry and UV download packages while they unpack and install, so the time
spent on the network cannot be cut out of the stage time. Instead, a sampler
reads the operating system's byte counters every ``interval`` seconds while the
timed command runs and reports:

* ``downloaded_bytes``     bytes received during the command;
* ``download_seconds``     time during which the machine received faster than
                            ``active_threshold`` bytes per second;
* ``download_speed``       bytes per second while downloading
                            (``downloaded_bytes`` received in active intervals
                            divided by ``download_seconds``).

The counters cover the whole machine, so other downloads running at the same
time are included. Only the standard library is used (``ctypes`` on Windows,
``/proc/net/dev`` on Linux), so the WSL worker can import this module.
"""

from __future__ import annotations

import ctypes
from pathlib import Path
import sys
import threading
import time

DEFAULT_INTERVAL = 0.25
# Below this rate the machine is considered idle (background chatter, keep-alives).
DEFAULT_ACTIVE_THRESHOLD = 100_000

# MIB_IF_ROW2 (iphlpapi GetIfTable2): 1352-byte rows with 64-bit counters.
# Windows also lists every filter driver stacked on a network card (QoS, WFP,
# VPN/proxy filters) as an interface with the same traffic, so only hardware,
# non-filter interfaces are counted; otherwise one download is counted ~5 times.
_IF_TABLE2_HEADER = 8
_IF_ROW2_SIZE = 1352
_IF_ROW2_INDEX_OFFSET = 8
_IF_ROW2_FLAGS_OFFSET = 1152
_IF_ROW2_IN_OCTETS_OFFSET = 1208
_FLAG_HARDWARE_INTERFACE = 0x01
_FLAG_FILTER_INTERFACE = 0x02


def _windows_counters() -> dict[int, int]:
    """Return ``{interface index: received bytes}`` for physical (hardware, non-filter) interfaces."""
    iphlpapi = ctypes.windll.iphlpapi  # type: ignore[attr-defined]
    table = ctypes.c_void_p()
    status = iphlpapi.GetIfTable2(ctypes.byref(table))
    if status != 0 or not table.value:
        raise OSError(f"GetIfTable2 failed with error {status}")
    try:
        count = ctypes.c_ulong.from_address(table.value).value
        counters: dict[int, int] = {}
        for index in range(count):
            row = ctypes.string_at(table.value + _IF_TABLE2_HEADER + index * _IF_ROW2_SIZE, _IF_ROW2_SIZE)
            flags = row[_IF_ROW2_FLAGS_OFFSET]
            if not flags & _FLAG_HARDWARE_INTERFACE or flags & _FLAG_FILTER_INTERFACE:
                continue
            interface = int.from_bytes(row[_IF_ROW2_INDEX_OFFSET : _IF_ROW2_INDEX_OFFSET + 4], "little")
            offset = _IF_ROW2_IN_OCTETS_OFFSET
            counters[interface] = int.from_bytes(row[offset : offset + 8], "little")
        return counters
    finally:
        iphlpapi.FreeMibTable(table)


def _linux_counters() -> dict[str, int]:
    """Return ``{interface: received bytes}`` from ``/proc/net/dev`` without loopback."""
    counters: dict[str, int] = {}
    for line in Path("/proc/net/dev").read_text(encoding="utf-8").splitlines()[2:]:
        name, _, values = line.partition(":")
        name = name.strip()
        if name and name != "lo":
            counters[name] = int(values.split()[0])
    return counters


def read_counters() -> dict[object, int] | None:
    """Return the received-byte counters per interface, or ``None`` when unavailable."""
    try:
        if sys.platform == "win32":
            return dict(_windows_counters())
        if Path("/proc/net/dev").is_file():
            return dict(_linux_counters())
    except (OSError, ValueError, AttributeError):
        return None
    return None


def received_since(previous: dict[object, int], current: dict[object, int]) -> int:
    """Return bytes received between two counter readings (a reset counter counts as zero)."""
    return sum(
        max(value - previous[interface], 0) for interface, value in current.items() if interface in previous
    )


class NetworkSampler:
    """Sample received bytes in a background thread while a command runs."""

    def __init__(self, interval: float = DEFAULT_INTERVAL, active_threshold: float = DEFAULT_ACTIVE_THRESHOLD) -> None:
        self.interval = interval
        self.active_threshold = active_threshold
        self.available = read_counters() is not None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._total = 0
        self._active_bytes = 0
        self._active_seconds = 0.0

    def __enter__(self) -> NetworkSampler:
        if self.available:
            self._thread = threading.Thread(target=self._run, name="network-sampler", daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        previous = read_counters()
        last = time.perf_counter()
        while previous is not None:
            stopping = self._stop.wait(self.interval)
            current = read_counters()
            now = time.perf_counter()
            if current is None:
                break
            received = received_since(previous, current)
            elapsed = now - last
            self._total += received
            if elapsed > 0 and received / elapsed >= self.active_threshold:
                self._active_bytes += received
                self._active_seconds += elapsed
            previous, last = current, now
            if stopping:
                break

    def result(self) -> dict[str, float | int | None]:
        """Return the measurement, or ``None`` values when counters are unavailable."""
        if not self.available:
            return {"downloaded_bytes": None, "download_seconds": None, "download_speed": None}
        speed = self._active_bytes / self._active_seconds if self._active_seconds > 0 else None
        return {
            "downloaded_bytes": self._total,
            "download_seconds": round(self._active_seconds, 3),
            "download_speed": speed,
        }
