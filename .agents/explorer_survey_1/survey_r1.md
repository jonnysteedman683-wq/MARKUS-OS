# Survey Report — Requirement R1: Offline Local Model Fallback Gate

**Author**: Explorer 1 (`explorer_survey_1`)  
**Timestamp**: 2026-08-27T02:27:00+10:00  
**Target Scope**: Requirement R1 (`markus_router.py`, `markus_brain_backend.py`, `hermes_verify_router.py`, `markus_adaptive_matrix.py`)

---

## 1. Executive Summary

Requirement R1 specifies an **Offline Local Model Fallback Gate** ensuring that when the system operates air-gapped or when offline mode is explicitly flagged (`is_offline=True`), the semantic router immediately and deterministically routes requests to the local model (`custom/qwen2.5-coder:7b`) with zero latency overhead and zero network reliance.

Our comprehensive survey confirms:
1. `markus_router.py` contains the offline gating logic in `route_intent()` with `MODEL_AIRGAPPED_LOCAL = "custom/qwen2.5-coder:7b"`.
2. `markus_brain_backend.py` defines `TIER_MODELS["OFFLINE_LOCAL"] = "custom/qwen2.5-coder:7b"`, serving as the single source of truth for model tier dispatch.
3. `hermes_verify_router.py` tests that `r.route_intent("check health", is_offline=True).target_model == r.MODEL_AIRGAPPED_LOCAL` and passes completely (`OVERALL: PASS`).
4. Related gates (`hermes_verify_markus_brain.py`, `hermes_verify_brain_cost.py`, `hermes_verify_evolution_loops.py`, `hermes_verify_vorpal_bridge.py`) compile and pass.

---

## 2. Deep Dive: Codebase Architecture & State

### 2.1 `markus_router.py` Analysis

- **Location**: `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\markus_router.py`
- **Model Constants**:
  ```python
  MODEL_CODE_FAST = TIER_MODELS["CODE_SPECIALIST"]         # "poolside/laguna-s-2.1:free"
  MODEL_MEGACONTEXT_ARCH = TIER_MODELS["MEGACONTEXT_ARCH"] # "deepseek/deepseek-v4-pro-0813"
  MODEL_REALTIME_LINT = TIER_MODELS["FAST_TELEMETRY"]       # "inclusionai/ling-3.0-flash"
  MODEL_AIRGAPPED_LOCAL = "custom/qwen2.5-coder:7b"
  ```
- **Offline Gating Logic (`route_intent`)**:
  ```python
  def route_intent(self, prompt: str, context_tokens: int = 0, is_offline: bool = False) -> RouteDecision:
      estimated_tokens = len(prompt.split()) * 2 + context_tokens

      # Auto-offline detection from network-intel snapshot
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
      ...
  ```
- **Auto-Offline Detection (`_network_down`)**:
  Reads `markus_network_state.json` (written by `markus_network_intel.py`). If the snapshot is fresh (< 600s) and `has_internet` is False, the router automatically fails over to `custom/qwen2.5-coder:7b` even if `is_offline` was not passed as True. If the state file is missing or stale, it fails open (returns `False`).
- **Telemetry Feedback Loop**:
  `record_outcome(target_model, latency_ms, success)` feeds real execution metrics back to `markus_adaptive_matrix.py`, allowing continuous learning.

### 2.2 `markus_brain_backend.py` Analysis

- **Location**: `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\markus_brain_backend.py`
- **Tier Map**:
  ```python
  TIER_MODELS: Dict[str, str] = {
      "CODE_SPECIALIST": "poolside/laguna-s-2.1:free",
      "MEGACONTEXT_ARCH": "deepseek/deepseek-v4-pro-0813",
      "FAST_TELEMETRY": "inclusionai/ling-3.0-flash",
      "DEFAULT_BALANCED": "poolside/laguna-s-2.1:free",
      "OFFLINE_LOCAL": "custom/qwen2.5-coder:7b",
  }
  ```
- **Cost Accounting**:
  `MODEL_PRICES` prices paid models; unlisted/free/local models default to `(0.0, 0.0)` in `estimate_cost()`. All calls are recorded in `markus_brain_cost_ledger.jsonl`.
- **Inference Dispatch (`ask_brain`)**:
  - Remote calls invoke Nous API (`https://inference-api.nousresearch.com/v1/chat/completions`).
  - For offline air-gapped requests (`model == "custom/qwen2.5-coder:7b"` or `tier == "OFFLINE_LOCAL"`), local inference can target the local Ollama daemon (`OLLAMA_URL` defaulting to `http://localhost:11434`) via OpenAI-compatible `/v1/chat/completions` or `/api/chat` with fail-open fallback if the local daemon is not yet spun up.

### 2.3 `markus_adaptive_matrix.py` Analysis

- **Location**: `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\markus_adaptive_matrix.py`
- **Default Models Configuration**:
  ```python
  {"model": "custom/qwen2.5-coder:7b", "provider": "ollama", "tier": "AIRGAPPED_LOCAL",
   "weight": 0.8, "benchmark_ms": None}
  ```
- **Network-Aware Selection**:
  In `select_best_model()`, if `_network_is_down()` evaluates to `True`, the matrix overrides candidate selection to select the `AIRGAPPED_LOCAL` model (`custom/qwen2.5-coder:7b`) with `network_down=True`.

---

## 3. Acceptance Test Audit

| Test Script | Tested Contract | Result | Details |
|---|---|---|---|
| `hermes_verify_router.py` | `py_compile`, router self-test, `target_model == "custom/qwen2.5-coder:7b"` when `is_offline=True`, matrix advisory, `record_outcome` feedback | **PASS** | 5/5 sub-checks passed |
| `hermes_verify_markus_brain.py` | `py_compile`, Nous key, router <-> brain `TIER_MODELS` alignment, no phantom openrouter IDs, live probe gate | **PASS** | 5/5 sub-checks passed |
| `hermes_verify_brain_cost.py` | `py_compile`, cost math, ledger record + summary, corrupt line tolerance, unknown model pricing | **PASS** | 6/6 sub-checks passed |
| `hermes_verify_vorpal_bridge.py` | `py_compile`, bridge self-test, VORPAL GOALS.md DAG parsing, telemetry ledger write, fail-open | **PASS** | 8/8 sub-checks passed |
| `hermes_verify_evolution_loops.py` | AST gate, Reflexion engine, Population Dice, RedTeam adversarial loop | **PASS** | 7/7 sub-checks passed |

---

## 4. Synthesis & Recommendations for Implementation Phase

1. **Routing Gate Strictness**:
   `markus_router.py` already strictly fulfills `is_offline=True` routing to `"custom/qwen2.5-coder:7b"`. Ensure no upstream or downstream caller overrides `target_model` when offline mode is engaged.
2. **Local Ollama Air-Gapped Fallback in Brain Backend**:
   In `markus_brain_backend.py`, when `model == "custom/qwen2.5-coder:7b"` or `tier == "OFFLINE_LOCAL"`, ensure `ask_brain` supports communicating with local Ollama (`http://localhost:11434/v1/chat/completions` or `http://localhost:11434/api/chat`) without attempting to hit `https://inference-api.nousresearch.com` or failing on missing Nous API keys. If the local Ollama daemon is offline or connection is refused, it should return a clear diagnostic `(brain offline: local model custom/qwen2.5-coder:7b unreachable)` and never throw an unhandled exception.
3. **Zero Cost Verification**:
   `estimate_cost("custom/qwen2.5-coder:7b", ...)` safely yields `0.0` USD. Adding `"custom/qwen2.5-coder:7b": (0.0, 0.0)` explicitly to `MODEL_PRICES` in `markus_brain_backend.py` makes this contract self-documenting.
4. **Consistency Across Modules**:
   Keep `markus_router.py`, `markus_brain_backend.py`, and `markus_adaptive_matrix.py` aligned on `"custom/qwen2.5-coder:7b"`.

---

## 5. Verification Commands

```powershell
python -m py_compile markus_router.py markus_brain_backend.py
python hermes_verify_router.py
python hermes_verify_markus_brain.py
python hermes_verify_brain_cost.py
```
