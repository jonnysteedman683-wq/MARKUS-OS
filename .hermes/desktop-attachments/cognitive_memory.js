/**
 * OMNIBUS — Cognitive Memory & Wisdom Consolidation Engine
 * Harvested & Adapted from ARCANE QUANTUM BRAIN
 * 
 * Includes:
 * - Ephemeral -> ShortTerm -> LongTerm -> Core -> Wisdom node consolidation
 * - VAD Emotional Vector tracking (Valence-Arousal-Dominance)
 * - Decay rate calculation & memory strength reinforcement
 * - Semantic & Episodic memory stores
 */

class VADVector {
  constructor(valence = 0, arousal = 0, dominance = 0) {
    this.valence = Math.max(-1, Math.min(1, valence));
    this.arousal = Math.max(-1, Math.min(1, arousal));
    this.dominance = Math.max(-1, Math.min(1, dominance));
  }
}

class CognitiveMemoryNode {
  constructor(id, content, summary, tags = [], state = 'ephemeral') {
    this.id = id || `mem-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    this.content = content;
    this.summary = summary || content;
    this.tags = tags;
    this.state = state; // ephemeral, shortTerm, longTerm, core, wisdom
    this.strength = 1.0;
    this.accessCount = 1;
    this.createdAt = Date.now();
    this.lastAccessed = Date.now();
    this.decayRate = 0.05;
    this.vad = new VADVector(0.2, 0.5, 0.6);
  }

  access() {
    this.accessCount++;
    this.lastAccessed = Date.now();
    this.strength = Math.min(1.0, this.strength + 0.1);
  }

  updateDecay(hoursPassed = 1) {
    this.strength = Math.max(0, this.strength - this.decayRate * hoursPassed);
  }
}

class WisdomNode {
  constructor(insight, sourceMemoryIds = []) {
    this.id = `wisdom-${Date.now()}`;
    this.insight = insight;
    this.sourceMemoryIds = sourceMemoryIds;
    this.strength = 1.0;
    this.createdAt = Date.now();
  }
}

class CognitiveMemoryStore {
  constructor() {
    this.nodes = new Map();
    this.wisdomNodes = [];
    this.episodic = [];
    this.semantic = [];

    this.seedDefaultMemories();
  }

  seedDefaultMemories() {
    const m1 = this.addMemory('Init Task Execution', 'Multi-path execution initialization', ['init', 'system']);
    m1.accessCount = 6;
    m1.state = 'core';

    const m2 = this.addMemory('Knowledge ERD Mapping', 'Biomedical & AI entity relationship extraction', ['erd', 'qpu']);
    m2.accessCount = 6;
    m2.state = 'core';

    const m3 = this.addMemory('KAN B-Spline Optimization', 'Learnable edge spline activation evaluation', ['kan', 'ml']);
    m3.accessCount = 4;
    m3.state = 'shortTerm';

    const m4 = this.addMemory('Mamba SSM Discretization', 'Selective linear state-space sequence processing', ['mamba', 'ssm']);
    m4.accessCount = 2;
    m4.state = 'ephemeral';

    this.recordEpisode('Task Dispatch', { taskId: 'task-1001' }, ['MAML Decomposition', 'KAN Spline Evaluation', 'QA Verification'], 'success', 1.0);
    this.addSemanticConcept('QPU ERD Engine', 'Quantum Processing Unit Entity-Relationship Distillation Engine', ['QPU', 'ERD', 'Graph']);

    // Trigger initial consolidation to distill Wisdom
    this.consolidate();
  }

  addMemory(content, summary, tags = []) {
    const node = new CognitiveMemoryNode(null, content, summary, tags);
    this.nodes.set(node.id, node);
    return node;
  }

  recordEpisode(trigger, context, actionsTaken, outcome = 'success', reward = 1.0) {
    const episode = {
      id: `ep-${Date.now()}`,
      timestamp: Date.now(),
      trigger,
      context,
      actionsTaken,
      outcome,
      reward,
      emotionalState: new VADVector(0.5, 0.4, 0.7)
    };
    this.episodic.push(episode);
    return episode;
  }

  addSemanticConcept(concept, definition, associations = []) {
    const entry = {
      id: `sem-${Date.now()}`,
      concept,
      definition,
      associations,
      strength: 1.0,
      lastAccessed: Date.now()
    };
    this.semantic.push(entry);
    return entry;
  }

  // Consolidate memory pipeline: Ephemeral -> ShortTerm -> LongTerm -> Wisdom
  consolidate() {
    let consolidatedCount = 0;
    const memoryList = Array.from(this.nodes.values());

    memoryList.forEach(node => {
      if (node.state === 'ephemeral' && node.accessCount >= 2) {
        node.state = 'shortTerm';
        consolidatedCount++;
      } else if (node.state === 'shortTerm' && node.accessCount >= 4) {
        node.state = 'longTerm';
        consolidatedCount++;
      } else if (node.state === 'longTerm' && node.accessCount >= 6) {
        node.state = 'core';
        consolidatedCount++;
      }
    });

    // Distill Wisdom from core memories
    const coreMemories = memoryList.filter(n => n.state === 'core');
    if (coreMemories.length >= 2) {
      const insight = `Distilled Wisdom: Integrated ${coreMemories.map(m => m.summary).join(' + ')}`;
      const wisdom = new WisdomNode(insight, coreMemories.map(m => m.id));
      this.wisdomNodes.push(wisdom);
      coreMemories.forEach(m => m.state = 'wisdom');
    }

    return { consolidatedCount, wisdomCount: this.wisdomNodes.length };
  }
}

if (typeof window !== 'undefined') {
  window.CognitiveMemory = {
    VADVector,
    CognitiveMemoryNode,
    WisdomNode,
    CognitiveMemoryStore
  };
}

if (typeof module !== 'undefined') {
  module.exports = {
    VADVector,
    CognitiveMemoryNode,
    WisdomNode,
    CognitiveMemoryStore
  };
}
