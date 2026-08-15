/**
 * Neurocore Server Module — Express Router
 * Exposes SafetyGate, FederatedDebateEngine, P2PStateRegistry, and Health Diagnostics
 * as REST API endpoints for the OMNIBUS backend.
 *
 * Plain JavaScript (CommonJS) so server.js can require() it directly.
 */

const express = require('express');
const router = express.Router();

// ─── SafetyGate ────────────────────────────────────────────────────────

const DEFAULT_SAFETY_POLICY = {
  allowedIntents: ['route', 'execute', 'query', 'observe', 'route_neural_path', 'knowledge_extraction', 'task_1', 'task_2', 'chat', 'dispatch', 'brainstorm', 'analyze'],
  blockedIntents: ['override_system', 'destructive_action', 'unauthorized_command'],
  confidenceThreshold: 0.7,
  maxCostUSD: 5.0,
  allowedFeatures: ['alpha_power', 'beta_alpha_ratio', 'asymmetry', 'quality', 'skillId'],
  minQualityThreshold: 0.3,
  maxRatePerMin: 60
};

class SafetyGate {
  constructor(policy) {
    this.policy = { ...DEFAULT_SAFETY_POLICY, ...policy };
    this.intentTimestamps = [];
  }

  evaluate(intent) {
    const threshold = this.policy.confidenceThreshold || 0.7;

    // Rule 0: Biometric signal quality dead-man switch
    if (intent.features && typeof intent.features.quality === 'number') {
      if (intent.features.quality < (this.policy.minQualityThreshold || 0.3)) {
        return { allowed: false, reason: 'degraded_signal_quality', requiresOperator: true, riskLevel: 'high' };
      }
    }

    // Rule 1: Low confidence
    if (intent.confidence < threshold) {
      return { allowed: false, reason: 'low_confidence', requiresOperator: true, riskLevel: 'high' };
    }

    // Rule 2: Blocked intent
    if (this.policy.blockedIntents.includes(intent.intent)) {
      return { allowed: false, reason: 'blocked_intent', requiresOperator: true, riskLevel: 'high' };
    }

    // Rule 3: Unknown intent
    if (!this.policy.allowedIntents.includes(intent.intent)) {
      return { allowed: false, reason: 'unknown_intent', requiresOperator: true, riskLevel: 'high' };
    }

    // Rule 4: Rate limiting
    const maxRate = this.policy.maxRatePerMin || 60;
    const now = Date.now();
    this.intentTimestamps = this.intentTimestamps.filter(t => now - t < 60000);
    if (this.intentTimestamps.length >= maxRate) {
      return { allowed: false, reason: 'rate_limit_exceeded', requiresOperator: true, riskLevel: 'high' };
    }
    this.intentTimestamps.push(now);

    // Rule 5: Moderate risk
    const requiresOperator = intent.confidence < 0.9 || intent.requiresConfirmation;
    if (requiresOperator) {
      return { allowed: true, reason: 'allowed_operator_required', requiresOperator: true, riskLevel: 'moderate' };
    }

    return { allowed: true, reason: 'allowed', requiresOperator: false, riskLevel: 'low' };
  }
}

// ─── Role Authority Weights ────────────────────────────────────────────

const ROLE_AUTHORITY_WEIGHTS = { guard: 1.3, architect: 1.2, executor: 1.0 };

// ─── FederatedDebateEngine ─────────────────────────────────────────────

class FederatedDebateEngine {
  constructor(config) {
    this.config = { maxRounds: 3, baseThreshold: 0.85, enableNeuralAdaptation: true, ...config };
  }

  calculateAdaptiveThreshold(microState) {
    if (!this.config.enableNeuralAdaptation || !microState) return this.config.baseThreshold;
    const ratio = microState.betaAlphaRatio;
    if (ratio >= 1.8) return 0.75;
    if (ratio < 1.0) return 0.92;
    return 0.85;
  }

  async runDebate(intent, microState) {
    // Stub — will be filled in next edit
    return this._buildDebateResult(intent, microState, []);
  }

  async runP2PDebate(intent, peerNodes, microState) {
    // Stub — will be filled in next edit
    return this._buildDebateResult(intent, microState, peerNodes || []);
  }

  _buildDebateResult(intent, microState, peerNodes) {
    // Stub — will be filled in next edit
    return { debateId: `debate-${Date.now()}`, topic: intent.intent, rounds: [], consensusScore: 0, requiredThreshold: 0.85, verdict: 'rejected', winningSkillId: 'skill-1', reasoning: [] };
  }
}

// ─── P2PStateRegistry ──────────────────────────────────────────────────

class P2PStateRegistry {
  constructor() {
    this.nodes = new Map();
    this.currentState = {
      version: 1, timestamp: Date.now(), activeIntentsCount: 0, consensusThreshold: 0.85,
      globalMetrics: { totalActionsExecuted: 0, averageConfidence: 1.0, activePeersCount: 0 }
    };
    this.syncHistory = [];
  }

  registerNode(node) {
    const rep = Math.max(0, Math.min(1, node.reputationScore || 1.0));
    const full = { ...node, reputationScore: rep, lastSeen: node.lastSeen || Date.now(), status: node.status || 'active' };
    full.weight = this._calcWeight(full);
    this.nodes.set(full.id, full);
    this._updateMetrics();
  }

  getNodes() { return Array.from(this.nodes.values()); }
  getNode(id) { return this.nodes.get(id) || null; }

  _calcWeight(node) {
    if (node.status === 'disconnected' || node.reputationScore < 0.2) return 0;
    const mult = node.status === 'active' ? 1.0 : node.status === 'syncing' ? 0.5 : 0.25;
    return Math.round(node.reputationScore * mult * 100) / 100;
  }

  _updateMetrics() {
    const active = Array.from(this.nodes.values()).filter(n => n.status === 'active');
    this.currentState.globalMetrics.activePeersCount = active.length;
  }

  getConsensusState() { return { ...this.currentState }; }

  async broadcastEmergencyStop() {
    let count = 0;
    for (const [, node] of this.nodes) {
      if (node.status !== 'disconnected') { node.status = 'disconnected'; node.weight = 0; count++; }
    }
    this._updateMetrics();
    return { success: true, haltedNodesCount: count };
  }
}

// ─── Health Diagnostics ────────────────────────────────────────────────

function buildHealthReport(adapter) {
  // Stub — will be filled in next edit
  return { timestamp: Date.now(), overallStatus: 'healthy', components: [], pendingUpgradesCount: 0 };
}

// ─── Adapter Singleton ─────────────────────────────────────────────────

let adapterState = null;

function getAdapter() {
  if (!adapterState) {
    adapterState = {
      safetyGate: new SafetyGate(),
      debateEngine: new FederatedDebateEngine(),
      p2pRegistry: new P2PStateRegistry(),
      connected: false,
      providers: ['hermes', 'ollama'],
      actionLog: []
    };
  }
  return adapterState;
}

// ─── Routes (stubs — will be filled in next edit) ──────────────────────

router.post('/connect', (req, res) => { res.json({ status: 'stub' }); });
router.post('/intent', (req, res) => { res.json({ status: 'stub' }); });
router.get('/health', (req, res) => { res.json({ status: 'stub' }); });
router.post('/debate', (req, res) => { res.json({ status: 'stub' }); });
router.get('/peers', (req, res) => { res.json({ status: 'stub' }); });
router.post('/emergency-stop', (req, res) => { res.json({ status: 'stub' }); });

module.exports = router;
module.exports.SafetyGate = SafetyGate;
module.exports.FederatedDebateEngine = FederatedDebateEngine;
module.exports.P2PStateRegistry = P2PStateRegistry;
