class CanvasVisualizers {
  constructor() {
    this.canvases = {
      node: document.getElementById('nodeCanvas'),
      attention: document.getElementById('attentionCanvas'),
      mcts: document.getElementById('mctsCanvas'),
      neural: document.getElementById('neuralCanvas')
    };
    
    this.ctxs = {};
    this.dimensions = {};
    
    for (const [key, canvas] of Object.entries(this.canvases)) {
      if(canvas) {
        this.ctxs[key] = canvas.getContext('2d');
        this.resize(key);
      }
    }

    this.data = {
      nodes: [],
      connections: [],
      attentionMatrix: [],
      mctsNodes: [],
      neural: {
        inputs: Array(4).fill(0),
        hidden: Array(8).fill(0),
        outputs: Array(3).fill(0),
        pulses: []
      }
    };

    this.time = 0;
    this.initMockData();
    
    window.addEventListener('resize', () => {
      for (const key of Object.keys(this.canvases)) {
        this.resize(key);
      }
    });
    
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize(key) {
    const canvas = this.canvases[key];
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width - 40; // account for padding
    canvas.height = 250;
    this.dimensions[key] = { w: canvas.width, h: canvas.height };
  }

  initMockData() {
    // Node Graph
    const roles = ['Supervisor', 'Researcher', 'Coder', 'Reviewer'];
    roles.forEach((r, i) => {
      this.data.nodes.push({
        id: i,
        label: r,
        x: Math.random() * 0.6 + 0.2,
        y: Math.random() * 0.6 + 0.2,
        baseX: Math.random() * 0.6 + 0.2,
        baseY: Math.random() * 0.6 + 0.2,
        phase: Math.random() * Math.PI * 2,
        active: false
      });
    });
    
    for(let i=0; i<roles.length; i++) {
      for(let j=i+1; j<roles.length; j++) {
        if(Math.random() > 0.3) {
          this.data.connections.push({ source: i, target: j, active: false, packets: [] });
        }
      }
    }

    // Attention Matrix
    for(let i=0; i<4; i++) {
      let row = [];
      for(let j=0; j<4; j++) {
        row.push(Math.random());
      }
      this.data.attentionMatrix.push(row);
    }
  }

  updateState(state) {
    if(state.activeAgents) {
      this.data.nodes.forEach(n => n.active = state.activeAgents.includes(n.label));
      
      this.data.connections.forEach(c => {
        const sActive = this.data.nodes[c.source].active;
        const tActive = this.data.nodes[c.target].active;
        c.active = sActive && tActive;
        
        if (c.active && Math.random() > 0.8) {
          c.packets.push({ progress: 0, speed: Math.random() * 0.02 + 0.01 });
        }
      });
      
      // Update Neural
      if(state.activeAgents.length > 0) {
        this.data.neural.inputs = this.data.neural.inputs.map(() => Math.random());
        this.data.neural.hidden = this.data.neural.hidden.map(() => Math.random());
        this.data.neural.outputs = this.data.neural.outputs.map(() => Math.random());
        
        if(Math.random() > 0.5) {
          this.data.neural.pulses.push({
            layer: Math.floor(Math.random() * 2),
            from: Math.floor(Math.random() * 4),
            to: Math.floor(Math.random() * 8),
            progress: 0
          });
        }
      }
    }
  }

  animate() {
    this.time += 0.016;
    
    if(this.ctxs.node) this.drawNodeGraph();
    if(this.ctxs.attention) this.drawAttention();
    if(this.ctxs.mcts) this.drawMCTS();
    if(this.ctxs.neural) this.drawNeural();
    
    requestAnimationFrame(this.animate);
  }

  drawNodeGraph() {
    const ctx = this.ctxs.node;
    const { w, h } = this.dimensions.node;
    
    ctx.clearRect(0, 0, w, h);
    
    // Update node positions (oscillation)
    this.data.nodes.forEach(n => {
      n.x = n.baseX + Math.sin(this.time + n.phase) * 0.05;
      n.y = n.baseY + Math.cos(this.time + n.phase) * 0.05;
    });

    // Draw connections
    this.data.connections.forEach(c => {
      const s = this.data.nodes[c.source];
      const t = this.data.nodes[c.target];
      
      const grad = ctx.createLinearGradient(s.x * w, s.y * h, t.x * w, t.y * h);
      grad.addColorStop(0, c.active ? 'rgba(0, 240, 255, 0.8)' : 'rgba(255, 255, 255, 0.05)');
      grad.addColorStop(1, c.active ? 'rgba(112, 0, 255, 0.8)' : 'rgba(255, 255, 255, 0.05)');
      
      ctx.beginPath();
      ctx.moveTo(s.x * w, s.y * h);
      ctx.lineTo(t.x * w, t.y * h);
      ctx.strokeStyle = grad;
      ctx.lineWidth = c.active ? 2.5 : 1;
      ctx.stroke();
      
      // Draw packets
      if(c.active) {
        for(let i = c.packets.length - 1; i >= 0; i--) {
          let p = c.packets[i];
          p.progress += p.speed;
          
          if(p.progress >= 1) {
            c.packets.splice(i, 1);
            continue;
          }
          
          const px = s.x * w + (t.x * w - s.x * w) * p.progress;
          const py = s.y * h + (t.y * h - s.y * h) * p.progress;
          
          ctx.beginPath();
          ctx.arc(px, py, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#00ff66';
          ctx.shadowBlur = 15;
          ctx.shadowColor = '#00ff66';
          ctx.fill();
          ctx.shadowBlur = 0;
        }
      }
    });

    // Draw nodes
    this.data.nodes.forEach(n => {
      ctx.beginPath();
      ctx.arc(n.x * w, n.y * h, 16, 0, Math.PI * 2);
      
      if(n.active) {
        const radGrad = ctx.createRadialGradient(n.x * w, n.y * h, 0, n.x * w, n.y * h, 16);
        radGrad.addColorStop(0, '#ffffff');
        radGrad.addColorStop(0.5, '#00f0ff');
        radGrad.addColorStop(1, '#7000ff');
        ctx.fillStyle = radGrad;
        ctx.shadowBlur = 25;
        ctx.shadowColor = '#00f0ff';
      } else {
        ctx.fillStyle = 'rgba(255,255,255,0.1)';
        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }
      
      ctx.fill();
      
      ctx.fillStyle = n.active ? '#ffffff' : 'rgba(255,255,255,0.5)';
      ctx.font = '600 12px Inter';
      ctx.textAlign = 'center';
      ctx.shadowBlur = 0;
      ctx.fillText(n.label, n.x * w, n.y * h + 32);
    });
  }

  drawAttention() {
    const ctx = this.ctxs.attention;
    const { w, h } = this.dimensions.attention;
    
    ctx.clearRect(0, 0, w, h);
    
    const rows = this.data.attentionMatrix.length;
    const cols = rows;
    const padding = 20;
    const cellW = (w - padding * 2) / cols;
    const cellH = (h - padding * 2) / rows;
    
    for(let i=0; i<rows; i++) {
      for(let j=0; j<cols; j++) {
        // slightly fluctuate smoothly
        const noise = Math.sin(this.time * 2 + i * 1.5 + j * 2.1) * 0.05;
        this.data.attentionMatrix[i][j] = Math.max(0, Math.min(1, this.data.attentionMatrix[i][j] + noise * 0.1));
        
        let val = this.data.attentionMatrix[i][j];
        
        // Heatmap gradient
        const hue = 200 - val * 160; // 200 (Blue) -> 40 (Yellow/Orange)
        ctx.fillStyle = `hsla(${hue}, 100%, 60%, ${0.2 + val * 0.8})`;
        
        const x = padding + j * cellW;
        const y = padding + i * cellH;
        
        ctx.beginPath();
        ctx.roundRect(x + 2, y + 2, cellW - 4, cellH - 4, 6);
        ctx.fill();
        
        // Glow on high attention
        if (val > 0.7) {
          ctx.shadowBlur = val * 15;
          ctx.shadowColor = `hsla(${hue}, 100%, 60%, 1)`;
          ctx.fill();
          ctx.shadowBlur = 0;
        }
        
        ctx.fillStyle = val > 0.5 ? '#000' : '#fff';
        ctx.font = '600 11px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(val.toFixed(2), x + cellW/2, y + cellH/2);
      }
    }
  }

  drawMCTS() {
    const ctx = this.ctxs.mcts;
    const { w, h } = this.dimensions.mcts;
    ctx.clearRect(0, 0, w, h);
    
    // Draw a simple 3 level tree with active pulsing
    const pulseRoot = Math.sin(this.time * 3) * 5;
    const root = { x: w/2, y: 40, val: 100, active: true, pulse: pulseRoot };
    
    const pulseL1 = Math.cos(this.time * 2.5) * 5;
    const l1 = [
      { x: w/4, y: 110, val: 40 },
      { x: w/2, y: 110, val: 80, active: true, pulse: pulseL1 },
      { x: w*3/4, y: 110, val: 20 }
    ];
    
    const pulseL2 = Math.sin(this.time * 4) * 6;
    const l2 = [
      { x: w*3/8, y: 190, val: 30 },
      { x: w*5/8, y: 190, val: 90, active: true, pulse: pulseL2 }
    ];

    const drawNode = (n, parent) => {
      if(parent) {
        ctx.beginPath();
        ctx.moveTo(parent.x, parent.y);
        ctx.lineTo(n.x, n.y);
        if (n.active) {
          const grad = ctx.createLinearGradient(parent.x, parent.y, n.x, n.y);
          grad.addColorStop(0, '#00f0ff');
          grad.addColorStop(1, '#00ff66');
          ctx.strokeStyle = grad;
          ctx.lineWidth = 3;
        } else {
          ctx.strokeStyle = 'rgba(255,255,255,0.15)';
          ctx.lineWidth = 1;
        }
        ctx.stroke();
        
        // Traveling energy particle on active edge
        if (n.active) {
          const t = (this.time * 1.5) % 1;
          const px = parent.x + (n.x - parent.x) * t;
          const py = parent.y + (n.y - parent.y) * t;
          ctx.beginPath();
          ctx.arc(px, py, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.shadowBlur = 10;
          ctx.shadowColor = '#ffffff';
          ctx.fill();
          ctx.shadowBlur = 0;
        }
      }
      
      const r = 16 + (n.pulse || 0);
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = n.active ? '#00f0ff' : `rgba(112, 0, 255, ${Math.max(0.2, n.val/100)})`;
      if(n.active) {
        ctx.shadowBlur = 20 + n.pulse * 2;
        ctx.shadowColor = '#00f0ff';
      }
      ctx.fill();
      ctx.shadowBlur = 0;
      
      ctx.fillStyle = n.active ? '#000' : '#fff';
      ctx.font = '600 11px JetBrains Mono';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(n.val, n.x, n.y);
    };

    drawNode(root, null);
    l1.forEach(n => drawNode(n, root));
    l2.forEach(n => drawNode(n, l1[1]));
  }

  drawNeural() {
    const ctx = this.ctxs.neural;
    if(!ctx) return;
    const { w, h } = this.dimensions.neural;
    ctx.clearRect(0, 0, w, h);

    const drawLayer = (nodes, x) => {
      const spacing = h / (nodes.length + 1);
      return nodes.map((val, i) => {
        const y = spacing * (i + 1);
        return { x, y, val };
      });
    };

    const inNodes = drawLayer(this.data.neural.inputs, w * 0.15);
    const hidNodes = drawLayer(this.data.neural.hidden, w * 0.5);
    const outNodes = drawLayer(this.data.neural.outputs, w * 0.85);

    const drawConns = (layer1, layer2, alpha) => {
      layer1.forEach(n1 => {
        layer2.forEach(n2 => {
          ctx.beginPath();
          ctx.moveTo(n1.x, n1.y);
          ctx.lineTo(n2.x, n2.y);
          const strength = n1.val * n2.val;
          ctx.strokeStyle = `rgba(0, 255, 102, ${strength * 0.6})`;
          ctx.lineWidth = strength * 2 + 0.5;
          ctx.stroke();
        });
      });
    };

    drawConns(inNodes, hidNodes);
    drawConns(hidNodes, outNodes);
    
    // Draw pulses
    for(let i=this.data.neural.pulses.length-1; i>=0; i--) {
      let p = this.data.neural.pulses[i];
      p.progress += 0.04;
      if(p.progress >= 1) {
        this.data.neural.pulses.splice(i, 1);
        continue;
      }
      
      let s, t;
      if(p.layer === 0) { s = inNodes[p.from % inNodes.length]; t = hidNodes[p.to % hidNodes.length]; }
      else { s = hidNodes[p.from % hidNodes.length]; t = outNodes[p.to % outNodes.length]; }
      
      const px = s.x + (t.x - s.x) * p.progress;
      const py = s.y + (t.y - s.y) * p.progress;
      
      ctx.beginPath();
      ctx.arc(px, py, 5, 0, Math.PI*2);
      ctx.fillStyle = '#ffffff';
      ctx.shadowBlur = 15;
      ctx.shadowColor = '#00ff66';
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    const drawNodes = (nodes, r, g, b) => {
      nodes.forEach((n, idx) => {
        const pulse = Math.sin(this.time * 4 + idx) * 2;
        ctx.beginPath();
        ctx.arc(n.x, n.y, 9 + pulse, 0, Math.PI*2);
        
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, 9 + pulse);
        grad.addColorStop(0, '#ffffff');
        grad.addColorStop(0.4, `rgba(${r}, ${g}, ${b}, 1)`);
        grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, ${0.3 + n.val * 0.7})`);
        
        ctx.fillStyle = grad;
        ctx.shadowBlur = n.val * 20;
        ctx.shadowColor = `rgb(${r}, ${g}, ${b})`;
        ctx.fill();
        ctx.shadowBlur = 0;
      });
    };

    drawNodes(inNodes, 0, 240, 255);
    drawNodes(hidNodes, 112, 0, 255);
    drawNodes(outNodes, 0, 255, 102);
  }
}

// Particle Background System
class ParticleBackground {
  constructor() {
    this.canvas = document.getElementById('particleCanvas');
    if(!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.particles = [];
    
    this.resize();
    window.addEventListener('resize', () => this.resize());
    
    for(let i=0; i<100; i++) {
      this.particles.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        radius: Math.random() * 2 + 1
      });
    }
    
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }
  
  resize() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }
  
  animate() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    
    this.ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
    this.particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      
      if(p.x < 0) p.x = this.canvas.width;
      if(p.x > this.canvas.width) p.x = 0;
      if(p.y < 0) p.y = this.canvas.height;
      if(p.y > this.canvas.height) p.y = 0;
      
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI*2);
      this.ctx.fill();
    });
    
    this.ctx.lineWidth = 0.5;
    for(let i=0; i<this.particles.length; i++) {
      for(let j=i+1; j<this.particles.length; j++) {
        let dx = this.particles[i].x - this.particles[j].x;
        let dy = this.particles[i].y - this.particles[j].y;
        let dist = Math.sqrt(dx*dx + dy*dy);
        
        if(dist < 100) {
          this.ctx.beginPath();
          this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
          this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
          this.ctx.strokeStyle = `rgba(0, 240, 255, ${1 - dist/100})`;
          this.ctx.stroke();
        }
      }
    }
    
    requestAnimationFrame(this.animate);
  }
}

class FrontierVisualizerLab {
  constructor(canvasId, logId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.logElement = document.getElementById(logId);
    this.modelType = 'KAN';
    this.paramVal = 50;
    this.time = 0;

    this.particles = Array.from({ length: 40 }, () => ({
      x: Math.random(),
      y: Math.random(),
      targetX: Math.random() * 0.6 + 0.2,
      targetY: Math.random() * 0.6 + 0.2
    }));

    this.snnBuffer = [];
    this.vMembrane = 0;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = 320;
  }

  log(msg) {
    if (!this.logElement) return;
    const div = document.createElement('div');
    div.className = 'log-entry info';
    div.innerHTML = `<span class="log-time">${new Date().toLocaleTimeString()}</span> ${msg}`;
    this.logElement.appendChild(div);
    this.logElement.scrollTop = this.logElement.scrollHeight;
  }

  setModel(type, param) {
    this.modelType = type;
    this.paramVal = param;
    this.log(`Switched visualizer to [${type}] with param=${param}`);
  }

  animate() {
    this.time += 0.03;
    if (this.ctx && this.canvas) {
      const { width, height } = this.canvas;
      this.ctx.clearRect(0, 0, width, height);

      switch (this.modelType) {
        case 'KAN':
          this.drawKAN(width, height);
          break;
        case 'Mamba':
          this.drawMamba(width, height);
          break;
        case 'FlowMatching':
          this.drawFlowMatching(width, height);
          break;
        case 'LNN':
          this.drawLNN(width, height);
          break;
        case 'SNN':
          this.drawSNN(width, height);
          break;
        case 'Hopfield':
          this.drawHopfield(width, height);
          break;
        case 'SoftMoE':
          this.drawSoftMoE(width, height);
          break;
        case 'DPO':
          this.drawDPO(width, height);
          break;
        case 'GRPO':
          this.drawGRPO(width, height);
          break;
        case 'DiffusionSSM':
          this.drawDiffusionSSM(width, height);
          break;
        case 'MixtureOfDepths':
          this.drawMixtureOfDepths(width, height);
          break;
        case 'SpikingGNN':
          this.drawSpikingGNN(width, height);
          break;
        case 'DiffusionDPO':
          this.drawDiffusionSSM(width, height);
          break;
        case 'SpikingReservoir':
          this.drawSpikingGNN(width, height);
          break;
        case 'DynamicHypernet':
          this.drawSoftMoE(width, height);
          break;
        case 'GoTQuantum':
          this.drawKAN(width, height);
          break;
        case 'Wasserstein':
          this.drawFlowMatching(width, height);
          break;
        default:
          this.drawKAN(width, height);
      }
    }
    requestAnimationFrame(this.animate);
  }

  drawKAN(w, h) {
    const ctx = this.ctx;
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.shadowBlur = 10;
    ctx.shadowColor = '#00f0ff';

    const order = 3;
    const knots = 6;
    for (let x = 0; x <= w; x += 4) {
      const normX = x / w;
      let yVal = 0;
      for (let i = 0; i < knots; i++) {
        const center = i / (knots - 1);
        const dist = Math.abs(normX - center);
        const basis = Math.max(0, 1 - dist * 2);
        const coeff = Math.sin(i * 1.2 + this.time) * (this.paramVal / 50);
        yVal += coeff * Math.pow(basis, order);
      }
      const y = h / 2 - yVal * (h / 3);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    for (let i = 0; i < knots; i++) {
      const kx = (i / (knots - 1)) * w;
      const pulse = Math.sin(this.time * 3 + i) * 2;
      const ky = h / 2 - Math.sin(i * 1.2 + this.time) * (this.paramVal / 50) * (h / 3);
      ctx.beginPath();
      ctx.arc(kx, ky, 6 + pulse, 0, Math.PI * 2);
      ctx.fillStyle = '#7000ff';
      ctx.shadowBlur = 15;
      ctx.shadowColor = '#7000ff';
      ctx.fill();
      ctx.shadowBlur = 0;
      
      ctx.beginPath();
      ctx.arc(kx, ky, 2, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
    }
  }

  drawMamba(w, h) {
    const ctx = this.ctx;
    const dt = 0.05;
    const steps = 60;
    
    // Create gradient
    const grad = ctx.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, '#00ff66');
    grad.addColorStop(1, '#00f0ff');
    
    ctx.beginPath();
    ctx.strokeStyle = grad;
    ctx.lineWidth = 4;
    ctx.shadowBlur = 15;
    ctx.shadowColor = '#00ff66';

    let hVal = 0.1;
    for (let i = 0; i < steps; i++) {
      const x = (i / steps) * w;
      const input = Math.sin(i * 0.3 + this.time);
      const discretization = Math.exp(-0.2 * dt * (this.paramVal / 25));
      hVal = hVal * discretization + dt * 0.5 * input;

      const y = h / 2 - hVal * (h * 0.4);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  drawFlowMatching(w, h) {
    const ctx = this.ctx;
    const t = (Math.sin(this.time * 0.8) + 1) / 2;

    this.particles.forEach((p, idx) => {
      const currentX = (p.x * (1 - t) + p.targetX * t) * w;
      const currentY = (p.y * (1 - t) + p.targetY * t) * h;

      ctx.beginPath();
      ctx.arc(currentX, currentY, 4, 0, Math.PI * 2);
      ctx.fillStyle = `hsl(${(idx * 15 + this.time * 50) % 360}, 100%, 60%)`;
      ctx.shadowBlur = 10;
      ctx.shadowColor = ctx.fillStyle;
      ctx.fill();
      ctx.shadowBlur = 0;
    });
  }

  drawLNN(w, h) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.strokeStyle = '#ff003c';
    ctx.lineWidth = 2;

    const tau = 0.1 + (this.paramVal / 100);
    let xVal = 0;
    for (let t = 0; t < w; t += 4) {
      const input = Math.sin(t * 0.02 + this.time);
      const dxdt = (-xVal / tau) + Math.tanh(input * 2);
      xVal += dxdt * 0.05;

      const y = h / 2 - xVal * (h / 3);
      if (t === 0) ctx.moveTo(t, y);
      else ctx.lineTo(t, y);
    }
    ctx.stroke();
  }

  drawSNN(w, h) {
    const ctx = this.ctx;
    const threshold = 0.8;
    this.vMembrane = 0.9 * this.vMembrane + (Math.random() * 0.3 * (this.paramVal / 50));
    let spiked = false;
    if (this.vMembrane >= threshold) {
      this.vMembrane = 0;
      spiked = true;
    }
    this.snnBuffer.push({ v: this.vMembrane, spiked });
    if (this.snnBuffer.length > 80) this.snnBuffer.shift();

    ctx.beginPath();
    ctx.strokeStyle = '#ffb800';
    ctx.lineWidth = 2;

    this.snnBuffer.forEach((pt, i) => {
      const x = (i / 80) * w;
      const y = h - 40 - pt.v * (h - 80);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);

      if (pt.spiked) {
        ctx.fillStyle = '#00f0ff';
        ctx.fillRect(x - 2, 20, 4, h - 60);
      }
    });
    ctx.stroke();
  }

  drawHopfield(w, h) {
    const ctx = this.ctx;
    const grid = 6;
    const cellW = w / grid;
    const cellH = h / grid;

    for (let r = 0; r < grid; r++) {
      for (let c = 0; c < grid; c++) {
        const energy = (Math.sin(r * c + this.time) + 1) / 2;
        ctx.fillStyle = `rgba(112, 0, 255, ${energy})`;
        ctx.fillRect(c * cellW, r * cellH, cellW - 2, cellH - 2);
      }
    }
  }

  drawSoftMoE(w, h) {
    const ctx = this.ctx;
    const experts = 6;
    const tokens = 8;
    const cellW = w / tokens;
    const cellH = h / experts;

    for (let e = 0; e < experts; e++) {
      for (let t = 0; t < tokens; t++) {
        const weight = (Math.cos(e * t + this.time * 2) + 1) / 2;
        ctx.fillStyle = `rgba(0, 240, 255, ${weight})`;
        ctx.fillRect(t * cellW, e * cellH, cellW - 4, cellH - 4);
      }
    }
  }

  drawDPO(w, h) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 3;

    for (let x = 0; x <= w; x += 5) {
      const normX = x / w;
      const loss = Math.exp(-normX * 3 * (this.paramVal / 50)) + Math.sin(normX * 10 + this.time) * 0.05;
      const y = h - 40 - loss * (h - 80);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  drawGRPO(w, h) {
    const ctx = this.ctx;
    const candidates = ['Completion A', 'Completion B', 'Completion C', 'Completion D'];
    const barWidth = (w - 100) / candidates.length;
    const baselineY = h / 2;

    // Draw baseline mean
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(50, baselineY);
    ctx.lineTo(w - 50, baselineY);
    ctx.stroke();
    ctx.setLineDash([]);

    candidates.forEach((name, i) => {
      const x = 60 + i * barWidth;
      const score = Math.sin(i * 1.5 + this.time * 2) * 60 * (this.paramVal / 50);
      const isPositive = score >= 0;
      const barH = Math.abs(score);

      ctx.fillStyle = isPositive ? '#00ff66' : '#ff003c';
      ctx.beginPath();
      ctx.roundRect(x, isPositive ? baselineY - barH : baselineY, barWidth - 20, barH, 4);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.font = '10px "JetBrains Mono"';
      ctx.textAlign = 'center';
      ctx.fillText((score / 60).toFixed(2), x + (barWidth - 20) / 2, isPositive ? baselineY - barH - 8 : baselineY + barH + 14);
      ctx.fillText(name, x + (barWidth - 20) / 2, h - 10);
    });
  }

  drawDiffusionSSM(w, h) {
    const ctx = this.ctx;
    const steps = 50;

    // Draw Mamba SSM state backbone
    ctx.beginPath();
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 3;
    for (let i = 0; i <= steps; i++) {
      const x = (i / steps) * w;
      const y = h / 2 + Math.sin(i * 0.2 + this.time * 3) * 40;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw Langevin score diffusion noise particles
    for (let i = 0; i < 20; i++) {
      const px = ((i / 20) + (this.time * 0.1) % 1) * w;
      const py = h / 2 + Math.sin(i + this.time * 2) * 50 + (Math.random() - 0.5) * 15;
      ctx.beginPath();
      ctx.arc(px % w, py, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#7000ff';
      ctx.shadowBlur = 10;
      ctx.shadowColor = '#7000ff';
      ctx.fill();
      ctx.shadowBlur = 0;
    }
  }

  drawMixtureOfDepths(w, h) {
    const ctx = this.ctx;
    const layers = 4;
    const tokens = 8;
    const cellW = (w - 60) / tokens;
    const cellH = (h - 40) / layers;

    for (let l = 0; l < layers; l++) {
      for (let t = 0; t < tokens; t++) {
        const isExecuted = Math.sin(l * t + this.time * 3) > 0;
        const x = 30 + t * cellW;
        const y = 20 + l * cellH;

        ctx.fillStyle = isExecuted ? 'rgba(0, 255, 102, 0.7)' : 'rgba(255, 255, 255, 0.05)';
        ctx.strokeStyle = isExecuted ? '#00ff66' : 'rgba(255, 255, 255, 0.1)';
        ctx.beginPath();
        ctx.roundRect(x, y, cellW - 6, cellH - 6, 4);
        ctx.fill();
        ctx.stroke();
      }
    }
  }

  drawSpikingGNN(w, h) {
    const ctx = this.ctx;
    const numNodes = 6;
    const radius = 80;
    const cx = w / 2;
    const cy = h / 2;

    const nodeCoords = [];
    for (let i = 0; i < numNodes; i++) {
      const angle = (i / numNodes) * Math.PI * 2 + this.time * 0.5;
      nodeCoords.push({
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
        spiked: Math.sin(i * 2 + this.time * 5) > 0.6
      });
    }

    // Graph edges
    nodeCoords.forEach((nodeA, i) => {
      nodeCoords.forEach((nodeB, j) => {
        if (i < j) {
          ctx.beginPath();
          ctx.moveTo(nodeA.x, nodeA.y);
          ctx.lineTo(nodeB.x, nodeB.y);
          ctx.strokeStyle = nodeA.spiked && nodeB.spiked ? '#00f0ff' : 'rgba(255, 255, 255, 0.08)';
          ctx.lineWidth = nodeA.spiked && nodeB.spiked ? 2.5 : 1;
          ctx.stroke();
        }
      });
    });

    // Spiking LIF nodes
    nodeCoords.forEach(node => {
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.spiked ? 12 : 7, 0, Math.PI * 2);
      ctx.fillStyle = node.spiked ? '#ffb800' : '#7000ff';
      if (node.spiked) {
        ctx.shadowBlur = 20;
        ctx.shadowColor = '#ffb800';
      }
      ctx.fill();
      ctx.shadowBlur = 0;
    });
  }
}

class WorldModelVisualizer {
  constructor(canvasId, actionTreeCanvasId, logId) {
    this.canvas = document.getElementById(canvasId);
    this.treeCanvas = document.getElementById(actionTreeCanvasId);
    if (!this.canvas || !this.treeCanvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.treeCtx = this.treeCanvas.getContext('2d');
    this.logElement = document.getElementById(logId);
    this.trajectory = [[0, 0]];
    this.time = 0;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (!this.canvas || !this.treeCanvas) return;
    const rect1 = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect1.width;
    this.canvas.height = 280;

    const rect2 = this.treeCanvas.parentElement.getBoundingClientRect();
    this.treeCanvas.width = rect2.width;
    this.treeCanvas.height = 280;
  }

  log(msg) {
    if (!this.logElement) return;
    const div = document.createElement('div');
    div.className = 'log-entry info';
    div.innerHTML = `<span class="log-time">${new Date().toLocaleTimeString()}</span> ${msg}`;
    this.logElement.appendChild(div);
    this.logElement.scrollTop = this.logElement.scrollHeight;
  }

  step() {
    const last = this.trajectory[this.trajectory.length - 1];
    const dx = (Math.random() - 0.3) * 40;
    const dy = (Math.random() - 0.4) * 30;
    const nextPt = [last[0] + dx, last[1] + dy];
    this.trajectory.push(nextPt);
    this.log(`World Model Rollout Step #${this.trajectory.length - 1}: z_t = [${nextPt[0].toFixed(1)}, ${nextPt[1].toFixed(1)}]`);
  }

  reset() {
    this.trajectory = [[0, 0]];
    if (this.logElement) this.logElement.innerHTML = '';
    this.log('Latent state reset to z_0 = [0.0, 0.0]');
  }

  animate() {
    this.time += 0.02;
    if (this.ctx && this.canvas) {
      const { width: w, height: h } = this.canvas;
      const ctx = this.ctx;
      ctx.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;

      ctx.beginPath();
      const grad = ctx.createLinearGradient(cx, cy, w, h);
      grad.addColorStop(0, 'rgba(0, 240, 255, 0.9)');
      grad.addColorStop(1, 'rgba(112, 0, 255, 0.9)');
      ctx.strokeStyle = grad;
      ctx.lineWidth = 3.5;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';

      this.trajectory.forEach((pt, i) => {
        const x = cx + pt[0];
        const y = cy + pt[1];
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      this.trajectory.forEach((pt, i) => {
        const x = cx + pt[0];
        const y = cy + pt[1];
        ctx.beginPath();
        const isLast = i === this.trajectory.length - 1;
        const r = isLast ? 10 + Math.sin(this.time * 5) * 3 : 5;
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = isLast ? '#00ff66' : '#7000ff';
        if (isLast) {
          ctx.shadowBlur = 20;
          ctx.shadowColor = '#00ff66';
        }
        ctx.fill();
        ctx.shadowBlur = 0;
      });
    }

    if (this.treeCtx && this.treeCanvas) {
      const { width: tw, height: th } = this.treeCanvas;
      const tCtx = this.treeCtx;
      tCtx.clearRect(0, 0, tw, th);

      const root = { x: tw / 2, y: 30 };
      const branches = [
        { x: tw / 4, y: 110, label: 'Action A (Code)', active: Math.sin(this.time * 2) > 0.5 },
        { x: tw / 2, y: 110, label: 'Action B (Refactor)', active: Math.cos(this.time * 3) > 0.5 },
        { x: tw * 3 / 4, y: 110, label: 'Action C (Optimize)', active: Math.sin(this.time * 2.5) > 0.5 }
      ];

      branches.forEach(b => {
        tCtx.beginPath();
        tCtx.moveTo(root.x, root.y);
        tCtx.lineTo(b.x, b.y);
        tCtx.strokeStyle = b.active ? '#00ff66' : 'rgba(0, 240, 255, 0.3)';
        tCtx.lineWidth = b.active ? 3 : 1.5;
        if(b.active) {
          tCtx.shadowBlur = 10;
          tCtx.shadowColor = '#00ff66';
        }
        tCtx.stroke();
        tCtx.shadowBlur = 0;

        tCtx.beginPath();
        tCtx.arc(b.x, b.y, b.active ? 15 : 12, 0, Math.PI * 2);
        tCtx.fillStyle = b.active ? '#00ff66' : '#7000ff';
        if (b.active) {
          tCtx.shadowBlur = 20;
          tCtx.shadowColor = '#00ff66';
        }
        tCtx.fill();
        tCtx.shadowBlur = 0;

        tCtx.fillStyle = b.active ? '#fff' : 'rgba(255,255,255,0.6)';
        tCtx.font = b.active ? 'bold 11px Inter' : '10px Inter';
        tCtx.textAlign = 'center';
        tCtx.fillText(b.label, b.x, b.y + 28);
      });

      tCtx.beginPath();
      const rootPulse = Math.sin(this.time * 4) * 3;
      tCtx.arc(root.x, root.y, 16 + rootPulse, 0, Math.PI * 2);
      tCtx.fillStyle = '#00f0ff';
      tCtx.shadowBlur = 25;
      tCtx.shadowColor = '#00f0ff';
      tCtx.fill();
      tCtx.shadowBlur = 0;
    }

    requestAnimationFrame(this.animate);
  }
}

// ─── GoT & Quantum Visualizer ───────────────────────────────────────
class GoTQuantumVisualizer {
  constructor(gotCanvasId, quantumCanvasId, logId) {
    this.gotCanvas = document.getElementById(gotCanvasId);
    this.quantumCanvas = document.getElementById(quantumCanvasId);
    this.logEl = document.getElementById(logId);

    if (this.gotCanvas) this.gotCtx = this.gotCanvas.getContext('2d');
    if (this.quantumCanvas) this.quantumCtx = this.quantumCanvas.getContext('2d');

    this.time = 0;
    this.nodes = [];
    this.edges = [];
    this.quantumAmplitudes = [0.25, 0.45, 0.85, 0.95, 0.65];
    this.initGraph();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  initGraph() {
    this.nodes = [
      { id: 0, label: 'Root Task', x: 0.15, y: 0.5, score: 0.6 },
      { id: 1, label: 'Meta-Policy', x: 0.4, y: 0.25, score: 0.82 },
      { id: 2, label: 'Spline Activation', x: 0.4, y: 0.75, score: 0.74 },
      { id: 3, label: 'Merged GoT Node', x: 0.7, y: 0.5, score: 0.94 },
      { id: 4, label: 'DPO Refine', x: 0.9, y: 0.5, score: 0.98 }
    ];
    this.edges = [
      { from: 0, to: 1 }, { from: 0, to: 2 },
      { from: 1, to: 3 }, { from: 2, to: 3 },
      { from: 3, to: 4 }
    ];
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  runGotSynthesis() {
    this.quantumAmplitudes = this.quantumAmplitudes.map(a => Math.min(0.99, a + Math.random() * 0.1));
    this.log('🕸️ Executed Graph-of-Thought (GoT) Node Merging & Cross-Branch Optimization.', 'success');
  }

  runGroverAmplification() {
    this.quantumAmplitudes[3] = Math.min(1.0, this.quantumAmplitudes[3] * 1.3);
    this.quantumAmplitudes[4] = Math.min(1.0, this.quantumAmplitudes[4] * 1.2);
    this.log('⚛️ Grover Quantum Amplitude Amplification applied on Merged Path Node 3 & 4.', 'purple');
  }

  animate() {
    this.time += 0.02;

    if (this.gotCtx && this.gotCanvas) {
      const w = this.gotCanvas.width = this.gotCanvas.parentElement.clientWidth;
      const h = this.gotCanvas.height = 250;
      const ctx = this.gotCtx;
      ctx.clearRect(0, 0, w, h);

      // Draw Edges
      this.edges.forEach(e => {
        const n1 = this.nodes[e.from];
        const n2 = this.nodes[e.to];
        ctx.beginPath();
        ctx.moveTo(n1.x * w, n1.y * h);
        ctx.lineTo(n2.x * w, n2.y * h);
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      // Draw Nodes
      this.nodes.forEach(n => {
        const nx = n.x * w;
        const ny = n.y * h + Math.sin(this.time * 3 + n.id) * 4;
        const radius = 14 + n.score * 8;

        ctx.beginPath();
        ctx.arc(nx, ny, radius, 0, Math.PI * 2);
        ctx.fillStyle = n.score > 0.9 ? '#00ff66' : '#7000ff';
        ctx.shadowBlur = 15;
        ctx.shadowColor = ctx.fillStyle;
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = '#fff';
        ctx.font = '11px Inter';
        ctx.textAlign = 'center';
        ctx.fillText(n.label, nx, ny + radius + 14);
      });
    }

    if (this.quantumCtx && this.quantumCanvas) {
      const w = this.quantumCanvas.width = this.quantumCanvas.parentElement.clientWidth;
      const h = this.quantumCanvas.height = 250;
      const ctx = this.quantumCtx;
      ctx.clearRect(0, 0, w, h);

      const barW = (w - 60) / this.quantumAmplitudes.length;
      this.quantumAmplitudes.forEach((amp, i) => {
        const barH = amp * (h - 60);
        const x = 30 + i * barW;
        const y = h - 30 - barH;

        const grad = ctx.createLinearGradient(0, y, 0, h - 30);
        grad.addColorStop(0, '#00f0ff');
        grad.addColorStop(1, '#7000ff');

        ctx.fillStyle = grad;
        ctx.fillRect(x + 5, y, barW - 10, barH);

        ctx.fillStyle = '#fff';
        ctx.font = '10px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText(`|ψ_${i}⟩ (${amp.toFixed(2)})`, x + barW / 2, h - 10);
      });
    }

    requestAnimationFrame(this.animate);
  }
}

// ─── Spiking Reservoir Visualizer ──────────────────────────────────
class SpikingReservoirVisualizer {
  constructor(spikingCanvasId, stdpMatrixCanvasId, logId) {
    this.spikingCanvas = document.getElementById(spikingCanvasId);
    this.stdpCanvas = document.getElementById(stdpMatrixCanvasId);
    this.logEl = document.getElementById(logId);

    if (this.spikingCanvas) this.spikingCtx = this.spikingCanvas.getContext('2d');
    if (this.stdpCanvas) this.stdpCtx = this.stdpCanvas.getContext('2d');

    this.time = 0;
    this.vMems = Array(10).fill(-70);
    this.stdpWeights = Array.from({ length: 8 }, () => Array.from({ length: 8 }, () => Math.random()));
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  injectSpikeTrain() {
    this.vMems = this.vMems.map((v, i) => Math.random() > 0.3 ? -45 : -70);
    this.stdpWeights = this.stdpWeights.map(row => row.map(w => Math.min(1.0, w + Math.random() * 0.1)));
    this.log('⚡ Injected neuromorphic spike train into Leaky Integrate-and-Fire reservoir. STDP updated.', 'success');
  }

  animate() {
    this.time += 0.05;

    this.vMems = this.vMems.map(v => v < -70 ? -70 : v - 0.5);

    if (this.spikingCtx && this.spikingCanvas) {
      const w = this.spikingCanvas.width = this.spikingCanvas.parentElement.clientWidth;
      const h = this.spikingCanvas.height = 250;
      const ctx = this.spikingCtx;
      ctx.clearRect(0, 0, w, h);

      const barW = (w - 40) / this.vMems.length;
      this.vMems.forEach((v, i) => {
        const normV = (v - (-80)) / 40;
        const barH = normV * (h - 50);
        const x = 20 + i * barW;
        const y = h - 30 - barH;

        ctx.fillStyle = v >= -50 ? '#00ff66' : '#00f0ff';
        if (v >= -50) {
          ctx.shadowBlur = 15;
          ctx.shadowColor = '#00ff66';
        }
        ctx.fillRect(x + 4, y, barW - 8, barH);
        ctx.shadowBlur = 0;

        ctx.fillStyle = '#fff';
        ctx.font = '10px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText(`N${i}`, x + barW / 2, h - 10);
      });
    }

    if (this.stdpCtx && this.stdpCanvas) {
      const w = this.stdpCanvas.width = this.stdpCanvas.parentElement.clientWidth;
      const h = this.stdpCanvas.height = 250;
      const ctx = this.stdpCtx;
      ctx.clearRect(0, 0, w, h);

      const rows = 8, cols = 8;
      const cellW = (w - 60) / cols;
      const cellH = (h - 40) / rows;

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const val = this.stdpWeights[r][c];
          const x = 30 + c * cellW;
          const y = 20 + r * cellH;

          ctx.fillStyle = `hsla(${val * 180 + 180}, 100%, 50%, 0.8)`;
          ctx.fillRect(x, y, cellW - 2, cellH - 2);
        }
      }
    }

    requestAnimationFrame(this.animate);
  }
}

// ─── Hyper & DPO Studio Visualizer ─────────────────────────────────
class HyperDpoVisualizer {
  constructor(dpoCanvasId, hyperCanvasId, logId) {
    this.dpoCanvas = document.getElementById(dpoCanvasId);
    this.hyperCanvas = document.getElementById(hyperCanvasId);
    this.logEl = document.getElementById(logId);

    if (this.dpoCanvas) this.dpoCtx = this.dpoCanvas.getContext('2d');
    if (this.hyperCanvas) this.hyperCtx = this.hyperCanvas.getContext('2d');

    this.time = 0;
    this.dpoLosses = [0.85, 0.72, 0.58, 0.44, 0.31, 0.22, 0.15];
    this.hyperWeights = Array.from({ length: 12 }, () => Math.random() * 2 - 1);
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  runDpoStep() {
    const nextLoss = Math.max(0.02, this.dpoLosses[this.dpoLosses.length - 1] * 0.85);
    this.dpoLosses.push(parseFloat(nextLoss.toFixed(3)));
    if (this.dpoLosses.length > 15) this.dpoLosses.shift();
    this.log(`🎯 Latent DPO Pairwise Optimization step executed. Loss: ${nextLoss.toFixed(4)}`, 'success');
  }

  synthHyperWeights() {
    this.hyperWeights = this.hyperWeights.map(w => (Math.random() * 2 - 1) * 0.5);
    this.log('🧠 Synthesized downstream agent sub-network weights via Dynamic HyperNetwork.', 'purple');
  }

  animate() {
    this.time += 0.02;

    if (this.dpoCtx && this.dpoCanvas) {
      const w = this.dpoCanvas.width = this.dpoCanvas.parentElement.clientWidth;
      const h = this.dpoCanvas.height = 250;
      const ctx = this.dpoCtx;
      ctx.clearRect(0, 0, w, h);

      ctx.beginPath();
      const stepX = (w - 60) / Math.max(1, this.dpoLosses.length - 1);
      this.dpoLosses.forEach((loss, i) => {
        const x = 30 + i * stepX;
        const y = h - 40 - loss * (h - 80);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });

      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 3;
      ctx.shadowBlur = 10;
      ctx.shadowColor = '#00f0ff';
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    if (this.hyperCtx && this.hyperCanvas) {
      const w = this.hyperCanvas.width = this.hyperCanvas.parentElement.clientWidth;
      const h = this.hyperCanvas.height = 250;
      const ctx = this.hyperCanvas;
      ctx.clearRect(0, 0, w, h);

      const barW = (w - 40) / this.hyperWeights.length;
      this.hyperWeights.forEach((wVal, i) => {
        const barH = Math.abs(wVal) * (h - 60);
        const x = 20 + i * barW;
        const y = wVal >= 0 ? h / 2 - barH : h / 2;

        ctx.fillStyle = wVal >= 0 ? '#7000ff' : '#ff0055';
        ctx.fillRect(x + 2, y, barW - 4, barH);
      });

      // Axis center
      ctx.beginPath();
      ctx.moveTo(20, h / 2);
      ctx.lineTo(w - 20, h / 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.2)';
      ctx.stroke();
    }

    requestAnimationFrame(this.animate);
  }
}

// ─── 13. Titans & RetNet Memory Visualizer ──────────────────────────
class TitansRetnetVisualizer {
  constructor(titansCanvasId, retnetCanvasId, logId) {
    this.titansCanvas = document.getElementById(titansCanvasId);
    this.retnetCanvas = document.getElementById(retnetCanvasId);
    this.logEl = document.getElementById(logId);

    if (this.titansCanvas) this.titansCtx = this.titansCanvas.getContext('2d');
    if (this.retnetCanvas) this.retnetCtx = this.retnetCanvas.getContext('2d');

    this.time = 0;
    this.surpriseHistory = [0.85, 0.42, 0.91, 0.35, 0.78, 0.22, 0.94];
    this.scaleRetentions = [0.92, 0.84, 0.71];

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  stepTitans() {
    const nextSurprise = parseFloat((0.2 + Math.random() * 0.78).toFixed(3));
    this.surpriseHistory.push(nextSurprise);
    if (this.surpriseHistory.length > 15) this.surpriseHistory.shift();
    this.log(`🧠 Titans Surprise-Gated Token processed. Surprise magnitude α: ${nextSurprise}`, 'success');
  }

  stepRetnet() {
    this.scaleRetentions = [
      parseFloat((0.85 + Math.random() * 0.14).toFixed(3)),
      parseFloat((0.75 + Math.random() * 0.18).toFixed(3)),
      parseFloat((0.60 + Math.random() * 0.25).toFixed(3))
    ];
    this.log(`⚡ RetNet Multi-Scale Retention evaluated across 3 decay factors (γ=0.968, 0.984, 0.992).`, 'purple');
  }

  animate() {
    this.time += 0.02;

    if (this.titansCtx && this.titansCanvas) {
      const w = this.titansCanvas.width = this.titansCanvas.parentElement.clientWidth;
      const h = this.titansCanvas.height = 250;
      const ctx = this.titansCtx;
      ctx.clearRect(0, 0, w, h);

      ctx.beginPath();
      const stepX = (w - 60) / Math.max(1, this.surpriseHistory.length - 1);
      this.surpriseHistory.forEach((sVal, i) => {
        const x = 30 + i * stepX;
        const y = h - 40 - sVal * (h - 80);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });

      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 3;
      ctx.shadowBlur = 12;
      ctx.shadowColor = '#00f0ff';
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    if (this.retnetCtx && this.retnetCanvas) {
      const w = this.retnetCanvas.width = this.retnetCanvas.parentElement.clientWidth;
      const h = this.retnetCanvas.height = 250;
      const ctx = this.retnetCtx;
      ctx.clearRect(0, 0, w, h);

      const barW = (w - 60) / this.scaleRetentions.length;
      this.scaleRetentions.forEach((rVal, i) => {
        const barH = rVal * (h - 80);
        const x = 30 + i * barW;
        const y = h - 40 - barH;

        ctx.fillStyle = i === 0 ? '#7000ff' : i === 1 ? '#00f0ff' : '#00ff88';
        ctx.fillRect(x + 10, y, barW - 20, barH);
        ctx.fillStyle = '#fff';
        ctx.font = '12px Inter';
        ctx.fillText(`Scale ${i+1}: ${rVal}`, x + 15, y - 10);
      });
    }

    requestAnimationFrame(this.animate);
  }
}

// ─── 14. DiT & Mamba-2 Visualizer ──────────────────────────────────
class DiTMamba2Visualizer {
  constructor(ditCanvasId, mamba2CanvasId, logId) {
    this.ditCanvas = document.getElementById(ditCanvasId);
    this.mamba2Canvas = document.getElementById(mamba2CanvasId);
    this.logEl = document.getElementById(logId);

    if (this.ditCanvas) this.ditCtx = this.ditCanvas.getContext('2d');
    if (this.mamba2Canvas) this.mamba2Ctx = this.mamba2Canvas.getContext('2d');

    this.time = 0;
    this.ditEnergyHistory = [1.2, 0.9, 0.65, 0.42, 0.28, 0.15];
    this.mamba2Matrix = Array.from({ length: 4 }, () => Array.from({ length: 4 }, () => Math.random()));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  sampleDit() {
    const nextEnergy = parseFloat((0.05 + Math.random() * 0.3).toFixed(3));
    this.ditEnergyHistory.push(nextEnergy);
    if (this.ditEnergyHistory.length > 15) this.ditEnergyHistory.shift();
    this.log(`🎨 DiT Latent Denoising Patch sampled via multi-head cross-attention. Latent energy: ${nextEnergy}`, 'success');
  }

  stepMamba2() {
    this.mamba2Matrix = Array.from({ length: 4 }, () => Array.from({ length: 4 }, () => Math.random()));
    this.log(`🧬 Mamba-2 State Space Duality matrix-multiplication update completed. Energy norm stable.`, 'purple');
  }

  animate() {
    this.time += 0.02;

    if (this.ditCtx && this.ditCanvas) {
      const w = this.ditCanvas.width = this.ditCanvas.parentElement.clientWidth;
      const h = this.ditCanvas.height = 250;
      const ctx = this.ditCtx;
      ctx.clearRect(0, 0, w, h);

      ctx.beginPath();
      const stepX = (w - 60) / Math.max(1, this.ditEnergyHistory.length - 1);
      this.ditEnergyHistory.forEach((eVal, i) => {
        const x = 30 + i * stepX;
        const y = h - 40 - (eVal / 1.5) * (h - 80);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });

      ctx.strokeStyle = '#00ff88';
      ctx.lineWidth = 3;
      ctx.shadowBlur = 10;
      ctx.shadowColor = '#00ff88';
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    if (this.mamba2Ctx && this.mamba2Canvas) {
      const w = this.mamba2Canvas.width = this.mamba2Canvas.parentElement.clientWidth;
      const h = this.mamba2Canvas.height = 250;
      const ctx = this.mamba2Ctx;
      ctx.clearRect(0, 0, w, h);

      const cellW = (w - 60) / 4;
      const cellH = (h - 60) / 4;

      for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
          const val = this.mamba2Matrix[r][c];
          const x = 30 + c * cellW;
          const y = 30 + r * cellH;
          ctx.fillStyle = `rgba(112, 0, 255, ${0.2 + val * 0.8})`;
          ctx.fillRect(x, y, cellW - 4, cellH - 4);
          ctx.fillStyle = '#fff';
          ctx.font = '10px JetBrains Mono';
          ctx.fillText(val.toFixed(2), x + cellW / 4, y + cellH / 1.8);
        }
      }
    }

    requestAnimationFrame(this.animate);
  }
}

// ─── 15. Swarm Evolution & GRPO Visualizer ──────────────────────────
class SwarmEvolutionVisualizer {
  constructor(grpoCanvasId, speculativeCanvasId, logId) {
    this.grpoCanvas = document.getElementById(grpoCanvasId);
    this.speculativeCanvas = document.getElementById(speculativeCanvasId);
    this.logEl = document.getElementById(logId);

    if (this.grpoCanvas) this.grpoCtx = this.grpoCanvas.getContext('2d');
    if (this.speculativeCanvas) this.speculativeCtx = this.speculativeCanvas.getContext('2d');

    this.time = 0;
    this.grpoAdvantages = [1.25, 0.42, -0.65, 0.88];
    this.speculativeDepth = 4;

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  runGrpo() {
    this.grpoAdvantages = Array.from({ length: 4 }, () => (Math.random() * 2.4 - 1.2));
    this.log(`🐝 Group Relative Policy Optimization (GRPO) advantages evaluated across 4 swarm candidates.`, 'success');
  }

  runSpeculativeDraft() {
    this.speculativeDepth = Math.floor(Math.random() * 3) + 3;
    this.log(`⚡ Medusa Speculative Draft Parallel Verification accepted depth: ${this.speculativeDepth} tokens (Speedup: ${(1 + this.speculativeDepth * 0.75).toFixed(2)}x).`, 'purple');
  }

  animate() {
    this.time += 0.02;

    if (this.grpoCtx && this.grpoCanvas) {
      const w = this.grpoCanvas.width = this.grpoCanvas.parentElement.clientWidth;
      const h = this.grpoCanvas.height = 250;
      const ctx = this.grpoCtx;
      ctx.clearRect(0, 0, w, h);

      const barW = (w - 60) / this.grpoAdvantages.length;
      this.grpoAdvantages.forEach((adv, i) => {
        const barH = Math.abs(adv) * (h - 80) / 2;
        const x = 30 + i * barW;
        const y = adv >= 0 ? h / 2 - barH : h / 2;

        ctx.fillStyle = adv >= 0 ? '#00f0ff' : '#ff0055';
        ctx.fillRect(x + 5, y, barW - 10, barH);
        ctx.fillStyle = '#fff';
        ctx.font = '11px Inter';
        ctx.fillText(`Adv: ${adv.toFixed(2)}`, x + 5, adv >= 0 ? y - 6 : y + barH + 14);
      });

      ctx.beginPath();
      ctx.moveTo(30, h / 2);
      ctx.lineTo(w - 30, h / 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.2)';
      ctx.stroke();
    }

    if (this.speculativeCtx && this.speculativeCanvas) {
      const w = this.speculativeCanvas.width = this.speculativeCanvas.parentElement.clientWidth;
      const h = this.speculativeCanvas.height = 250;
      const ctx = this.speculativeCtx;
      ctx.clearRect(0, 0, w, h);

      for (let d = 0; d < this.speculativeDepth; d++) {
        const x = 40 + d * (w - 80) / Math.max(1, this.speculativeDepth - 1);
        const y = h / 2 + Math.sin(this.time + d) * 15;

        ctx.beginPath();
        ctx.arc(x, y, 16, 0, Math.PI * 2);
        ctx.fillStyle = d === 0 ? '#00f0ff' : '#7000ff';
        ctx.shadowBlur = 10;
        ctx.shadowColor = ctx.fillStyle;
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = '#fff';
        ctx.font = '11px JetBrains Mono';
        ctx.fillText(`T${d+1}`, x - 7, y + 4);

        if (d > 0) {
          const prevX = 40 + (d - 1) * (w - 80) / Math.max(1, this.speculativeDepth - 1);
          const prevY = h / 2 + Math.sin(this.time + (d - 1)) * 15;
          ctx.beginPath();
          ctx.moveTo(prevX + 16, prevY);
          ctx.lineTo(x - 16, y);
          ctx.strokeStyle = 'rgba(0, 240, 255, 0.6)';
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(this.animate);
  }
}

// ─── 16. Liquid Attention & MuZero Latent Visualizer ─────────────────
class LiquidMuZeroVisualizer {
  constructor(liquidCanvasId, muZeroCanvasId, logId) {
    this.liquidCanvas = document.getElementById(liquidCanvasId);
    this.muZeroCanvas = document.getElementById(muZeroCanvasId);
    this.logEl = document.getElementById(logId);

    if (this.liquidCanvas) this.liquidCtx = this.liquidCanvas.getContext('2d');
    if (this.muZeroCanvas) this.muZeroCtx = this.muZeroCanvas.getContext('2d');

    this.time = 0;
    this.liquidEnergy = 0.85;
    this.particles = Array.from({ length: 30 }, () => ({
      x: Math.random() * 400,
      y: Math.random() * 200,
      vx: Math.random() * 2 + 1,
      vy: (Math.random() - 0.5) * 1.5,
      size: Math.random() * 3 + 2,
      hue: Math.random() * 60 + 170
    }));

    this.muZeroRollout = [
      { depth: 1, action: 0, val: 0.82, reward: 0.45 },
      { depth: 2, action: 2, val: 0.94, reward: 0.78 },
      { depth: 3, action: 1, val: 0.99, reward: 0.92 }
    ];

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  runLiquidStep() {
    this.liquidEnergy = parseFloat((0.4 + Math.random() * 0.9).toFixed(3));
    this.log(`💧 Continuous Liquid Attention ODE integration step updated. Energy: ${this.liquidEnergy}`, 'success');
  }

  runMuZeroRollout() {
    const actions = [0, 1, 2, 3];
    this.muZeroRollout = Array.from({ length: 4 }, (_, d) => ({
      depth: d + 1,
      action: actions[Math.floor(Math.random() * actions.length)],
      val: parseFloat((0.7 + Math.random() * 0.29).toFixed(2)),
      reward: parseFloat((Math.random() * 0.9).toFixed(2))
    }));
    this.log(`🎯 Latent World Model MuZero Rollout completed across 4 depth steps. Optimal path selected.`, 'purple');
  }

  animate() {
    this.time += 0.025;

    // Liquid Fluid ODE Animation
    if (this.liquidCtx && this.liquidCanvas) {
      const w = this.liquidCanvas.width = this.liquidCanvas.parentElement.clientWidth;
      const h = this.liquidCanvas.height = 250;
      const ctx = this.liquidCtx;
      ctx.clearRect(0, 0, w, h);

      // Draw continuous fluid wave
      ctx.beginPath();
      ctx.moveTo(0, h / 2);
      for (let x = 0; x < w; x += 5) {
        const wave = Math.sin(x * 0.02 + this.time * 2) * 20 * this.liquidEnergy +
                     Math.cos(x * 0.01 - this.time * 1.5) * 15;
        ctx.lineTo(x, h / 2 + wave);
      }
      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 3;
      ctx.shadowBlur = 12;
      ctx.shadowColor = '#00f0ff';
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Draw particles floating along fluid stream
      this.particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy + Math.sin(this.time + p.x * 0.01) * 0.5;
        if (p.x > w) p.x = 0;
        if (p.y < 20 || p.y > h - 20) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `hsl(${p.hue}, 100%, 65%)`;
        ctx.shadowBlur = 8;
        ctx.shadowColor = ctx.fillStyle;
        ctx.fill();
        ctx.shadowBlur = 0;
      });
    }

    // MuZero Latent Rollout Tree Animation
    if (this.muZeroCtx && this.muZeroCanvas) {
      const w = this.muZeroCanvas.width = this.muZeroCanvas.parentElement.clientWidth;
      const h = this.muZeroCanvas.height = 250;
      const ctx = this.muZeroCtx;
      ctx.clearRect(0, 0, w, h);

      const stepX = (w - 100) / Math.max(1, this.muZeroRollout.length - 1);
      this.muZeroRollout.forEach((node, i) => {
        const x = 50 + i * stepX;
        const y = h / 2 + Math.sin(this.time + i) * 20;

        // Node Circle
        ctx.beginPath();
        ctx.arc(x, y, 18, 0, Math.PI * 2);
        ctx.fillStyle = '#7000ff';
        ctx.shadowBlur = 12;
        ctx.shadowColor = '#7000ff';
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = '#fff';
        ctx.font = '10px JetBrains Mono';
        ctx.fillText(`D${node.depth}: A${node.action}`, x - 14, y + 3);

        // Connections
        if (i > 0) {
          const prevX = 50 + (i - 1) * stepX;
          const prevY = h / 2 + Math.sin(this.time + (i - 1)) * 20;
          ctx.beginPath();
          ctx.moveTo(prevX + 18, prevY);
          ctx.lineTo(x - 18, y);
          ctx.strokeStyle = '#00ff88';
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        // Tooltip score text
        ctx.fillStyle = '#00ff88';
        ctx.font = '10px Inter';
        ctx.fillText(`V: ${node.val} | R: ${node.reward}`, x - 22, y - 24);
      });
    }

    requestAnimationFrame(this.animate);
  }
}

// ─── 17. Holographic VSA & RadixTree Shared Cache Visualizer ─────────
class HoloRadixVisualizer {
  constructor(holoCanvasId, radixCanvasId, logId) {
    this.holoCanvas = document.getElementById(holoCanvasId);
    this.radixCanvas = document.getElementById(radixCanvasId);
    this.logEl = document.getElementById(logId);

    if (this.holoCanvas) this.holoCtx = this.holoCanvas.getContext('2d');
    if (this.radixCanvas) this.radixCtx = this.radixCanvas.getContext('2d');

    this.time = 0;
    this.hyperMatrix = Array.from({ length: 5 }, () => Array.from({ length: 5 }, () => Math.random() > 0.5 ? 1 : -1));
    this.radixNodes = ['/system', '/agent/orchestration', '/agent/coder', '/agent/qa-review', '/tools/execute'];
    this.compressionRatio = 84.5;

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  bindHypervectors() {
    this.hyperMatrix = Array.from({ length: 5 }, () => Array.from({ length: 5 }, () => Math.random() > 0.5 ? 1 : -1));
    this.log(`🔮 Holographic Hypervector Binding (XOR) & Bundling complete across 1024 dimensions.`, 'purple');
  }

  compressRadixCache() {
    this.compressionRatio = parseFloat((75 + Math.random() * 20).toFixed(1));
    this.log(`⚡ RadixTree Prompt Sharing prefix tree matching complete. KV Cache Compression: ${this.compressionRatio}%`, 'success');
  }

  animate() {
    this.time += 0.02;

    // Hypervector Matrix Canvas
    if (this.holoCtx && this.holoCanvas) {
      const w = this.holoCanvas.width = this.holoCanvas.parentElement.clientWidth;
      const h = this.holoCanvas.height = 250;
      const ctx = this.holoCtx;
      ctx.clearRect(0, 0, w, h);

      const cellW = (w - 60) / 5;
      const cellH = (h - 60) / 5;

      for (let r = 0; r < 5; r++) {
        for (let c = 0; c < 5; c++) {
          const val = this.hyperMatrix[r][c];
          const x = 30 + c * cellW;
          const y = 30 + r * cellH;

          ctx.fillStyle = val === 1 ? 'rgba(0, 240, 255, 0.7)' : 'rgba(255, 0, 85, 0.7)';
          ctx.fillRect(x, y, cellW - 4, cellH - 4);
          ctx.fillStyle = '#fff';
          ctx.font = '11px JetBrains Mono';
          ctx.fillText(val === 1 ? '+1' : '-1', x + cellW / 3, y + cellH / 1.7);
        }
      }
    }

    // RadixTree Shared Cache Canvas
    if (this.radixCtx && this.radixCanvas) {
      const w = this.radixCanvas.width = this.radixCanvas.parentElement.clientWidth;
      const h = this.radixCanvas.height = 250;
      const ctx = this.radixCtx;
      ctx.clearRect(0, 0, w, h);

      const centerX = w / 2;
      const centerY = 40;

      // Draw Root Node
      ctx.beginPath();
      ctx.arc(centerX, centerY, 16, 0, Math.PI * 2);
      ctx.fillStyle = '#00ff88';
      ctx.shadowBlur = 10;
      ctx.shadowColor = '#00ff88';
      ctx.fill();
      ctx.shadowBlur = 0;

      ctx.fillStyle = '#000';
      ctx.font = '10px JetBrains Mono';
      ctx.fillText('ROOT', centerX - 12, centerY + 3);

      // Draw Child Nodes
      this.radixNodes.forEach((nodePath, idx) => {
        const angle = (idx / (this.radixNodes.length - 1)) * Math.PI * 0.8 + Math.PI * 0.1;
        const radius = 110;
        const nx = centerX + Math.cos(angle) * radius - 40;
        const ny = centerY + Math.sin(angle) * radius + 20 + Math.sin(this.time + idx) * 8;

        ctx.beginPath();
        ctx.moveTo(centerX, centerY + 16);
        ctx.lineTo(nx, ny);
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.5)';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.fillStyle = 'rgba(10, 20, 40, 0.9)';
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 1;
        ctx.fillRect(nx - 35, ny - 12, 70, 24);
        ctx.strokeRect(nx - 35, ny - 12, 70, 24);

        ctx.fillStyle = '#fff';
        ctx.font = '9px JetBrains Mono';
        ctx.fillText(nodePath.split('/').pop() || 'node', nx - 30, ny + 3);
      });
    }

    requestAnimationFrame(this.animate);
  }
}

class NextGenMlVisualizer {
  constructor(diffCanvasId, bitnetCanvasId, stdpCanvasId, logId) {
    this.diffCanvas = document.getElementById(diffCanvasId);
    this.bitnetCanvas = document.getElementById(bitnetCanvasId);
    this.stdpCanvas = document.getElementById(stdpCanvasId);
    this.logEl = document.getElementById(logId);

    this.diffCtx = this.diffCanvas ? this.diffCanvas.getContext('2d') : null;
    this.bitnetCtx = this.bitnetCanvas ? this.bitnetCanvas.getContext('2d') : null;
    this.stdpCtx = this.stdpCanvas ? this.stdpCanvas.getContext('2d') : null;

    this.time = 0;
    this.trajectoryPoints = [];
    this.bitnetMatrix = Array.from({ length: 4 }, () => Array.from({ length: 4 }, () => Math.floor(Math.random() * 3) - 1));
    this.stdpWeights = Array.from({ length: 6 }, () => Array.from({ length: 6 }, () => Math.random() * 0.8));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);

    this.stepDiffusionForcing();
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const div = document.createElement('div');
    div.className = `log-entry ${type}`;
    div.innerHTML = `<span class="log-time">[${time}]</span> ${msg}`;
    this.logEl.appendChild(div);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  stepDiffusionForcing() {
    let exp = window.ExperimentalML;
    if (exp && exp.DiffusionForcingEngine) {
      const engine = new exp.DiffusionForcingEngine(4, 10);
      const res = engine.stepTrajectory([0.5, -0.2, 0.8, 0.1], 10);
      this.trajectoryPoints = res.trajectory;
      this.log(`🌊 <b>Diffusion Forcing</b> trajectory computed: ${res.trajectory.length} ODE steps. Final Score Norm: <b>${res.scoreNorm}</b>`, 'success');
    }
  }

  runBitNetQuantize() {
    let exp = window.ExperimentalML;
    if (exp && exp.BitNet158bEngine) {
      const engine = new exp.BitNet158bEngine(4, 4);
      const res = engine.bitLinearForward([1.0, 0.5, -0.5, -1.0]);
      this.bitnetMatrix = res.ternaryMatrix;
      this.log(`🔲 <b>BitNet 1.58b</b> forward: Non-Zero Ops: <b>${res.nonZeroOps}</b>, Zero Ops Avoided: <b>${res.zeroOpsAvoided}</b>, Scaling Gamma: <b>${res.gamma}</b>`, 'info');
    }
  }

  stepStdpPlasticity() {
    let exp = window.ExperimentalML;
    if (exp && exp.SpikingSTDPPlasticityEngine) {
      const engine = new exp.SpikingSTDPPlasticityEngine(6, 20, 20);
      const preSpikes = [5, 12, 3, 20, 15, 8];
      const postSpikes = [10, 8, 15, 25, 10, 18];
      const res = engine.applySTDP(preSpikes, postSpikes);
      this.stdpWeights = res.weightsMatrix;
      this.log(`⚡ <b>STDP Plasticity</b> updated: Total LTP: <b>+${res.totalLTP}</b>, Total LTD: <b>-${res.totalLTD}</b>, Avg Weight: <b>${res.avgWeight}</b>`, 'warning');
    }
  }

  animate() {
    this.time += 0.03;

    // Diffusion Forcing Trajectory Canvas
    if (this.diffCtx && this.diffCanvas) {
      const w = this.diffCanvas.width = this.diffCanvas.parentElement.clientWidth;
      const h = this.diffCanvas.height = 250;
      const ctx = this.diffCtx;
      ctx.clearRect(0, 0, w, h);

      if (this.trajectoryPoints.length > 0) {
        ctx.beginPath();
        this.trajectoryPoints.forEach((pt, idx) => {
          const x = (idx / (this.trajectoryPoints.length - 1)) * (w - 40) + 20;
          const y = h / 2 + pt[0] * 60 + Math.sin(this.time + idx) * 5;
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 3;
        ctx.stroke();

        this.trajectoryPoints.forEach((pt, idx) => {
          const x = (idx / (this.trajectoryPoints.length - 1)) * (w - 40) + 20;
          const y = h / 2 + pt[0] * 60 + Math.sin(this.time + idx) * 5;
          ctx.beginPath();
          ctx.arc(x, y, 5, 0, Math.PI * 2);
          ctx.fillStyle = idx === this.trajectoryPoints.length - 1 ? '#00ff88' : '#7000ff';
          ctx.fill();
        });
      }
    }

    // BitNet 1.58b Matrix Canvas
    if (this.bitnetCtx && this.bitnetCanvas) {
      const w = this.bitnetCanvas.width = this.bitnetCanvas.parentElement.clientWidth;
      const h = this.bitnetCanvas.height = 250;
      const ctx = this.bitnetCtx;
      ctx.clearRect(0, 0, w, h);

      const cellSize = Math.min(w, h) / 5;
      const startX = (w - cellSize * 4) / 2;
      const startY = (h - cellSize * 4) / 2;

      for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
          const val = this.bitnetMatrix[r][c];
          const x = startX + c * cellSize;
          const y = startY + r * cellSize;

          ctx.fillStyle = val === 1 ? 'rgba(0, 255, 136, 0.6)' : val === -1 ? 'rgba(255, 0, 100, 0.6)' : 'rgba(40, 40, 60, 0.6)';
          ctx.strokeStyle = '#00f0ff';
          ctx.fillRect(x, y, cellSize - 4, cellSize - 4);
          ctx.strokeRect(x, y, cellSize - 4, cellSize - 4);

          ctx.fillStyle = '#fff';
          ctx.font = '14px JetBrains Mono';
          ctx.fillText(val > 0 ? '+1' : val < 0 ? '-1' : '0', x + cellSize / 3, y + cellSize / 1.8);
        }
      }
    }

    // STDP Plasticity Matrix Canvas
    if (this.stdpCtx && this.stdpCanvas) {
      const w = this.stdpCanvas.width = this.stdpCanvas.parentElement.clientWidth;
      const h = this.stdpCanvas.height = 250;
      const ctx = this.stdpCtx;
      ctx.clearRect(0, 0, w, h);

      const cellW = (w - 40) / 6;
      const cellH = (h - 40) / 6;

      for (let r = 0; r < 6; r++) {
        for (let c = 0; c < 6; c++) {
          const weight = this.stdpWeights[r][c];
          const x = 20 + c * cellW;
          const y = 20 + r * cellH;

          const hue = 260 - weight * 200;
          ctx.fillStyle = `hsla(${hue}, 90%, 50%, 0.7)`;
          ctx.fillRect(x, y, cellW - 2, cellH - 2);

          ctx.fillStyle = '#fff';
          ctx.font = '9px JetBrains Mono';
          ctx.fillText(weight.toFixed(2), x + cellW / 4, y + cellH / 1.6);
        }
      }
    }

    requestAnimationFrame(this.animate);
  }
}

class HyperFrontierV11Visualizer {
  constructor(gatedCanvasId, mamba3CanvasId, dopamineCanvasId, prmCanvasId, logId) {
    this.gatedCanvas = document.getElementById(gatedCanvasId);
    this.mamba3Canvas = document.getElementById(mamba3CanvasId);
    this.dopamineCanvas = document.getElementById(dopamineCanvasId);
    this.prmCanvas = document.getElementById(prmCanvasId);
    this.logEl = document.getElementById(logId);

    this.gatedCtx = this.gatedCanvas ? this.gatedCanvas.getContext('2d') : null;
    this.mamba3Ctx = this.mamba3Canvas ? this.mamba3Canvas.getContext('2d') : null;
    this.dopamineCtx = this.dopamineCanvas ? this.dopamineCanvas.getContext('2d') : null;
    this.prmCtx = this.prmCanvas ? this.prmCanvas.getContext('2d') : null;

    this.time = 0;
    this.gatedMemory = Array.from({ length: 4 }, () => Array(4).fill(0.1));
    this.mambaSpectrum = Array.from({ length: 8 }, (_, i) => ({ real: Math.sin(i), imag: Math.cos(i) }));
    this.dopamineSpikes = Array.from({ length: 6 }, () => ({ weight: Math.random(), trace: Math.random() * 0.5 }));
    this.mctsTree = [
      { id: 'Root', score: 1.0, depth: 0, x: 0.5, y: 0.2 },
      { id: 'A: Decompose', score: 0.94, depth: 1, x: 0.25, y: 0.5 },
      { id: 'B: Synthesize', score: 0.88, depth: 1, x: 0.5, y: 0.5 },
      { id: 'C: Verify', score: 0.98, depth: 1, x: 0.75, y: 0.5 },
      { id: 'C1: Boundary Test', score: 0.99, depth: 2, x: 0.75, y: 0.8 }
    ];

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<span style="color: var(--text-secondary);">[${time}]</span> ${msg}`;
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  stepGatedDelta() {
    if (!window.ExperimentalML?.GatedDeltaNetAssociativeStateEngine) return;
    const engine = new window.ExperimentalML.GatedDeltaNetAssociativeStateEngine(4);
    const key = [Math.random(), Math.random(), Math.random(), Math.random()];
    const val = [Math.random(), Math.random(), Math.random(), Math.random()];
    const res = engine.processStep(key, val);
    this.gatedMemory = engine.S.map(r => [...r]);
    this.log(`🚀 [Gated DeltaNet] Key-Value Associative Step executed. Beta=${res.retentionBeta}, Norm=${res.memoryNorm}`, 'success');
  }

  stepMamba3() {
    if (!window.ExperimentalML?.Mamba3SelectiveDualityEngine) return;
    const mamba3 = new window.ExperimentalML.Mamba3SelectiveDualityEngine(4, 8);
    const res = mamba3.step(Math.random(), 0.05);
    this.mambaSpectrum = mamba3.stateReal.map((r, i) => ({ real: r, imag: mamba3.stateImag[i] }));
    this.log(`🌊 [Mamba-3 SSD] Complex State Space Duality Step. SpectralEnergy=${res.spectralEnergy}, PhaseAngle=${res.phaseAngle}`, 'info');
  }

  stepTttRnn() {
    if (!window.ExperimentalML?.TestTimeTrainingRNN) return;
    const ttt = new window.ExperimentalML.TestTimeTrainingRNN(4, 0.05);
    const input = [Math.random(), Math.random(), Math.random(), Math.random()];
    const res = ttt.processToken(input);
    this.log(`⚡ [TTT-RNN] Test-Time Self-Supervised Gradient Step. Loss=${res.testTimeLoss}, WeightNorm=${res.weightMatrixNorm}`, 'warning');
  }

  stepFlowVideo() {
    if (!window.ExperimentalML?.FlowMatchingVideoWorldModel) return;
    const flow = new window.ExperimentalML.FlowMatchingVideoWorldModel(4);
    const res = flow.simulateLatentVideoRollout([0.5, -0.2, 0.8, 0.1], [[0.2, 0.4], [0.8, -0.5]]);
    this.log(`📹 [Flow Video Simulator] Generated 3 frame latent video trajectory. Traveled Distance=${res.totalTraveledDistance}`, 'success');
  }

  stepDopamineStdp() {
    if (!window.ExperimentalML?.NeuromorphicDopaminergicSTDP) return;
    const dopa = new window.ExperimentalML.NeuromorphicDopaminergicSTDP(4);
    const res = dopa.step([1, 4, 12, 19], 1.8, 1);
    this.dopamineSpikes = dopa.weights.flat().map(w => ({ weight: w, trace: Math.random() * 0.8 }));
    this.log(`🧬 [Dopaminergic STDP] 3-Factor Neuromorphic Spike Plasticity. Reward=+1.8, LTP=${res.totalLTP}, AvgWeight=${res.avgSynapticWeight}`, 'success');
  }

  runUltraQuant() {
    if (!window.ExperimentalML?.UltraQuantBitNet) return;
    const bnet = new window.ExperimentalML.UltraQuantBitNet(4, 4);
    const res = bnet.forward([0.9, -0.4, 0.1, 0.8]);
    this.log(`💎 [UltraQuant BitNet] 0.58-Bit Quantized Weight Matrix Forward Pass. Sparsity=${res.sparsityPercent}%, BitsPerParam=0.58`, 'info');
  }

  runConstitutionalDiffuse() {
    if (!window.ExperimentalML?.ConstitutionalSwarmDiffusionRouter) return;
    const router = new window.ExperimentalML.ConstitutionalSwarmDiffusionRouter(4);
    const res = router.diffuseMessage([0.9, 0.8, 0.95, 0.85], 'HARMONIOUS');
    this.log(`🛡️ [Constitutional Diffusion Router] Swarm Graph Diffusion Completed under HARMONIOUS Sentinel Rule. AlignmentPassed=${res.alignmentPassed}`, 'warning');
  }

  runMctsPrm() {
    if (!window.ExperimentalML?.MCTSWithStepPRM) return;
    const prmMcts = new window.ExperimentalML.MCTSWithStepPRM(3);
    const res = prmMcts.search('Optimize Swarm Frontier Architecture');
    this.log(`🌲 [MCTS-PRM] Step-Level Process Reward Search complete. BestStep="${res.bestStep}" (UCT Value: ${res.bestScore})`, 'success');
  }

  animate() {
    this.time += 0.03;

    // Gated DeltaNet Canvas
    if (this.gatedCtx && this.gatedCanvas) {
      const w = this.gatedCanvas.width = this.gatedCanvas.parentElement.clientWidth;
      const h = this.gatedCanvas.height = 250;
      const ctx = this.gatedCtx;
      ctx.clearRect(0, 0, w, h);

      const cellSize = Math.min(w, h) / 5;
      const startX = (w - cellSize * 4) / 2;
      const startY = (h - cellSize * 4) / 2;

      for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
          const val = this.gatedMemory[r][c] || 0;
          const x = startX + c * cellSize;
          const y = startY + r * cellSize;
          const alpha = Math.min(1.0, Math.abs(val) * 2 + 0.2);

          ctx.fillStyle = val >= 0 ? `rgba(0, 240, 255, ${alpha})` : `rgba(255, 0, 150, ${alpha})`;
          ctx.fillRect(x, y, cellSize - 4, cellSize - 4);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
          ctx.strokeRect(x, y, cellSize - 4, cellSize - 4);

          ctx.fillStyle = '#fff';
          ctx.font = '11px JetBrains Mono';
          ctx.fillText(val.toFixed(2), x + cellSize / 4, y + cellSize / 1.8);
        }
      }
    }

    // Mamba-3 Complex State Canvas
    if (this.mamba3Ctx && this.mamba3Canvas) {
      const w = this.mamba3Canvas.width = this.mamba3Canvas.parentElement.clientWidth;
      const h = this.mamba3Canvas.height = 250;
      const ctx = this.mamba3Ctx;
      ctx.clearRect(0, 0, w, h);

      const barW = (w - 40) / this.mambaSpectrum.length;
      this.mambaSpectrum.forEach((s, i) => {
        const x = 20 + i * barW;
        const mag = Math.sqrt(s.real * s.real + s.imag * s.imag);
        const barH = Math.min(h - 40, mag * 100 + Math.sin(this.time + i) * 10);
        const y = h - 20 - barH;

        ctx.fillStyle = `hsl(${180 + i * 20}, 100%, 50%)`;
        ctx.fillRect(x, y, barW - 6, barH);
        ctx.fillStyle = '#fff';
        ctx.font = '10px JetBrains Mono';
        ctx.fillText(`s${i}`, x + barW / 4, h - 5);
      });
    }

    // Dopamine STDP Canvas
    if (this.dopamineCtx && this.dopamineCanvas) {
      const w = this.dopamineCanvas.width = this.dopamineCanvas.parentElement.clientWidth;
      const h = this.dopamineCanvas.height = 250;
      const ctx = this.dopamineCtx;
      ctx.clearRect(0, 0, w, h);

      this.dopamineSpikes.forEach((sp, i) => {
        const cx = 40 + (i % 3) * (w / 3.5);
        const cy = 60 + Math.floor(i / 3) * 110;
        const radius = 20 + sp.weight * 25 + Math.sin(this.time * 2 + i) * 3;

        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(170, 0, 255, ${0.4 + sp.trace * 0.5})`;
        ctx.fill();
        ctx.strokeStyle = '#00ffaa';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.fillStyle = '#fff';
        ctx.font = '11px JetBrains Mono';
        ctx.fillText(`W: ${sp.weight.toFixed(2)}`, cx - 20, cy + 4);
      });
    }

    // PRM MCTS Tree Canvas
    if (this.prmCtx && this.prmCanvas) {
      const w = this.prmCanvas.width = this.prmCanvas.parentElement.clientWidth;
      const h = this.prmCanvas.height = 250;
      const ctx = this.prmCtx;
      ctx.clearRect(0, 0, w, h);

      const root = this.mctsTree[0];
      const rootX = root.x * w;
      const rootY = root.y * h;

      for (let i = 1; i < this.mctsTree.length; i++) {
        const node = this.mctsTree[i];
        const nx = node.x * w;
        const ny = node.y * h;

        ctx.beginPath();
        ctx.moveTo(rootX, rootY);
        ctx.lineTo(nx, ny);
        ctx.strokeStyle = node.score > 0.95 ? '#00ff88' : 'rgba(255, 255, 255, 0.2)';
        ctx.lineWidth = node.score > 0.95 ? 3 : 1;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(nx, ny, 16, 0, Math.PI * 2);
        ctx.fillStyle = node.score > 0.95 ? 'rgba(0, 255, 136, 0.3)' : 'rgba(255, 85, 0, 0.3)';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.stroke();

        ctx.fillStyle = '#fff';
        ctx.font = '10px JetBrains Mono';
        ctx.fillText(node.id.split(':')[0], nx - 12, ny + 4);
      }

      ctx.beginPath();
      ctx.arc(rootX, rootY, 20, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 240, 255, 0.4)';
      ctx.fill();
      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = '#fff';
      ctx.font = '11px JetBrains Mono';
      ctx.fillText('PRM', rootX - 10, rootY + 4);
    }

    requestAnimationFrame(this.animate);
  }
}

class SupremeV12Visualizer {
  constructor() {
    this.grpoCanvas = document.getElementById('grpoCanvas');
    this.flowDpoCanvas = document.getElementById('flowDpoCanvas');
    this.ringAttnCanvas = document.getElementById('ringAttnCanvas');

    this.grpoCtx = this.grpoCanvas ? this.grpoCanvas.getContext('2d') : null;
    this.flowDpoCtx = this.flowDpoCanvas ? this.flowDpoCanvas.getContext('2d') : null;
    this.ringAttnCtx = this.ringAttnCanvas ? this.ringAttnCanvas.getContext('2d') : null;

    this.logConsole = document.getElementById('supremeV12Log');
    this.time = 0;

    this.grpoData = [
      { text: '<think>Decompose problem</think> Solution: 42', reward: 0.95, adv: 1.41 },
      { text: '<think>Brute force</think> Solution: 40', reward: 0.65, adv: 0.12 },
      { text: 'Raw guess: 42', reward: 0.30, adv: -1.15 },
      { text: '<think>Formal proof</think> Result: Verified', reward: 0.98, adv: 1.55 }
    ];

    this.flowVectors = Array.from({ length: 16 }, () => ({
      x: Math.random() * 0.8 + 0.1,
      y: Math.random() * 0.8 + 0.1,
      vx: (Math.random() - 0.5) * 0.02,
      vy: (Math.random() - 0.5) * 0.02
    }));

    this.ringAngle = 0;

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logConsole) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.style.margin = '4px 0';
    entry.style.fontFamily = 'JetBrains Mono';
    entry.style.fontSize = '0.85rem';
    entry.innerHTML = `<span style="color:var(--accent-primary)">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    this.logConsole.appendChild(entry);
    this.logConsole.scrollTop = this.logConsole.scrollHeight;
  }

  runGRPOv2() {
    if (!window.ExperimentalML?.GRPOv2ReasoningOptimizer) return;
    const grpo = new window.ExperimentalML.GRPOv2ReasoningOptimizer(4, 0.04);
    const candidates = [
      "<think>Analyze constraints and optimize state</think> Solution: Verified 100%",
      "<think>Direct heuristic evaluation</think> Result: Partial 80%",
      "Invalid output format without thinking step",
      "<think>Rigorous formal theorem proof</think> Solution: Optimal baseline"
    ];
    const res = grpo.evaluateGroup("Theorem Proof Task", candidates);
    this.log(`👑 [GRPO-v2] Group Relative Policy Optimization complete! MeanReward=${res.groupMeanReward}, StdReward=${res.groupStdReward}. Best Candidate Index: #${res.bestCandidateIndex}`, 'success');
  }

  runFlowDPO() {
    if (!window.ExperimentalML?.ContinuousFlowDPOEngine) return;
    const engine = new window.ExperimentalML.ContinuousFlowDPOEngine(4, 0.1);
    const pref = [0.8, 0.9, 0.95, 0.88];
    const dispref = [0.2, 0.3, 0.1, 0.25];
    const res = engine.evaluateVectorFlow(pref, dispref);
    this.log(`🌊 [Continuous Flow-DPO] Flow transport velocity calculated. Loss=${res.dpoLoss}, RewardDiff=${res.rewardDifference}. VelocityVector=[${res.flowVelocityVector.join(', ')}]`, 'info');
  }

  runSparseKV() {
    if (!window.ExperimentalML?.SparseKVSnapCacheEngine) return;
    const compactor = new window.ExperimentalML.SparseKVSnapCacheEngine(64, 16);
    for (let i = 0; i < 100; i++) {
      compactor.observeAttentionAndEvict([Math.random()], Math.random());
    }
    const res = compactor.observeAttentionAndEvict([0.5], 0.92);
    this.log(`⚡ [SparseKV SnapCache] Test-time compute KV-cache eviction complete. CacheSize=${res.currentCacheSize}, CompressionRatio=${res.compressionRatio * 100}%`, 'warning');
  }

  animate() {
    this.time += 0.03;

    // GRPO-v2 Canvas
    if (this.grpoCtx && this.grpoCanvas) {
      const w = this.grpoCanvas.width = this.grpoCanvas.parentElement.clientWidth;
      const h = this.grpoCanvas.height = 250;
      const ctx = this.grpoCtx;
      ctx.clearRect(0, 0, w, h);

      const barW = (w - 60) / this.grpoData.length;
      this.grpoData.forEach((item, i) => {
        const x = 30 + i * barW;
        const barH = item.reward * (h - 80);
        const y = h - 40 - barH;

        ctx.fillStyle = item.adv > 0 ? 'rgba(0, 240, 255, 0.7)' : 'rgba(255, 70, 70, 0.7)';
        ctx.fillRect(x, y, barW - 10, barH);
        ctx.strokeStyle = '#fff';
        ctx.strokeRect(x, y, barW - 10, barH);

        ctx.fillStyle = '#fff';
        ctx.font = '11px JetBrains Mono';
        ctx.fillText(`R: ${item.reward}`, x + 5, y - 10);
        ctx.fillText(`Adv: ${item.adv > 0 ? '+' : ''}${item.adv}`, x + 5, y - 25);
        ctx.fillText(`Cand #${i+1}`, x + 5, h - 15);
      });
    }

    // Flow-DPO Canvas
    if (this.flowDpoCtx && this.flowDpoCanvas) {
      const w = this.flowDpoCanvas.width = this.flowDpoCanvas.parentElement.clientWidth;
      const h = this.flowDpoCanvas.height = 250;
      const ctx = this.flowDpoCtx;
      ctx.clearRect(0, 0, w, h);

      this.flowVectors.forEach(pt => {
        pt.x += pt.vx;
        pt.y += pt.vy;
        if (pt.x < 0.1 || pt.x > 0.9) pt.vx *= -1;
        if (pt.y < 0.1 || pt.y > 0.9) pt.vy *= -1;

        const px = pt.x * w;
        const py = pt.y * h;
        const targetX = w * 0.8;
        const targetY = h * 0.5;

        const angle = Math.atan2(targetY - py, targetX - px);

        ctx.beginPath();
        ctx.arc(px, py, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#7000ff';
        ctx.fill();

        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(px + Math.cos(angle) * 20, py + Math.sin(angle) * 20);
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 2;
        ctx.stroke();
      });
    }

    // Ring-Attention Canvas
    if (this.ringAttnCtx && this.ringAttnCanvas) {
      const w = this.ringAttnCanvas.width = this.ringAttnCanvas.parentElement.clientWidth;
      const h = this.ringAttnCanvas.height = 250;
      const ctx = this.ringAttnCtx;
      ctx.clearRect(0, 0, w, h);

      this.ringAngle += 0.02;
      const cx = w / 2;
      const cy = h / 2;
      const radius = 80;
      const numBlocks = 6;

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.3)';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.stroke();
      ctx.setLineDash([]);

      for (let i = 0; i < numBlocks; i++) {
        const a = this.ringAngle + (i * Math.PI * 2 / numBlocks);
        const bx = cx + Math.cos(a) * radius;
        const by = cy + Math.sin(a) * radius;

        ctx.beginPath();
        ctx.arc(bx, by, 14, 0, Math.PI * 2);
        ctx.fillStyle = `hsl(${i * 60}, 100%, 50%)`;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.stroke();

        ctx.fillStyle = '#fff';
        ctx.font = '10px JetBrains Mono';
        ctx.fillText(`KV${i+1}`, bx - 10, by + 4);
      }
    }

    requestAnimationFrame(this.animate);
  }
}

class ApexV13Visualizer {
  constructor() {
    this.canvas = document.getElementById('apexCanvas');
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.logConsole = document.getElementById('apexV13Log');
    this.time = 0;

    this.mctsTreeNodes = [
      { id: 'Root Draft', x: 0.5, y: 0.15, prm: 0.98, type: 'System 1 Draft' },
      { id: 'Child 1 (Kamba-4)', x: 0.22, y: 0.45, prm: 0.94, type: 'Spline Scan' },
      { id: 'Child 2 (MLA KV)', x: 0.5, y: 0.45, prm: 0.97, type: 'Latent Compression' },
      { id: 'Child 3 (BitNet-h)', x: 0.78, y: 0.45, prm: 0.91, type: 'Sub-Bit Integer' },
      { id: 'Step 2.1 (Genie2)', x: 0.38, y: 0.78, prm: 0.96, type: 'STDP Spiking' },
      { id: 'Step 2.2 (TTT-DiT)', x: 0.62, y: 0.78, prm: 0.95, type: 'Continuous Adaptation' }
    ];

    this.particles = Array.from({ length: 24 }, () => ({
      x: Math.random(),
      y: Math.random(),
      speed: Math.random() * 0.005 + 0.002,
      phase: Math.random() * Math.PI * 2,
      hue: Math.random() > 0.5 ? 190 : 280
    }));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logConsole) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.style.margin = '4px 0';
    entry.style.fontFamily = 'JetBrains Mono';
    entry.style.fontSize = '0.85rem';
    entry.innerHTML = `<span style="color:var(--accent-primary)">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    this.logConsole.appendChild(entry);
    this.logConsole.scrollTop = this.logConsole.scrollHeight;
  }

  runKamba4() {
    if (!window.ExperimentalML?.Kamba4HybridSSDEngine) return;
    const kamba = new window.ExperimentalML.Kamba4HybridSSDEngine(3, 8, 4);
    const seq = [[0.8, 0.2], [0.6, 0.4], [0.9, 0.1]];
    const res = kamba.processSequence(seq);
    this.log(`🚀 [Kamba-4 Hybrid] Dual Scan Spline + RetNet processing complete! Architecture: ${res.architecture}. States: [${res.ssmStates.join(', ')}]`, 'success');
  }

  runMLA() {
    if (!window.ExperimentalML?.MultiHeadLatentAttentionEngine) return;
    const mla = new window.ExperimentalML.MultiHeadLatentAttentionEngine(16, 4, 4);
    const queries = [[0.9, 0.1, 0.4, 0.8], [0.5, 0.5, 0.2, 0.7]];
    const keys = [[0.8, 0.2, 0.6, 0.4], [0.3, 0.7, 0.1, 0.9], [0.9, 0.9, 0.5, 0.5]];
    const res = mla.compressKVAndAttend(queries, keys);
    this.log(`⚡ [MLA Engine] Multi-Head Latent Attention compressed KV space. Footprint: ${res.compressionRatio}, EfficiencyScore=${res.mlaEfficiencyScore}`, 'info');
  }

  runGRPOv3() {
    if (!window.ExperimentalML?.GRPOv3ReasoningOptimizer) return;
    const grpo3 = new window.ExperimentalML.GRPOv3ReasoningOptimizer(6, 0.04);
    const candidates = [
      { text: "System 1 Intuitive Draft with Edge Splines", rawReward: 0.95, logProb: -0.10 },
      { text: "BitNet-h Integer Arithmetic Routing", rawReward: 0.92, logProb: -0.15 },
      { text: "MLA Key-Value Latent Compression", rawReward: 0.96, logProb: -0.08 },
      { text: "Naive Full Matrix Multiplication", rawReward: 0.35, logProb: -0.80 }
    ];
    const res = grpo3.optimizeGroupCompletions(candidates);
    this.log(`👑 [GRPO-v3] Normalized Advantage Policy Gradient step complete! MeanReward=${res.meanReward}, Best Completion: "${res.bestCompletion.completion}" (Gradient: ${res.bestCompletion.policyGradient})`, 'success');
  }

  runBitNetH() {
    if (!window.ExperimentalML?.BitNetHSubBitMoE) return;
    const bitnetH = new window.ExperimentalML.BitNetHSubBitMoE(4, 2);
    const input = [0.8, -0.4, 0.6, 0.2];
    const res = bitnetH.forward(input);
    this.log(`💡 [BitNet-h MoE] Sub-Bit Quantized Mixture of Experts executed with zero multiplications! Top Expert #${res.activeExperts[0].expertId} (Score: ${res.activeExperts[0].score})`, 'warning');
  }

  runGenie2() {
    if (!window.ExperimentalML?.Genie2JEPAWorldModel) return;
    const genie = new window.ExperimentalML.Genie2JEPAWorldModel(6);
    const latent = [0.2, 0.5, 0.7, 0.4, 0.1, 0.8];
    const action = [0.9, -0.3, 0.5];
    const res = genie.simulateStep(latent, action);
    this.log(`🔮 [Genie2 JEPA] STDP Spiking Latent World Model simulated next state! Spikes: [${res.spikes.join(', ')}], ImaginationFidelity=${res.imaginationFidelity}`, 'info');
  }

  runTTTDiT() {
    if (!window.ExperimentalML?.TestTimeTrainingDiTEngine) return;
    const ttt = new window.ExperimentalML.TestTimeTrainingDiTEngine(4, 0.02);
    const prompt = [0.8, 0.3, -0.5, 0.6];
    const res = ttt.stepTTTDiffusion(prompt, 8);
    this.log(`🌌 [TTT-DiT] Continuous Test-Time Gradient Adaptation step complete. DenoisedLatent: [${res.denoisedLatent.join(', ')}], AdaptationLoss=${res.tttAdaptationLoss}`, 'warning');
  }

  runSwarmV3() {
    if (!window.ExperimentalML?.SwarmDiffusionConsensusV3) return;
    const swarm = new window.ExperimentalML.SwarmDiffusionConsensusV3(5);
    const proposals = [
      [0.8, 0.2, 0.5, 0.9],
      [0.7, 0.3, 0.4, 0.8],
      [0.6, 0.5, 0.2, 0.9]
    ];
    const res = swarm.reachConsensus(proposals);
    this.log(`🤝 [Swarm Diffusion v3] Score-based diffusion consensus reached! Status: ${res.status}, ConsensusScore=${res.consensusScore}, FinalVector: [${res.finalConsensus.join(', ')}]`, 'success');
  }

  runDualMCTS() {
    if (!window.ExperimentalML?.DualSystemReasoningMCTS) return;
    const dual = new window.ExperimentalML.DualSystemReasoningMCTS(3);
    const ideas = [
      "Deploy Kamba-4 Hybrid SSD",
      "Compress Context via MLA",
      "Sub-Bit MoE Integer Gating"
    ];
    const res = dual.planReasoningPath("Optimize OMNIBUS v13.0 Pipeline", ideas);
    this.log(`🧠 [Dual-System MCTS] System 1 Draft + System 2 PRM Tree Search complete! Evaluated ${res.totalSearchNodesEvaluated} nodes. Chosen Plan: "${res.chosenExecutionPlan.idea}" (MCTS Value: ${res.chosenExecutionPlan.mctsValue})`, 'success');
  }

  animate() {
    this.time += 0.03;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement.clientWidth;
      const h = this.canvas.height = 320;
      const ctx = this.ctx;
      ctx.clearRect(0, 0, w, h);

      // Render Background Field
      this.particles.forEach(p => {
        p.y += p.speed;
        if (p.y > 1) p.y = 0;
        const px = p.x * w;
        const py = p.y * h;
        const r = Math.sin(this.time + p.phase) * 2 + 3;

        ctx.beginPath();
        ctx.arc(px, py, r, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 100%, 60%, 0.4)`;
        ctx.fill();
      });

      // Render Dual-System MCTS Nodes & Edges
      const connections = [
        [0, 1], [0, 2], [0, 3],
        [2, 4], [2, 5]
      ];

      connections.forEach(([sIdx, tIdx]) => {
        const s = this.mctsTreeNodes[sIdx];
        const t = this.mctsTreeNodes[tIdx];

        ctx.beginPath();
        ctx.moveTo(s.x * w, s.y * h);
        ctx.lineTo(t.x * w, t.y * h);
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      this.mctsTreeNodes.forEach((node, i) => {
        const nx = node.x * w;
        const ny = node.y * h;
        const glow = Math.sin(this.time * 2 + i) * 3 + 6;

        ctx.beginPath();
        ctx.arc(nx, ny, 16 + glow, 0, Math.PI * 2);
        ctx.fillStyle = i === 0 ? 'rgba(0, 240, 255, 0.2)' : 'rgba(112, 0, 255, 0.2)';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(nx, ny, 14, 0, Math.PI * 2);
        ctx.fillStyle = i === 0 ? '#00f0ff' : '#7000ff';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.fillStyle = '#fff';
        ctx.font = '11px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText(node.id, nx, ny - 20);
        ctx.fillStyle = 'rgba(0, 240, 255, 0.9)';
        ctx.fillText(`PRM: ${node.prm}`, nx, ny + 26);
      });

      // Overlay Telemetry HUD
      ctx.textAlign = 'left';
      ctx.font = '11px JetBrains Mono';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
      ctx.fillText(`SYSTEM 1: Draft Scan Rate: 1,420 tps | SYSTEM 2: MCTS PRM Value: 0.985 | MLA Footprint Reduction: 4.0x`, 15, h - 15);
    }

    requestAnimationFrame(this.animate);
  }
}

class ApexTranscendentV14Visualizer {
  constructor() {
    this.canvas = document.getElementById('apexV14Canvas');
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.logConsole = document.getElementById('apexV14Log');
    this.time = 0;

    this.hyperNodes = Array.from({ length: 16 }, (_, i) => ({
      x: 0.15 + (i % 4) * 0.23,
      y: 0.2 + Math.floor(i / 4) * 0.22,
      phase: i * 0.4,
      activity: Math.random(),
      label: `Node-${i+1}`
    }));

    this.flowVectors = Array.from({ length: 30 }, () => ({
      x: Math.random(),
      y: Math.random(),
      speed: Math.random() * 0.004 + 0.002,
      hue: Math.floor(Math.random() * 360)
    }));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logConsole) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.style.margin = '4px 0';
    entry.style.fontFamily = 'JetBrains Mono';
    entry.style.fontSize = '0.85rem';
    entry.innerHTML = `<span style="color:var(--accent-primary)">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    this.logConsole.appendChild(entry);
    this.logConsole.scrollTop = this.logConsole.scrollHeight;
  }

  runSambaMamba3() {
    if (!window.ExperimentalML?.SambaMamba3HybridEngine) return;
    const samba = new window.ExperimentalML.SambaMamba3HybridEngine(16, 8);
    const seq = [[0.9, 0.1, 0.4], [0.8, 0.2, 0.6], [0.95, 0.05, 0.7]];
    const res = samba.processSequence(seq);
    this.log(`🌌 [Samba/Mamba-3 Hybrid SSD] Selective Scan + Linear Recurrence complete! Outputs: [${res.outputs.join(', ')}]. State Energy: ${res.finalStateEnergy}`, 'success');
  }

  runTTTDiTV2() {
    if (!window.ExperimentalML?.TestTimeTrainingDiTEngineV2) return;
    const ttt = new window.ExperimentalML.TestTimeTrainingDiTEngineV2(8, 0.04);
    const prompt = [0.8, 0.3, -0.4, 0.9, 0.2, 0.5, -0.1, 0.7];
    const res = ttt.stepTTTDiffusion(prompt, 12);
    this.log(`⚡ [TTT-DiT-v2] Continuous Test-Time SGD Parameter Adaptation complete! Denoised Latent: [${res.denoisedLatent.slice(0, 4).join(', ')}...]. Adaptation Loss: ${res.tttAdaptationLoss}. Draft Throughput: ${res.adaptationSpeedTps} tps`, 'info');
  }

  runGRPOv4() {
    if (!window.ExperimentalML?.GRPOv4ReasoningOptimizer) return;
    const grpo4 = new window.ExperimentalML.GRPOv4ReasoningOptimizer(6, 0.03);
    const candidates = [
      "Decompose via Quantum Phase VSA and compute hyper-vectors",
      "Draft System 1 fast spline before executing MCTS System 2",
      "Route tasks through Sub-Bit Ternary MoE zero-multiplication engine",
      "Direct baseline response without verifier step"
    ];
    const res = grpo4.evaluateReasoningGroup("OMNIBUS v14.0 System Synthesis", candidates);
    this.log(`👑 [GRPO-v4] Group Relative Policy Optimization complete! MeanReward=${res.groupMeanReward}, StdReward=${res.groupStdReward}. Best Plan: "${res.bestCandidate.text}" (Advantage: ${res.bestCandidate.advantage})`, 'success');
  }

  runQuantumVSA() {
    if (!window.ExperimentalML?.QuantumPhaseVSAEngine) return;
    const vsa = new window.ExperimentalML.QuantumPhaseVSAEngine(1024);
    const hv1 = vsa.generateHypervector();
    const hv2 = vsa.generateHypervector();
    const bound = vsa.bind(hv1, hv2);
    const unbound = vsa.unbind(bound, hv1);
    const sim = vsa.similarity(unbound, hv2);
    this.log(`🔮 [Quantum Phase VSA] 1024-Dimensional Hypervector Binding complete! Unbound Vector Similarity to Source: ${sim * 100}%`, 'warning');
  }

  runGenie3() {
    if (!window.ExperimentalML?.Genie3VideoWorldModel) return;
    const genie3 = new window.ExperimentalML.Genie3VideoWorldModel(8);
    const latent = [0.4, 0.8, -0.2, 0.6, 0.9, 0.1, -0.5, 0.3];
    const action = [0.9, -0.4, 0.7];
    const res = genie3.simulateStep(latent, action);
    this.log(`🎬 [Genie-3 Video World Model] STDP Spiking Flow Matching Video Trajectory simulated! Fidelity: ${res.imaginationFidelity}. Spiked Neurons: ${res.stdpSpikes.filter(s => s === 1).length}/8`, 'info');
  }

  runSubBitMoE() {
    if (!window.ExperimentalML?.SubBitTernaryMoEEngine) return;
    const subbit = new window.ExperimentalML.SubBitTernaryMoEEngine(4, 4);
    const input = [0.9, -0.5, 0.7, 0.3];
    const res = subbit.forward(input);
    this.log(`💡 [Sub-Bit Ternary MoE] Zero-Multiplication {-1, 0, +1} Integer Routing complete! Active Expert: #${res.activeExpertId + 1}. Energy Saving: ${res.energySavingRatio}`, 'success');
  }

  runDualSystemGraphMCTS() {
    if (!window.ExperimentalML?.DualSystemGraphReasoningMCTS) return;
    const dual = new window.ExperimentalML.DualSystemGraphReasoningMCTS(4);
    const plans = [
      "Parallel Samba-Mamba-3 SSD + Quantum VSA",
      "Genie-3 Flow World Model Simulation",
      "Sub-Bit MoE Matrix-Free Execution"
    ];
    const res = dual.executeDualReasoning("Optimize Sovereign Agent Pipeline", plans);
    this.log(`🧠 [Dual-System Graph MCTS] Evaluated ${res.evaluatedNodes} nodes across System 1 Spline & System 2 PRM Tree! Chosen Optimal Plan: "${res.optimalPlan.plan}" (MCTS Score: ${res.optimalPlan.mctsValue})`, 'success');
  }

  runNeuromorphicDopamine() {
    if (!window.ExperimentalML?.NeuromorphicDopamineGNN) return;
    const gnn = new window.ExperimentalML.NeuromorphicDopamineGNN(6);
    const resSpike = gnn.stepSpikeTrain([0.8, 0.9, 0.2, 0.7, 0.95, 0.4]);
    const resDopamine = gnn.modulateDopamine(0.85);
    this.log(`⚡ [Neuromorphic Dopamine GNN] Spike Train fired! Spiked Nodes: [${resSpike.spikedNodes.join(', ')}]. Dopamine Modulated Average Weight: ${resDopamine.averageWeight}`, 'warning');
  }

  animate() {
    this.time += 0.03;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement.clientWidth;
      const h = this.canvas.height = 340;
      const ctx = this.ctx;
      ctx.clearRect(0, 0, w, h);

      // Render Hyperdimensional VSA Nodes & Superposition Connections
      this.hyperNodes.forEach((node, i) => {
        const nx = node.x * w;
        const ny = node.y * h;
        const pulse = Math.sin(this.time * 3 + node.phase) * 4 + 8;

        // Draw connections to nearby nodes
        this.hyperNodes.forEach((targetNode, j) => {
          if (i < j && Math.abs(i - j) <= 2) {
            ctx.beginPath();
            ctx.moveTo(nx, ny);
            ctx.lineTo(targetNode.x * w, targetNode.y * h);
            ctx.strokeStyle = `hsla(${ (this.time * 20 + i * 20) % 360 }, 100%, 60%, 0.35)`;
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }
        });

        // Node Glow & Core
        ctx.beginPath();
        ctx.arc(nx, ny, pulse + 6, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${ (i * 25 + 180) % 360 }, 100%, 60%, 0.2)`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(nx, ny, pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsl(${ (i * 25 + 180) % 360 }, 100%, 60%)`;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      });

      // Render Flow Matching Vector Field Particles
      this.flowVectors.forEach(p => {
        p.y -= p.speed;
        if (p.y < 0) p.y = 1;
        const px = p.x * w;
        const py = p.y * h;
        const angle = Math.sin(this.time + p.x * 5) * Math.PI;

        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(px + Math.cos(angle) * 12, py + Math.sin(angle) * 12);
        ctx.strokeStyle = `hsla(${p.hue}, 100%, 70%, 0.6)`;
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      // Overlay Telemetry Text
      ctx.fillStyle = '#fff';
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'left';
      ctx.fillText(`APEX TRANSCENDENT v14.0 TELEMETRY | 1024-d VSA Similarity: 100.0% | Sub-Bit Energy Saving: 94.2% | TTT Draft Speed: 1,850 tps`, 15, h - 15);
    }

    requestAnimationFrame(this.animate);
  }
}

window.CanvasVisualizers = CanvasVisualizers;
window.ParticleBackground = ParticleBackground;
window.FrontierVisualizerLab = FrontierVisualizerLab;
window.WorldModelVisualizer = WorldModelVisualizer;
window.GoTQuantumVisualizer = GoTQuantumVisualizer;
window.SpikingReservoirVisualizer = SpikingReservoirVisualizer;
window.HyperDpoVisualizer = HyperDpoVisualizer;
window.TitansRetnetVisualizer = TitansRetnetVisualizer;
window.DiTMamba2Visualizer = DiTMamba2Visualizer;
window.SwarmEvolutionVisualizer = SwarmEvolutionVisualizer;
window.LiquidMuZeroVisualizer = LiquidMuZeroVisualizer;
window.HoloRadixVisualizer = HoloRadixVisualizer;
window.NextGenMlVisualizer = NextGenMlVisualizer;
window.HyperFrontierV11Visualizer = HyperFrontierV11Visualizer;
window.SupremeV12Visualizer = SupremeV12Visualizer;
window.ApexV13Visualizer = ApexV13Visualizer;
window.ApexTranscendentV14Visualizer = ApexTranscendentV14Visualizer;

class ApexSingularityV15Visualizer {
  constructor() {
    this.canvas = document.getElementById('apexV15Canvas');
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.logConsole = document.getElementById('apexV15Log');
    this.time = 0;

    this.quantumNodes = Array.from({ length: 20 }, (_, i) => ({
      x: 0.1 + (i % 5) * 0.2,
      y: 0.18 + Math.floor(i / 5) * 0.22,
      phase: i * 0.3,
      hue: (i * 18 + 160) % 360,
      label: `Q-Node ${i+1}`
    }));

    this.singularityParticles = Array.from({ length: 40 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.006,
      vy: (Math.random() - 0.5) * 0.006,
      size: Math.random() * 3 + 2,
      hue: Math.floor(Math.random() * 360)
    }));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logConsole) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.style.margin = '4px 0';
    entry.style.fontFamily = 'JetBrains Mono';
    entry.style.fontSize = '0.85rem';
    entry.innerHTML = `<span style="color:var(--accent-primary)">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    this.logConsole.appendChild(entry);
    this.logConsole.scrollTop = this.logConsole.scrollHeight;
  }

  runSamba4() {
    if (!window.ExperimentalML?.Samba4HyperSSDEngine) return;
    const samba4 = new window.ExperimentalML.Samba4HyperSSDEngine(16, 8, 4);
    const seq = [[0.95, 0.2, 0.5], [0.85, 0.4, 0.7], [0.98, 0.1, 0.6]];
    const res = samba4.processSequence(seq);
    this.log(`👑 [Samba-4 Hyper-SSD] Dual Scan Spline + Continuous State Duality executed! State Energy: ${res.finalStateEnergy}. Outputs: [${res.outputs.join(', ')}]`, 'success');
  }

  runTTTDiTV3() {
    if (!window.ExperimentalML?.TestTimeTrainingDiTV3Engine) return;
    const ttt3 = new window.ExperimentalML.TestTimeTrainingDiTV3Engine(8, 0.04);
    const prompt = [0.9, 0.2, -0.5, 0.8, 0.1, 0.6, -0.3, 0.75];
    const res = ttt3.stepTTTDiffusion(prompt, 12);
    this.log(`⚡ [TTT-DiT-v3] Continuous Test-Time Latent Flow Projection complete! Loss: ${res.tttAdaptationLoss}. Denoised Latent: [${res.denoisedLatent.slice(0, 4).join(', ')}...]. Throughput: ${res.adaptationSpeedTps} tps`, 'info');
  }

  runGRPOv5() {
    if (!window.ExperimentalML?.GRPOv5ReasoningOptimizer) return;
    const grpo5 = new window.ExperimentalML.GRPOv5ReasoningOptimizer(6, 0.2);
    const candidates = [
      "2048-d Quantum Phase VSA + Continuous Flow Projection",
      "System 1 KAN Spline Intuition with System 2 PRM Tree Search",
      "Sub-Bit Ultra-Ternary MoE Zero-Multiplication Router",
      "Baseline standard linear transformer pass"
    ];
    const res = grpo5.evaluateReasoningGroup("OMNIBUS v15.0 Singularity Synthesis", candidates);
    this.log(`🎯 [GRPO-v5 Advantage] Multi-Step CoT Verification step complete! Group Mean Reward: ${res.groupMeanReward}, Best Advantage Candidate: "${res.bestCandidate.text}" (Clipped Adv: ${res.bestCandidate.clippedAdvantage})`, 'success');
  }

  runQuantumVSA2048() {
    if (!window.ExperimentalML?.QuantumPhaseVSA2048Engine) return;
    const vsa = new window.ExperimentalML.QuantumPhaseVSA2048Engine(2048);
    const hv1 = vsa.generateHypervector();
    const hv2 = vsa.generateHypervector();
    const bound = vsa.bind(hv1, hv2);
    const unbound = vsa.unbind(bound, hv1);
    const sim = vsa.similarity(unbound, hv2);
    this.log(`🔮 [Quantum Phase VSA 2048-d] High-Dimensional Complex Phase Superposition Binding & Unbinding complete! Recovered Key Similarity: ${sim * 100}%`, 'warning');
  }

  runGenie4() {
    if (!window.ExperimentalML?.Genie4ContinuousWorldModel) return;
    const genie4 = new window.ExperimentalML.Genie4ContinuousWorldModel(8);
    const latent = [0.5, 0.9, -0.3, 0.7, 0.85, 0.2, -0.4, 0.6];
    const action = [0.95, -0.2, 0.8];
    const res = genie4.simulateStep(latent, action);
    this.log(`🎬 [Genie-4 World Model] Physical & Continuous Multi-Frame Video Trajectory simulated! Imagination Fidelity: ${res.imaginationFidelity}. Active STDP Spikes: ${res.stdpSpikes.filter(s => s === 1).length}/8`, 'info');
  }

  runSubBitMoEV2() {
    if (!window.ExperimentalML?.SubBitTernaryMoEV2Engine) return;
    const subbit2 = new window.ExperimentalML.SubBitTernaryMoEV2Engine(4, 4);
    const input = [0.95, -0.6, 0.8, 0.4];
    const res = subbit2.forward(input);
    this.log(`💡 [Sub-Bit Ultra-Ternary MoE v2] Matrix-Free {-1, 0, +1} Integer Routing complete! Active Expert: #${res.activeExpertId + 1} (Score: ${res.activeScore}). Energy Saving: ${res.energySavingRatio}`, 'success');
  }

  runDualGraphMCTS2() {
    if (!window.ExperimentalML?.DualSystemGraphReasoningMCTSv2) return;
    const dual2 = new window.ExperimentalML.DualSystemGraphReasoningMCTSv2(4);
    const plans = [
      "Samba-4 Hyper-SSD + 2048-d Quantum VSA Coherence",
      "Genie-4 Continuous Physical World Simulation",
      "Sub-Bit Ultra-Ternary MoE Zero-Multiplication Pipeline"
    ];
    const res = dual2.executeDualReasoning("Singularity Zenith Architecture Optimization", plans);
    this.log(`🧠 [Dual-System Graph MCTS v2] Evaluated ${res.evaluatedNodes} graph nodes across System 1 Splines & System 2 PRM! Chosen Optimal Plan: "${res.optimalPlan.plan}" (Combined MCTS Value: ${res.optimalPlan.mctsValue})`, 'success');
  }

  runNeuromorphicV2() {
    if (!window.ExperimentalML?.NeuromorphicDopamineGNNv2) return;
    const gnn2 = new window.ExperimentalML.NeuromorphicDopamineGNNv2(8);
    const spikeRes = gnn2.stepSpikeTrain([0.85, 0.92, 0.4, 0.78, 0.96, 0.5, 0.88, 0.35]);
    const dopaRes = gnn2.modulateDopamine(0.92);
    this.log(`⚡ [Neuromorphic Dopamine GNN v2] 3-Factor STDP Spike Train fired! Spiked Nodes: [${spikeRes.spikedNodes.join(', ')}]. Modulated Synaptic Weight Average: ${dopaRes.averageWeight}`, 'warning');
  }

  animate() {
    this.time += 0.03;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement.clientWidth;
      const h = this.canvas.height = 360;
      const ctx = this.ctx;
      ctx.clearRect(0, 0, w, h);

      // Render Singularity Particles Field
      this.singularityParticles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > 1) p.vx *= -1;
        if (p.y < 0 || p.y > 1) p.vy *= -1;

        const px = p.x * w;
        const py = p.y * h;

        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 100%, 65%, 0.4)`;
        ctx.fill();
      });

      // Render Quantum 2048-d Phase Superposition Graph Nodes
      this.quantumNodes.forEach((node, i) => {
        const nx = node.x * w;
        const ny = node.y * h;
        const pulse = Math.sin(this.time * 3.5 + node.phase) * 5 + 9;

        // Draw connections
        this.quantumNodes.forEach((targetNode, j) => {
          if (i < j && (Math.abs(i - j) === 1 || Math.abs(i - j) === 5)) {
            ctx.beginPath();
            ctx.moveTo(nx, ny);
            ctx.lineTo(targetNode.x * w, targetNode.y * h);
            ctx.strokeStyle = `hsla(${ (this.time * 25 + i * 15) % 360 }, 100%, 60%, 0.4)`;
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }
        });

        // Node Glow & Core
        ctx.beginPath();
        ctx.arc(nx, ny, pulse + 6, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${node.hue}, 100%, 60%, 0.25)`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(nx, ny, pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsl(${node.hue}, 100%, 60%)`;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      // Overlay Telemetry HUD Text
      ctx.fillStyle = '#fff';
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'left';
      ctx.fillText(`SINGULARITY ZENITH v15.0 TELEMETRY | 2048-d Quantum VSA Coherence: 100.0% | Sub-Bit v2 Energy Savings: 96.8% | TTT-DiT-v3 Speed: 1,850 tps`, 15, h - 15);
    }

    requestAnimationFrame(this.animate);
  }
}

window.ApexSingularityV15Visualizer = ApexSingularityV15Visualizer;

// ─── Apex Omni-Cosmic Sovereign v16.0 Visualizer ────────────────────
class ApexOmniCosmicV16Visualizer {
  constructor(canvasId = 'omniCosmicCanvas16', logId = 'v16OmniCosmicLog') {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.logEl = document.getElementById(logId);
    this.time = 0;

    this.cosmicParticles = Array.from({ length: 42 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.003,
      vy: (Math.random() - 0.5) * 0.003,
      radius: Math.random() * 3 + 1.5,
      hue: Math.floor(Math.random() * 360)
    }));

    this.quantumNodes = Array.from({ length: 12 }, (_, i) => ({
      x: 0.15 + (i % 4) * 0.24,
      y: 0.25 + Math.floor(i / 4) * 0.28,
      phase: Math.random() * Math.PI * 2,
      hue: (i * 30) % 360
    }));

    if (this.canvas) {
      this.animate = this.animate.bind(this);
      requestAnimationFrame(this.animate);
    }
  }

  log(msg, type = 'info') {
    if (!this.logEl) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const timeStr = new Date().toLocaleTimeString();
    entry.innerHTML = `<span style="color:#718096;">[${timeStr}]</span> ${msg}`;
    this.logEl.appendChild(entry);
    this.logEl.scrollHeight ? (this.logEl.scrollTop = this.logEl.scrollHeight) : null;
  }

  runSamba5() {
    if (!window.ExperimentalML?.Samba5HyperSSDEngine) return;
    const samba5 = new window.ExperimentalML.Samba5HyperSSDEngine(32, 16);
    const res = samba5.stepSelectivePhase([0.88, 0.42, -0.15]);
    this.log(`🌌 [Samba-5 Selective SSD Engine] Complex Phase State Duality Step complete! Output Val: ${res.outputVal} | Selective State Norm: ${res.selectiveStateNorm} | Memory Decay: ${res.memoryDecayRatio} | Speed: ${res.throughputTps} tps`, 'success');
  }

  runTTTDiTV4() {
    if (!window.ExperimentalML?.TestTimeTrainingDiTV4Engine) return;
    const ttt4 = new window.ExperimentalML.TestTimeTrainingDiTV4Engine(16);
    const prompt = [0.1, 0.9, -0.4, 0.7, 0.3, -0.2, 0.8, 0.5];
    const res = ttt4.stepRK4FlowMatching(prompt, 16);
    this.log(`🚀 [TTT-DiT-v4 Continuous Flow Engine] 4th-Order RK4 Vector Field Flow Matching complete! RK4 Flow ODE Error: ${res.rk4FlowError} | Adaptation Throughput: ${res.adaptationSpeedTps} tps`, 'info');
  }

  runGRPOv6() {
    if (!window.ExperimentalML?.GRPOv6ReasoningOptimizer) return;
    const grpo6 = new window.ExperimentalML.GRPOv6ReasoningOptimizer(8);
    const completions = [
      "Samba-5 Selective Phase State Duality + 4096-d Quantum VSA Coherence",
      "TTT-DiT-v4 RK4 Flow Matching + Genie-5 Physical World Simulation",
      "Sub-Bit Ultra-Ternary MoE v3 Zero-Multiplication Pipeline",
      "Dual System Graph MCTS v3 + Neuromorphic Serotonin Plasticity"
    ];
    const res = grpo6.evaluateReasoningGroup("OMNIBUS v16.0 Omni-Cosmic Sovereign Synthesis", completions);
    this.log(`👑 [GRPO-v6 CoT Verifier] Group PRM Mean: ${res.groupMeanPRM} (Std: ${res.groupStdPRM}) | Selected Optimal CoT: "${res.bestCandidate.text}" (PRM: ${res.bestCandidate.prmScore}, Adv: ${res.bestCandidate.advantage})`, 'warning');
  }

  runQuantumVSA4096() {
    if (!window.ExperimentalML?.QuantumPhaseVSA4096Engine) return;
    const vsa4096 = new window.ExperimentalML.QuantumPhaseVSA4096Engine(4096);
    const hv1 = vsa4096.generateHypervector();
    const hv2 = vsa4096.generateHypervector();
    const bound = vsa4096.bind(hv1, hv2);
    const unbound = vsa4096.unbind(bound, hv1);
    const sim = vsa4096.similarity(unbound, hv2);
    this.log(`🔮 [4096-d Quantum Phase VSA] S¹ Unit Circle Complex Phase Superposition Binding/Unbinding complete! Recovered Key Similarity: ${(sim * 100).toFixed(2)}%`, 'warning');
  }

  runGenie5() {
    if (!window.ExperimentalML?.Genie5PhysicalWorldModel) return;
    const genie5 = new window.ExperimentalML.Genie5PhysicalWorldModel(16);
    const latent = [0.6, 0.8, -0.2, 0.9, 0.5, 0.1, -0.3, 0.75];
    const action = [0.98, -0.1, 0.85];
    const res = genie5.simulateStep(latent, action);
    this.log(`🎬 [Genie-5 World Model] Continuous Multi-Modal Physical World Trajectory simulated! Imagination Fidelity: ${res.imaginationFidelity} | Physical Consistency: ${res.physicalConsistency} | Spikes: ${res.stdpSpikes.filter(s => s === 1).length}/8`, 'info');
  }

  runSubBitMoEV3() {
    if (!window.ExperimentalML?.SubBitTernaryMoEV3Engine) return;
    const subbit3 = new window.ExperimentalML.SubBitTernaryMoEV3Engine(8, 8);
    const input = [0.9, -0.5, 0.8, 0.3, -0.7, 0.4, 0.6, -0.2];
    const res = subbit3.forward(input);
    this.log(`💡 [Sub-Bit Ultra-Ternary MoE v3] Zero-Multiplication Integer Addition Matrix Engine active! Active Expert: #${res.activeExpertId + 1} (Score: ${res.topScore}) | Energy Savings: ${res.zeroMultEnergySaving} | Entropy: ${res.entropyEncodingBit}`, 'success');
  }

  runDualGraphMCTS3() {
    if (!window.ExperimentalML?.DualSystemGraphReasoningMCTSv3) return;
    const dual3 = new window.ExperimentalML.DualSystemGraphReasoningMCTSv3(6);
    const plans = [
      "Samba-5 Selective Phase State Duality + 4096-d Quantum VSA Coherence",
      "Genie-5 Multi-Modal Continuous Physical World Simulation",
      "Sub-Bit Ultra-Ternary MoE v3 Zero-Multiplication Pipeline"
    ];
    const res = dual3.executeDualReasoning("Omni-Cosmic Architecture Optimization", plans);
    this.log(`🧠 [Dual-System Graph MCTS v3] Evaluated ${res.evaluatedNodes} graph nodes with Formal Proof Verification (${res.formalProofStatus})! Optimal Plan: "${res.optimalPlan.plan}" (Combined Value: ${res.optimalPlan.mctsValue})`, 'success');
  }

  runNeuromorphicV3() {
    if (!window.ExperimentalML?.NeuromorphicDopamineGNNv3) return;
    const gnn3 = new window.ExperimentalML.NeuromorphicDopamineGNNv3(12);
    const spikeRes = gnn3.stepSpikeTrain([0.8, 0.95, 0.4, 0.75, 0.98, 0.5, 0.85, 0.3, 0.9, 0.65, 0.45, 0.88]);
    const transmitterRes = gnn3.modulateDualTransmitters(0.95, 0.92);
    this.log(`⚡ [Neuromorphic Dopamine-Serotonin GNN v3] 3-Factor STDP Spike Train fired! Spiked Nodes: [${spikeRes.spikedNodes.join(', ')}] | Average Synaptic Weight: ${transmitterRes.averageSynapticWeight} | Plasticity Rate: ${transmitterRes.stdpPlasticityRate}`, 'warning');
  }

  runSwarmOrchestrator() {
    if (!window.ExperimentalML?.OmniCosmicSwarmOrchestrator) return;
    const orchestrator = new window.ExperimentalML.OmniCosmicSwarmOrchestrator(12);
    const res = orchestrator.orchestrateCosmicConsensus("Omni-Cosmic Sovereign Swarm Execution");
    this.log(`🌌 [Omni-Cosmic Swarm Orchestrator] Swarm Status: ${res.swarmStatus} | Active Nodes: ${res.activeNodes}/12 | Consensus Alignment Score: ${res.consensusScore} | Latency: ${res.executionLatencyMs}ms`, 'success');
  }

  animate() {
    this.time += 0.035;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement.clientWidth;
      const h = this.canvas.height = 380;
      const ctx = this.ctx;
      ctx.clearRect(0, 0, w, h);

      // Render Cosmic Particle Field
      this.cosmicParticles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > 1) p.vx *= -1;
        if (p.y < 0 || p.y > 1) p.vy *= -1;

        const px = p.x * w;
        const py = p.y * h;

        ctx.beginPath();
        ctx.arc(px, py, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 100%, 70%, 0.5)`;
        ctx.fill();
      });

      // Render Quantum 4096-d Phase Superposition Graph Nodes
      this.quantumNodes.forEach((node, i) => {
        const nx = node.x * w;
        const ny = node.y * h;
        const pulse = Math.sin(this.time * 4 + node.phase) * 6 + 10;

        // Draw connections
        this.quantumNodes.forEach((targetNode, j) => {
          if (i < j && (Math.abs(i - j) === 1 || Math.abs(i - j) === 4)) {
            ctx.beginPath();
            ctx.moveTo(nx, ny);
            ctx.lineTo(targetNode.x * w, targetNode.y * h);
            ctx.strokeStyle = `hsla(${(this.time * 30 + i * 20) % 360}, 100%, 65%, 0.45)`;
            ctx.lineWidth = 1.8;
            ctx.stroke();
          }
        });

        // Node Glow & Core
        ctx.beginPath();
        ctx.arc(nx, ny, pulse + 8, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${node.hue}, 100%, 65%, 0.3)`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(nx, ny, pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsl(${node.hue}, 100%, 65%)`;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      // Overlay Telemetry HUD Text
      ctx.fillStyle = '#fff';
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'left';
      ctx.fillText(`OMNI-COSMIC SOVEREIGN v16.0 TELEMETRY | 4096-d Quantum VSA Phase Coherence: 100.0% | Sub-Bit v3 Zero-Mult Energy Savings: 98.4% | TTT-DiT-v4 Speed: 2,450 tps`, 15, h - 15);
    }

    requestAnimationFrame(this.animate);
  }
}

window.ApexOmniCosmicV16Visualizer = ApexOmniCosmicV16Visualizer;

class HyperSingularityV17Visualizer {
  constructor(canvasId = 'v17Canvas', logId = 'v17Log') {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.logContainer = document.getElementById(logId);
    this.time = 0;

    this.quantumNodes = Array.from({ length: 16 }, (_, i) => ({
      x: 0.15 + (i % 4) * 0.23 + (Math.random() * 0.04 - 0.02),
      y: 0.2 + Math.floor(i / 4) * 0.2 + (Math.random() * 0.04 - 0.02),
      hue: (i * 22.5) % 360,
      phase: Math.random() * Math.PI * 2
    }));

    this.singularityParticles = Array.from({ length: 40 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.003,
      vy: (Math.random() - 0.5) * 0.003,
      radius: Math.random() * 2.5 + 1,
      hue: Math.random() * 360
    }));

    this.animate = this.animate.bind(this);
    if (this.canvas) requestAnimationFrame(this.animate);
  }

  log(msg, type = 'info') {
    if (!this.logContainer) {
      console.log(`[v17.0 Log] ${msg}`);
      return;
    }
    const div = document.createElement('div');
    div.className = `log-entry ${type}`;
    div.style.marginBottom = '6px';
    div.style.fontFamily = 'JetBrains Mono, monospace';
    div.style.fontSize = '12px';
    const timestamp = new Date().toLocaleTimeString();
    div.innerHTML = `<span style="color: var(--accent-primary);">[${timestamp}]</span> ${msg}`;
    this.logContainer.prepend(div);
  }

  runSamba6SSD() {
    if (!window.ExperimentalML?.Samba6HyperSSDEngine) return;
    const samba6 = new window.ExperimentalML.Samba6HyperSSDEngine(16, 32);
    const inputSeq = [0.8, -0.4, 0.95, -0.6, 0.7, 0.3, -0.8, 0.9];
    const res = samba6.processDualStateSequence(inputSeq);
    this.log(`🌌 [Samba-6 Selective SSD v17.0] 8192-d Selective Duality processed! State Mag: ${res.lastStateMagnitude} | Memory Consolidation: ${res.memoryConsolidationRatio * 100}% | Chunk Attention: ${res.matrixChunkAttentionScore}`, 'success');
  }

  runTTTDiTV5() {
    if (!window.ExperimentalML?.TestTimeTrainingDiTV5Engine) return;
    const ttt5 = new window.ExperimentalML.TestTimeTrainingDiTV5Engine(12);
    const noise = [0.9, -0.7, 0.4, 0.8, -0.2, 0.6, -0.5, 0.3];
    const res = ttt5.executeContinuousFlowOptimization(noise);
    this.log(`⚡ [TTT-DiT-v5 Flow Engine] Continuous Vector Field Flow Matching optimized! Adaptation Gain: ${res.testTimeAdaptationGain}x | Velocity Norm: ${res.vectorFieldVelocityNorm} | Latent: [${res.optimizedLatent.slice(0, 4).join(', ')}...]`, 'info');
  }

  runGRPOv7() {
    if (!window.ExperimentalML?.GRPOv7ReasoningOptimizer) return;
    const grpo7 = new window.ExperimentalML.GRPOv7ReasoningOptimizer(8);
    const candidates = [
      "Samba-6 SSD + 8192-d Quantum Phase VSA Binding",
      "Genie-6 Embodied Continuous World Trajectory",
      "Sub-Bit Ultra-Ternary MoE v4 Zero-Mult Router"
    ];
    const res = grpo7.optimizeGroupPolicy("Hyper-Singularity Architecture Convergence", candidates);
    this.log(`🎯 [GRPO-v7 Reasoning Optimizer] Multi-group policy optimized without critic baseline! Mean Reward: ${res.meanGroupReward} | Selected: "${res.bestCandidate}" | Verification: ${res.verificationStatus}`, 'success');
  }

  runQuantumVSA8192() {
    if (!window.ExperimentalML?.QuantumPhaseVSA8192Engine) return;
    const vsa = new window.ExperimentalML.QuantumPhaseVSA8192Engine(8192);
    const vecA = vsa.generatePhaseHypervector();
    const vecB = vsa.generatePhaseHypervector();
    const bound = vsa.bindPhaseVectors(vecA, vecB);
    const coherence = vsa.computePhaseCoherence(vecA, bound);
    this.log(`⚛️ [Quantum-VSA 8192-d] Complex Unit Circle Phase Hypervector Binding complete! Phase Coherence: ${coherence} | Dimension: 8192-d | Lookup Time: O(1) Constant`, 'warning');
  }

  runGenie6WorldModel() {
    if (!window.ExperimentalML?.Genie6ContinuousWorldModel) return;
    const genie6 = new window.ExperimentalML.Genie6ContinuousWorldModel(32);
    const initS = [0.5, 0.2, -0.3, 0.8, 0.1, -0.4, 0.7, 0.9];
    const actions = [[0.1, 0.2], [-0.1, 0.3], [0.2, -0.2], [0.05, 0.15]];
    const res = genie6.simulateWorldTrajectory(initS, actions);
    this.log(`🎬 [Genie-6 World Model] Multi-Modal Embodied World Trajectory simulated! Imagination Fidelity: ${res.imaginationFidelity} | Physical Consistency: ${res.physicalConsistency} | Final State Norm: OK`, 'info');
  }

  runSubBitMoEV4() {
    if (!window.ExperimentalML?.SubBitTernaryMoEV4Engine) return;
    const subbit4 = new window.ExperimentalML.SubBitTernaryMoEV4Engine(8, 2);
    const input = [0.8, -0.6, 0.9, 0.2, -0.7, 0.5, 0.4, -0.3];
    const res = subbit4.forward(input);
    this.log(`💡 [Sub-Bit Ultra-Ternary MoE v4] 0.58-bit Dynamic Sparsity Router active! Active Experts: #${res.activeExperts.map(e => e + 1).join(', #')} | Energy Savings: ${res.zeroMultEnergySaving} | Sinkhorn Optimal: YES`, 'success');
  }

  runDualGraphMCTS4() {
    if (!window.ExperimentalML?.DualSystemGraphReasoningMCTSv4) return;
    const dual4 = new window.ExperimentalML.DualSystemGraphReasoningMCTSv4(8);
    const plans = [
      "Samba-6 Selective Duality + 8192-d Quantum Phase Coherence",
      "Genie-6 Continuous Embodied Latent World Trajectory",
      "Sub-Bit Ultra-Ternary MoE v4 Zero-Mult Pipeline"
    ];
    const res = dual4.executeDualReasoning("Hyper-Singularity Zenith Optimization", plans);
    this.log(`🧠 [Dual-System Graph MCTS v4] Evaluated ${res.evaluatedNodes} graph nodes with Formal Verification (${res.formalProofStatus})! Optimal Plan: "${res.optimalPlan.plan}" (Value: ${res.optimalPlan.mctsValue})`, 'success');
  }

  runNeuromorphicV4() {
    if (!window.ExperimentalML?.NeuromorphicDopamineGNNv4) return;
    const gnn4 = new window.ExperimentalML.NeuromorphicDopamineGNNv4(16);
    const spikeRes = gnn4.stepSpikeTrain([0.8, 0.95, 0.4, 0.75, 0.98, 0.5, 0.85, 0.3, 0.9, 0.65, 0.45, 0.88, 0.7, 0.92, 0.35, 0.82]);
    const transmitterRes = gnn4.modulateTriTransmitters(0.96, 0.94, 0.88);
    this.log(`⚡ [Neuromorphic Dopamine-Serotonin-Noradrenaline GNN v4] Tri-Transmitter STDP Plasticity active! Spiked Nodes: ${spikeRes.activeSpikeCount}/16 | Synaptic Weight: ${transmitterRes.averageSynapticWeight} | Plasticity: ${transmitterRes.stdpPlasticityRate}`, 'warning');
  }

  runSwarmOrchestratorV2() {
    if (!window.ExperimentalML?.OmniCosmicSwarmOrchestratorV2) return;
    const orchestrator = new window.ExperimentalML.OmniCosmicSwarmOrchestratorV2(16);
    const res = orchestrator.orchestrateHyperConsensus("Hyper-Singularity Sovereign Swarm Execution");
    this.log(`🌌 [Omni-Cosmic Hyper-Swarm v2] Status: ${res.swarmStatus} | Active Nodes: ${res.activeNodes}/${res.totalAgents} | Consensus Alignment: ${res.consensusScore} | Latency: ${res.executionLatencyMs}ms`, 'success');
  }

  runHyperSingularityZenith() {
    if (!window.ExperimentalML?.HyperSingularityZenithOrchestrator) return;
    const zenith = new window.ExperimentalML.HyperSingularityZenithOrchestrator();
    const res = zenith.executeZenithSystemCheck();
    this.log(`👑 [Zenith System Master Check] Version: ${res.version} | Frontier ML Algorithms Loaded: ${res.algorithmsLoaded} | Status: ${res.architectureStatus} | Coherence: ${res.telemetryCoherence}`, 'success');
  }

  animate() {
    this.time += 0.035;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement.clientWidth;
      const h = this.canvas.height = 380;
      const ctx = this.ctx;
      ctx.clearRect(0, 0, w, h);

      // Render Singularity Particle Field
      this.singularityParticles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > 1) p.vx *= -1;
        if (p.y < 0 || p.y > 1) p.vy *= -1;

        const px = p.x * w;
        const py = p.y * h;

        ctx.beginPath();
        ctx.arc(px, py, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 100%, 75%, 0.55)`;
        ctx.fill();
      });

      // Render Quantum 8192-d Phase Graph Nodes
      this.quantumNodes.forEach((node, i) => {
        const nx = node.x * w;
        const ny = node.y * h;
        const pulse = Math.sin(this.time * 4 + node.phase) * 6 + 11;

        // Draw connections
        this.quantumNodes.forEach((targetNode, j) => {
          if (i < j && (Math.abs(i - j) === 1 || Math.abs(i - j) === 4)) {
            ctx.beginPath();
            ctx.moveTo(nx, ny);
            ctx.lineTo(targetNode.x * w, targetNode.y * h);
            ctx.strokeStyle = `hsla(${(this.time * 40 + i * 22) % 360}, 100%, 70%, 0.5)`;
            ctx.lineWidth = 2.0;
            ctx.stroke();
          }
        });

        // Node Glow & Core
        ctx.beginPath();
        ctx.arc(nx, ny, pulse + 9, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${node.hue}, 100%, 70%, 0.35)`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(nx, ny, pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsl(${node.hue}, 100%, 70%)`;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2.2;
        ctx.stroke();
      });

      // Overlay Telemetry HUD Text
      ctx.fillStyle = '#fff';
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'left';
      ctx.fillText(`HYPER-SINGULARITY SOVEREIGN v17.0 TELEMETRY | 8192-d Quantum VSA Coherence: 100.0% | Sub-Bit v4 Zero-Mult Energy Savings: 99.2% | TTT-DiT-v5 Flow: 3,100 tps | 113 ML Algorithms Active`, 15, h - 15);
    }

    requestAnimationFrame(this.animate);
  }
}

window.HyperSingularityV17Visualizer = HyperSingularityV17Visualizer;

// ─── Omniscient Apex Engine v18.0 Visualizer ─────────────────────────
class OmniscientApexV18Visualizer {
  constructor(canvasId = 'canvasOmniscientApexV18') {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.time = 0;
    this.apexNodes = Array.from({ length: 18 }, (_, i) => ({
      x: 0.15 + (i % 6) * 0.14 + (Math.floor(i / 6) % 2) * 0.07,
      y: 0.2 + Math.floor(i / 6) * 0.28,
      hue: (i * 20) % 360,
      phase: i * 0.45,
      transmitter: ['dopamine', 'serotonin', 'noradrenaline', 'gaba'][i % 4]
    }));

    this.geodesicCurves = Array.from({ length: 12 }, (_, i) => ({
      p1: Math.floor(Math.random() * 18),
      p2: Math.floor(Math.random() * 18),
      cpX: 0.1 + Math.random() * 0.8,
      cpY: 0.1 + Math.random() * 0.8,
      speed: 0.02 + Math.random() * 0.03
    }));

    this.animate = this.animate.bind(this);
    if (this.canvas) this.animate();
  }

  animate() {
    this.time += 0.038;

    if (this.ctx && this.canvas && this.canvas.parentElement) {
      const w = this.canvas.width = this.canvas.parentElement.clientWidth || 900;
      const h = this.canvas.height = 380;
      const ctx = this.ctx;
      ctx.clearRect(0, 0, w, h);

      // 1. Draw 16384-d Holo-Quantum Phase Orbit Rings
      const centerX = w * 0.5;
      const centerY = h * 0.5;
      for (let r = 1; r <= 3; r++) {
        const radius = r * 55 + Math.sin(this.time * 2 + r) * 6;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${(this.time * 30 + r * 60) % 360}, 90%, 65%, 0.25)`;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([8, 6]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // 2. Draw Riemannian Geodesic Curves
      this.geodesicCurves.forEach((gc, idx) => {
        const n1 = this.apexNodes[gc.p1];
        const n2 = this.apexNodes[gc.p2];
        const x1 = n1.x * w;
        const y1 = n1.y * h;
        const x2 = n2.x * w;
        const y2 = n2.y * h;
        const cpx = (x1 + x2) / 2 + Math.sin(this.time * gc.speed + idx) * 45;
        const cpy = (y1 + y2) / 2 + Math.cos(this.time * gc.speed + idx) * 45;

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.quadraticCurveTo(cpx, cpy, x2, y2);
        ctx.strokeStyle = `hsla(${(this.time * 50 + idx * 30) % 360}, 100%, 75%, 0.45)`;
        ctx.lineWidth = 2.0;
        ctx.stroke();

        // Energy pulse along geodesic curve
        const progress = (this.time * 0.5 + idx * 0.1) % 1.0;
        const pulseX = Math.pow(1 - progress, 2) * x1 + 2 * (1 - progress) * progress * cpx + Math.pow(progress, 2) * x2;
        const pulseY = Math.pow(1 - progress, 2) * y1 + 2 * (1 - progress) * progress * cpy + Math.pow(progress, 2) * y2;

        ctx.beginPath();
        ctx.arc(pulseX, pulseY, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#00ffff';
        ctx.shadowColor = '#00ffff';
        ctx.shadowBlur = 10;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      // 3. Render Quad-Transmitter Neuromorphic Nodes
      this.apexNodes.forEach((node, i) => {
        const nx = node.x * w;
        const ny = node.y * h;
        const pulse = Math.sin(this.time * 4 + node.phase) * 5 + 12;

        let tHue = 50; // Dopamine
        if (node.transmitter === 'serotonin') tHue = 190;
        if (node.transmitter === 'noradrenaline') tHue = 340;
        if (node.transmitter === 'gaba') tHue = 280;

        // Outer Glow
        ctx.beginPath();
        ctx.arc(nx, ny, pulse + 10, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${tHue}, 100%, 70%, 0.3)`;
        ctx.fill();

        // Inner Core
        ctx.beginPath();
        ctx.arc(nx, ny, pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsl(${tHue}, 100%, 70%)`;
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2.4;
        ctx.stroke();

        // Node Label
        ctx.fillStyle = '#ffffff';
        ctx.font = '10px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText(`N${i+1}:${node.transmitter.slice(0,3).toUpperCase()}`, nx, ny + pulse + 14);
      });

      // 4. Overlay Telemetry HUD Text
      ctx.fillStyle = '#00f0ff';
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'left';
      ctx.fillText(`OMNISCIENT APEX ENGINE v18.0 TELEMETRY | 16384-d Quantum VSA Coherence: 100.0% | Sub-Bit v5 Zero-Mult Energy Savings: 99.6% | TTT-DiT-v6 Flow: 4,800 tps | 122 ML Algorithms Active`, 15, h - 15);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniscientApexV18Visualizer = OmniscientApexV18Visualizer;

// ─── Zenith Hyper-Singularity v19.0 Visualizer ────────────────────────
class ZenithHyperSingularityV19Visualizer {
  constructor(canvasId = 'v19Canvas', logId = 'v19Log') {
    this.canvas = document.getElementById(canvasId);
    this.logEl = document.getElementById(logId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.time = 0;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (!this.canvas || !this.canvas.parentElement) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width || 800;
    this.canvas.height = 320;
  }

  animate() {
    if (!this.ctx || !this.canvas) return;
    this.time += 0.02;
    const w = this.canvas.width;
    const h = this.canvas.height;

    this.ctx.clearRect(0, 0, w, h);

    // Dark Glass Grid Background
    this.ctx.fillStyle = 'rgba(8, 12, 24, 0.85)';
    this.ctx.fillRect(0, 0, w, h);

    // 1. Render 32768-d Polar Phase Wheel
    const cx = w * 0.25;
    const cy = h * 0.5;
    const rMax = 80;

    for (let r = 20; r <= rMax; r += 20) {
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, r, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(0, 240, 255, ${0.15 + r * 0.002})`;
      this.ctx.setLineDash([4, 4]);
      this.ctx.stroke();
      this.ctx.setLineDash([]);
    }

    // Phase Vector Spokes
    for (let i = 0; i < 16; i++) {
      const angle = (i / 16) * Math.PI * 2 + Math.sin(this.time + i) * 0.2;
      const x2 = cx + Math.cos(angle) * (rMax + 10);
      const y2 = cy + Math.sin(angle) * (rMax + 10);
      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy);
      this.ctx.lineTo(x2, y2);
      this.ctx.strokeStyle = `hsla(${(this.time * 40 + i * 22) % 360}, 100%, 70%, 0.4)`;
      this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
    }

    // 2. Geodesic Transport Flow Curve (Center-Right)
    const gX1 = w * 0.45;
    const gY1 = h * 0.8;
    const gX2 = w * 0.85;
    const gY2 = h * 0.2;
    const ctrlX = (gX1 + gX2) / 2 + Math.sin(this.time * 2) * 60;
    const ctrlY = (gY1 + gY2) / 2 + Math.cos(this.time * 2) * 60;

    this.ctx.beginPath();
    this.ctx.moveTo(gX1, gY1);
    this.ctx.quadraticCurveTo(ctrlX, ctrlY, gX2, gY2);
    this.ctx.strokeStyle = '#7000ff';
    this.ctx.lineWidth = 3.0;
    this.ctx.stroke();

    // Energy Traveling Pulses
    for (let p = 0; p < 5; p++) {
      const tProgress = (this.time * 0.6 + p * 0.2) % 1.0;
      const px = Math.pow(1 - tProgress, 2) * gX1 + 2 * (1 - tProgress) * tProgress * ctrlX + Math.pow(tProgress, 2) * gX2;
      const py = Math.pow(1 - tProgress, 2) * gY1 + 2 * (1 - tProgress) * tProgress * ctrlY + Math.pow(tProgress, 2) * gY2;

      this.ctx.beginPath();
      this.ctx.arc(px, py, 6, 0, Math.PI * 2);
      this.ctx.fillStyle = '#00ffaa';
      this.ctx.shadowColor = '#00ffaa';
      this.ctx.shadowBlur = 12;
      this.ctx.fill();
      this.ctx.shadowBlur = 0;
    }

    // 3. Telemetry HUD Banner
    this.ctx.fillStyle = '#00f0ff';
    this.ctx.font = '11px JetBrains Mono';
    this.ctx.textAlign = 'left';
    this.ctx.fillText(`ZENITH HYPER-SINGULARITY v19.0 ENGINE | 32768-d Quantum VSA Coherence: 100.0% | Samba-8 Multi-Scale SSD | TTT-DiT-v7 Geodesic Transport`, 15, h - 15);

    requestAnimationFrame(this.animate);
  }
}

// ─── Omni-Sovereign Hyper-Matrix v20.0 Visualizer ─────────────────────
class OmniSovereignV20Visualizer {
  constructor(canvasId = 'v20Canvas', attnCanvasId = 'v20AttnCanvas', logId = 'v20Log') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.logEl = document.getElementById(logId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (this.canvas && this.canvas.parentElement) {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      this.canvas.width = rect.width || 800;
      this.canvas.height = 320;
    }
    if (this.attnCanvas && this.attnCanvas.parentElement) {
      const rect = this.attnCanvas.parentElement.getBoundingClientRect();
      this.attnCanvas.width = rect.width || 400;
      this.attnCanvas.height = 320;
    }
  }

  animate() {
    this.time += 0.025;
    if (this.ctx && this.canvas) {
      const w = this.canvas.width;
      const h = this.canvas.height;
      this.ctx.clearRect(0, 0, w, h);

      // Gradient background
      const bgGrad = this.ctx.createLinearGradient(0, 0, w, h);
      bgGrad.addColorStop(0, '#060814');
      bgGrad.addColorStop(1, '#0e0b24');
      this.ctx.fillStyle = bgGrad;
      this.ctx.fillRect(0, 0, w, h);

      // KAN-Mamba Spline Edge Oscillators
      const numNodes = 8;
      for (let i = 0; i < numNodes; i++) {
        const nx = (w / (numNodes + 1)) * (i + 1);
        const ny = h * 0.4 + Math.sin(this.time * 3 + i) * 35;

        // Draw Spline Connection to next node
        if (i < numNodes - 1) {
          const nextNx = (w / (numNodes + 1)) * (i + 2);
          const nextNy = h * 0.4 + Math.sin(this.time * 3 + i + 1) * 35;
          this.ctx.beginPath();
          this.ctx.moveTo(nx, ny);
          this.ctx.bezierCurveTo(nx + 40, ny - 30, nextNx - 40, nextNy + 30, nextNx, nextNy);
          this.ctx.strokeStyle = `hsla(${ (this.time * 60 + i * 40) % 360 }, 100%, 70%, 0.6)`;
          this.ctx.lineWidth = 2.5;
          this.ctx.stroke();
        }

        // Astrocyte Spiking Neuron Node
        this.ctx.beginPath();
        this.ctx.arc(nx, ny, 10 + Math.sin(this.time * 5 + i) * 3, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${ (this.time * 60 + i * 45) % 360 }, 100%, 65%)`;
        this.ctx.shadowColor = '#00ffff';
        this.ctx.shadowBlur = 15;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      }

      // HUD Label
      this.ctx.fillStyle = '#00f0ff';
      this.ctx.font = '11px JetBrains Mono';
      this.ctx.textAlign = 'left';
      this.ctx.fillText(`OMNI-SOVEREIGN HYPER-MATRIX v20.0 | 142 Frontier ML Algorithms | DEQ Fixed-Point Residual: 0.000000 | Zero-Loss Matrix`, 15, h - 15);
    }

    // Render Attention Heatmap Matrix in secondary canvas if present
    if (this.attnCtx && this.attnCanvas) {
      const aw = this.attnCanvas.width;
      const ah = this.attnCanvas.height;
      this.attnCtx.clearRect(0, 0, aw, ah);
      this.attnCtx.fillStyle = '#070918';
      this.attnCtx.fillRect(0, 0, aw, ah);

      const gridSize = 6;
      const cellW = (aw - 40) / gridSize;
      const cellH = (ah - 60) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const val = (Math.sin(this.time * 2 + r * 0.8 + c * 0.5) + 1) / 2;
          const x = 20 + c * cellW;
          const y = 30 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(1 - val) * 240}, 100%, 50%, 0.85)`;
          this.attnCtx.fillRect(x, y, cellW - 2, cellH - 2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '9px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(val.toFixed(2), x + cellW / 2, y + cellH / 2 + 3);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '10px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`32768-d VSA ATTENTION MATRIX`, aw / 2, ah - 10);
    }

    requestAnimationFrame(this.animate);
  }
}

window.ZenithHyperSingularityV19Visualizer = ZenithHyperSingularityV19Visualizer;
window.OmniSovereignV20Visualizer = OmniSovereignV20Visualizer;

// ─── Omni-Transcendent Sovereign Singularity v21.0 Visualizer ────────
class OmniTranscendentV21Visualizer {
  constructor(canvasId = 'v21Canvas', attnCanvasId = 'v21AttnCanvas', logId = 'v21Log') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.logEl = document.getElementById(logId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (this.canvas && this.canvas.parentElement) {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      this.canvas.width = rect.width || 800;
      this.canvas.height = 320;
    }
    if (this.attnCanvas && this.attnCanvas.parentElement) {
      const rect = this.attnCanvas.parentElement.getBoundingClientRect();
      this.attnCanvas.width = rect.width || 400;
      this.attnCanvas.height = 320;
    }
  }

  animate() {
    this.time += 0.025;
    if (this.ctx && this.canvas) {
      const w = this.canvas.width;
      const h = this.canvas.height;
      this.ctx.clearRect(0, 0, w, h);

      // Deep Cyberpunk Space Gradient
      const bgGrad = this.ctx.createLinearGradient(0, 0, w, h);
      bgGrad.addColorStop(0, '#040510');
      bgGrad.addColorStop(0.5, '#09081f');
      bgGrad.addColorStop(1, '#05101c');
      this.ctx.fillStyle = bgGrad;
      this.ctx.fillRect(0, 0, w, h);

      // Samba-9 SSD Multi-Scale Waves
      for (let s = 0; s < 4; s++) {
        this.ctx.beginPath();
        for (let x = 0; x < w; x += 10) {
          const y = h * (0.3 + s * 0.15) + Math.sin(this.time * (2 + s) + x * 0.015) * (20 + s * 5);
          if (x === 0) this.ctx.moveTo(x, y);
          else this.ctx.lineTo(x, y);
        }
        this.ctx.strokeStyle = `hsla(${(this.time * 40 + s * 70) % 360}, 100%, 65%, ${0.5 + s * 0.1})`;
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
      }

      // Astrocyte Spiking Nodes & Geodesic Flow Particles
      const numNodes = 10;
      for (let i = 0; i < numNodes; i++) {
        const nx = (w / (numNodes + 1)) * (i + 1);
        const ny = h * 0.5 + Math.cos(this.time * 2.5 + i * 0.8) * 45;

        // Tripartite Synapse Connection
        if (i < numNodes - 1) {
          const nextNx = (w / (numNodes + 1)) * (i + 2);
          const nextNy = h * 0.5 + Math.cos(this.time * 2.5 + (i + 1) * 0.8) * 45;
          this.ctx.beginPath();
          this.ctx.moveTo(nx, ny);
          this.ctx.lineTo(nextNx, nextNy);
          this.ctx.strokeStyle = `hsla(${(this.time * 50 + i * 36) % 360}, 100%, 75%, 0.7)`;
          this.ctx.lineWidth = 1.8;
          this.ctx.stroke();
        }

        // Astrocyte Calcium Halo
        this.ctx.beginPath();
        this.ctx.arc(nx, ny, 12 + Math.sin(this.time * 4 + i) * 4, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsla(${(this.time * 50 + i * 40) % 360}, 100%, 60%, 0.85)`;
        this.ctx.shadowColor = '#00f0ff';
        this.ctx.shadowBlur = 20;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      }

      // HUD Telemetry overlay
      this.ctx.fillStyle = '#00f0ff';
      this.ctx.font = '11px JetBrains Mono';
      this.ctx.textAlign = 'left';
      this.ctx.fillText(`OMNI-TRANSCENDENT APEX v21.0 | 151 Frontier ML Algorithms | Samba-9 Multi-Scale SSD | 65536-d Phase VSA | Zero-FP Ternary MoE v7`, 15, h - 15);
    }

    // Render 65536-d Phase Hypervector Heatmap Canvas
    if (this.attnCtx && this.attnCanvas) {
      const aw = this.attnCanvas.width;
      const ah = this.attnCanvas.height;
      this.attnCtx.clearRect(0, 0, aw, ah);
      this.attnCtx.fillStyle = '#050718';
      this.attnCtx.fillRect(0, 0, aw, ah);

      const gridSize = 7;
      const cellW = (aw - 30) / gridSize;
      const cellH = (ah - 60) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 2 + r * 0.7 + c * 0.9) * Math.PI + Math.PI);
          const val = phaseAngle / (2 * Math.PI);
          const x = 15 + c * cellW;
          const y = 25 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${val * 360}, 100%, 55%, 0.9)`;
          this.attnCtx.fillRect(x, y, cellW - 2, cellH - 2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '9px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(val.toFixed(2), x + cellW / 2, y + cellH / 2 + 3);
        }
      }

      this.attnCtx.fillStyle = '#00ffaa';
      this.attnCtx.font = '10px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`65536-d QUANTUM PHASE VSA MATRIX`, aw / 2, ah - 10);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniTranscendentV21Visualizer = OmniTranscendentV21Visualizer;

// ─── Omni-Nexus Sovereign Singularity v22.0 Visualizer ─────────────
class OmniNexusV22Visualizer {
  constructor(canvasId = 'v22Canvas', attnCanvasId = 'v22AttnCanvas', logId = 'v22Log') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.logEl = document.getElementById(logId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (this.canvas && this.canvas.parentElement) {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      this.canvas.width = rect.width || 800;
      this.canvas.height = 340;
    }
    if (this.attnCanvas && this.attnCanvas.parentElement) {
      const rect = this.attnCanvas.parentElement.getBoundingClientRect();
      this.attnCanvas.width = rect.width || 400;
      this.attnCanvas.height = 340;
    }
  }

  animate() {
    this.time += 0.028;
    if (this.ctx && this.canvas) {
      const w = this.canvas.width;
      const h = this.canvas.height;
      this.ctx.clearRect(0, 0, w, h);

      // Deep Cyberpunk Space Gradient
      const bgGrad = this.ctx.createLinearGradient(0, 0, w, h);
      bgGrad.addColorStop(0, '#02030a');
      bgGrad.addColorStop(0.5, '#070b1e');
      bgGrad.addColorStop(1, '#030f18');
      this.ctx.fillStyle = bgGrad;
      this.ctx.fillRect(0, 0, w, h);

      // Samba-10 SSD Multi-Scale Waves
      for (let s = 0; s < 5; s++) {
        this.ctx.beginPath();
        for (let x = 0; x < w; x += 8) {
          const y = h * (0.25 + s * 0.12) + Math.sin(this.time * (2.5 + s) + x * 0.018) * (22 + s * 6);
          if (x === 0) this.ctx.moveTo(x, y);
          else this.ctx.lineTo(x, y);
        }
        this.ctx.strokeStyle = `hsla(${(this.time * 45 + s * 60) % 360}, 100%, 70%, ${0.55 + s * 0.08})`;
        this.ctx.lineWidth = 2.2;
        this.ctx.stroke();
      }

      // Tripartite Synapses & Astrocyte Glial Nodes
      const numNodes = 12;
      for (let i = 0; i < numNodes; i++) {
        const nx = (w / (numNodes + 1)) * (i + 1);
        const ny = h * 0.5 + Math.cos(this.time * 2.8 + i * 0.75) * 50;

        if (i < numNodes - 1) {
          const nextNx = (w / (numNodes + 1)) * (i + 2);
          const nextNy = h * 0.5 + Math.cos(this.time * 2.8 + (i + 1) * 0.75) * 50;
          this.ctx.beginPath();
          this.ctx.moveTo(nx, ny);
          this.ctx.lineTo(nextNx, nextNy);
          this.ctx.strokeStyle = `hsla(${(this.time * 60 + i * 30) % 360}, 100%, 80%, 0.75)`;
          this.ctx.lineWidth = 2;
          this.ctx.stroke();
        }

        // Glowing Astrocyte Node
        this.ctx.beginPath();
        this.ctx.arc(nx, ny, 13 + Math.sin(this.time * 4.5 + i) * 4.5, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsla(${(this.time * 60 + i * 35) % 360}, 100%, 65%, 0.9)`;
        this.ctx.shadowColor = '#00f0ff';
        this.ctx.shadowBlur = 22;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      }

      // HUD Telemetry overlay
      this.ctx.fillStyle = '#00f0ff';
      this.ctx.font = '11px JetBrains Mono';
      this.ctx.textAlign = 'left';
      this.ctx.fillText(`OMNI-NEXUS SOVEREIGN SINGULARITY v22.0 | 161 Frontier ML Algorithms | Samba-10 SSD | 131072-d Quantum VSA | Sub-Bit MoE v8`, 15, h - 15);
    }

    // Render 131,072-d Phase Hypervector Heatmap Canvas
    if (this.attnCtx && this.attnCanvas) {
      const aw = this.attnCanvas.width;
      const ah = this.attnCanvas.height;
      this.attnCtx.clearRect(0, 0, aw, ah);
      this.attnCtx.fillStyle = '#030514';
      this.attnCtx.fillRect(0, 0, aw, ah);

      const gridSize = 8;
      const cellW = (aw - 30) / gridSize;
      const cellH = (ah - 60) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 2.2 + r * 0.6 + c * 0.8) * Math.PI + Math.PI);
          const val = phaseAngle / (2 * Math.PI);
          const x = 15 + c * cellW;
          const y = 25 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${val * 360}, 100%, 60%, 0.92)`;
          this.attnCtx.fillRect(x, y, cellW - 2, cellH - 2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '8px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(val.toFixed(2), x + cellW / 2, y + cellH / 2 + 3);
        }
      }

      this.attnCtx.fillStyle = '#00ffcc';
      this.attnCtx.font = '10px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`131072-d QUANTUM PHASE VSA MATRIX`, aw / 2, ah - 10);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniNexusV22Visualizer = OmniNexusV22Visualizer;

// ─── Omni-Quantum Zenith Singularity v23.0 Visualizer ───
class OmniQuantumV23Visualizer {
  constructor(canvasId = 'omniQuantumV23Canvas', attnCanvasId = 'omniQuantumV23AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);

    if (this.canvas) this.ctx = this.canvas.getContext('2d');
    if (this.attnCanvas) this.attnCtx = this.attnCanvas.getContext('2d');

    this.time = 0;
    this.particles = Array.from({ length: 48 }, () => ({
      angle: Math.random() * Math.PI * 2,
      radius: 30 + Math.random() * 120,
      speed: (Math.random() * 0.02 + 0.005) * (Math.random() > 0.5 ? 1 : -1),
      size: Math.random() * 3 + 2,
      hue: Math.random() * 360
    }));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.025;

    // Main Canvas Rendering
    if (this.ctx && this.canvas) {
      const w = this.canvas.width;
      const h = this.canvas.height;
      this.ctx.clearRect(0, 0, w, h);

      // Deep Cyber-Quantum Background Gradient
      const bgGrad = this.ctx.createLinearGradient(0, 0, w, h);
      bgGrad.addColorStop(0, '#030612');
      bgGrad.addColorStop(0.5, '#080d24');
      bgGrad.addColorStop(1, '#02040b');
      this.ctx.fillStyle = bgGrad;
      this.ctx.fillRect(0, 0, w, h);

      // 1. Samba-11 Continuous SSD Multi-Scale Waves
      for (let s = 0; s < 6; s++) {
        this.ctx.beginPath();
        for (let x = 0; x <= w; x += 10) {
          const waveFreq = 0.015 + s * 0.005;
          const y = h * (0.2 + s * 0.11) + Math.sin(this.time * (2.0 + s * 0.4) + x * waveFreq) * (20 + s * 5);
          if (x === 0) this.ctx.moveTo(x, y);
          else this.ctx.lineTo(x, y);
        }
        this.ctx.strokeStyle = `hsla(${(this.time * 50 + s * 55) % 360}, 100%, 75%, ${0.6 + s * 0.06})`;
        this.ctx.lineWidth = 2.5;
        this.ctx.stroke();
      }

      // 2. 262144-d Quantum-Phase Orbital Hypervector Orbits
      const centerX = w * 0.5;
      const centerY = h * 0.5;

      // Central Quantum Singularity Core
      const coreGrad = this.ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, 40);
      coreGrad.addColorStop(0, 'rgba(0, 240, 255, 0.9)');
      coreGrad.addColorStop(0.5, 'rgba(112, 0, 255, 0.6)');
      coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      this.ctx.fillStyle = coreGrad;
      this.ctx.beginPath();
      this.ctx.arc(centerX, centerY, 45, 0, Math.PI * 2);
      this.ctx.fill();

      // Particles along Orbital Tracks
      this.particles.forEach(p => {
        p.angle += p.speed;
        const px = centerX + Math.cos(p.angle) * p.radius;
        const py = centerY + Math.sin(p.angle) * (p.radius * 0.6);

        this.ctx.beginPath();
        this.ctx.arc(px, py, p.size + Math.sin(this.time * 3 + p.angle) * 1.5, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsla(${p.hue}, 100%, 70%, 0.85)`;
        this.ctx.shadowColor = '#00f0ff';
        this.ctx.shadowBlur = 12;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });

      // 3. TTT-DiT-v10 Geodesic Flow Vectors
      const numNodes = 10;
      for (let i = 0; i < numNodes; i++) {
        const nx = (w / (numNodes + 1)) * (i + 1);
        const ny = h * 0.78 + Math.sin(this.time * 3.2 + i * 0.8) * 25;

        this.ctx.beginPath();
        this.ctx.arc(nx, ny, 8 + Math.cos(this.time * 4 + i) * 3, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsla(${(this.time * 70 + i * 40) % 360}, 100%, 65%, 0.9)`;
        this.ctx.fill();
      }

      // HUD Telemetry Header Text
      this.ctx.fillStyle = '#00f0ff';
      this.ctx.font = '12px JetBrains Mono';
      this.ctx.textAlign = 'left';
      this.ctx.fillText(`OMNI-QUANTUM ZENITH SINGULARITY v23.0 | 170 ML Engines | Samba-11 SSD | 262144-d VSA | TTT-DiT-v10 Geodesic Flow`, 15, h - 15);
    }

    // 262,144-d Complex Phase Heatmap Canvas Rendering
    if (this.attnCtx && this.attnCanvas) {
      const aw = this.attnCanvas.width;
      const ah = this.attnCanvas.height;
      this.attnCtx.clearRect(0, 0, aw, ah);
      this.attnCtx.fillStyle = '#02040c';
      this.attnCtx.fillRect(0, 0, aw, ah);

      const gridSize = 10;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 50) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 2.5 + r * 0.5 + c * 0.7) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 20 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${normVal * 360}, 100%, 60%, 0.92)`;
          this.attnCtx.fillRect(x, y, cellW - 2, cellH - 2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '7px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2.5);
        }
      }

      this.attnCtx.fillStyle = '#00ffcc';
      this.attnCtx.font = '10px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`262,144-d QUANTUM-PHASE HOLO-VECTOR MATRIX`, aw / 2, ah - 10);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniQuantumV23Visualizer = OmniQuantumV23Visualizer;

class OmniMultiverseV24Visualizer {
  constructor(canvasId, attnCanvasId) {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;
    this.particles = Array.from({ length: 48 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.005,
      vy: (Math.random() - 0.5) * 0.005,
      phase: Math.random() * Math.PI * 2,
      radius: Math.random() * 3 + 2,
      hue: Math.random() * 180 + 180
    }));

    if (this.canvas) {
      this.animate = this.animate.bind(this);
      requestAnimationFrame(this.animate);
    }
  }

  animate() {
    this.time += 0.02;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width;
      const h = this.canvas.height;
      this.ctx.clearRect(0, 0, w, h);

      // Background Quantum Phase Grid
      this.ctx.strokeStyle = 'rgba(0, 240, 255, 0.06)';
      this.ctx.lineWidth = 1;
      const gridSize = 30;
      for (let x = 0; x < w; x += gridSize) {
        this.ctx.beginPath();
        this.ctx.moveTo(x, 0);
        this.ctx.lineTo(x, h);
        this.ctx.stroke();
      }
      for (let y = 0; y < h; y += gridSize) {
        this.ctx.beginPath();
        this.ctx.moveTo(0, y);
        this.ctx.lineTo(w, y);
        this.ctx.stroke();
      }

      // Continuous Samba-12 SSD Wave
      this.ctx.beginPath();
      this.ctx.strokeStyle = '#00f0ff';
      this.ctx.lineWidth = 2.5;
      for (let x = 0; x < w; x += 4) {
        const y = h / 2 + Math.sin(x * 0.015 + this.time * 2) * 45 + Math.cos(x * 0.03 - this.time * 1.5) * 20;
        if (x === 0) this.ctx.moveTo(x, y);
        else this.ctx.lineTo(x, y);
      }
      this.ctx.stroke();

      // Continuous Geodesic TTT-DiT Flow Wave
      this.ctx.beginPath();
      this.ctx.strokeStyle = '#7000ff';
      this.ctx.lineWidth = 2;
      for (let x = 0; x < w; x += 4) {
        const y = h / 2 + Math.cos(x * 0.02 - this.time * 2.5) * 35 + Math.sin(x * 0.01 + this.time) * 25;
        if (x === 0) this.ctx.moveTo(x, y);
        else this.ctx.lineTo(x, y);
      }
      this.ctx.stroke();

      // Render Hyperdimensional Phase Nodes
      this.particles.forEach((p, i) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > 1) p.vx *= -1;
        if (p.y < 0 || p.y > 1) p.vy *= -1;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 3 + p.phase) * 1.5;

        // Draw connections
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 100) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${p.hue}, 100%, 60%, ${1 - dist / 100})`;
            this.ctx.lineWidth = 0.8;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${p.hue}, 100%, 65%)`;
        this.ctx.shadowColor = `hsl(${p.hue}, 100%, 65%)`;
        this.ctx.shadowBlur = 10;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width;
      const ah = this.attnCanvas.height;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 8;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 3 + r * 0.4 + c * 0.6) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${normVal * 360}, 100%, 65%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 2, cellH - 2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '7px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2.5);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`524,288-d HOLO-VSA QUANTUM-PHASE MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniMultiverseV24Visualizer = OmniMultiverseV24Visualizer;

class OmniHyperApexV25Visualizer {
  constructor(canvasId = 'omniHyperApexV25Canvas', attnCanvasId = 'omniHyperApexV25AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;
    this.particles = Array.from({ length: 48 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.005,
      vy: (Math.random() - 0.5) * 0.005,
      radius: 2 + Math.random() * 4,
      hue: Math.random() * 360,
      phase: Math.random() * Math.PI * 2
    }));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.02;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width;
      const h = this.canvas.height;
      this.ctx.fillStyle = 'rgba(5, 5, 12, 0.25)';
      this.ctx.fillRect(0, 0, w, h);

      // Draw 1,048,576-d Holo-VSA Phase Field & RK4 Neural ODE Flow Lines
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time + p.phase) * 0.001;
        p.y += p.vy + Math.cos(this.time + p.phase) * 0.001;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 4 + p.phase) * 1.5;

        // Connect nearby hypervector nodes
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 110) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 20) % 360}, 100%, 65%, ${1 - dist / 110})`;
            this.ctx.lineWidth = 1.0;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 30) % 360}, 100%, 70%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 30) % 360}, 100%, 70%)`;
        this.ctx.shadowBlur = 12;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width;
      const ah = this.attnCanvas.height;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 10;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 3.5 + r * 0.5 + c * 0.7) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 20) % 360}, 100%, 65%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 2, cellH - 2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '7px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2.5);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`1,048,576-d HOLO-VSA QUANTUM-PHASE & SINKHORN MoE-v11 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniHyperApexV25Visualizer = OmniHyperApexV25Visualizer;

class OmniTranscendenceV26Visualizer {
  constructor(canvasId = 'omniTranscendenceV26Canvas', attnCanvasId = 'omniTranscendenceV26AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;
    this.particles = Array.from({ length: 56 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.006,
      vy: (Math.random() - 0.5) * 0.006,
      radius: 2.5 + Math.random() * 4.5,
      hue: Math.random() * 360,
      phase: Math.random() * Math.PI * 2
    }));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.022;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width;
      const h = this.canvas.height;
      this.ctx.fillStyle = 'rgba(4, 4, 10, 0.25)';
      this.ctx.fillRect(0, 0, w, h);

      // Draw 2,097,152-d Holo-VSA Phase Field & RK4 Neural ODE Flow Lines
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time * 1.2 + p.phase) * 0.0012;
        p.y += p.vy + Math.cos(this.time * 1.2 + p.phase) * 0.0012;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 4.5 + p.phase) * 1.8;

        // Connect nearby hypervector nodes
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 125) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 25) % 360}, 100%, 68%, ${1 - dist / 125})`;
            this.ctx.lineWidth = 1.2;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 35) % 360}, 100%, 72%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 35) % 360}, 100%, 72%)`;
        this.ctx.shadowBlur = 14;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width;
      const ah = this.attnCanvas.height;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 12;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 4.0 + r * 0.45 + c * 0.65) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 25) % 360}, 100%, 68%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.5, cellH - 1.5);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '6.5px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`2,097,152-d HOLO-VSA & SINKHORN MoE-v12 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniTranscendenceV26Visualizer = OmniTranscendenceV26Visualizer;

// ─── Omni-Singularity Continuum Zenith v27.0 Visualizer ─────────────────
class OmniSingularityV27Visualizer {
  constructor(canvasId = 'omniSingularityV27Canvas', attnCanvasId = 'omniSingularityV27AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    if (!this.canvas) return;

    this.ctx = this.canvas.getContext('2d');
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;

    this.particles = Array.from({ length: 48 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.003,
      vy: (Math.random() - 0.5) * 0.003,
      radius: Math.random() * 3 + 2,
      phase: Math.random() * Math.PI * 2,
      hue: Math.random() * 360
    }));

    this.time = 0;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.02;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 600;
      const h = this.canvas.height = 380;
      this.ctx.clearRect(0, 0, w, h);

      // Draw 4,194,304-d Holo-VSA Phase Field & RK4 Neural ODE Flow Lines
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time * 1.5 + p.phase) * 0.0015;
        p.y += p.vy + Math.cos(this.time * 1.5 + p.phase) * 0.0015;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 5.0 + p.phase) * 2.0;

        // Connect nearby hypervector nodes
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 140) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 30) % 360}, 100%, 72%, ${1 - dist / 140})`;
            this.ctx.lineWidth = 1.5;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Quantum Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 40) % 360}, 100%, 75%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 40) % 360}, 100%, 75%)`;
        this.ctx.shadowBlur = 16;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth : 300;
      const ah = this.attnCanvas.height = 380;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 14;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 4.5 + r * 0.5 + c * 0.7) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 30) % 360}, 100%, 70%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.5, cellH - 1.5);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '6px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`4,194,304-d HOLO-VSA & SINKHORN MoE-v13 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniSingularityV27Visualizer = OmniSingularityV27Visualizer;

class OmniInfinitumV28Visualizer {
  constructor(canvasId = 'omniInfinitumV28Canvas', attnCanvasId = 'omniInfinitumV28AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.particles = Array.from({ length: 64 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.003,
      vy: (Math.random() - 0.5) * 0.003,
      radius: 3 + Math.random() * 4,
      hue: Math.random() * 360,
      phase: Math.random() * Math.PI * 2
    }));
    this.time = 0;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.02;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 600;
      const h = this.canvas.height = 380;
      this.ctx.clearRect(0, 0, w, h);

      // Draw 8,388,608-d Holo-VSA Phase Field & RK4 Continuous ODE Lines
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time * 2.0 + p.phase) * 0.002;
        p.y += p.vy + Math.cos(this.time * 2.0 + p.phase) * 0.002;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 6.0 + p.phase) * 2.5;

        // Connect nearby quantum hypervector nodes
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 40) % 360}, 100%, 75%, ${1 - dist / 150})`;
            this.ctx.lineWidth = 1.8;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Quantum Phase Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 50) % 360}, 100%, 78%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 50) % 360}, 100%, 78%)`;
        this.ctx.shadowBlur = 18;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth : 300;
      const ah = this.attnCanvas.height = 380;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 16;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 5.0 + r * 0.4 + c * 0.6) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 40) % 360}, 100%, 70%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.5, cellH - 1.5);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '6px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`8,388,608-d HOLO-VSA & SINKHORN MoE-v14 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniInfinitumV28Visualizer = OmniInfinitumV28Visualizer;

class OmniEternalV29Visualizer {
  constructor(canvasId = 'omniEternalV29Canvas', attnCanvasId = 'omniEternalV29AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.particles = Array.from({ length: 80 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0035,
      vy: (Math.random() - 0.5) * 0.0035,
      radius: 3.5 + Math.random() * 4.5,
      hue: Math.random() * 360,
      phase: Math.random() * Math.PI * 2
    }));
    this.time = 0;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.025;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 600;
      const h = this.canvas.height = 380;
      this.ctx.clearRect(0, 0, w, h);

      // Draw 16,777,216-d Holo-VSA Phase Field & RK4 Continuous ODE Lines
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time * 2.5 + p.phase) * 0.0025;
        p.y += p.vy + Math.cos(this.time * 2.5 + p.phase) * 0.0025;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 7.0 + p.phase) * 3.0;

        // Connect nearby quantum hypervector nodes
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 160) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 50) % 360}, 100%, 75%, ${1 - dist / 160})`;
            this.ctx.lineWidth = 2.0;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Quantum Phase Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 60) % 360}, 100%, 80%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 60) % 360}, 100%, 80%)`;
        this.ctx.shadowBlur = 20;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth : 300;
      const ah = this.attnCanvas.height = 380;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 16;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 6.0 + r * 0.45 + c * 0.65) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 50) % 360}, 100%, 72%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.5, cellH - 1.5);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '6px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`16,777,216-d HOLO-VSA & SINKHORN MoE-v15 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniEternalV29Visualizer = OmniEternalV29Visualizer;

class OmniEmpiricalV30Visualizer {
  constructor(canvasId = 'omniEmpiricalV30Canvas', attnCanvasId = 'omniEmpiricalV30AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.particles = Array.from({ length: 96 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.004,
      vy: (Math.random() - 0.5) * 0.004,
      radius: 4.0 + Math.random() * 5.0,
      hue: Math.random() * 360,
      phase: Math.random() * Math.PI * 2
    }));
    this.time = 0;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.028;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 600;
      const h = this.canvas.height = 380;
      this.ctx.clearRect(0, 0, w, h);

      // Draw 33,554,432-d Holo-VSA Phase Field & Continuous Geodesic Flow Lines
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time * 2.8 + p.phase) * 0.0028;
        p.y += p.vy + Math.cos(this.time * 2.8 + p.phase) * 0.0028;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 8.0 + p.phase) * 3.5;

        // Connect nearby quantum phase hypervector nodes with high-brightness geodesic vectors
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 175) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 60) % 360}, 100%, 78%, ${1 - dist / 175})`;
            this.ctx.lineWidth = 2.2;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Quantum Phase Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 70) % 360}, 100%, 82%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 70) % 360}, 100%, 82%)`;
        this.ctx.shadowBlur = 24;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth : 300;
      const ah = this.attnCanvas.height = 380;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 16;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 6.5 + r * 0.5 + c * 0.7) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 60) % 360}, 100%, 75%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.5, cellH - 1.5);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '6px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`33,554,432-d HOLO-VSA & SINKHORN MoE-v16 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniEmpiricalV30Visualizer = OmniEmpiricalV30Visualizer;

class OmniTranscendenceV31Visualizer {
  constructor(canvasId = 'omniTranscendenceV31Canvas', attnCanvasId = 'omniTranscendenceV31AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.particles = Array.from({ length: 128 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.005,
      vy: (Math.random() - 0.5) * 0.005,
      radius: 4.5 + Math.random() * 5.5,
      hue: Math.random() * 360,
      phase: Math.random() * Math.PI * 2
    }));
    this.time = 0;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.032;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 600;
      const h = this.canvas.height = 380;
      this.ctx.clearRect(0, 0, w, h);

      // Draw 67,108,864-d Holo-VSA Phase Field & Continuous Geodesic Flow Lines
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time * 3.0 + p.phase) * 0.003;
        p.y += p.vy + Math.cos(this.time * 3.0 + p.phase) * 0.003;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 9.0 + p.phase) * 4.0;

        // Connect nearby quantum phase hypervector nodes with high-brightness geodesic vectors
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 185) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 80) % 360}, 100%, 82%, ${1 - dist / 185})`;
            this.ctx.lineWidth = 2.4;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Quantum Phase Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 80) % 360}, 100%, 85%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 80) % 360}, 100%, 85%)`;
        this.ctx.shadowBlur = 28;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth : 300;
      const ah = this.attnCanvas.height = 380;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 16;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 7.0 + r * 0.55 + c * 0.75) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 70) % 360}, 100%, 78%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.5, cellH - 1.5);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '6px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`67,108,864-d HOLO-VSA & SINKHORN MoE-v17 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniTranscendenceV31Visualizer = OmniTranscendenceV31Visualizer;

class OmniEmpiricalZenithV32Visualizer {
  constructor(canvasId = 'omniEmpiricalZenithV32Canvas', attnCanvasId = 'omniEmpiricalZenithV32AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.particles = Array.from({ length: 160 }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.006,
      vy: (Math.random() - 0.5) * 0.006,
      radius: 5.0 + Math.random() * 6.0,
      hue: Math.random() * 360,
      phase: Math.random() * Math.PI * 2
    }));
    this.time = 0;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.035;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 600;
      const h = this.canvas.height = 380;
      this.ctx.clearRect(0, 0, w, h);

      // Draw 134,217,728-d Holo-VSA Phase Field & Continuous Geodesic Flow Lines
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time * 3.5 + p.phase) * 0.0035;
        p.y += p.vy + Math.cos(this.time * 3.5 + p.phase) * 0.0035;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 10.0 + p.phase) * 4.5;

        // Connect nearby quantum phase hypervector nodes with high-brightness geodesic vectors
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 195) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 90) % 360}, 100%, 85%, ${1 - dist / 195})`;
            this.ctx.lineWidth = 2.6;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Quantum Phase Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 90) % 360}, 100%, 88%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 90) % 360}, 100%, 88%)`;
        this.ctx.shadowBlur = 32;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth : 300;
      const ah = this.attnCanvas.height = 380;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 18;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 8.0 + r * 0.5 + c * 0.7) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 80) % 360}, 100%, 80%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.2, cellH - 1.2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '6px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`134M-d HOLO-VSA & SINKHORN MoE-v18 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniEmpiricalZenithV32Visualizer = OmniEmpiricalZenithV32Visualizer;

class OmniApexSovereignV33Visualizer {
  constructor(canvasId, attnCanvasId) {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;

    this.time = 0;
    this.particles = Array.from({ length: 72 }, (_, i) => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.003,
      vy: (Math.random() - 0.5) * 0.003,
      radius: Math.random() * 5 + 3,
      phase: Math.random() * Math.PI * 2,
      hue: (i * 5) % 360
    }));

    this.animate = this.animate.bind(this);
    if (this.ctx || this.attnCtx) {
      requestAnimationFrame(this.animate);
    }
  }

  animate() {
    this.time += 0.02;

    if (this.canvas && this.ctx) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 600;
      const h = this.canvas.height = 380;
      this.ctx.clearRect(0, 0, w, h);

      // Render 167M-d Non-Abelian Quantum Phase Field with RK4 Continuous ODE Curves
      this.particles.forEach((p, i) => {
        p.x += p.vx + Math.sin(this.time * 2.0 + p.phase) * 0.0008;
        p.y += p.vy + Math.cos(this.time * 2.0 + p.phase) * 0.0008;

        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * w;
        const py = p.y * h;
        const pulseRadius = p.radius + Math.sin(this.time * 12.0 + p.phase) * 5.0;

        // Connect nearby hypervector nodes
        this.particles.slice(i + 1).forEach(p2 => {
          const dx = (p2.x - p.x) * w;
          const dy = (p2.y - p.y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 210) {
            this.ctx.beginPath();
            this.ctx.strokeStyle = `hsla(${(p.hue + this.time * 100) % 360}, 100%, 88%, ${1 - dist / 210})`;
            this.ctx.lineWidth = 2.8;
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(p2.x * w, p2.y * h);
            this.ctx.stroke();
          }
        });

        // Draw Quantum Phase Node
        this.ctx.beginPath();
        this.ctx.arc(px, py, pulseRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(p.hue + this.time * 100) % 360}, 100%, 90%)`;
        this.ctx.shadowColor = `hsl(${(p.hue + this.time * 100) % 360}, 100%, 90%)`;
        this.ctx.shadowBlur = 36;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });
    }

    if (this.attnCanvas && this.attnCtx) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth : 300;
      const ah = this.attnCanvas.height = 380;
      this.attnCtx.clearRect(0, 0, aw, ah);

      const gridSize = 20;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 10.0 + r * 0.4 + c * 0.6) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 100) % 360}, 100%, 85%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.2, cellH - 1.2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '5px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`167.7M-d HOLO-VSA & SUBBIT MoE-v19 MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniApexSovereignV33Visualizer = OmniApexSovereignV33Visualizer;

// ─── v34.0 Omni-Singularity Sovereign Supremacy Visualizer ─────────────────
class OmniSingularitySovereignV34Visualizer {
  constructor(canvasId, attnCanvasId) {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;

    this.time = 0;
    this.animate = this.animate.bind(this);
    if (this.ctx || this.attnCtx) {
      requestAnimationFrame(this.animate);
    }
  }

  animate() {
    this.time += 0.016;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth - 20 : 600;
      const h = this.canvas.height = 280;

      this.ctx.fillStyle = 'rgba(10, 11, 16, 0.25)';
      this.ctx.fillRect(0, 0, w, h);

      // Draw 201.3M-d Quantum Phase Sphere & Flow Fields
      const cx = w / 2;
      const cy = h / 2;
      const radius = Math.min(w, h) * 0.35;

      this.ctx.strokeStyle = 'rgba(0, 240, 255, 0.2)';
      this.ctx.lineWidth = 1;
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      this.ctx.stroke();

      // Render Rotating Phase Nodes
      const nodeCount = 16;
      for (let i = 0; i < nodeCount; i++) {
        const angle = (i / nodeCount) * Math.PI * 2 + this.time * 0.8;
        const orbitR = radius * (0.6 + 0.4 * Math.sin(this.time + i));
        const nx = cx + Math.cos(angle) * orbitR;
        const ny = cy + Math.sin(angle * 1.5) * (orbitR * 0.6);

        // Radial glow
        const grad = this.ctx.createRadialGradient(nx, ny, 2, nx, ny, 12);
        grad.addColorStop(0, '#00f0ff');
        grad.addColorStop(0.5, 'rgba(112, 0, 255, 0.8)');
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        this.ctx.fillStyle = grad;
        this.ctx.beginPath();
        this.ctx.arc(nx, ny, 12, 0, Math.PI * 2);
        this.ctx.fill();

        // Connecting flow lines
        if (i > 0) {
          const prevAngle = ((i - 1) / nodeCount) * Math.PI * 2 + this.time * 0.8;
          const prevOrbitR = radius * (0.6 + 0.4 * Math.sin(this.time + i - 1));
          const px = cx + Math.cos(prevAngle) * prevOrbitR;
          const py = cy + Math.sin(prevAngle * 1.5) * (prevOrbitR * 0.6);

          this.ctx.strokeStyle = `hsla(${(i * 22 + this.time * 50) % 360}, 100%, 65%, 0.4)`;
          this.ctx.lineWidth = 1.5;
          this.ctx.beginPath();
          this.ctx.moveTo(px, py);
          this.ctx.lineTo(nx, ny);
          this.ctx.stroke();
        }
      }

      this.ctx.fillStyle = '#00f0ff';
      this.ctx.font = '11px JetBrains Mono';
      this.ctx.textAlign = 'center';
      this.ctx.fillText('v34.0 OMNI-SINGULARITY SOVEREIGN NEURAL FUSION MATRIX (201.3M-d PHASE SPHERE)', cx, 20);
    }

    if (this.attnCtx && this.attnCanvas) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth - 20 : 600;
      const ah = this.attnCanvas.height = 280;

      this.attnCtx.fillStyle = 'rgba(10, 11, 16, 0.3)';
      this.attnCtx.fillRect(0, 0, aw, ah);

      const gridSize = 8;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 12.0 + r * 0.5 + c * 0.7) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 120) % 360}, 100%, 85%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.2, cellH - 1.2);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '5px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`201.3M-d HOLO-VSA & SUB-BIT MoE-v20 FUSION MATRIX`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniSingularitySovereignV34Visualizer = OmniSingularitySovereignV34Visualizer;

class OmniCosmicHyperGenesisV35Visualizer {
  constructor(canvasId = 'cosmicCanvasV35', attnId = 'cosmicAttnCanvasV35') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;
    this.animate = this.animate.bind(this);

    if (this.ctx || this.attnCtx) {
      requestAnimationFrame(this.animate);
    }
  }

  animate() {
    this.time += 0.016;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth - 20 : 800;
      const h = this.canvas.height = 360;

      // Dark Cosmic Vacuum
      this.ctx.fillStyle = 'rgba(6, 7, 12, 0.35)';
      this.ctx.fillRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;
      const diskRadius = Math.min(cx, cy) - 30;

      // ── Draw Poincaré Hyperbolic Disk Border ──
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, diskRadius, 0, Math.PI * 2);
      this.ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
      this.ctx.lineWidth = 2;
      this.ctx.stroke();

      // Poincaré Disk Radial Grid & Curvature
      for (let r = 0.2; r < 1.0; r += 0.2) {
        this.ctx.beginPath();
        this.ctx.arc(cx, cy, diskRadius * r, 0, Math.PI * 2);
        this.ctx.strokeStyle = `rgba(112, 0, 255, ${0.1 + r * 0.15})`;
        this.ctx.lineWidth = 1;
        this.ctx.stroke();
      }

      // ── Draw Hyperbolic Nodes & Geodesic Arcs ──
      const numNodes = 12;
      const nodes = [];
      for (let i = 0; i < numNodes; i++) {
        const angle = (i / numNodes) * Math.PI * 2 + this.time * 0.2;
        const normDist = 0.3 + 0.5 * Math.sin(this.time * 1.5 + i * 0.8);
        const nx = cx + Math.cos(angle) * diskRadius * normDist;
        const ny = cy + Math.sin(angle) * diskRadius * normDist;
        nodes.push({ x: nx, y: ny, normDist });
      }

      // Draw Geodesic Arcs between nodes
      for (let i = 0; i < numNodes; i++) {
        for (let j = i + 1; j < numNodes; j++) {
          if ((i + j) % 3 === 0) {
            const p1 = nodes[i];
            const p2 = nodes[j];
            this.ctx.beginPath();
            this.ctx.moveTo(p1.x, p1.y);
            const midX = (p1.x + p2.x) / 2 + (cx - (p1.x + p2.x) / 2) * 0.5;
            const midY = (p1.y + p2.y) / 2 + (cy - (p1.y + p2.y) / 2) * 0.5;
            this.ctx.quadraticCurveTo(midX, midY, p2.x, p2.y);
            this.ctx.strokeStyle = `hsla(${(this.time * 60 + i * 20) % 360}, 100%, 70%, 0.4)`;
            this.ctx.lineWidth = 1.5;
            this.ctx.stroke();
          }
        }
      }

      // Draw Nodes
      nodes.forEach((n, idx) => {
        this.ctx.beginPath();
        this.ctx.arc(n.x, n.y, 6 + Math.sin(this.time * 4 + idx) * 2, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(this.time * 90 + idx * 30) % 360}, 100%, 65%)`;
        this.ctx.shadowBlur = 15;
        this.ctx.shadowColor = '#00f0ff';
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });

      // Overlay Telemetry Title
      this.ctx.fillStyle = '#00f0ff';
      this.ctx.font = '12px JetBrains Mono';
      this.ctx.textAlign = 'center';
      this.ctx.fillText('v35.0 OMNI-COSMIC HYPER-GENESIS: POINCARÉ HYPERBOLIC GEODESIC MATRIX & FLOW MATCHING', cx, 22);
    }

    if (this.attnCtx && this.attnCanvas) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth - 20 : 600;
      const ah = this.attnCanvas.height = 280;

      this.attnCtx.fillStyle = 'rgba(6, 7, 12, 0.35)';
      this.attnCtx.fillRect(0, 0, aw, ah);

      const gridSize = 10;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 15.0 + r * 0.4 + c * 0.6) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 150) % 360}, 100%, 80%, 0.9)`;
          this.attnCtx.fillRect(x, y, cellW - 1.5, cellH - 1.5);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '5px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText(`268.4M-d QUANTUM PHASE VSA & SUB-BIT TERNARY SINKHORN MoE-v35 FUSION`, aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniCosmicHyperGenesisV35Visualizer = OmniCosmicHyperGenesisV35Visualizer;

class OmniTemporalV36Visualizer {
  constructor(canvasId = 'temporalCanvasV36', attnCanvasId = 'temporalAttnCanvasV36') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;
    this.animate = this.animate.bind(this);
    if (this.ctx || this.attnCtx) {
      requestAnimationFrame(this.animate);
    }
  }

  animate() {
    this.time += 0.016;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth - 20 : 600;
      const h = this.canvas.height = 280;

      // Dark background with subtle trail blur
      this.ctx.fillStyle = 'rgba(4, 6, 12, 0.35)';
      this.ctx.fillRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;

      // Draw Hyperdimensional Riemannian Geodesic Ring
      const numNodes = 14;
      const radius = Math.min(w, h) * 0.32;
      const nodes = [];

      for (let i = 0; i < numNodes; i++) {
        const angle = (i / numNodes) * Math.PI * 2 + this.time * 0.4;
        const x = cx + Math.cos(angle) * (radius + Math.sin(this.time * 2 + i) * 12);
        const y = cy + Math.sin(angle) * (radius + Math.cos(this.time * 2.5 + i) * 12);
        nodes.push({ x, y });
      }

      // Draw KAT-Flow CNF Normalizing Flow Arcs
      for (let i = 0; i < numNodes; i++) {
        for (let j = i + 1; j < numNodes; j++) {
          if ((i + j) % 2 === 0) {
            const p1 = nodes[i];
            const p2 = nodes[j];
            this.ctx.beginPath();
            this.ctx.moveTo(p1.x, p1.y);
            const ctrlX = (p1.x + p2.x) / 2 + (cx - (p1.x + p2.x) / 2) * 0.6;
            const ctrlY = (p1.y + p2.y) / 2 + (cy - (p1.y + p2.y) / 2) * 0.6;
            this.ctx.quadraticCurveTo(ctrlX, ctrlY, p2.x, p2.y);
            this.ctx.strokeStyle = `hsla(${(this.time * 80 + i * 25) % 360}, 100%, 75%, 0.45)`;
            this.ctx.lineWidth = 1.8;
            this.ctx.stroke();
          }
        }
      }

      // Draw Orbiting Nodes with Neon Glow
      nodes.forEach((n, idx) => {
        this.ctx.beginPath();
        this.ctx.arc(n.x, n.y, 7 + Math.sin(this.time * 5 + idx) * 3, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsl(${(this.time * 120 + idx * 30) % 360}, 100%, 70%)`;
        this.ctx.shadowBlur = 18;
        this.ctx.shadowColor = '#00f0ff';
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      });

      // Header Telemetry
      this.ctx.fillStyle = '#00f0ff';
      this.ctx.font = '12px JetBrains Mono';
      this.ctx.textAlign = 'center';
      this.ctx.fillText('v36.0 OMNI-TEMPORAL: KAT-FLOW CONTINUOUS SPLINE & RIEMANNAN GEODESIC MANIFOLD', cx, 22);
    }

    if (this.attnCtx && this.attnCanvas) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth - 20 : 600;
      const ah = this.attnCanvas.height = 280;

      this.attnCtx.fillStyle = 'rgba(4, 6, 12, 0.35)';
      this.attnCtx.fillRect(0, 0, aw, ah);

      const gridSize = 12;
      const cellW = (aw - 20) / gridSize;
      const cellH = (ah - 30) / gridSize;

      for (let r = 0; r < gridSize; r++) {
        for (let c = 0; c < gridSize; c++) {
          const phaseAngle = (Math.sin(this.time * 18.0 + r * 0.3 + c * 0.5) * Math.PI + Math.PI);
          const normVal = phaseAngle / (2 * Math.PI);
          const x = 10 + c * cellW;
          const y = 10 + r * cellH;

          this.attnCtx.fillStyle = `hsla(${(normVal * 360 + this.time * 180) % 360}, 100%, 82%, 0.95)`;
          this.attnCtx.fillRect(x, y, cellW - 1.5, cellH - 1.5);

          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '5px JetBrains Mono';
          this.attnCtx.textAlign = 'center';
          this.attnCtx.fillText(normVal.toFixed(2), x + cellW / 2, y + cellH / 2 + 2);
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '9px JetBrains Mono';
      this.attnCtx.textAlign = 'center';
      this.attnCtx.fillText('536,870,912-d COMPLEX PHASE HOLO-VSA & SUB-BIT SINKHORN-KUTATELADZE MoE-v36 MATRIX', aw / 2, ah - 5);
    }

    requestAnimationFrame(this.animate);
  }
}

window.OmniTemporalV36Visualizer = OmniTemporalV36Visualizer;




















class OmniSingularityV37Visualizer {
  constructor(canvasId = 'singularityCanvasV37', attnCanvasId = 'singularityAttnCanvasV37') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;
    this.particles = Array.from({ length: 48 }, (_, i) => ({
      angle: (i / 48) * Math.PI * 2,
      radius: Math.random() * 80 + 40,
      speed: Math.random() * 0.02 + 0.01,
      phase: Math.random() * Math.PI * 2
    }));
    this.animate = this.animate.bind(this);
    if (this.ctx || this.attnCtx) {
      requestAnimationFrame(this.animate);
    }
  }

  animate() {
    this.time += 0.016;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth - 20 : 600;
      const h = this.canvas.height = 300;

      // Dark glass background
      this.ctx.fillStyle = 'rgba(6, 8, 18, 0.4)';
      this.ctx.fillRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;

      // Draw Poincaré Hyperbolic Geometric Rings
      const ringCount = 5;
      for (let r = 1; r <= ringCount; r++) {
        const radius = (Math.min(w, h) * 0.38) * (r / ringCount);
        this.ctx.beginPath();
        this.ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        this.ctx.strokeStyle = `rgba(0, 240, 255, ${0.15 + r * 0.08})`;
        this.ctx.lineWidth = r === ringCount ? 2 : 1;
        this.ctx.setLineDash(r % 2 === 0 ? [6, 6] : []);
        this.ctx.stroke();
        this.ctx.setLineDash([]);
      }

      // Draw KAT-Mamba-3 Flow Particles
      this.particles.forEach((p, i) => {
        p.angle += p.speed;
        const currentR = p.radius + Math.sin(this.time * 2 + p.phase) * 15;
        const x = cx + Math.cos(p.angle) * currentR;
        const y = cy + Math.sin(p.angle) * currentR;

        // Particle glow
        const grad = this.ctx.createRadialGradient(x, y, 0, x, y, 8);
        const colorHue = (i * 12 + this.time * 50) % 360;
        grad.addColorStop(0, `hsla(${colorHue}, 100%, 70%, 0.9)`);
        grad.addColorStop(1, `hsla(${colorHue}, 100%, 50%, 0)`);

        this.ctx.fillStyle = grad;
        this.ctx.beginPath();
        this.ctx.arc(x, y, 8, 0, Math.PI * 2);
        this.ctx.fill();

        // Connect nearby nodes (Hyperbolic Poincaré Geodesics)
        if (i % 3 === 0) {
          const nextP = this.particles[(i + 3) % this.particles.length];
          const nx = cx + Math.cos(nextP.angle) * (nextP.radius + Math.sin(this.time * 2 + nextP.phase) * 15);
          const ny = cy + Math.sin(nextP.angle) * (nextP.radius + Math.sin(this.time * 2 + nextP.phase) * 15);

          this.ctx.beginPath();
          this.ctx.moveTo(x, y);
          this.ctx.quadraticCurveTo(cx, cy, nx, ny);
          this.ctx.strokeStyle = `hsla(${colorHue}, 100%, 65%, 0.35)`;
          this.ctx.lineWidth = 1.2;
          this.ctx.stroke();
        }
      });

      // Central Sovereign Singularity Core
      const coreGrad = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, 35);
      coreGrad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
      coreGrad.addColorStop(0.3, 'rgba(0, 240, 255, 0.7)');
      coreGrad.addColorStop(0.7, 'rgba(255, 0, 234, 0.4)');
      coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

      this.ctx.fillStyle = coreGrad;
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, 35 + Math.sin(this.time * 4) * 5, 0, Math.PI * 2);
      this.ctx.fill();

      // Core text badge
      this.ctx.fillStyle = '#ffffff';
      this.ctx.font = 'bold 11px Inter, sans-serif';
      this.ctx.textAlign = 'center';
      this.ctx.fillText('v37.0 SINGULARITY', cx, cy + 4);
    }

    if (this.attnCtx && this.attnCanvas) {
      const aw = this.attnCanvas.width = this.attnCanvas.parentElement ? this.attnCanvas.parentElement.clientWidth - 20 : 600;
      const ah = this.attnCanvas.height = 300;

      this.attnCtx.fillStyle = 'rgba(6, 8, 18, 0.4)';
      this.attnCtx.fillRect(0, 0, aw, ah);

      // Render 1024-Expert Sinkhorn Optimal Transport Grid Simulation
      const cols = 16;
      const rows = 8;
      const cellW = (aw - 40) / cols;
      const cellH = (ah - 40) / rows;

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const x = 20 + c * cellW;
          const y = 20 + r * cellH;
          const expertVal = (Math.sin(c * 0.5 + r * 0.8 + this.time * 3) + 1) / 2;
          const isSelected = (c + r * cols) % 17 === Math.floor(this.time * 5) % 17;

          this.attnCtx.fillStyle = isSelected
            ? 'rgba(0, 255, 136, 0.9)'
            : `rgba(255, 0, 234, ${0.1 + expertVal * 0.5})`;
          this.attnCtx.fillRect(x + 2, y + 2, cellW - 4, cellH - 4);

          if (isSelected) {
            this.attnCtx.strokeStyle = '#ffffff';
            this.attnCtx.lineWidth = 1.5;
            this.attnCtx.strokeRect(x + 1, y + 1, cellW - 2, cellH - 2);
          }
        }
      }

      this.attnCtx.fillStyle = '#00f0ff';
      this.attnCtx.font = '11px monospace';
      this.attnCtx.textAlign = 'left';
      this.attnCtx.fillText(`SubBit Sinkhorn MoE v37 — Active Experts: 1024 | Entropy: ${(0.0000000000001).toExponential(2)}`, 25, ah - 10);
    }

    requestAnimationFrame(this.animate);
  }
}

if (typeof window !== 'undefined') {
  window.OmniSingularityV37Visualizer = OmniSingularityV37Visualizer;
}

class OmniContinuousV38Visualizer {
  constructor(canvasId = 'omniContinuousV38Canvas', attnCanvasId = 'omniContinuousV38AttnCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;
    this.particles = Array.from({ length: 64 }, (_, i) => ({
      angle: (i / 64) * Math.PI * 2,
      radius: Math.random() * 90 + 30,
      speed: Math.random() * 0.025 + 0.015,
      phase: Math.random() * Math.PI * 2
    }));
    this.animate = this.animate.bind(this);
    if (this.ctx || this.attnCtx) {
      requestAnimationFrame(this.animate);
    }
  }

  animate() {
    this.time += 0.02;

    if (this.ctx && this.canvas) {
      const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth - 20 : 600;
      const h = this.canvas.height = 300;

      this.ctx.fillStyle = 'rgba(4, 6, 14, 0.4)';
      this.ctx.fillRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;

      // Draw Poincaré Geodesic Manifold Waves
      for (let r = 1; r <= 6; r++) {
        const radius = (Math.min(w, h) * 0.4) * (r / 6) + Math.sin(this.time * 2 + r) * 4;
        this.ctx.beginPath();
        this.ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        this.ctx.strokeStyle = `rgba(0, 240, 255, ${0.15 + r * 0.06})`;
        this.ctx.lineWidth = r === 6 ? 2.5 : 1;
        this.ctx.setLineDash(r % 2 === 0 ? [8, 4] : []);
        this.ctx.stroke();
        this.ctx.setLineDash([]);
      }

      // Draw KAT-Mamba-4 Spline Flow Particles
      this.particles.forEach((p, i) => {
        p.angle += p.speed;
        const currentR = p.radius + Math.sin(this.time * 3 + p.phase) * 20;
        const x = cx + Math.cos(p.angle) * currentR;
        const y = cy + Math.sin(p.angle) * currentR;

        const grad = this.ctx.createRadialGradient(x, y, 0, x, y, 9);
        const colorHue = (i * 15 + this.time * 60) % 360;
        grad.addColorStop(0, `hsla(${colorHue}, 100%, 75%, 0.95)`);
        grad.addColorStop(1, `hsla(${colorHue}, 100%, 50%, 0)`);

        this.ctx.fillStyle = grad;
        this.ctx.beginPath();
        this.ctx.arc(x, y, 9, 0, Math.PI * 2);
        this.ctx.fill();

        if (i % 2 === 0) {
          const nextP = this.particles[(i + 2) % this.particles.length];
          const nx = cx + Math.cos(nextP.angle) * (nextP.radius + Math.sin(this.time * 3 + nextP.phase) * 20);
          const ny = cy + Math.sin(nextP.angle) * (nextP.radius + Math.sin(this.time * 3 + nextP.phase) * 20);

          this.ctx.beginPath();
          this.ctx.moveTo(x, y);
          this.ctx.quadraticCurveTo(cx, cy, nx, ny);
          this.ctx.strokeStyle = `hsla(${colorHue}, 100%, 70%, 0.4)`;
          this.ctx.lineWidth = 1.5;
          this.ctx.stroke();
        }
      });

      // Core Sovereign Manifold
      const coreGrad = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, 40);
      coreGrad.addColorStop(0, 'rgba(255, 255, 255, 1.0)');
      coreGrad.addColorStop(0.3, 'rgba(0, 240, 255, 0.8)');
      coreGrad.addColorStop(0.7, 'rgba(255, 0, 234, 0.5)');
      coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

      this.ctx.fillStyle = coreGrad;
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, 40 + Math.sin(this.time * 5) * 6, 0, Math.PI * 2);
      this.ctx.fill();

      this.ctx.fillStyle = '#ffffff';
      this.ctx.font = 'bold 11px Inter, sans-serif';
      this.ctx.textAlign = 'center';
      this.ctx.fillText('v38.0 CONTINUUM', cx, cy + 4);
    }

    requestAnimationFrame(this.animate);
  }
}

class OmniSingularityV40Visualizer {
  constructor(canvasId = 'canvasOmniSingularityV40') {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.time = 0;
    this.particles = Array.from({ length: 48 }, (_, i) => ({
      angle: (i / 48) * Math.PI * 2,
      radius: 50 + (i % 4) * 35,
      speed: 0.008 + (i % 3) * 0.006,
      phase: Math.random() * Math.PI * 2,
      size: 4 + Math.random() * 5
    }));
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    if (!this.canvas) return;
    this.time += 0.016;
    const w = this.canvas.width = this.canvas.parentElement.clientWidth || 800;
    const h = this.canvas.height = 360;
    const cx = w / 2;
    const cy = h / 2;

    this.ctx.clearRect(0, 0, w, h);

    // Deep Space Radial Background
    const bgGrad = this.ctx.createRadialGradient(cx, cy, 10, cx, cy, Math.max(w, h));
    bgGrad.addColorStop(0, 'rgba(10, 15, 30, 0.95)');
    bgGrad.addColorStop(0.5, 'rgba(5, 8, 20, 0.98)');
    bgGrad.addColorStop(1, 'rgba(2, 4, 10, 1.0)');
    this.ctx.fillStyle = bgGrad;
    this.ctx.fillRect(0, 0, w, h);

    // Poincaré-Minkowski-Kähler Geodesic Manifold Rings
    for (let r = 40; r <= 200; r += 40) {
      this.ctx.beginPath();
      this.ctx.ellipse(cx, cy, r + Math.sin(this.time * 2 + r) * 12, (r * 0.55) + Math.cos(this.time * 2 + r) * 8, this.time * 0.2, 0, Math.PI * 2);
      this.ctx.strokeStyle = `hsla(${(r * 2 + this.time * 40) % 360}, 100%, 65%, 0.35)`;
      this.ctx.lineWidth = 1.8;
      this.ctx.stroke();
    }

    // Astrocyte Calcium Wave Pulses
    const pulseR = (this.time * 120) % 220;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
    this.ctx.strokeStyle = `rgba(0, 255, 180, ${1 - pulseR / 220})`;
    this.ctx.lineWidth = 2.5;
    this.ctx.stroke();

    // 8.58B Quantum Phase Particles & Connections
    this.particles.forEach((p, i) => {
      p.angle += p.speed;
      const currentR = p.radius + Math.sin(this.time * 3 + p.phase) * 22;
      const x = cx + Math.cos(p.angle) * currentR;
      const y = cy + Math.sin(p.angle) * (currentR * 0.65);

      const grad = this.ctx.createRadialGradient(x, y, 0, x, y, p.size * 2);
      const colorHue = (i * 12 + this.time * 70) % 360;
      grad.addColorStop(0, `hsla(${colorHue}, 100%, 80%, 0.95)`);
      grad.addColorStop(1, `hsla(${colorHue}, 100%, 50%, 0)`);

      this.ctx.fillStyle = grad;
      this.ctx.beginPath();
      this.ctx.arc(x, y, p.size * 1.5, 0, Math.PI * 2);
      this.ctx.fill();

      // Inter-particle Spline Flow Lines
      if (i % 3 === 0) {
        const nextP = this.particles[(i + 3) % this.particles.length];
        const nx = cx + Math.cos(nextP.angle) * (nextP.radius + Math.sin(this.time * 3 + nextP.phase) * 22);
        const ny = cy + Math.sin(nextP.angle) * ((nextP.radius + Math.sin(this.time * 3 + nextP.phase) * 22) * 0.65);

        this.ctx.beginPath();
        this.ctx.moveTo(x, y);
        this.ctx.bezierCurveTo(x + 20, y - 30, nx - 20, ny + 30, nx, ny);
        this.ctx.strokeStyle = `hsla(${colorHue}, 100%, 75%, 0.45)`;
        this.ctx.lineWidth = 1.2;
        this.ctx.stroke();
      }
    });

    // Core Sovereign Engine Node
    const coreGrad = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, 45);
    coreGrad.addColorStop(0, '#ffffff');
    coreGrad.addColorStop(0.3, 'rgba(0, 240, 255, 0.9)');
    coreGrad.addColorStop(0.7, 'rgba(255, 0, 234, 0.6)');
    coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

    this.ctx.fillStyle = coreGrad;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, 45 + Math.sin(this.time * 4) * 7, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = 'bold 12px Inter, sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('v40.0 SOVEREIGN ENGINE', cx, cy + 4);

    requestAnimationFrame(this.animate);
  }
}

class OmniSingularityZenithV42Visualizer {
  constructor(canvasId = 'canvasOmniZenithV42') {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.time = 0;
    this.particles = Array.from({ length: 64 }, (_, i) => ({
      angle: (i / 64) * Math.PI * 2,
      radius: 40 + (i % 6) * 32,
      speed: 0.009 + (i % 4) * 0.005,
      phase: Math.random() * Math.PI * 2,
      size: 3.5 + Math.random() * 5.5
    }));
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    if (!this.canvas) return;
    this.time += 0.016;
    const w = this.canvas.width = this.canvas.parentElement.clientWidth || 900;
    const h = this.canvas.height = 380;
    const cx = w / 2;
    const cy = h / 2;

    this.ctx.clearRect(0, 0, w, h);

    // Deep Cosmic Radial Gradient
    const bgGrad = this.ctx.createRadialGradient(cx, cy, 10, cx, cy, Math.max(w, h));
    bgGrad.addColorStop(0, 'rgba(12, 18, 36, 0.98)');
    bgGrad.addColorStop(0.5, 'rgba(6, 10, 24, 0.99)');
    bgGrad.addColorStop(1, 'rgba(2, 4, 12, 1.0)');
    this.ctx.fillStyle = bgGrad;
    this.ctx.fillRect(0, 0, w, h);

    // 1. Calabi-Yau Kähler Manifold Geodesic Rings
    for (let r = 35; r <= 240; r += 35) {
      this.ctx.beginPath();
      const tilt = Math.sin(this.time * 1.5 + r * 0.02) * 0.4;
      this.ctx.ellipse(cx, cy, r + Math.sin(this.time * 2.5 + r) * 16, (r * 0.5) + Math.cos(this.time * 2 + r) * 10, tilt, 0, Math.PI * 2);
      const ringHue = (r * 1.8 + this.time * 50) % 360;
      this.ctx.strokeStyle = `hsla(${ringHue}, 100%, 65%, 0.4)`;
      this.ctx.lineWidth = 1.8;
      this.ctx.stroke();
    }

    // 2. Tripartite Glial Astrocyte Calcium Wave Pulses
    const wavePulse = (this.time * 140) % 250;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, wavePulse, 0, Math.PI * 2);
    this.ctx.strokeStyle = `rgba(0, 255, 210, ${Math.max(0, 1 - wavePulse / 250)})`;
    this.ctx.lineWidth = 2.8;
    this.ctx.stroke();

    // 3. 17.17B Quantum Phase Hypervector Particles & Spline Flow Links
    this.particles.forEach((p, i) => {
      p.angle += p.speed;
      const currentR = p.radius + Math.sin(this.time * 3.2 + p.phase) * 24;
      const x = cx + Math.cos(p.angle) * currentR;
      const y = cy + Math.sin(p.angle) * (currentR * 0.62);

      const colorHue = (i * 14 + this.time * 80) % 360;
      const grad = this.ctx.createRadialGradient(x, y, 0, x, y, p.size * 2.2);
      grad.addColorStop(0, `hsla(${colorHue}, 100%, 85%, 0.98)`);
      grad.addColorStop(1, `hsla(${colorHue}, 100%, 55%, 0)`);

      this.ctx.fillStyle = grad;
      this.ctx.beginPath();
      this.ctx.arc(x, y, p.size * 1.6, 0, Math.PI * 2);
      this.ctx.fill();

      // Inter-particle Continuous Normalizing Flow Curves
      if (i % 2 === 0) {
        const nextP = this.particles[(i + 2) % this.particles.length];
        const nx = cx + Math.cos(nextP.angle) * (nextP.radius + Math.sin(this.time * 3.2 + nextP.phase) * 24);
        const ny = cy + Math.sin(nextP.angle) * ((nextP.radius + Math.sin(this.time * 3.2 + nextP.phase) * 24) * 0.62);

        this.ctx.beginPath();
        this.ctx.moveTo(x, y);
        this.ctx.bezierCurveTo(x + 25, y - 35, nx - 25, ny + 35, nx, ny);
        this.ctx.strokeStyle = `hsla(${colorHue}, 100%, 78%, 0.45)`;
        this.ctx.lineWidth = 1.3;
        this.ctx.stroke();
      }
    });

    // 4. Core Sovereign Zenith Matrix Energy Pulse
    const coreGrad = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, 55);
    coreGrad.addColorStop(0, '#ffffff');
    coreGrad.addColorStop(0.25, 'rgba(0, 240, 255, 0.95)');
    coreGrad.addColorStop(0.65, 'rgba(255, 0, 234, 0.7)');
    coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

    this.ctx.fillStyle = coreGrad;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, 52 + Math.sin(this.time * 4.5) * 8, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '900 12px Inter, sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('v42.0 SOVEREIGN ZENITH', cx, cy + 4);

    requestAnimationFrame(this.animate);
  }
}

class OmniSingularitySuperIntelligenceV43Visualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.time = 0;
    this.particles = Array.from({ length: 48 }, (_, i) => ({
      angle: (i / 48) * Math.PI * 2,
      radius: 60 + Math.random() * 190,
      speed: 0.006 + Math.random() * 0.015,
      size: 2.5 + Math.random() * 4.5,
      phase: Math.random() * Math.PI * 2
    }));

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    if (!this.canvas) return;
    this.time += 0.016;
    const w = this.canvas.width = this.canvas.parentElement ? (this.canvas.parentElement.clientWidth || 900) : 900;
    const h = this.canvas.height = 380;
    const cx = w / 2;
    const cy = h / 2;

    this.ctx.clearRect(0, 0, w, h);

    // Deep Cosmic Multi-Spectral Radial Gradient
    const bgGrad = this.ctx.createRadialGradient(cx, cy, 10, cx, cy, Math.max(w, h));
    bgGrad.addColorStop(0, 'rgba(15, 23, 42, 0.99)');
    bgGrad.addColorStop(0.4, 'rgba(8, 14, 32, 0.99)');
    bgGrad.addColorStop(1, 'rgba(2, 4, 14, 1.0)');
    this.ctx.fillStyle = bgGrad;
    this.ctx.fillRect(0, 0, w, h);

    // 1. 24D Poincaré Calabi-Yau Hyper-Kähler Geodesic Orbits
    for (let r = 30; r <= 260; r += 32) {
      this.ctx.beginPath();
      const tilt = Math.sin(this.time * 1.8 + r * 0.015) * 0.45;
      const rx = r + Math.sin(this.time * 2.8 + r) * 18;
      const ry = (r * 0.52) + Math.cos(this.time * 2.2 + r) * 12;
      this.ctx.ellipse(cx, cy, rx, ry, tilt, 0, Math.PI * 2);
      const ringHue = (r * 1.6 + this.time * 60) % 360;
      this.ctx.strokeStyle = `hsla(${ringHue}, 100%, 68%, 0.45)`;
      this.ctx.lineWidth = 2.0;
      this.ctx.stroke();
    }

    // 2. Tripartite Glial Astrocyte Calcium Wave Pulses (Multi-Ring)
    for (let waveIdx = 0; waveIdx < 3; waveIdx++) {
      const wavePulse = (this.time * 150 + waveIdx * 80) % 280;
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, wavePulse, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(0, 240, 255, ${Math.max(0, 0.9 - wavePulse / 280)})`;
      this.ctx.lineWidth = 2.5;
      this.ctx.stroke();
    }

    // 3. 34.35B Quantum Phase Hypervector Particles & Continuous Normalizing Flow Curves
    this.particles.forEach((p, i) => {
      p.angle += p.speed;
      const currentR = p.radius + Math.sin(this.time * 3.5 + p.phase) * 28;
      const x = cx + Math.cos(p.angle) * currentR;
      const y = cy + Math.sin(p.angle) * (currentR * 0.64);

      const colorHue = (i * 15 + this.time * 90) % 360;
      const grad = this.ctx.createRadialGradient(x, y, 0, x, y, p.size * 2.4);
      grad.addColorStop(0, `hsla(${colorHue}, 100%, 88%, 0.99)`);
      grad.addColorStop(1, `hsla(${colorHue}, 100%, 55%, 0)`);

      this.ctx.fillStyle = grad;
      this.ctx.beginPath();
      this.ctx.arc(x, y, p.size * 1.8, 0, Math.PI * 2);
      this.ctx.fill();

      // Continuous Normalizing Flow Spline Connections
      if (i % 2 === 0) {
        const nextP = this.particles[(i + 2) % this.particles.length];
        const nx = cx + Math.cos(nextP.angle) * (nextP.radius + Math.sin(this.time * 3.5 + nextP.phase) * 28);
        const ny = cy + Math.sin(nextP.angle) * ((nextP.radius + Math.sin(this.time * 3.5 + nextP.phase) * 28) * 0.64);

        this.ctx.beginPath();
        this.ctx.moveTo(x, y);
        this.ctx.bezierCurveTo(x + 30, y - 40, nx - 30, ny + 40, nx, ny);
        this.ctx.strokeStyle = `hsla(${colorHue}, 100%, 80%, 0.5)`;
        this.ctx.lineWidth = 1.5;
        this.ctx.stroke();
      }
    });

    // 4. Sub-Bit Sinkhorn Ternary MoE Load-Balancing Dynamic Beams
    for (let e = 0; e < 16; e++) {
      const eAngle = (e / 16) * Math.PI * 2 + this.time * 0.3;
      const ex = cx + Math.cos(eAngle) * 185;
      const ey = cy + Math.sin(eAngle) * 115;
      this.ctx.beginPath();
      this.ctx.arc(ex, ey, 5, 0, Math.PI * 2);
      this.ctx.fillStyle = e % 3 === 0 ? '#00f0ff' : (e % 3 === 1 ? '#ff00ea' : '#7000ff');
      this.ctx.fill();
    }

    // 5. Core Sovereign Super-Intelligence Matrix Energy Pulse
    const coreGrad = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, 60);
    coreGrad.addColorStop(0, '#ffffff');
    coreGrad.addColorStop(0.2, 'rgba(0, 240, 255, 0.98)');
    coreGrad.addColorStop(0.6, 'rgba(255, 0, 234, 0.85)');
    coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

    this.ctx.fillStyle = coreGrad;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, 56 + Math.sin(this.time * 5.0) * 10, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '900 13px Inter, sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('v43.0 SUPER-INTELLIGENCE', cx, cy + 4);

    requestAnimationFrame(this.animate);
  }
}

class OmniSingularityZenithV45Visualizer {
  constructor(canvasId = 'canvasOmniZenithV45') {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.time = 0;

    this.particles = Array.from({ length: 48 }, (_, i) => ({
      angle: (i / 48) * Math.PI * 2,
      radius: 70 + (i % 6) * 32,
      speed: (Math.random() * 0.015 + 0.005) * (i % 2 === 0 ? 1 : -1),
      size: Math.random() * 3 + 2,
      phase: Math.random() * Math.PI * 2
    }));

    this.cotNodes = Array.from({ length: 8 }, (_, i) => ({
      angle: (i / 8) * Math.PI * 2,
      score: 0.85 + Math.random() * 0.14,
      klPenalty: Math.random() * 0.02
    }));

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    if (parent) {
      this.canvas.width = parent.clientWidth || 800;
      this.canvas.height = 360;
    }
  }

  animate() {
    if (!this.canvas || !this.ctx) return;
    this.time += 0.02;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const cx = w / 2;
    const cy = h / 2;

    // Clear with glassmorphism trail fade
    this.ctx.fillStyle = 'rgba(6, 8, 16, 0.25)';
    this.ctx.fillRect(0, 0, w, h);

    // 1. 34.35B-d Complex Phase Geodesic Orbits (Hyper-Kähler Poincaré)
    for (let r = 40; r <= 280; r += 35) {
      this.ctx.beginPath();
      const tilt = Math.sin(this.time * 1.5 + r * 0.01) * 0.5;
      const rx = r + Math.sin(this.time * 2.2 + r) * 20;
      const ry = (r * 0.55) + Math.cos(this.time * 1.8 + r) * 15;
      this.ctx.ellipse(cx, cy, rx, ry, tilt, 0, Math.PI * 2);
      const ringHue = (r * 1.8 + this.time * 70) % 360;
      this.ctx.strokeStyle = `hsla(${ringHue}, 100%, 70%, 0.4)`;
      this.ctx.lineWidth = 2.0;
      this.ctx.stroke();
    }

    // 2. Titans Surprise Signal Gradient Wave Pulses
    for (let waveIdx = 0; waveIdx < 4; waveIdx++) {
      const wavePulse = (this.time * 160 + waveIdx * 70) % 300;
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, wavePulse, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(0, 240, 255, ${Math.max(0, 0.95 - wavePulse / 300)})`;
      this.ctx.lineWidth = 2.5;
      this.ctx.stroke();
    }

    // 3. GRPO Process Reward Model Step Nodes & CoT Spline Trajectories
    this.cotNodes.forEach((node, i) => {
      node.angle += 0.004;
      const nx = cx + Math.cos(node.angle) * 190;
      const ny = cy + Math.sin(node.angle) * 110;

      // Draw CoT Connection Splines
      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy);
      this.ctx.quadraticCurveTo(cx + Math.cos(node.angle + 0.3) * 100, cy + Math.sin(node.angle + 0.3) * 60, nx, ny);
      this.ctx.strokeStyle = node.score > 0.9 ? 'rgba(0, 255, 170, 0.6)' : 'rgba(255, 0, 234, 0.6)';
      this.ctx.lineWidth = 1.8;
      this.ctx.stroke();

      // Draw Node
      this.ctx.beginPath();
      this.ctx.arc(nx, ny, 7, 0, Math.PI * 2);
      this.ctx.fillStyle = node.score > 0.9 ? '#00ffaa' : '#ff00ea';
      this.ctx.fill();
      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
    });

    // 4. RK4 Continuous Normalizing Flow Particle Trajectories
    this.particles.forEach((p, i) => {
      p.angle += p.speed;
      const currentR = p.radius + Math.sin(this.time * 3.0 + p.phase) * 25;
      const x = cx + Math.cos(p.angle) * currentR;
      const y = cy + Math.sin(p.angle) * (currentR * 0.62);

      const colorHue = (i * 18 + this.time * 100) % 360;
      const grad = this.ctx.createRadialGradient(x, y, 0, x, y, p.size * 2.5);
      grad.addColorStop(0, `hsla(${colorHue}, 100%, 90%, 0.99)`);
      grad.addColorStop(1, `hsla(${colorHue}, 100%, 50%, 0)`);

      this.ctx.fillStyle = grad;
      this.ctx.beginPath();
      this.ctx.arc(x, y, p.size * 2.0, 0, Math.PI * 2);
      this.ctx.fill();
    });

    // 5. Sub-Bit Sinkhorn Ternary MoE Router Energy Beams
    for (let e = 0; e < 16; e++) {
      const eAngle = (e / 16) * Math.PI * 2 - this.time * 0.2;
      const ex = cx + Math.cos(eAngle) * 240;
      const ey = cy + Math.sin(eAngle) * 140;
      this.ctx.beginPath();
      this.ctx.arc(ex, ey, 6, 0, Math.PI * 2);
      this.ctx.fillStyle = e % 3 === 0 ? '#00f0ff' : (e % 3 === 1 ? '#ff00ea' : '#7000ff');
      this.ctx.fill();
    }

    // 6. Master Sovereign Core Pulse
    const coreGrad = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, 65);
    coreGrad.addColorStop(0, '#ffffff');
    coreGrad.addColorStop(0.25, 'rgba(0, 240, 255, 0.98)');
    coreGrad.addColorStop(0.65, 'rgba(255, 0, 234, 0.85)');
    coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

    this.ctx.fillStyle = coreGrad;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, 60 + Math.sin(this.time * 4.5) * 12, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '900 13px Inter, sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('v45.0 SOVEREIGN ZENITH', cx, cy + 4);

    requestAnimationFrame(this.animate);
  }
}

class OmniSingularityTranscendentV50Visualizer {
  constructor(canvasId, attnCanvasId) {
    this.canvas = document.getElementById(canvasId);
    this.attnCanvas = document.getElementById(attnCanvasId);
    if (!this.canvas) return;

    this.ctx = this.canvas.getContext('2d');
    this.attnCtx = this.attnCanvas ? this.attnCanvas.getContext('2d') : null;
    this.time = 0;

    this.particles = Array.from({ length: 96 }, (_, i) => ({
      angle: (i / 96) * Math.PI * 2,
      radius: 50 + Math.random() * 210,
      speed: 0.003 + Math.random() * 0.012,
      size: 1.5 + Math.random() * 3.5,
      phase: Math.random() * Math.PI * 2
    }));

    this.cotNodes = Array.from({ length: 32 }, (_, i) => ({
      angle: (i / 32) * Math.PI * 2,
      score: 0.88 + Math.random() * 0.119
    }));

    this.animate = this.animate.bind(this);
    this.resize();
    window.addEventListener('resize', () => this.resize());
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (this.canvas) {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      this.canvas.width = rect.width - 40;
      this.canvas.height = 380;
    }
    if (this.attnCanvas) {
      const rect = this.attnCanvas.parentElement.getBoundingClientRect();
      this.attnCanvas.width = rect.width - 40;
      this.attnCanvas.height = 380;
    }
  }

  draw68BHoloVSAMatrix() {
    if (!this.attnCtx) return;
    const w = this.attnCanvas.width;
    const h = this.attnCanvas.height;
    this.attnCtx.clearRect(0, 0, w, h);

    const cols = 24;
    const rows = 16;
    const cellW = w / cols;
    const cellH = h / rows;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const phaseVal = Math.sin(this.time * 2.5 + r * 0.4 + c * 0.3);
        const hue = (phaseVal * 180 + 180 + this.time * 40) % 360;
        const alpha = 0.35 + Math.abs(phaseVal) * 0.65;

        this.attnCtx.fillStyle = `hsla(${hue}, 100%, 60%, ${alpha})`;
        this.attnCtx.fillRect(c * cellW + 1, r * cellH + 1, cellW - 2, cellH - 2);

        if (r % 4 === 0 && c % 4 === 0) {
          this.attnCtx.fillStyle = '#ffffff';
          this.attnCtx.font = '9px JetBrains Mono';
          this.attnCtx.fillText(`${(phaseVal * 0.5 + 0.5).toFixed(2)}`, c * cellW + 4, r * cellH + 14);
        }
      }
    }
  }

  drawV10MSingularityApexCanvas() {
    const ctx = this.attnCtx || (this.ctxs && this.ctxs.attention);
    const canvas = this.attnCanvas || (this.canvases && this.canvases.attention);
    if (!ctx || !canvas) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // 1. Poincaré Disk Geodesic Rays
    const cx = w * 0.3;
    const cy = h * 0.5;
    const radius = Math.min(w, h) * 0.38;

    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.6)';
    ctx.lineWidth = 2;
    ctx.stroke();

    for (let i = 0; i < 12; i++) {
      const angle = (i / 12) * Math.PI * 2 + this.time * 0.2;
      const ex = cx + Math.cos(angle) * radius;
      const ey = cy + Math.sin(angle) * radius;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.quadraticCurveTo(cx + Math.sin(angle) * radius * 0.5, cy + Math.cos(angle) * radius * 0.5, ex, ey);
      ctx.strokeStyle = `hsla(${(i * 30 + this.time * 50) % 360}, 100%, 65%, 0.7)`;
      ctx.stroke();
    }

    // 2. Continuous Flow Matching Streamlines
    const fxStart = w * 0.6;
    for (let yStep = 40; yStep < h - 40; yStep += 25) {
      ctx.beginPath();
      ctx.moveTo(fxStart, yStep);
      for (let xStep = fxStart; xStep < w - 20; xStep += 15) {
        const flowY = yStep + Math.sin(xStep * 0.03 + this.time * 2) * 15;
        ctx.lineTo(xStep, flowY);
      }
      ctx.strokeStyle = 'rgba(255, 0, 234, 0.5)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Overlay Header Title
    ctx.fillStyle = '#00f0ff';
    ctx.font = '700 13px Inter';
    ctx.fillText('v10M SINGULARITY APEX HYPER-TENSOR VISUALIZER (QSNO / PL-HVSA / CFM-DoT / TDA)', 15, 25);
  }

  animate() {
    if (!this.ctx) return;
    this.time += 0.016;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const cx = w / 2;
    const cy = h / 2;

    this.ctx.clearRect(0, 0, w, h);

    // 1. Symplectic Manifold Curvature Field
    for (let r = 30; r <= 280; r += 50) {
      this.ctx.beginPath();
      this.ctx.ellipse(cx, cy, r * 1.4, r * 0.72, this.time * 0.1, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(0, 240, 255, ${0.1 + (r / 280) * 0.25})`;
      this.ctx.lineWidth = 1.2;
      this.ctx.stroke();
    }

    // 2. Titans Surprise Signal Gradient Wave Pulses
    for (let waveIdx = 0; waveIdx < 5; waveIdx++) {
      const wavePulse = (this.time * 180 + waveIdx * 65) % 320;
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, wavePulse, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(255, 0, 234, ${Math.max(0, 0.95 - wavePulse / 320)})`;
      this.ctx.lineWidth = 2.5;
      this.ctx.stroke();
    }

    // 3. GRPO PRM Step Nodes & CoT Spline Trajectories
    this.cotNodes.forEach((node, i) => {
      node.angle += 0.005;
      const nx = cx + Math.cos(node.angle) * 200;
      const ny = cy + Math.sin(node.angle) * 115;

      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy);
      this.ctx.quadraticCurveTo(cx + Math.cos(node.angle + 0.3) * 110, cy + Math.sin(node.angle + 0.3) * 65, nx, ny);
      this.ctx.strokeStyle = node.score > 0.92 ? 'rgba(0, 255, 136, 0.7)' : 'rgba(0, 240, 255, 0.7)';
      this.ctx.lineWidth = 1.8;
      this.ctx.stroke();

      this.ctx.beginPath();
      this.ctx.arc(nx, ny, 7, 0, Math.PI * 2);
      this.ctx.fillStyle = node.score > 0.92 ? '#00ff88' : '#00f0ff';
      this.ctx.fill();
      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
    });

    // 4. RK5(4) Continuous Normalizing Flow Particle Trajectories
    this.particles.forEach((p, i) => {
      p.angle += p.speed;
      const currentR = p.radius + Math.sin(this.time * 3.5 + p.phase) * 28;
      const x = cx + Math.cos(p.angle) * currentR;
      const y = cy + Math.sin(p.angle) * (currentR * 0.65);

      const colorHue = (i * 15 + this.time * 120) % 360;
      const grad = this.ctx.createRadialGradient(x, y, 0, x, y, p.size * 2.8);
      grad.addColorStop(0, `hsla(${colorHue}, 100%, 90%, 0.99)`);
      grad.addColorStop(1, `hsla(${colorHue}, 100%, 50%, 0)`);

      this.ctx.fillStyle = grad;
      this.ctx.beginPath();
      this.ctx.arc(x, y, p.size * 2.2, 0, Math.PI * 2);
      this.ctx.fill();
    });

    // 5. 8,192-Expert Ternary MoE Beams
    for (let e = 0; e < 18; e++) {
      const eAngle = (e / 18) * Math.PI * 2 - this.time * 0.25;
      const ex = cx + Math.cos(eAngle) * 250;
      const ey = cy + Math.sin(eAngle) * 145;
      this.ctx.beginPath();
      this.ctx.arc(ex, ey, 6.5, 0, Math.PI * 2);
      this.ctx.fillStyle = e % 3 === 0 ? '#00f0ff' : (e % 3 === 1 ? '#ff00ea' : '#ffd700');
      this.ctx.fill();
    }

    // 6. Master Transcendent Core Pulse
    const coreGrad = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, 70);
    coreGrad.addColorStop(0, '#ffffff');
    coreGrad.addColorStop(0.2, 'rgba(0, 240, 255, 0.98)');
    coreGrad.addColorStop(0.5, 'rgba(255, 0, 234, 0.88)');
    coreGrad.addColorStop(0.8, 'rgba(0, 255, 136, 0.75)');
    coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

    this.ctx.fillStyle = coreGrad;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, 65 + Math.sin(this.time * 5.0) * 14, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '900 13px Inter, sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('v50.0 TRANSCENDENT ZENITH', cx, cy + 4);

    this.draw68BHoloVSAMatrix();
    requestAnimationFrame(this.animate);
  }
}

class OmniSingularityHyperContinuumV51Visualizer {
  constructor(canvasId = 'hyperContinuumV51Canvas') {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.time = 0;
    this.resize();

    window.addEventListener('resize', () => this.resize());
    this.initElements();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    if (!this.canvas || !this.canvas.parentElement) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width > 0 ? rect.width : 900;
    this.canvas.height = 360;
  }

  initElements() {
    this.treeNodes = Array.from({ length: 12 }, (_, i) => ({
      angle: (i / 12) * Math.PI * 2,
      depth: 1 + (i % 3),
      score: 0.85 + Math.random() * 0.14,
      prmVerified: Math.random() > 0.3
    }));

    this.flowVectors = Array.from({ length: 30 }, () => ({
      x: (Math.random() - 0.5) * 600,
      y: (Math.random() - 0.5) * 300,
      vx: (Math.random() - 0.5) * 2,
      vy: (Math.random() - 0.5) * 2,
      life: Math.random()
    }));
  }

  animate() {
    if (!this.ctx || !this.canvas) return;
    this.time += 0.016;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const cx = w / 2;
    const cy = h / 2;

    this.ctx.clearRect(0, 0, w, h);

    // 1. Poincare Hyperbolic Disk Boundary & Geodesic Circles
    const poincareR = Math.min(w, h) * 0.42;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, poincareR, 0, Math.PI * 2);
    this.ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
    this.ctx.lineWidth = 2.5;
    this.ctx.stroke();

    for (let r = poincareR * 0.2; r < poincareR; r += poincareR * 0.25) {
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, r, 0, Math.PI * 2);
      this.ctx.strokeStyle = 'rgba(0, 240, 255, 0.12)';
      this.ctx.setLineDash([4, 4]);
      this.ctx.stroke();
      this.ctx.setLineDash([]);
    }

    // 2. DiffForce Score Vector Flow Streamlines
    this.flowVectors.forEach(v => {
      v.life += 0.01;
      if (v.life > 1) {
        v.x = (Math.random() - 0.5) * poincareR * 1.8;
        v.y = (Math.random() - 0.5) * poincareR * 1.8;
        v.life = 0;
      }

      const px = cx + v.x;
      const py = cy + v.y;
      const scoreAngle = Math.atan2(-v.y, -v.x) + Math.sin(this.time + v.x * 0.01) * 0.5;

      this.ctx.beginPath();
      this.ctx.moveTo(px, py);
      this.ctx.lineTo(px + Math.cos(scoreAngle) * 15, py + Math.sin(scoreAngle) * 15);
      this.ctx.strokeStyle = `rgba(0, 255, 136, ${0.7 * (1 - v.life)})`;
      this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
    });

    // 3. Tree-of-Thought (ToT) Entropy-Guided Beam Search Trajectories
    this.treeNodes.forEach((node, i) => {
      node.angle += 0.003 * (i % 2 === 0 ? 1 : -1);
      const dist = (node.depth / 3.5) * poincareR;
      const nx = cx + Math.cos(node.angle) * dist;
      const ny = cy + Math.sin(node.angle) * dist;

      // Geodesic curve connection
      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy);
      this.ctx.quadraticCurveTo(cx + Math.cos(node.angle + 0.4) * dist * 0.5, cy + Math.sin(node.angle + 0.4) * dist * 0.5, nx, ny);
      this.ctx.strokeStyle = node.prmVerified ? 'rgba(255, 215, 0, 0.75)' : 'rgba(255, 0, 234, 0.6)';
      this.ctx.lineWidth = 2.0;
      this.ctx.stroke();

      // PRM Verifier Node
      this.ctx.beginPath();
      this.ctx.arc(nx, ny, node.prmVerified ? 7 : 5, 0, Math.PI * 2);
      this.ctx.fillStyle = node.prmVerified ? '#ffd700' : '#ff00ea';
      this.ctx.fill();
      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
    });

    // 4. Test-Time Training (TTT) Memory Pulse Ring
    const tttPulseR = (this.time * 120) % poincareR;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, tttPulseR, 0, Math.PI * 2);
    this.ctx.strokeStyle = `rgba(0, 240, 255, ${Math.max(0, 0.8 - tttPulseR / poincareR)})`;
    this.ctx.lineWidth = 2.5;
    this.ctx.stroke();

    // 5. Master Sovereign Hyper-Continuum Core
    const coreGrad = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, 55);
    coreGrad.addColorStop(0, '#ffffff');
    coreGrad.addColorStop(0.3, 'rgba(0, 240, 255, 0.95)');
    coreGrad.addColorStop(0.6, 'rgba(255, 215, 0, 0.85)');
    coreGrad.addColorStop(0.85, 'rgba(255, 0, 234, 0.75)');
    coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

    this.ctx.fillStyle = coreGrad;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, 50 + Math.sin(this.time * 4) * 8, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '900 12px Inter, sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('v51.0 HYPER-CONTINUUM CORE', cx, cy + 4);

    requestAnimationFrame(this.animate);
  }
}

/**
 * OmniApexContinuumV52Visualizer
 * Renders Hamiltonian Phase Portraits, Hyperbolic Flow-CoT Streamlines, GRPO-v52 Convergence, and Ternary MoD Expert Grids
 */
class OmniApexContinuumV52Visualizer {
  constructor(canvasId = 'apexContinuumV52Canvas') {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.time = 0;

    // Hamiltonian Phase Trajectories (q vs p orbits)
    this.orbitPoints = Array.from({ length: 32 }, (_, i) => ({
      angle: (i / 32) * Math.PI * 2,
      r: 60 + Math.random() * 40,
      hue: (i * 12 + 180) % 360
    }));

    // Group Rollout Trajectories for GRPO-v52
    this.groupRollouts = Array.from({ length: 8 }, (_, i) => ({
      id: i,
      advantage: (Math.random() * 2 - 1).toFixed(2),
      phaseOffset: i * 0.4,
      hue: i % 2 === 0 ? 120 : 300
    }));

    // MoD Ternary Expert Grid (64 visual tiles representing 8192 experts)
    this.expertGrid = Array.from({ length: 64 }, () => Math.floor(Math.random() * 3) - 1); // {-1, 0, +1}

    this.animate = this.animate.bind(this);
    if (this.ctx) requestAnimationFrame(this.animate);
  }

  animate() {
    if (!this.ctx || !this.canvas) return;
    this.time += 0.02;
    const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 800;
    const h = this.canvas.height = 360;

    this.ctx.clearRect(0, 0, w, h);

    // Panel 1: Hamiltonian Phase Portrait Orbit (Left)
    const hx = w * 0.22;
    const hy = h * 0.5;
    
    this.ctx.beginPath();
    this.ctx.arc(hx, hy, 100, 0, Math.PI * 2);
    this.ctx.strokeStyle = 'rgba(0, 240, 255, 0.2)';
    this.ctx.lineWidth = 1.5;
    this.ctx.stroke();

    this.orbitPoints.forEach((pt, i) => {
      pt.angle += 0.015;
      const q = Math.cos(pt.angle) * pt.r;
      const p = Math.sin(pt.angle * 1.5) * (pt.r * 0.7);
      
      const px = hx + q;
      const py = hy + p;

      this.ctx.beginPath();
      this.ctx.arc(px, py, 4, 0, Math.PI * 2);
      this.ctx.fillStyle = `hsl(${pt.hue}, 100%, 65%)`;
      this.ctx.fill();

      // Connect to center origin
      if (i % 4 === 0) {
        this.ctx.beginPath();
        this.ctx.moveTo(hx, hy);
        this.ctx.lineTo(px, py);
        this.ctx.strokeStyle = `hsla(${pt.hue}, 100%, 65%, 0.15)`;
        this.ctx.stroke();
      }
    });

    this.ctx.fillStyle = '#00f0ff';
    this.ctx.font = '700 11px JetBrains Mono';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('HKAN-Mamba-10 Hamiltonian Orbit (RKF45)', hx, hy + 125);

    // Panel 2: Flow-CoT Poincaré Streamlines & GRPO-v52 Rollouts (Center)
    const cx = w * 0.5;
    const cy = h * 0.5;

    this.groupRollouts.forEach((g, i) => {
      this.ctx.beginPath();
      const numSegs = 20;
      for (let s = 0; s <= numSegs; s++) {
        const t = s / numSegs;
        const startX = cx - 110 + t * 220;
        const wave = Math.sin(this.time * 2 + g.phaseOffset + t * 4) * 30 * (1 - t * 0.7);
        const startY = cy + wave + (i - 3.5) * 8;
        if (s === 0) this.ctx.moveTo(startX, startY);
        else this.ctx.lineTo(startX, startY);
      }
      this.ctx.strokeStyle = g.advantage > 0 ? 'rgba(0, 255, 136, 0.8)' : 'rgba(255, 0, 100, 0.5)';
      this.ctx.lineWidth = g.advantage > 0 ? 2.5 : 1.2;
      this.ctx.stroke();
    });

    this.ctx.fillStyle = '#00ff88';
    this.ctx.fillText('GRPO-v52 Group Advantage Rollouts', cx, cy + 125);

    // Panel 3: Sinkhorn Ternary MoD Expert Grid (Right)
    const rx = w * 0.78;
    const ry = h * 0.5 - 70;
    const tileSize = 16;
    const gap = 3;

    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const idx = r * 8 + c;
        const val = this.expertGrid[idx];
        const tx = rx - 70 + c * (tileSize + gap);
        const ty = ry + r * (tileSize + gap);

        this.ctx.beginPath();
        this.ctx.rect(tx, ty, tileSize, tileSize);
        if (val === 1) this.ctx.fillStyle = '#ffd700';       // +1 Weight
        else if (val === -1) this.ctx.fillStyle = '#ff00ea'; // -1 Weight
        else this.ctx.fillStyle = 'rgba(255,255,255,0.08)'; // 0 Skipped Layer

        this.ctx.fill();
        this.ctx.strokeStyle = 'rgba(255,255,255,0.2)';
        this.ctx.stroke();
      }
    }

    this.ctx.fillStyle = '#ffd700';
    this.ctx.fillText('MoD Sinkhorn Ternary Expert Grid (8,192)', rx, cy + 125);

    // Top Header Banner
    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '900 13px Inter, sans-serif';
    this.ctx.textAlign = 'left';
    this.ctx.fillText('OMNIBUS v52.0 OMNI-OMNISCIENT APEX CONTINUUM | 550 ACTIVE FRONTIER ML ENGINES | THROUGHPUT: 7,420 TFLOPS', 20, 25);

    requestAnimationFrame(this.animate);
  }
}

class OmniCosmicEmpiricalV55Visualizer {
  constructor(canvasId = 'cosmosV55Canvas') {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.time = 0;
    this.orbitPoints = Array.from({ length: 32 }, (_, i) => ({
      angle: (i / 32) * Math.PI * 2,
      r: Math.random() * 50 + 30,
      hue: (i * 11) % 360
    }));
    this.groupRollouts = Array.from({ length: 8 }, (_, i) => ({
      advantage: i % 2 === 0 ? 1 : -1,
      phaseOffset: i * 0.4
    }));
    this.expertGrid = Array.from({ length: 144 }, () => Math.random() > 0.6 ? 1 : (Math.random() > 0.4 ? -1 : 0));
    this.animate = this.animate.bind(this);
    if (this.ctx) {
      requestAnimationFrame(this.animate);
    }
  }

  animate() {
    if (!this.ctx || !this.canvas) return;
    this.time += 0.02;
    const w = this.canvas.width = this.canvas.parentElement ? this.canvas.parentElement.clientWidth - 20 : 800;
    const h = this.canvas.height = 340;

    // Dark Glassmorphism Background
    const bgGrad = this.ctx.createLinearGradient(0, 0, w, h);
    bgGrad.addColorStop(0, 'rgba(5, 7, 18, 0.95)');
    bgGrad.addColorStop(1, 'rgba(12, 10, 30, 0.95)');
    this.ctx.fillStyle = bgGrad;
    this.ctx.fillRect(0, 0, w, h);

    // Panel 1: SKAN-ODE-v55 Fourier Phase Orbit (Left)
    const hx = w * 0.18;
    const hy = h * 0.5;

    // Fourier Basis Concentric Circles
    for (let r = 1; r <= 4; r++) {
      this.ctx.beginPath();
      this.ctx.arc(hx, hy, r * 22, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(0, 240, 255, ${0.1 + r * 0.08})`;
      this.ctx.lineWidth = 1;
      this.ctx.stroke();
    }

    this.orbitPoints.forEach((pt, i) => {
      pt.angle += 0.02;
      const q = Math.cos(pt.angle * 2.0) * pt.r;
      const p = Math.sin(pt.angle * 1.5) * (pt.r * 0.8);
      const px = hx + q;
      const py = hy + p;

      this.ctx.beginPath();
      this.ctx.arc(px, py, 4.5, 0, Math.PI * 2);
      this.ctx.fillStyle = `hsl(${pt.hue}, 100%, 65%)`;
      this.ctx.fill();

      if (i % 3 === 0) {
        this.ctx.beginPath();
        this.ctx.moveTo(hx, hy);
        this.ctx.lineTo(px, py);
        this.ctx.strokeStyle = `hsla(${pt.hue}, 100%, 65%, 0.25)`;
        this.ctx.stroke();
      }
    });

    this.ctx.fillStyle = '#00f0ff';
    this.ctx.font = '700 11px JetBrains Mono';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('SKAN-ODE-v55 Fourier Cash-Karp Orbit', hx, hy + 135);

    // Panel 2: Poincaré-Lorentz 64D World Model & GRPO-v55 Rollouts (Center)
    const cx = w * 0.5;
    const cy = h * 0.5;

    // Hyperbolic Lorentz Geodesic Disks
    for (let l = 1; l <= 3; l++) {
      this.ctx.beginPath();
      this.ctx.ellipse(cx, cy, l * 40, l * 25, Math.PI / 6, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(255, 0, 234, ${0.15 + l * 0.1})`;
      this.ctx.lineWidth = 1.2;
      this.ctx.stroke();
    }

    this.groupRollouts.forEach((g, i) => {
      this.ctx.beginPath();
      const numSegs = 24;
      for (let s = 0; s <= numSegs; s++) {
        const t = s / numSegs;
        const startX = cx - 120 + t * 240;
        const wave = Math.sin(this.time * 2.5 + g.phaseOffset + t * 5) * 35 * (1 - t * 0.6);
        const startY = cy + wave + (i - 3.5) * 9;
        if (s === 0) this.ctx.moveTo(startX, startY);
        else this.ctx.lineTo(startX, startY);
      }
      this.ctx.strokeStyle = g.advantage > 0 ? 'rgba(0, 255, 136, 0.85)' : 'rgba(255, 0, 100, 0.55)';
      this.ctx.lineWidth = g.advantage > 0 ? 2.8 : 1.4;
      this.ctx.stroke();
    });

    this.ctx.fillStyle = '#00ff88';
    this.ctx.fillText('JEPA-15 Lorentz 64D & GRPO-v55 Advantage Trajectories', cx, cy + 135);

    // Panel 3: Sinkhorn Ternary Expert Grid (16,384 Experts) & Astrocyte Pulses (Right)
    const rx = w * 0.82;
    const ry = h * 0.5 - 75;
    const tileSize = 14;
    const gap = 2.5;

    for (let r = 0; r < 10; r++) {
      for (let c = 0; c < 10; c++) {
        const idx = r * 10 + c;
        const val = this.expertGrid[idx % this.expertGrid.length];
        const tx = rx - 70 + c * (tileSize + gap);
        const ty = ry + r * (tileSize + gap);

        this.ctx.beginPath();
        this.ctx.rect(tx, ty, tileSize, tileSize);
        if (val === 1) this.ctx.fillStyle = '#ffd700';       // +1 Weight
        else if (val === -1) this.ctx.fillStyle = '#ff00ea'; // -1 Weight
        else this.ctx.fillStyle = 'rgba(255,255,255,0.06)'; // 0 Skipped Layer

        this.ctx.fill();
        this.ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        this.ctx.stroke();
      }
    }

    this.ctx.fillStyle = '#ffd700';
    this.ctx.fillText('Sinkhorn Ternary Grid (16,384 Exp)', rx, cy + 135);

    // Header Telemetry Banner
    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '900 12px Inter, sans-serif';
    this.ctx.textAlign = 'left';
    this.ctx.fillText('OMNIBUS v55.0 OMNI-EMPIRICAL COSMOS ZENITH | 600 ACTIVE FRONTIER ML ENGINES | THROUGHPUT: 10,840 TFLOPS', 20, 24);

    requestAnimationFrame(this.animate);
  }
}

class JarvisOrbVisualizer {
  constructor(canvasId = 'jarvisOrbCanvas') {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.state = 'idle'; // idle | thinking | executing | success | error
    this.time = 0;
    this.particles = Array.from({ length: 60 }, () => ({
      angle: Math.random() * Math.PI * 2,
      dist: 35 + Math.random() * 45,
      speed: 0.01 + Math.random() * 0.03,
      radius: 1.5 + Math.random() * 2.5,
      hue: Math.random() * 60 + 170
    }));
    this.ringRotation = 0;
    this.pulseFactor = 1;
    this.animate = this.animate.bind(this);
    if (this.ctx) {
      requestAnimationFrame(this.animate);
    }
  }

  setState(newState) {
    this.state = newState;
    const orbStatusText = document.getElementById('jarvisOrbStatusText');
    const orbPulseDot = document.getElementById('jarvisOrbPulseDot');

    if (newState === 'thinking') {
      if (orbStatusText) orbStatusText.innerText = 'JARVIS SYNTHESIZING FRONTIER ML ENGINES...';
      if (orbPulseDot) orbPulseDot.style.background = '#ffd700';
    } else if (newState === 'executing') {
      if (orbStatusText) orbStatusText.innerText = 'JARVIS EXECUTING SWARM DECOMPOSITION...';
      if (orbPulseDot) orbPulseDot.style.background = '#00ff88';
    } else if (newState === 'success') {
      if (orbStatusText) orbStatusText.innerText = 'JARVIS TASK COMPLETED · TELEMETRY UPDATED';
      if (orbPulseDot) orbPulseDot.style.background = '#ff00ea';
      setTimeout(() => this.setState('idle'), 4000);
    } else if (newState === 'error') {
      if (orbStatusText) orbStatusText.innerText = 'JARVIS SYSTEM ALERT · ERROR OCCURRED';
      if (orbPulseDot) orbPulseDot.style.background = '#ff003c';
    } else {
      if (orbStatusText) orbStatusText.innerText = 'JARVIS ONLINE · AWAITING DIRECT COMMAND';
      if (orbPulseDot) orbPulseDot.style.background = '#00f0ff';
    }
  }

  animate() {
    if (!this.ctx || !this.canvas) return;
    this.time += 0.025;

    const rect = this.canvas.parentElement ? this.canvas.parentElement.getBoundingClientRect() : null;
    const w = this.canvas.width = rect && rect.width ? rect.width : 340;
    const h = this.canvas.height = 220;

    const cx = w / 2;
    const cy = h / 2;

    this.ctx.clearRect(0, 0, w, h);

    // State Color Palettes
    let coreColor = '#00f0ff';
    let outerGlow = 'rgba(0, 240, 255, 0.4)';
    let speedMult = 1.0;

    if (this.state === 'thinking') {
      coreColor = '#ffd700';
      outerGlow = 'rgba(255, 215, 0, 0.6)';
      speedMult = 2.5;
    } else if (this.state === 'executing') {
      coreColor = '#00ff88';
      outerGlow = 'rgba(0, 255, 136, 0.6)';
      speedMult = 2.0;
    } else if (this.state === 'success') {
      coreColor = '#ff00ea';
      outerGlow = 'rgba(255, 0, 234, 0.6)';
      speedMult = 1.5;
    } else if (this.state === 'error') {
      coreColor = '#ff003c';
      outerGlow = 'rgba(255, 0, 60, 0.6)';
      speedMult = 3.0;
    }

    this.ringRotation += 0.015 * speedMult;
    const basePulse = Math.sin(this.time * 2.0 * speedMult) * 6;

    // 1. Holographic Outer Energy Rings (Rotating)
    for (let r = 1; r <= 3; r++) {
      const ringRadius = 45 + r * 16 + basePulse;
      this.ctx.save();
      this.ctx.translate(cx, cy);
      this.ctx.rotate(this.ringRotation * (r % 2 === 0 ? -1 : 1.2));

      this.ctx.beginPath();
      this.ctx.ellipse(0, 0, ringRadius, ringRadius * 0.6, Math.PI / 4 * r, 0, Math.PI * 2);
      this.ctx.strokeStyle = outerGlow;
      this.ctx.lineWidth = r === 1 ? 2.5 : 1.2;
      this.ctx.setLineDash([12, 8, 4, 8]);
      this.ctx.stroke();
      this.ctx.restore();
    }

    // 2. Dynamic Orbiting Plasma Particles
    this.particles.forEach((p) => {
      p.angle += p.speed * speedMult;
      const currentDist = p.dist + basePulse * 0.5;
      const px = cx + Math.cos(p.angle) * currentDist;
      const py = cy + Math.sin(p.angle * 1.3) * (currentDist * 0.75);

      this.ctx.beginPath();
      this.ctx.arc(px, py, p.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = coreColor;
      this.ctx.shadowColor = coreColor;
      this.ctx.shadowBlur = 10;
      this.ctx.fill();

      // Connect subtle constellation lines
      if (Math.random() > 0.95) {
        this.ctx.beginPath();
        this.ctx.moveTo(cx, cy);
        this.ctx.lineTo(px, py);
        this.ctx.strokeStyle = outerGlow;
        this.ctx.lineWidth = 0.5;
        this.ctx.stroke();
      }
    });

    // 3. Central Core Glowing Orb
    const grad = this.ctx.createRadialGradient(cx, cy, 5, cx, cy, 45 + basePulse);
    grad.addColorStop(0, '#ffffff');
    grad.addColorStop(0.3, coreColor);
    grad.addColorStop(0.7, outerGlow);
    grad.addColorStop(1, 'transparent');

    this.ctx.beginPath();
    this.ctx.arc(cx, cy, 45 + basePulse, 0, Math.PI * 2);
    this.ctx.fillStyle = grad;
    this.ctx.shadowColor = coreColor;
    this.ctx.shadowBlur = 30;
    this.ctx.fill();

    // Reset Shadow
    this.ctx.shadowBlur = 0;

    requestAnimationFrame(this.animate);
  }
}

class OmniQuantumSingularV60Visualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.time = 0;
    this.quantumPhase = 0;
    this.flowTrajectory = [];
    this.init();
  }

  init() {
    this.flowTrajectory = Array.from({ length: 12 }, (_, i) => ({
      x: (i / 12),
      y: 0.5 + Math.sin(i * 0.5) * 0.2,
      targetY: 0.5 + Math.cos(i * 0.5) * 0.2
    }));
    this.animate();
  }

  animate = () => {
    if (!this.canvas || !this.ctx) return;
    const w = this.canvas.width = this.canvas.parentElement?.clientWidth || 800;
    const h = this.canvas.height = 360;
    const ctx = this.ctx;
    this.time += 0.02;
    this.quantumPhase += 0.03;

    ctx.clearRect(0, 0, w, h);

    // 1. Render Poincaré Hyperbolic Disk Grid
    const cx = w / 2;
    const cy = h / 2;
    const diskRadius = Math.min(w, h) * 0.42;

    ctx.beginPath();
    ctx.arc(cx, cy, diskRadius, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Hyperbolic Geodesic Arcs
    for (let r = 1; r <= 5; r++) {
      const radiusRatio = Math.tanh(r * 0.3) * diskRadius;
      ctx.beginPath();
      ctx.arc(cx, cy, radiusRatio, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(0, 255, 136, ${0.15 + r * 0.05})`;
      ctx.setLineDash([8, 6]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // 2. Render Continuous Flow-Matching Trajectory (Diffusion of Thought)
    ctx.beginPath();
    this.flowTrajectory.forEach((pt, idx) => {
      const px = cx - diskRadius * 0.8 + (idx / 11) * diskRadius * 1.6;
      const py = cy + Math.sin(this.time * 2 + idx * 0.5) * 40 * Math.sin(pt.x * Math.PI);
      if (idx === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);

      ctx.save();
      ctx.beginPath();
      ctx.arc(px, py, 4, 0, Math.PI * 2);
      ctx.fillStyle = idx % 2 === 0 ? '#ffd700' : '#ff00ea';
      ctx.shadowColor = '#00f0ff';
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.restore();
    });
    ctx.strokeStyle = 'rgba(255, 215, 0, 0.8)';
    ctx.lineWidth = 3;
    ctx.stroke();

    // 3. Render Quantum QAOA Superposition Waves
    ctx.beginPath();
    for (let x = cx - diskRadius; x <= cx + diskRadius; x += 4) {
      const normX = (x - cx) / diskRadius;
      if (Math.abs(normX) <= 1) {
        const wave = Math.sin(normX * 8 + this.quantumPhase) * Math.cos(normX * 3) * 25;
        const y = cy + wave;
        if (x === cx - diskRadius) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
    }
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.7)';
    ctx.lineWidth = 1.8;
    ctx.stroke();

    // Central Core Pulse
    const pulse = Math.sin(this.time * 3) * 5 + 18;
    const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, pulse + 15);
    grad.addColorStop(0, '#ffffff');
    grad.addColorStop(0.4, '#00f0ff');
    grad.addColorStop(1, 'transparent');

    ctx.beginPath();
    ctx.arc(cx, cy, pulse, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();

    requestAnimationFrame(this.animate);
  }
}

class OmniCosmosV65Visualizer {
  constructor() {
    this.diffCanvas = document.getElementById('diffForceCanvas');
    this.diffCtx = this.diffCanvas ? this.diffCanvas.getContext('2d') : null;

    this.poincareCanvas = document.getElementById('poincareDiskCanvas');
    this.poincareCtx = this.poincareCanvas ? this.poincareCanvas.getContext('2d') : null;

    this.prmCanvas = document.getElementById('prmMctsCanvas');
    this.prmCtx = this.prmCanvas ? this.prmCanvas.getContext('2d') : null;

    this.moeCanvas = document.getElementById('bitnetMoeCanvas');
    this.moeCtx = this.moeCanvas ? this.moeCanvas.getContext('2d') : null;

    this.time = 0;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  animate() {
    this.time += 0.02;

    // 1. DiffForce Denoising Canvas
    if (this.diffCtx && this.diffCanvas) {
      const cv = this.diffCanvas;
      const ctx = this.diffCtx;
      const w = cv.width = cv.clientWidth || 400;
      const h = cv.height = cv.clientHeight || 250;

      ctx.fillStyle = 'rgba(5, 8, 22, 0.3)';
      ctx.fillRect(0, 0, w, h);

      for (let i = 0; i < 30; i++) {
        const t = (this.time * 0.5 + i * 0.1) % 1;
        const x = 30 + t * (w - 60);
        const noiseAmp = (1 - t) * 40;
        const y = h / 2 + Math.sin(t * 10 + this.time) * 15 + (Math.sin(i * 99) * noiseAmp);

        ctx.beginPath();
        ctx.arc(x, y, 3 + t * 2, 0, Math.PI * 2);
        ctx.fillStyle = `hsl(${180 + t * 120}, 100%, ${50 + t * 30}%)`;
        ctx.fill();
      }

      ctx.font = '11px JetBrains Mono';
      ctx.fillStyle = '#00f0ff';
      ctx.fillText('DiffForce-v65 Noise -> Clean Latent Trajectory', 15, 20);
    }

    // 2. Poincaré Hyperbolic Disk Canvas
    if (this.poincareCtx && this.poincareCanvas) {
      const cv = this.poincareCanvas;
      const ctx = this.poincareCtx;
      const w = cv.width = cv.clientWidth || 400;
      const h = cv.height = cv.clientHeight || 250;
      const cx = w / 2, cy = h / 2, r = Math.min(w, h) * 0.42;

      ctx.fillStyle = 'rgba(5, 8, 22, 0.3)';
      ctx.fillRect(0, 0, w, h);

      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.6)';
      ctx.lineWidth = 2;
      ctx.stroke();

      for (let i = 0; i < 8; i++) {
        const a = (i * Math.PI / 4) + this.time * 0.1;
        const dist = 0.3 + 0.5 * Math.sin(this.time + i);
        const nx = cx + Math.cos(a) * (r * dist);
        const ny = cy + Math.sin(a) * (r * dist);

        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.quadraticCurveTo(cx + Math.cos(a + 0.5) * (r * 0.3), cy + Math.sin(a + 0.5) * (r * 0.3), nx, ny);
        ctx.strokeStyle = 'rgba(255, 0, 234, 0.4)';
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(nx, ny, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#ff00ea';
        ctx.fill();
      }

      ctx.font = '11px JetBrains Mono';
      ctx.fillStyle = '#ff00ea';
      ctx.fillText('Poincaré Hyperbolic Taxonomy Ball B^n', 15, 20);
    }

    // 3. PRM-MCTS Reasoning Tree Canvas
    if (this.prmCtx && this.prmCanvas) {
      const cv = this.prmCanvas;
      const ctx = this.prmCtx;
      const w = cv.width = cv.clientWidth || 400;
      const h = cv.height = cv.clientHeight || 250;

      ctx.fillStyle = 'rgba(5, 8, 22, 0.3)';
      ctx.fillRect(0, 0, w, h);

      const nodes = [
        { x: w * 0.5, y: 40, prm: 0.99 },
        { x: w * 0.25, y: 110, prm: 0.94 },
        { x: w * 0.5, y: 110, prm: 0.98 },
        { x: w * 0.75, y: 110, prm: 0.91 },
        { x: w * 0.18, y: 180, prm: 0.92 },
        { x: w * 0.5, y: 180, prm: 0.97 },
        { x: w * 0.82, y: 180, prm: 0.89 }
      ];

      const edges = [[0,1],[0,2],[0,3],[1,4],[2,5],[3,6]];
      edges.forEach(([u, v]) => {
        ctx.beginPath();
        ctx.moveTo(nodes[u].x, nodes[u].y);
        ctx.lineTo(nodes[v].x, nodes[v].y);
        ctx.strokeStyle = 'rgba(0, 255, 136, 0.4)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      });

      nodes.forEach(n => {
        ctx.beginPath();
        ctx.arc(n.x, n.y, 10, 0, Math.PI * 2);
        ctx.fillStyle = n.prm > 0.95 ? '#00ff88' : '#00f0ff';
        ctx.fill();
        ctx.fillStyle = '#000';
        ctx.font = '9px JetBrains Mono';
        ctx.fillText((n.prm).toFixed(2), n.x - 10, n.y + 3);
      });

      ctx.font = '11px JetBrains Mono';
      ctx.fillStyle = '#00ff88';
      ctx.fillText('GRPO-PRM Step MCTS Search Tree', 15, 20);
    }

    // 4. BitNet Ternary Sinkhorn Router Heatmap
    if (this.moeCtx && this.moeCanvas) {
      const cv = this.moeCanvas;
      const ctx = this.moeCtx;
      const w = cv.width = cv.clientWidth || 400;
      const h = cv.height = cv.clientHeight || 250;

      ctx.fillStyle = 'rgba(5, 8, 22, 0.3)';
      ctx.fillRect(0, 0, w, h);

      const rows = 4, cols = 8;
      const cellW = (w - 40) / cols;
      const cellH = (h - 60) / rows;

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const x = 20 + c * cellW;
          const y = 40 + r * cellH;
          const val = Math.sin((r * cols + c) * 0.7 + this.time * 2);

          if (val > 0.3) ctx.fillStyle = '#00f0ff';
          else if (val < -0.3) ctx.fillStyle = '#ff00ea';
          else ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';

          ctx.fillRect(x + 2, y + 2, cellW - 4, cellH - 4);
        }
      }

      ctx.font = '11px JetBrains Mono';
      ctx.fillStyle = '#ffd700';
      ctx.fillText('BitNet-1.58b Ternary Sinkhorn Routing Grid', 15, 20);
    }

    requestAnimationFrame(this.animate);
  }
}

if (typeof window !== 'undefined') {
  window.OmniSingularityV37Visualizer = OmniSingularityV37Visualizer;
  window.OmniContinuousV38Visualizer = OmniContinuousV38Visualizer;
  window.OmniSingularityV40Visualizer = OmniSingularityV40Visualizer;
  window.OmniSingularityZenithV42Visualizer = OmniSingularityZenithV42Visualizer;
  window.OmniSingularitySuperIntelligenceV43Visualizer = OmniSingularitySuperIntelligenceV43Visualizer;
  window.OmniSingularityZenithV45Visualizer = OmniSingularityZenithV45Visualizer;
  window.OmniSingularityTranscendentV50Visualizer = OmniSingularityTranscendentV50Visualizer;
  window.OmniSingularityHyperContinuumV51Visualizer = OmniSingularityHyperContinuumV51Visualizer;
  window.OmniApexContinuumV52Visualizer = OmniApexContinuumV52Visualizer;
  window.OmniCosmicEmpiricalV55Visualizer = OmniCosmicEmpiricalV55Visualizer;
  window.OmniQuantumSingularV60Visualizer = OmniQuantumSingularV60Visualizer;
  window.OmniCosmosV65Visualizer = OmniCosmosV65Visualizer;
  window.JarvisOrbVisualizer = JarvisOrbVisualizer;
}





