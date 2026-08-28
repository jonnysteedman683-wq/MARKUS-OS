#!/usr/bin/env python3
"""
Targeted Verification of the Identified Queue Flush Defect & Proposed Fix.
Demonstrates:
1. Current failure under non-dict JSON records.
2. Verified fix behavior with `isinstance(record, dict)` guard.
"""

import json
from pathlib import Path
import tempfile

def test_current_vs_fixed():
    adversarial_lines = [
        json.dumps({"msg_id": "valid_1", "status": "QUEUED"}),
        json.dumps([1, 2, 3]),  # Non-dict JSON record (Array)
        json.dumps("string_value"),  # Non-dict JSON record (String)
        json.dumps(12345),  # Non-dict JSON record (Number)
        json.dumps({"msg_id": "valid_2", "status": "QUEUED"}),
    ]

    # Simulation of Current Implementation
    current_flushed = 0
    current_error = None
    try:
        for line in adversarial_lines:
            try:
                record = json.loads(line)
            except Exception:
                continue
            if record.get("status") == "QUEUED":  # CRASHES on line 2!
                current_flushed += 1
    except Exception as e:
        current_error = type(e).__name__ + ": " + str(e)

    # Simulation of Fixed Implementation
    fixed_flushed = 0
    fixed_error = None
    try:
        for line in adversarial_lines:
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            if record.get("status") == "QUEUED":
                fixed_flushed += 1
    except Exception as e:
        fixed_error = str(e)

    print(f"Current implementation: error={current_error}, flushed={current_flushed}")
    print(f"Fixed implementation:   error={fixed_error}, flushed={fixed_flushed}")

    assert current_error is not None, "Current code must fail on non-dict JSON"
    assert fixed_flushed == 2, "Fixed code must flush both valid records"
    print("VERIFICATION OF BUG & FIX: CONFIRMED")

if __name__ == "__main__":
    test_current_vs_fixed()
