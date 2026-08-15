/**
 * OMNIBUS — Knowledge Graph & ERD Entity Extraction Module
 * Harvested & Adapted from ARCANE QUANTUM BRAIN (/api/knowledge/erd)
 * 
 * Extracts entities, canonical terms, and relationship edges,
 * and provides a 5th Canvas Visualizer for interactive Knowledge Graph rendering.
 */

class ERDEntity {
  constructor(name, type, canonical, relations = []) {
    this.name = name;
    this.type = type; // Biological, Quantum, Agent, Algorithm, Infrastructure, Concept
    this.canonical = canonical || name.toLowerCase();
    this.relations = relations;
  }
}

class KnowledgeERD {
  constructor() {
    this.entities = new Map();
    this.edges = [];
    this.time = 0;

    this.seedDefaultEntities();
  }

  seedDefaultEntities() {
    const defaultEntities = [
      { name: 'OMNIBUS Core', type: 'Infrastructure', canonical: 'omnibus', relations: ['supervisor', 'ml-expert', 'coder', 'memory'] },
      { name: 'Supervisor', type: 'Agent', canonical: 'supervisor', relations: ['researcher', 'coder', 'qa-agent'] },
      { name: 'ML Engineer', type: 'Agent', canonical: 'ml-expert', relations: ['kan', 'mamba', 'jepa'] },
      { name: 'Researcher', type: 'Agent', canonical: 'researcher', relations: ['erd', 'qpu'] },
      { name: 'Coder', type: 'Agent', canonical: 'coder', relations: ['qa-agent'] },
      { name: 'Reviewer', type: 'Agent', canonical: 'qa-agent', relations: [] },
      { name: 'KAN B-Splines', type: 'Algorithm', canonical: 'kan', relations: ['mamba'] },
      { name: 'Mamba SSM', type: 'Algorithm', canonical: 'mamba', relations: ['jepa'] },
      { name: 'JEPA World Model', type: 'Algorithm', canonical: 'jepa', relations: ['memory'] },
      { name: 'Deep Equilibrium', type: 'Algorithm', canonical: 'deq', relations: ['kan'] },
      { name: 'Cognitive Memory', type: 'Infrastructure', canonical: 'memory', relations: ['erd'] },
      { name: 'QPU ERD Engine', type: 'Infrastructure', canonical: 'qpu', relations: ['erd'] },
      { name: 'Knowledge ERD', type: 'Concept', canonical: 'erd', relations: [] }
    ];

    defaultEntities.forEach(e => this.addEntity(e.name, e.type, e.canonical, e.relations));
  }

  addEntity(name, type, canonical, relations = []) {
    const entity = new ERDEntity(name, type, canonical, relations);
    this.entities.set(canonical, entity);
    
    relations.forEach(target => {
      const tgtCanonical = target.toLowerCase();
      if (!this.edges.some(edge => edge.source === canonical && edge.target === tgtCanonical)) {
        this.edges.push({ source: canonical, target: tgtCanonical });
      }
    });

    return entity;
  }

  extractFromText(text) {
    const terms = text.match(/\b([A-Z][a-zA-Z0-9_\-]{2,})\b/g) || [];
    const extracted = [];

    terms.forEach(term => {
      let type = 'Concept';
      if (['KAN', 'Mamba', 'PPO', 'DQN', 'VAE', 'GAN', 'LSTM', 'GNN', 'HTN', 'DEQ', 'SNN', 'RoPE', 'JEPA'].includes(term)) {
        type = 'Algorithm';
      } else if (['Supervisor', 'Coder', 'Researcher', 'Reviewer', 'Agent', 'Orchestrator', 'Sidekick', 'Swarm'].includes(term)) {
        type = 'Agent';
      } else if (['Firebase', 'Database', 'Memory', 'ERD', 'Graph', 'QPU'].includes(term)) {
        type = 'Infrastructure';
      }

      const entity = this.addEntity(term, type, term.toLowerCase(), []);
      extracted.push(entity);
    });

    for (let i = 0; i < extracted.length - 1; i++) {
      const src = extracted[i].canonical;
      const tgt = extracted[i + 1].canonical;
      if (src !== tgt && !this.edges.some(e => e.source === src && e.target === tgt)) {
        this.edges.push({ source: src, target: tgt });
      }
    }

    return { entities: Array.from(this.entities.values()), edges: this.edges };
  }

  // Visualizer method to draw Knowledge Graph on HTML5 canvas with animation
  renderToCanvas(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (parent) {
      canvas.width = parent.getBoundingClientRect().width || 800;
      canvas.height = 300;
    }

    const ctx = canvas.getContext('2d');
    const { width, height } = canvas;

    this.time += 0.02;

    ctx.clearRect(0, 0, width, height);

    const nodesList = Array.from(this.entities.values());
    if (nodesList.length === 0) return;

    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.38;

    const positions = new Map();
    nodesList.forEach((node, i) => {
      const angle = (i / nodesList.length) * Math.PI * 2 + Math.sin(this.time * 0.5 + i) * 0.05;
      const x = centerX + Math.cos(angle) * (radius + Math.sin(this.time + i) * 10);
      const y = centerY + Math.sin(angle) * (radius + Math.cos(this.time + i) * 10);
      positions.set(node.canonical, { x, y, node });
    });

    // Draw connecting edges
    ctx.lineWidth = 1.5;
    this.edges.forEach(edge => {
      const p1 = positions.get(edge.source);
      const p2 = positions.get(edge.target);
      if (p1 && p2) {
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.35)';
        ctx.stroke();

        // Animated packet along edge
        const packetPos = (Math.sin(this.time * 2 + p1.x) + 1) / 2;
        const px = p1.x + (p2.x - p1.x) * packetPos;
        const py = p1.y + (p2.y - p1.y) * packetPos;

        ctx.beginPath();
        ctx.arc(px, py, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#00ff66';
        ctx.fill();
      }
    });

    // Draw nodes
    positions.forEach(({ x, y, node }) => {
      ctx.beginPath();
      ctx.arc(x, y, 14, 0, Math.PI * 2);
      ctx.fillStyle = node.type === 'Algorithm' ? '#7000ff' : (node.type === 'Agent' ? '#00f0ff' : (node.type === 'Infrastructure' ? '#ffb800' : '#00ff66'));
      ctx.shadowBlur = 12;
      ctx.shadowColor = ctx.fillStyle;
      ctx.fill();
      ctx.shadowBlur = 0;

      ctx.fillStyle = '#ffffff';
      ctx.font = '600 11px "Inter", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(node.name, x, y + 26);
    });
  }
}

if (typeof window !== 'undefined') {
  window.KnowledgeERD = KnowledgeERD;
}

if (typeof module !== 'undefined') {
  module.exports = { KnowledgeERD, ERDEntity };
}
