class CodeGenerator {
  constructor(outputElementId, speed = 15) {
    this.outputElement = document.getElementById(outputElementId);
    this.speed = speed;
    this.templates = {
      javascript: `// Architect: Designed Express API Route
// Coder: Implementing middleware and handler
const express = require('express');
const router = express.Router();

/**
 * @route GET /api/v1/agent/status
 * @desc Retrieve current status of AI agents
 */
router.get('/status', authMiddleware, async (req, res) => {
  try {
    const activeAgents = await AgentManager.getActive();
    
    return res.status(200).json({
      success: true,
      count: activeAgents.length,
      data: activeAgents,
      timestamp: Date.now()
    });
  } catch (error) {
    Logger.error("Failed to fetch agent status");
    return res.status(500).json({ error: "Internal Server Error" });
  }
});

module.exports = router;`,
      python: `# Architect: System architecture requires high-performance async API
# Coder: Building FastAPI endpoint with Pydantic validation
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

class TaskRequest(BaseModel):
    task_id: str
    priority: int = 1
    parameters: dict
    
@app.post("/api/tasks/submit", response_model=TaskResponse)
async def submit_task(request: TaskRequest, db: Session = Depends(get_db)):
    """
    Submits a new task to the processing queue.
    """
    if request.priority < 0:
        raise HTTPException(status_code=400, detail="Invalid priority")
        
    task = await queue_manager.add(request)
    return {"status": "queued", "task_id": task.id}`,
      rust: `// Architect: Memory safety is critical for the agent runtime
// Coder: Implementing Core Structs and Traits in Rust
use std::collections::HashMap;
use tokio::sync::mpsc;

pub struct AgentRuntime {
    id: String,
    state: AgentState,
    memory: HashMap<String, Vec<u8>>,
    channel: mpsc::Sender<Message>,
}

impl AgentRuntime {
    pub fn new(id: &str, sender: mpsc::Sender<Message>) -> Self {
        AgentRuntime {
            id: id.to_string(),
            state: AgentState::Idle,
            memory: HashMap::new(),
            channel: sender,
        }
    }
    
    pub async fn process_task(&mut self, task: Task) -> Result<(), Error> {
        self.state = AgentState::Processing;
        // Execute neural pathways
        let result = self.execute_internal(task).await?;
        Ok(result)
    }
}`,
      html: `<!-- Architect: Component structure for Agent Profile -->
<!-- Coder: Building semantic HTML with accessibility -->
<section class="agent-profile" aria-labelledby="profile-heading">
  <header class="profile-header glassmorphism">
    <img src="/assets/avatars/agent-x.svg" alt="Agent X Avatar" class="avatar" />
    <div class="profile-info">
      <h2 id="profile-heading" class="gradient-text">Agent X-99</h2>
      <span class="badge status-active">Online</span>
    </div>
  </header>
  
  <article class="capabilities-grid">
    <div class="capability-card">
      <h3>Natural Language</h3>
      <progress value="95" max="100">95%</progress>
    </div>
    <div class="capability-card">
      <h3>Code Generation</h3>
      <progress value="88" max="100">88%</progress>
    </div>
  </article>
</section>`
    };
  }

  highlightSyntax(text) {
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Comments
    html = html.replace(/(\/\/[^\n]*|<!--[\s\S]*?-->|#[^\n]*)/g, '<span class="comment">$1</span>');
    // Strings
    html = html.replace(/(["'`])(?:(?=(\\?))\2.)*?\1/g, '<span class="string">$&</span>');
    // Numbers
    html = html.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="number">$1</span>');
    // Keywords
    const keywords = ['const', 'let', 'var', 'function', 'class', 'def', 'fn', 'impl', 'struct', 'pub', 'use', 'async', 'await', 'return', 'if', 'else', 'try', 'catch', 'import', 'from'];
    const kwRegex = new RegExp(`\\b(${keywords.join('|')})\\b`, 'g');
    html = html.replace(kwRegex, '<span class="keyword">$1</span>');
    // Types/Classes
    html = html.replace(/\b([A-Z][a-zA-Z0-9_]*)\b/g, '<span class="type">$1</span>');
    // Functions/Methods
    html = html.replace(/\b([a-zA-Z0-9_]+)(?=\s*\()/g, '<span class="function">$1</span>');
    
    return html;
  }

  generate(language, taskDescription) {
    return new Promise((resolve) => {
      if (!this.outputElement) {
        resolve();
        return;
      }

      this.outputElement.innerHTML = '';
      const template = this.templates[language] || this.templates.javascript;
      let currentIndex = 0;

      const cursor = document.createElement('span');
      cursor.className = 'cursor-blink';
      cursor.innerHTML = '&#9608;';
      
      const contentSpan = document.createElement('span');
      this.outputElement.appendChild(contentSpan);
      this.outputElement.appendChild(cursor);

      const typeChar = () => {
        if (currentIndex < template.length) {
          contentSpan.textContent = template.substring(0, currentIndex + 1);
          // Only highlight periodically for performance, or at the end. For typewriter, doing it end is safer, but let's do simple innerHTML replace periodically
          if (currentIndex % 10 === 0 || currentIndex === template.length - 1) {
             contentSpan.innerHTML = this.highlightSyntax(template.substring(0, currentIndex + 1));
          }
          currentIndex++;
          setTimeout(typeChar, this.speed + (Math.random() * 20 - 10)); // Variable typing speed
        } else {
          contentSpan.innerHTML = this.highlightSyntax(template);
          resolve();
        }
      };

      typeChar();
    });
  }
}

class AgentCodeSession {
  constructor(outputElementId, indicatorElementId) {
    this.generator = new CodeGenerator(outputElementId);
    this.indicatorElement = document.getElementById(indicatorElementId);
    this.agents = [
      { name: 'Architect (Design)', icon: 'fa-sitemap', color: '#7000ff' },
      { name: 'Coder (Implement)', icon: 'fa-code', color: '#00f0ff' },
      { name: 'Reviewer (Test)', icon: 'fa-check-double', color: '#00ff66' }
    ];
  }

  setAgentIndicator(agentIndex) {
    if (!this.indicatorElement) return;
    if (agentIndex === -1) {
      this.indicatorElement.innerHTML = '';
      return;
    }
    const agent = this.agents[agentIndex];
    this.indicatorElement.innerHTML = `
      <div class="agent-writing-indicator" style="color: ${agent.color}">
        <i class="fas ${agent.icon}"></i>
        <span>${agent.name} is typing</span>
        <div class="status-dot cursor-blink" style="background-color: ${agent.color}"></div>
      </div>
    `;
  }

  async runSession(language, taskDescription) {
    // Architect thinking
    this.setAgentIndicator(0);
    await new Promise(r => setTimeout(r, 1500));
    
    // Coder typing
    this.setAgentIndicator(1);
    await this.generator.generate(language, taskDescription);
    
    // Reviewer checking
    this.setAgentIndicator(2);
    await new Promise(r => setTimeout(r, 2000));
    
    // Done
    this.setAgentIndicator(-1);
    if(this.indicatorElement) {
        this.indicatorElement.innerHTML = `<div class="agent-writing-indicator" style="color: #00ff66"><i class="fas fa-check"></i> <span>Code Generation Complete</span></div>`;
    }
  }

  clear() {
    if (this.generator.outputElement) this.generator.outputElement.innerHTML = '';
    this.setAgentIndicator(-1);
  }
}

window.CodeArena = { CodeGenerator, AgentCodeSession };
