# Project: Neurocore Swarm Hive Mind Upgrade

## Architecture
- `lib/neurocore-swarm.ts`: Core `OmniSwarmAdapter`, `SwarmProvider` interface, peer node aggregation, emergency stop propagation.
- `lib/swarm-debate.ts`: `FederatedDebateEngine`, peer debate rounds, dynamic confidence score weighting, adaptive thresholding (`betaAlphaRatio`).
- `lib/hermes-adapter.ts`: `HermesAgentAdapter` implementing `SwarmProvider`, zero-cost Hermes agent provider integration, local endpoint / fallback execution, `SafetyGate` binding.
- `lib/p2p-sync.ts`: Decentralized state synchronization & peer registry (`P2PStateRegistry`, `PeerNode`).
- `lib/safety_gate.ts`: Safety policy enforcement, biometric dead-man switch (`minQualityThreshold: 0.3`), token bucket rate-limiting (`maxRatePerMin: 60`).
- `lib/upgrade-manifest.ts`: System health diagnostics rollup (`runHealthDiagnostics()`) including `hermes-provider` and `p2p-consensus-engine`.
- `tests/`: Automated unit & integration test suite executed via `npx tsx --test tests/*.test.ts`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Free Hermes Provider Adapter | Implement `HermesAgentAdapter` conforming to `SwarmProvider` with 0 API cost | M1 | R2 |
| 2 | P2P Hive Mind Consensus Engine | Extend `OmniSwarmAdapter` & `FederatedDebateEngine` with dynamic weight consensus & state sync | M2 | R1 |
| 3 | E2E Verification & Health Diagnostics | Expand `tests/` with `p2p_consensus.test.ts`, `hermes_provider.test.ts`, health diagnostics, & update `package.json` | M3 | R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Hermes Agent Provider | Implement `lib/hermes-adapter.ts`, `SwarmProvider` compliance, local fallback, `SafetyGate` integration | none | DONE |
| 2 | M2: P2P Swarm Engine | Implement P2P consensus, peer state registry, dynamic confidence weighting, emergency stop cascade | M1 | DONE |
| 3 | M3: Test Suite & Verification | Add unit/integration tests for P2P & Hermes, update health diagnostics, update `package.json` test script | M1, M2 | DONE |

## Interface Contracts
### HermesAgentAdapter <-> SwarmProvider
- Implements `SwarmProvider` interface: `connect()`, `capabilities()`, `start()`, `status()`, `stop()`, `emergencyStop()`.
- Enforces `SafetyGate.evaluate(intent)` prior to intent start.

### OmniSwarmAdapter <-> P2PStateRegistry & FederatedDebateEngine
- `P2PStateRegistry`: `registerNode(node)`, `getNodes()`, `syncState(state)`.
- `FederatedDebateEngine.runP2PDebate(intent, peerNodes, microState)`: aggregates dynamic peer arguments, weights by node reputation/role/microState, checks `SafetyGate`, returns `SwarmDebateResult`.

## Code Layout
- `lib/hermes-adapter.ts` (new)
- `lib/p2p-sync.ts` (new)
- `lib/swarm-debate.ts` (extend)
- `lib/neurocore-swarm.ts` (extend)
- `lib/upgrade-manifest.ts` (extend)
- `package.json` (update test script)
- `tests/hermes_provider.test.ts` (new)
- `tests/p2p_consensus.test.ts` (new)
- `tests/upgrade_manifest.test.ts` (extend)
