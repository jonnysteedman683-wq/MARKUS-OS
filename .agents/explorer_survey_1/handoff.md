# Handoff Report — Explorer 1 (Survey Phase: Requirement R1)

## 1. Observation

- **Exact File Paths & Lines Inspected**:
  1. `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\markus_router.py`:
     - Line 19: `from markus_brain_backend import TIER_MODELS`
     - Line 48: `MODEL_AIRGAPPED_LOCAL = "custom/qwen2.5-coder:7b"`
     - Lines 86-103:
       ```python
       def route_intent(self, prompt: str, context_tokens: int = 0, is_offline: bool = False) -> RouteDecision:
           estimated_tokens = len(prompt.split()) * 2 + context_tokens

           # Auto-offline detection: if the transport is down (fresh network-intel
           # snapshot says no internet), route to the local model regardless.
           network_down = self._network_down()
           if is_offline or network_down:
               return RouteDecision(
                   target_model=self.MODEL_AIRGAPPED_LOCAL,
                   provider="custom",
                   tier_category="OFFLINE_LOCAL",
                   confidence=1.0,
                   reason=("System offline / local fallback mode requested."
                           if is_offline else "Network down -> forced local model (network-intel)."),
                   estimated_tokens=estimated_tokens,
                   network_down=network_down
               )
       ```
  2. `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\markus_brain_backend.py`:
     - Lines 40-46:
       ```python
       TIER_MODELS: Dict[str, str] = {
           "CODE_SPECIALIST": "poolside/laguna-s-2.1:free",
           "MEGACONTEXT_ARCH": "deepseek/deepseek-v4-pro-0813",
           "FAST_TELEMETRY": "inclusionai/ling-3.0-flash",
           "DEFAULT_BALANCED": "poolside/laguna-s-2.1:free",
           "OFFLINE_LOCAL": "custom/qwen2.5-coder:7b",
       }
       ```
     - Line 208-210:
       ```python
       def route_brain_model(tier_category: str) -> str:
           """Map an intent-router tier to the cheapest adequate Nous model."""
           return TIER_MODELS.get(tier_category, DEFAULT_MODEL)
       ```
  3. `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\hermes_verify_router.py`:
     - Lines 50-51:
       ```python
       d = r.route_intent("check health", is_offline=True)
       results.append(check("offline -> local model", d.target_model == r.MODEL_AIRGAPPED_LOCAL))
       ```
  4. `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\markus_adaptive_matrix.py`:
     - Lines 91-92:
       ```python
       {"model": "custom/qwen2.5-coder:7b", "provider": "ollama", "tier": "AIRGAPPED_LOCAL",
        "weight": 0.8, "benchmark_ms": None}
       ```

- **Tool Commands & Verbatim Results**:
  1. `python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_db.py markus_context_pruner.py`
     - Return code: 0 (No syntax/AST errors).
  2. `python hermes_verify_router.py`
     - Output:
       ```
       PASS  -  py_compile markus_router.py
       PASS  -  router self-test (benchmark + feedback loop)  (exit=0)
       PASS  -  offline -> local model
       PASS  -  matrix advisory attached
       PASS  -  record_outcome feedback loop moves weights  (dipped=0.100->recovered=0.500)
       OVERALL: PASS
       ```
  3. `python hermes_verify_markus_brain.py`
     - Output:
       ```
       [PASS] G1 brain backend compiles
       [PASS] G2 Nous key present
       [PASS] G3 router == brain TIER_MODELS (single source of truth) (code=poolside/laguna-s-2.1:free, arch=deepseek/deepseek-v4-pro-0813, lint=inclusionai/ling-3.0-flash)
       [PASS] G4 no phantom openrouter IDs clean
       [PASS] G5 live brain probe (opt-in) skipped (MARKUS_BRAIN_LIVE_PROBE=1 to enable)
       TOTAL PASS=5 TOTAL_FAIL=0 (of 5)
       RESULT: PASS
       ```
  4. `python hermes_verify_brain_cost.py`
     - Output:
       ```
       [PASS] G1 brain backend compiles
       [PASS] G2 cost math free=0.0, paid=0.002244000000
       [PASS] G3 record + summary calls=2 per_model={'deepseek/deepseek-v4-flash': 2.127e-05, 'poolside/laguna-s-2.1:free': 0.0}
       [PASS] G4 corrupt-line tolerance calls=2
       [PASS] G5 unknown model = $0
       [PASS] G6 live probe (opt-in) skipped (MARKUS_BRAIN_LIVE_PROBE=1 to enable)
       TOTAL PASS=6 TOTAL_FAIL=0 (of 6)
       RESULT: PASS
       ```

---

## 2. Logic Chain

1. **Premise 1**: Requirement R1 requires that when `is_offline=True`, the semantic router dispatches to the local model `custom/qwen2.5-coder:7b`.
2. **Premise 2**: `markus_router.py` defines `MODEL_AIRGAPPED_LOCAL = "custom/qwen2.5-coder:7b"` and executes an immediate return in `route_intent()` when `is_offline=True` (or when `_network_down()` returns True), returning `RouteDecision(target_model="custom/qwen2.5-coder:7b", provider="custom", tier_category="OFFLINE_LOCAL", ...)`.
3. **Premise 3**: `markus_brain_backend.py` defines `TIER_MODELS["OFFLINE_LOCAL"] = "custom/qwen2.5-coder:7b"`, matching `markus_router.py`.
4. **Premise 4**: Running `python hermes_verify_router.py` evaluates `d = r.route_intent("check health", is_offline=True)` and verifies `d.target_model == r.MODEL_AIRGAPPED_LOCAL`, passing with `PASS - offline -> local model` and `OVERALL: PASS`.
5. **Premise 5**: `markus_adaptive_matrix.py` registers `"custom/qwen2.5-coder:7b"` as the `AIRGAPPED_LOCAL` tier and overrides selection to this model when network is down.
6. **Inference / Conclusion**: The fallback gating contract is verified and aligned across the routing and backend layers.

---

## 3. Caveats

- In `markus_brain_backend.py`, remote execution uses the Nous API endpoint. For full local execution when `custom/qwen2.5-coder:7b` is queried directly via `ask_brain()`, the backend should support local Ollama endpoint communication (`OLLAMA_URL` defaulting to `http://localhost:11434`) with fail-open error handling if the local daemon is not running.
- In `markus_adaptive_matrix.py`, matrix weights adapt based on real calls; when offline, matrix advisory retains `"custom/qwen2.5-coder:7b"`.

---

## 4. Conclusion

Requirement R1 (`markus_router.py`, `markus_brain_backend.py`, `hermes_verify_router.py`) is verified in the current codebase. The routing gate deterministically selects `"custom/qwen2.5-coder:7b"` whenever `is_offline=True` or `network_down=True`. All AST compilation and verification scripts pass without error. Detailed analysis and implementation recommendations are documented in `survey_r1.md`.

---

## 5. Verification Method

To independently verify:
```powershell
python -m py_compile markus_router.py markus_brain_backend.py
python hermes_verify_router.py
python hermes_verify_markus_brain.py
python hermes_verify_brain_cost.py
```

Expected Output:
- `py_compile` succeeds with exit code 0.
- `hermes_verify_router.py` prints `PASS - offline -> local model` and `OVERALL: PASS` (exit code 0).
- `hermes_verify_markus_brain.py` prints `TOTAL PASS=5 TOTAL_FAIL=0 (of 5)` and `RESULT: PASS` (exit code 0).
- `hermes_verify_brain_cost.py` prints `TOTAL PASS=6 TOTAL_FAIL=0 (of 6)` and `RESULT: PASS` (exit code 0).
