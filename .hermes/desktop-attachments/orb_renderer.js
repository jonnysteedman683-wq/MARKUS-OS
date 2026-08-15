/**
 * OMNIBUS Floating Rotating Glowing Orb Renderer
 * HTML5 Canvas 3D Particle & Orbital Ring Core
 */
class GlowingOrbVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.width = this.canvas.width = 300;
    this.height = this.canvas.height = 300;
    this.particles = [];
    this.numParticles = 120;
    this.angleX = 0;
    this.angleY = 0;
    this.angleZ = 0;
    this.speed = 0.008;
    this.state = 'idle'; // 'idle', 'thinking', 'responding'
    this.pulseFactor = 0;

    this.initParticles();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  initParticles() {
    this.particles = [];
    const radius = 75;
    for (let i = 0; i < this.numParticles; i++) {
      // Uniform spherical sampling
      const theta = Math.acos(2 * Math.random() - 1);
      const phi = 2 * Math.PI * Math.random();
      
      this.particles.push({
        x: radius * Math.sin(theta) * Math.cos(phi),
        y: radius * Math.sin(theta) * Math.sin(phi),
        z: radius * Math.cos(theta),
        baseX: radius * Math.sin(theta) * Math.cos(phi),
        baseY: radius * Math.sin(theta) * Math.sin(phi),
        baseZ: radius * Math.cos(theta),
        size: Math.random() * 2.2 + 0.8,
        color: Math.random() > 0.5 ? '#00f0ff' : '#ff00ea'
      });
    }
  }

  setState(newState) {
    this.state = newState;
    if (newState === 'thinking') {
      this.speed = 0.035;
    } else if (newState === 'responding') {
      this.speed = 0.015;
    } else {
      this.speed = 0.008;
    }
  }

  rotateX(p, angle) {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const y = p.y * cos - p.z * sin;
    const z = p.y * sin + p.z * cos;
    return { x: p.x, y, z };
  }

  rotateY(p, angle) {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const x = p.x * cos + p.z * sin;
    const z = -p.x * sin + p.z * cos;
    return { x, y: p.y, z };
  }

  rotateZ(p, angle) {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const x = p.x * cos - p.y * sin;
    const y = p.x * sin + p.y * cos;
    return { x, y, z: p.z };
  }

  drawOrbitalRing(radiusX, radiusY, angle, color, strokeWidth = 1.5) {
    this.ctx.save();
    this.ctx.translate(this.width / 2, this.height / 2);
    this.ctx.rotate(angle);
    this.ctx.beginPath();
    this.ctx.ellipse(0, 0, radiusX, radiusY, 0, 0, Math.PI * 2);
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = strokeWidth;
    this.ctx.shadowColor = color;
    this.ctx.shadowBlur = 15;
    this.ctx.stroke();
    this.ctx.restore();
  }

  animate() {
    this.ctx.clearRect(0, 0, this.width, this.height);

    const centerX = this.width / 2;
    const centerY = this.height / 2;

    this.angleX += this.speed;
    this.angleY += this.speed * 1.3;
    this.angleZ += this.speed * 0.7;
    this.pulseFactor += 0.04;

    const currentPulse = Math.sin(this.pulseFactor) * (this.state === 'thinking' ? 12 : 5);

    // 1. Draw Volumetric Core Glow
    const glowGradient = this.ctx.createRadialGradient(
      centerX, centerY, 5,
      centerX, centerY, 90 + currentPulse
    );
    if (this.state === 'thinking') {
      glowGradient.addColorStop(0, 'rgba(255, 0, 234, 0.9)');
      glowGradient.addColorStop(0.4, 'rgba(191, 0, 255, 0.5)');
      glowGradient.addColorStop(0.8, 'rgba(0, 240, 255, 0.2)');
      glowGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    } else {
      glowGradient.addColorStop(0, 'rgba(0, 240, 255, 0.8)');
      glowGradient.addColorStop(0.5, 'rgba(112, 0, 255, 0.35)');
      glowGradient.addColorStop(0.85, 'rgba(255, 0, 234, 0.15)');
      glowGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    }
    this.ctx.fillStyle = glowGradient;
    this.ctx.beginPath();
    this.ctx.arc(centerX, centerY, 95 + currentPulse, 0, Math.PI * 2);
    this.ctx.fill();

    // 2. Draw Outer Rotating Cyber Rings
    this.drawOrbitalRing(105 + currentPulse * 0.5, 45, this.angleY, 'rgba(0, 240, 255, 0.8)', 2.0);
    this.drawOrbitalRing(115 + currentPulse * 0.5, 38, -this.angleX * 1.2, 'rgba(255, 0, 234, 0.75)', 1.5);
    this.drawOrbitalRing(90, 90, this.angleZ, 'rgba(0, 255, 136, 0.4)', 1.0);

    // 3. Project and Render 3D Particles
    const projected = [];
    for (let p of this.particles) {
      let r = this.rotateX(p, this.angleX);
      r = this.rotateY(r, this.angleY);
      r = this.rotateZ(r, this.angleZ);

      // Perspective projection
      const perspective = 300 / (300 + r.z);
      const projX = centerX + r.x * perspective;
      const projY = centerY + r.y * perspective;
      const projSize = Math.max(0.5, p.size * perspective);

      projected.push({
        x: projX,
        y: projY,
        z: r.z,
        size: projSize,
        color: p.color
      });
    }

    // Sort by Z for proper depth ordering
    projected.sort((a, b) => b.z - a.z);

    // Render particles & connect near neighbors
    for (let i = 0; i < projected.length; i++) {
      const p = projected[i];
      const alpha = Math.min(1.0, Math.max(0.2, (p.z + 100) / 200));

      this.ctx.fillStyle = p.color;
      this.ctx.globalAlpha = alpha;
      this.ctx.shadowColor = p.color;
      this.ctx.shadowBlur = 8;
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      this.ctx.fill();

      // Draw faint interconnecting energy lines
      for (let j = i + 1; j < Math.min(i + 4, projected.length); j++) {
        const p2 = projected[j];
        const dist = Math.hypot(p.x - p2.x, p.y - p2.y);
        if (dist < 40) {
          this.ctx.strokeStyle = p.color;
          this.ctx.globalAlpha = (1 - dist / 40) * 0.25 * alpha;
          this.ctx.lineWidth = 0.8;
          this.ctx.beginPath();
          this.ctx.moveTo(p.x, p.y);
          this.ctx.lineTo(p2.x, p2.y);
          this.ctx.stroke();
        }
      }
    }

    this.ctx.globalAlpha = 1.0;
    requestAnimationFrame(this.animate);
  }
}

window.GlowingOrbVisualizer = GlowingOrbVisualizer;
