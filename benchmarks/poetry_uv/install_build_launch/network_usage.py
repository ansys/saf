"""Measure the network around a benchmark command.

Two different things are measured:

* The **download rate of the tool**: while the timed command runs, a sampler
  reads the operating system's byte counters every ``interval`` seconds and
  reports ``downloaded_bytes``, ``download_seconds`` (time receiving faster than
  ``active_threshold`` bytes per second), and ``download_speed`` (bytes received
  in those intervals divided by ``download_seconds``). This depends on the
  internet *and* on how the tool downloads (UV fetches many packages at once,
  pip one file at a time), so it differs between backends on the same
  connection.
* The **internet speed**: :func:`measure_internet_speed` downloads the same
  public file before every timed command (not timed), with several parallel
  connections, and reports ``internet_speed`` in bytes per second. It does not
  depend on the backend, so it is comparable across all runs and sessions.

The counters cover the whole machine, so other downloads running at the same
time are included. Only the standard library is used (``ctypes`` on Windows,
``/proc/net/dev`` on Linux, ``urllib`` for the speed test), so the WSL worker
can import this module.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ctypes
import http.client
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request

DEFAULT_INTERVAL = 0.25
# Below this rate the machine is considered idle (background chatter, keep-alives).
DEFAULT_ACTIVE_THRESHOLD = 100_000

# Internet speed test: always the same public, immutable file (plotly 7.2.0, 9.7 MB,
# also in fixture/uv.lock), downloaded in byte ranges over parallel connections so the
# result reflects the connection, not one TCP stream.
SPEED_TEST_URL = (
    "https://files.pythonhosted.org/packages/f8/43/86c04582164c54476d4dae5c053af82ba70b975f5babbf183ae6e51159b9/"
    "plotly-7.2.0-py3-none-any.whl"
)
SPEED_TEST_CONNECTIONS = 4
SPEED_TEST_TIMEOUT = 60.0
# One download of the file takes well under a second on a fast line, which mostly
# measures connection setup. The file is downloaded again until this much time has
# passed (after one warm-up round), so the result is an average over a few seconds.
SPEED_TEST_DURATION = 3.0
SPEED_TEST_MAX_ROUNDS = 10
_CHUNK = 256 * 1024

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


def _download_range(url: str, start: int, end: int, timeout: float) -> int:
    """Download bytes ``start``-``end`` of ``url`` and return how many were received."""
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    received = 0
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 206:
            raise OSError(f"server ignored the byte range (HTTP {response.status})")
        while chunk := response.read(_CHUNK):
            received += len(chunk)
    return received


def measure_internet_speed(
    url: str = SPEED_TEST_URL,
    connections: int = SPEED_TEST_CONNECTIONS,
    timeout: float = SPEED_TEST_TIMEOUT,
    duration: float = SPEED_TEST_DURATION,
) -> float | None:
    """Return the internet download speed in bytes per second, or ``None`` if the test failed.

    The same file is downloaded every time, split into ``connections`` byte
    ranges fetched in parallel, so the result reflects the connection rather
    than the behavior of Poetry, UV, or pip. After one warm-up round (connection
    setup), the file is downloaded again until ``duration`` seconds have passed.
    A failed test never fails a run.
    """
    try:
        head = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(head, timeout=timeout) as response:
            size = int(response.headers["Content-Length"])
        step = -(-size // connections)
        ranges = [(start, min(start + step, size) - 1) for start in range(0, size, step)]
        with ThreadPoolExecutor(max_workers=len(ranges)) as pool:

            def one_round() -> int:
                return sum(pool.map(lambda bounds: _download_range(url, *bounds, timeout), ranges))

            if one_round() != size:  # warm-up: DNS, TLS, and TCP ramp-up are not measured
                return None
            received, rounds = 0, 0
            started = time.perf_counter()
            while rounds < SPEED_TEST_MAX_ROUNDS and (rounds == 0 or time.perf_counter() - started < duration):
                received += one_round()
                rounds += 1
            elapsed = time.perf_counter() - started
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException, urllib.error.URLError):
        return None
    if received != size * rounds or elapsed <= 0:
        return None
    return received / elapsed
