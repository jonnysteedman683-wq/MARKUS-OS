#!/usr/bin/env python3
"""hermes_verify_network_intel.py — standalone verification for markus_network_intel.py.

AST gate + module self-test + direct unit checks on the transport-snapshot
primitives. Stdlib-only, no network dependency beyond the module's own probes
(which degrade gracefully). Matches the triad verification doctrine.
"""
from __future__ import annotations
import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "markus_network_intel.py"


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  -  {name}" + (f"  ({detail})" if detail else ""))
    return ok


def main() -> int:
    results = []
    try:
        py_compile.compile(str(TARGET), doraise=True)
        results.append(check("py_compile markus_network_intel.py", True))
    except Exception as e:  # noqa: BLE001
        results.append(check("py_compile markus_network_intel.py", False, str(e)))
        print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
        return 0 if all(results) else 1

    # Module self-test (probes current transport; must not crash).
    proc = subprocess.run([sys.executable, str(TARGET)], capture_output=True, text=True)
    ok_run = proc.returncode == 0 and "PASSED" in proc.stdout
    results.append(check("module self-test passes", ok_run, "exit={}".format(proc.returncode)))
    if not ok_run:
        print(proc.stdout[-1200:])
        print(proc.stderr[-1200:])

    # Direct unit checks on primitives (deterministic, no hard probe dependency).
    sys.path.insert(0, str(HERE))
    import importlib.util
    spec = importlib.util.spec_from_file_location("nintel", TARGET)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    results.append(check("classifies WiFi", mod.classify_description("Intel Wi-Fi 6E AX211") == "wifi"))
    results.append(check("classifies Ethernet", mod.classify_description("Realtek PCIe GbE Family") == "ethernet"))
    results.append(check("classifies VPN", mod.classify_description("Surfshark OpenVPN Tunnel") == "vpn"))
    results.append(check("classifies Cellular", mod.classify_description("Qualcomm WWAN Mobile Broadband") == "cellular"))

    # build_report degrades gracefully (probe=False => no exception, valid shape).
    rep = mod.build_report(probe=False)
    results.append(check("build_report probe=False valid", isinstance(rep.active_adapters, list)))
    results.append(check("primary type is valid enum",
                         rep.primary_connection_type in ("wifi", "ethernet", "vpn", "cellular", "none")))

    # Persistence round-trip.
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "net.json"
        mod.save_report(rep, path=p)
        loaded = mod.load_report(path=p)
        results.append(check("state persists round-trip", loaded.get("primary_connection_type") == rep.primary_connection_type))

    print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
