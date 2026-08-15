class TrainingChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.data = [];
    this.maxPoints = 50;
    this.canvasId = canvasId;
    
    // Setup canvas sizing
    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = 250;
    this.draw();
  }

  addPoint(epoch, loss, accuracy) {
    this.data.push({ epoch, loss, accuracy });
    if (this.data.length > this.maxPoints) {
      this.data.shift();
    }
    this.draw();
  }

  draw() {
    if (!this.ctx || !this.canvas) return;
    const { width, height } = this.canvas;
    const ctx = this.ctx;

    // Clear background
    ctx.clearRect(0, 0, width, height);

    // Draw Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < height; i += 25) {
      ctx.moveTo(0, i);
      ctx.lineTo(width, i);
    }
    for (let i = 0; i < width; i += 50) {
      ctx.moveTo(i, 0);
      ctx.lineTo(i, height);
    }
    ctx.stroke();

    if (this.data.length === 0) return;

    // Layout margins
    const padding = 40;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    const maxLoss = Math.max(...this.data.map(d => d.loss), 1);
    
    // Draw Axis Labels
    ctx.fillStyle = '#8b92a5';
    ctx.font = '10px "JetBrains Mono"';
    ctx.textAlign = 'center';
    
    // X-axis
    this.data.forEach((d, i) => {
      if (i % 5 === 0 || i === this.data.length - 1) {
        const x = padding + (i / Math.max(1, this.data.length - 1)) * chartWidth;
        ctx.fillText(d.epoch, x, height - 15);
      }
    });

    // Helper to draw curve
    const drawCurve = (key, gradientColors, isLoss) => {
      ctx.beginPath();
      let lastX, lastY;
      
      this.data.forEach((d, i) => {
        const x = padding + (i / Math.max(1, this.data.length - 1)) * chartWidth;
        const val = isLoss ? d.loss / maxLoss : d.accuracy;
        const y = height - padding - val * chartHeight;
        
        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          const cpX = (lastX + x) / 2;
          ctx.bezierCurveTo(cpX, lastY, cpX, y, x, y);
        }
        lastX = x;
        lastY = y;
      });

      // Gradients
      const strokeGrad = ctx.createLinearGradient(0, 0, width, 0);
      strokeGrad.addColorStop(0, gradientColors[0]);
      strokeGrad.addColorStop(1, gradientColors[1]);

      ctx.strokeStyle = strokeGrad;
      ctx.lineWidth = 3;
      ctx.stroke();

      // Fill area
      ctx.lineTo(lastX, height - padding);
      ctx.lineTo(padding, height - padding);
      ctx.closePath();
      
      const fillGrad = ctx.createLinearGradient(0, 0, 0, height);
      fillGrad.addColorStop(0, `rgba(${gradientColors[2]}, 0.15)`);
      fillGrad.addColorStop(1, 'rgba(0,0,0,0)');
      
      ctx.fillStyle = fillGrad;
      ctx.fill();

      // Glowing dot
      if (lastX !== undefined && lastY !== undefined) {
        ctx.beginPath();
        ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
        ctx.fillStyle = gradientColors[1];
        ctx.fill();
        
        ctx.beginPath();
        ctx.arc(lastX, lastY, 10, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${gradientColors[2]}, 0.3)`;
        ctx.fill();
      }
    };

    // Accuracy Curve (cyan -> blue)
    drawCurve('accuracy', ['#00f0ff', '#0055ff', '0, 240, 255'], false);
    // Loss Curve (red -> orange)
    drawCurve('loss', ['#ff003c', '#ffb800', '255, 0, 60'], true);

    // Legend
    ctx.font = '12px "Inter"';
    ctx.textAlign = 'right';
    ctx.fillStyle = '#f0f2f5';
    
    // Loss legend
    ctx.fillStyle = '#ffb800';
    ctx.fillText('Loss', width - 20, 20);
    
    // Accuracy legend
    ctx.fillStyle = '#00f0ff';
    ctx.fillText('Accuracy', width - 20, 35);
  }
}

class ModelBenchmark {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.algorithms = [];
    this.animProgress = 0;
    
    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = 250;
    this.draw();
  }

  setData(algorithms) {
    this.algorithms = algorithms.sort((a, b) => b.score - a.score);
    this.animProgress = 0;
    this.animate();
  }

  animate() {
    if (this.animProgress < 1) {
      this.animProgress += 0.05;
      this.draw();
      requestAnimationFrame(() => this.animate());
    }
  }

  draw() {
    if (!this.ctx || !this.canvas || this.algorithms.length === 0) return;
    const { width, height } = this.canvas;
    const ctx = this.ctx;

    ctx.clearRect(0, 0, width, height);

    const padding = 30;
    const barHeight = (height - padding * 2) / this.algorithms.length - 10;
    
    this.algorithms.forEach((algo, i) => {
      const y = padding + i * (barHeight + 10);
      const maxBarWidth = width - 150;
      const barWidth = maxBarWidth * algo.score * this.animProgress;

      // Label
      ctx.fillStyle = '#f0f2f5';
      ctx.font = '12px "Inter"';
      ctx.textAlign = 'right';
      ctx.fillText(algo.name, 100, y + barHeight / 1.5);

      // Track
      ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.beginPath();
      ctx.roundRect(110, y, maxBarWidth, barHeight, 5);
      ctx.fill();

      // Bar
      const grad = ctx.createLinearGradient(110, 0, 110 + barWidth, 0);
      grad.addColorStop(0, algo.color);
      grad.addColorStop(1, '#ffffff');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(110, y, barWidth, barHeight, 5);
      ctx.fill();

      // Score
      ctx.fillStyle = algo.color;
      ctx.textAlign = 'left';
      ctx.font = 'bold 12px "JetBrains Mono"';
      ctx.fillText((algo.score * this.animProgress).toFixed(3), 110 + barWidth + 10, y + barHeight / 1.5);
    });
  }
}

class TrainingSession {
  constructor(chartId, benchmarkId, logId) {
    this.chart = new TrainingChart(chartId);
    this.benchmark = new ModelBenchmark(benchmarkId);
    this.logElement = document.getElementById(logId);
    this.running = false;
    this.currentEpoch = 0;
  }

  log(msg) {
    if (!this.logElement) return;
    const div = document.createElement('div');
    div.className = 'log-entry info';
    div.innerHTML = `<span class="log-time">${new Date().toLocaleTimeString()}</span> ${msg}`;
    this.logElement.appendChild(div);
    this.logElement.scrollTop = this.logElement.scrollHeight;
  }

  async start(modelName, epochs) {
    if (this.running) return;
    this.running = true;
    this.chart.data = [];
    this.currentEpoch = 0;
    
    if (this.logElement) this.logElement.innerHTML = '';
    this.log(`Starting training for ${modelName} (${epochs} epochs)...`);

    let loss = 2.5;
    let accuracy = 0.1;

    const trainStep = () => {
      if (!this.running || this.currentEpoch >= epochs) {
        this.running = false;
        this.log(`Training completed for ${modelName}.`);
        this.generateBenchmark();
        return;
      }

      this.currentEpoch++;
      
      // Simulated decay with noise
      loss = loss * 0.95 + (Math.random() * 0.1 - 0.02);
      if (loss < 0.1) loss = 0.1 + Math.random() * 0.05;
      
      accuracy = accuracy + (1 - accuracy) * 0.08 + (Math.random() * 0.02 - 0.01);
      if (accuracy > 0.99) accuracy = 0.99;

      this.chart.addPoint(this.currentEpoch, Math.max(0, loss), Math.min(1, Math.max(0, accuracy)));
      
      if (this.currentEpoch % 10 === 0 || this.currentEpoch === epochs) {
        this.log(`Epoch ${this.currentEpoch}/${epochs} - Loss: ${loss.toFixed(4)}, Acc: ${(accuracy * 100).toFixed(2)}%`);
      }

      setTimeout(trainStep, 50);
    };

    trainStep();
  }

  stop() {
    this.running = false;
    this.log('Training forcefully stopped.');
  }

  isRunning() {
    return this.running;
  }

  generateBenchmark() {
    const algos = [
      { name: 'KATFlow-Mamba5 (v39)', score: 0.985 + Math.random() * 0.014, color: '#00f0ff' },
      { name: 'GRPO-v39 Optimizer', score: 0.978 + Math.random() * 0.02, color: '#7000ff' },
      { name: 'Poincaré-Minkowski (v39)', score: 0.969 + Math.random() * 0.025, color: '#00ff66' },
      { name: 'SubBit-Sinkhorn MoE', score: 0.958 + Math.random() * 0.03, color: '#ffb800' },
      { name: 'Astrocyte-SNN (v39)', score: 0.945 + Math.random() * 0.04, color: '#ff003c' }
    ];
    this.benchmark.setData(algos);
  }
}

window.TrainingLab = { TrainingChart, ModelBenchmark, TrainingSession };
