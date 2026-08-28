---
name: omniprime-zero-cost-routing
description: Guidelines and procedure for zero-cost AI model triage, circuit breaker rate-limit protection, and local Ollama fallback routing.
---

# OMNIPRIME Zero-Cost Routing Procedure

1. **Zero-Cost Model Triage**:
   - Fast Telemetry / Status: `inclusionai/ling-3.0-flash` ($0.00)
   - Code Generation: `poolside/laguna-s-2.1:free` ($0.00)
   - Megacontext / Architecture: `nvidia/nemotron-3-ultra:free` / `deepseek-v4-pro` ($0.00)
   - Air-Gapped Local Fallback: Local Ollama (`custom/qwen2.5-coder:7b`)

2. **Adaptive Matrix Telemetry Wrapping**:
   - Always wrap offline RouteDecision instances with `self._apply_matrix(...)` so routing weight matrix feedback is recorded even during air-gapped runs.
