# Windows Console UTF-8 & Encoding Invariant

When authoring or updating Python scripts or verification harnesses on Windows:
1. **Reconfigure Stdout Encoding**: Place `if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at startup.
2. **Use ASCII Equivalents**: Prefer ASCII status strings in logging and stdout (`[OK]`, `[PASS]`, `[FAIL]`, `->`) over raw Unicode emojis to ensure clean console output across all execution environments.
