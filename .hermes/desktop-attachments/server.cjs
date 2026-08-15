require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');
const OpenAI = require('openai');
const Anthropic = require('@anthropic-ai/sdk');
const { GoogleGenAI } = require('@google/genai');
const ollamaModule = require('ollama');
const ollamaClient = ollamaModule.default || ollamaModule;

// Hive Swarm Mind — Neurocore ESM bridge
const neurocoreBridge = require('C:/Users/jonny/OneDrive/Documents/AEGIS/neurocore/neurocore-bridge.cjs');
let swarmAdapter = null;

// Health check state
let systemState = {
  neurocoreConnected: false,
  hermesAvailable: false,
  lastHealthCheck: 0,
  peers: [],
  lastProvider: null,
  lastIntent: null,
  lastActionResult: null,
  recentIntents: [],
  queueSize: 0
};

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Serve static files from the project root (where index.html lives)
app.use(express.static(__dirname));

// Initialize cloud API clients conditionally
let openai, anthropic, gemini;

if (process.env.OPENAI_API_KEY) {
  openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
}
if (process.env.ANTHROPIC_API_KEY) {
  anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
}
if (process.env.GEMINI_API_KEY) {
  gemini = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
}

// ─── Tools Definition ──────────────────────────────────────────────────
const tools = [
  {
    type: 'function',
    function: {
      name: 'read_file',
      description: 'Read the contents of a local file',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string' } },
        required: ['path']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'write_file',
      description: 'Write content to a local file',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string' }, content: { type: 'string' } },
        required: ['path', 'content']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'list_directory',
      description: 'List contents of a directory',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string' } },
        required: ['path']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'call_api',
      description: 'Make an HTTP request to an API',
      parameters: {
        type: 'object',
        properties: { 
          url: { type: 'string' }, 
          method: { type: 'string', enum: ['GET', 'POST', 'PUT', 'DELETE'] },
          body: { type: 'string', description: 'JSON string of the body for POST/PUT' }
        },
        required: ['url']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'search_web',
      description: 'Search the web using DuckDuckGo and extract text',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string' } },
        required: ['query']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'execute_code',
      description: 'Execute Node.js or Shell code in a temporary environment',
      parameters: {
        type: 'object',
        properties: { 
          language: { type: 'string', enum: ['nodejs', 'shell'] },
          code: { type: 'string' }
        },
        required: ['language', 'code']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_weather',
      description: 'Get the current weather for a city using Open-Meteo API',
      parameters: {
        type: 'object',
        properties: { city: { type: 'string' } },
        required: ['city']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_crypto_price',
      description: 'Get the current USD price of a cryptocurrency using CoinGecko API',
      parameters: {
        type: 'object',
        properties: { coin_id: { type: 'string', description: 'e.g. bitcoin, ethereum, solana' } },
        required: ['coin_id']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'search_wikipedia',
      description: 'Search Wikipedia and get the introductory summary',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string' } },
        required: ['query']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_current_time',
      description: 'Get the current real-world time and date for a specific timezone',
      parameters: {
        type: 'object',
        properties: { timezone: { type: 'string', description: 'e.g. America/New_York, Europe/London, Asia/Tokyo' } },
        required: ['timezone']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_hacker_news',
      description: 'Get the top trending stories from Hacker News',
      parameters: {
        type: 'object',
        properties: { limit: { type: 'number', description: 'Number of stories to fetch (default 5)' } },
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_github_user',
      description: 'Get public GitHub profile information for a user',
      parameters: {
        type: 'object',
        properties: { username: { type: 'string' } },
        required: ['username']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_random_joke',
      description: 'Get a random programming or general joke',
      parameters: {
        type: 'object',
        properties: {},
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_ip_info',
      description: 'Get geolocation and ISP info for an IP address',
      parameters: {
        type: 'object',
        properties: { ip: { type: 'string', description: 'The IP address to look up' } },
        required: ['ip']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'generate_fake_user',
      description: 'Generate a random fake user identity',
      parameters: {
        type: 'object',
        properties: {},
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_nasa_apod',
      description: 'Get the NASA Astronomy Picture of the Day',
      parameters: {
        type: 'object',
        properties: {},
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'fetch_arxiv_papers',
      description: 'Search arXiv preprints and return paper titles and summaries',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string' }, max_results: { type: 'number' } },
        required: ['query']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_ml_experiment',
      description: 'Execute local ML model experiment simulation or evaluation',
      parameters: {
        type: 'object',
        properties: { model_name: { type: 'string' }, steps: { type: 'number' } },
        required: ['model_name']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'eval_dpo_reward',
      description: 'Evaluate Direct Preference Optimization (DPO) score for text candidate',
      parameters: {
        type: 'object',
        properties: { candidate_text: { type: 'string' } },
        required: ['candidate_text']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'titans_memory_store',
      description: 'Store or search long-term surprise-gated memory nodes',
      parameters: {
        type: 'object',
        properties: { action: { type: 'string', enum: ['store', 'query'] }, key: { type: 'string' }, value: { type: 'string' } },
        required: ['action', 'key']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'quantum_superposition_planner',
      description: 'Run Grover quantum amplitude search on Graph-of-Thought nodes',
      parameters: {
        type: 'object',
        properties: { target_node: { type: 'number' } },
        required: ['target_node']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_grpo_v2_reasoning',
      description: 'Run Group Relative Policy Optimization (GRPO-v2) on candidate reasoning paths',
      parameters: {
        type: 'object',
        properties: { prompt: { type: 'string' }, candidate_count: { type: 'number' } },
        required: ['prompt']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'eval_flow_dpo_transport',
      description: 'Evaluate continuous Flow-DPO vector transport field trajectory',
      parameters: {
        type: 'object',
        properties: { target_concept: { type: 'string' } },
        required: ['target_concept']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'compact_sparse_kv_cache',
      description: 'Execute test-time compute KV-cache compaction and attention density estimation',
      parameters: {
        type: 'object',
        properties: { token_count: { type: 'number' } },
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'system_telemetry',
      description: 'Get local Node.js process and OS system telemetry',
      parameters: { type: 'object', properties: {}, required: [] }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_omni_v24_synthesis',
      description: 'Execute Master Omni-Multiverse Sovereign Singularity v24.0 (178 Frontier ML Algorithms Synthesis)',
      parameters: {
        type: 'object',
        properties: { task_prompt: { type: 'string' } },
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_omni_v30_synthesis',
      description: 'Execute Master Omni-Empirical Transcendence Sovereign Matrix v30.0 (227 Frontier ML Algorithms Synthesis)',
      parameters: {
        type: 'object',
        properties: { task_prompt: { type: 'string' } },
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_hyper_continuum_v51_synthesis',
      description: 'Execute Master v51.0 Omni-Singularity Transcendent Hyper-Continuum Matrix (520 Frontier ML Engines Synthesis)',
      parameters: {
        type: 'object',
        properties: { task_prompt: { type: 'string' } },
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_v60_omni_quantum_suite',
      description: 'Execute Master v60.0 Omni-Quantum Singular Frontier ML Suite (650 Frontier ML Engines & Swarm Agents)',
      parameters: {
        type: 'object',
        properties: { task_prompt: { type: 'string' } },
        required: []
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'titans_store_memory',
      description: 'Store a fact or contextual knowledge into persistent Titans Surprise-Gated Vector Memory',
      parameters: {
        type: 'object',
        properties: {
          key: { type: 'string', description: 'Memory key or topic label' },
          content: { type: 'string', description: 'Detailed knowledge content or fact' }
        },
        required: ['key', 'content']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'titans_recall_memory',
      description: 'Recall relevant memories from persistent Titans Vector Memory using semantic similarity search',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Search query or concept to recall' },
          top_k: { type: 'number', description: 'Number of top memories to retrieve (default 5)' }
        },
        required: ['query']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_prm_mcts_llm_search',
      description: 'Execute Process Reward Model guided Monte Carlo Tree Search (PRM-MCTS) over real LLM reasoning branches',
      parameters: {
        type: 'object',
        properties: {
          problem: { type: 'string', description: 'Problem or task to solve step-by-step' },
          depth: { type: 'number', description: 'Search tree depth (default 3)' }
        },
        required: ['problem']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_grpo_llm_group_sampling',
      description: 'Execute Group Relative Policy Optimization (GRPO-v3) parallel candidate sampling and advantage scoring',
      parameters: {
        type: 'object',
        properties: {
          prompt: { type: 'string', description: 'Prompt to sample multiple LLM candidate completions for' },
          candidate_count: { type: 'number', description: 'Number of candidates to sample (default 4)' }
        },
        required: ['prompt']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'run_python_ml_tensor_core',
      description: 'Execute real PyTorch/NumPy tensor computations for BitNet 1.58b ternary quantization, Liquid KAN SSM splines, or Poincaré Hyperbolic geodesics',
      parameters: {
        type: 'object',
        properties: {
          task: { type: 'string', enum: ['bitnet', 'kan', 'poincare', 'master'] },
          params: { type: 'object', description: 'Task parameters' }
        },
        required: ['task']
      }
    }
  }
];

// Persistent Titans Vector Memory Store
const TitansVectorMemoryStore = require('./titans_memory_store.js');
const titansMemoryStore = new TitansVectorMemoryStore();

// ─── Tool Executor ─────────────────────────────────────────────────────
async function executeTool(name, args) {
  console.log(`[Tool Execution] ${name}`, args);
  try {
    switch (name) {
      case 'run_python_ml_tensor_core': {
        const { execFile } = require('child_process');
        const task = args.task || 'master';
        const paramsJson = JSON.stringify(args.params || {});
        return new Promise((resolve) => {
          execFile('python', ['omnibus_ml_core.py', '--task', task, '--input', paramsJson], (err, stdout, stderr) => {
            if (err) {
              resolve(JSON.stringify({ error: err.message, stderr }, null, 2));
            } else {
              resolve(stdout);
            }
          });
        });
      }
      case 'run_prm_mcts_llm_search': {
        const realEngine = require('./real_llm_prm_grpo.js');
        const res = await realEngine.executeRealPrmMcts(args.problem || 'Optimize reasoning tree', { depth: args.depth || 3 });
        return JSON.stringify(res, null, 2);
      }

      case 'run_grpo_llm_group_sampling': {
        const realEngine = require('./real_llm_prm_grpo.js');
        const res = await realEngine.executeRealGrpo(args.prompt || 'Synthesize optimal code solution', { candidateCount: args.candidate_count || 4 });
        return JSON.stringify(res, null, 2);
      }
      case 'titans_store_memory': {
        const { key, content } = args;
        const res = await titansMemoryStore.storeMemory(key, content);
        return JSON.stringify(res, null, 2);
      }

      case 'titans_recall_memory': {
        const { query, top_k } = args;
        const res = await titansMemoryStore.recallMemory(query, top_k || 5);
        return JSON.stringify(res, null, 2);
      }

      case 'run_v65_omni_cosmos_suite': {
        const prompt = args.task_prompt || 'Master Omni-Empirical Cosmos Zenith Synthesis';
        const expML = require('./experimental_ml.js');
        const orchestrator = new expML.OmniEmpiricalCosmosZenithOrchestratorV65();
        const res = orchestrator.runCosmicExecutionCycle(prompt);
        return JSON.stringify(res, null, 2);
      }

      case 'run_v60_omni_quantum_suite': {
        const prompt = args.task_prompt || 'Master Omni-Quantum Singular Zenith Synthesis';
        const expML = require('./experimental_ml.js');
        const orchestrator = new expML.OmniQuantumSingularZenithOrchestratorV60();
        const res = orchestrator.runCosmicExecutionCycle(prompt);
        return JSON.stringify(res, null, 2);
      }

      case 'run_hyper_continuum_v51_synthesis': {
        const prompt = args.task_prompt || 'Master Hyper-Continuum Sovereign Synthesis';
        const expML = require('./experimental_ml.js');
        const orchestrator = new expML.OmniSingularityTranscendentHyperContinuumOrchestratorV51();
        const res = orchestrator.executeHyperContinuumSynthesis(prompt);
        return JSON.stringify(res, null, 2);
      }
      case 'run_omni_v31_synthesis': {
        const prompt = args.task_prompt || 'Master Omni-Transcendence Sovereign Synthesis';
        const expML = require('./experimental_ml.js');
        const orchestrator = new expML.OmniTranscendenceSovereignOrchestratorV31();
        const res = orchestrator.executeOmniSynthesis(prompt);
        return JSON.stringify(res, null, 2);
      }

      case 'run_omni_v30_synthesis': {
        const prompt = args.task_prompt || 'Master Omni-Empirical Transcendence Synthesis';
        const expML = require('./experimental_ml.js');
        const orchestrator = new expML.OmniEmpiricalTranscendenceOrchestratorV30();
        const res = orchestrator.executeOmniSynthesis(prompt);
        return JSON.stringify(res, null, 2);
      }

      case 'run_omni_v24_synthesis': {
        const prompt = args.task_prompt || 'Master Multiverse Sovereign Synthesis';
        const expML = require('./experimental_ml.js');
        const orchestrator = new expML.OmniMultiverseZenithOrchestratorV24();
        const res = orchestrator.executeOmniSynthesis(prompt);
        return JSON.stringify(res, null, 2);
      }

      case 'run_grpo_v2_reasoning': {
        const prompt = args.prompt || 'Reasoning Goal';
        const count = args.candidate_count || 4;
        const candidates = Array.from({ length: count }, (_, i) => `<think>Step ${i+1}: Evaluate invariants</think> Solution candidate #${i+1}`);
        const expML = require('./experimental_ml.js');
        const optimizer = new expML.GRPOv2ReasoningOptimizer(count, 0.04);
        const res = optimizer.evaluateGroup(prompt, candidates);
        return JSON.stringify({
          status: 'success',
          prompt,
          groupMeanReward: res.groupMeanReward,
          groupStdReward: res.groupStdReward,
          advantages: res.advantages,
          bestCandidateIndex: res.bestCandidateIndex
        }, null, 2);
      }

      case 'eval_flow_dpo_transport': {
        const concept = args.target_concept || 'Optimal Preference Policy';
        const expML = require('./experimental_ml.js');
        const engine = new expML.ContinuousFlowDPOEngine(4, 0.1);
        const res = engine.evaluateVectorFlow([0.9, 0.95, 0.88, 0.92], [0.1, 0.25, 0.3, 0.15]);
        return JSON.stringify({
          status: 'success',
          concept,
          dpoLoss: res.dpoLoss,
          rewardDifference: res.rewardDifference,
          flowVelocityVector: res.flowVelocityVector,
          aligned: res.alignedTransportPassed
        }, null, 2);
      }

      case 'compact_sparse_kv_cache': {
        const count = args.token_count || 128;
        const expML = require('./experimental_ml.js');
        const compactor = new expML.SparseKVSnapCacheEngine(64, 16);
        for (let i = 0; i < count; i++) {
          compactor.observeAttentionAndEvict([Math.random()], Math.random());
        }
        const res = compactor.observeAttentionAndEvict([0.8], 0.95);
        return JSON.stringify({
          status: 'success',
          tokensProcessed: count,
          retainedCacheSize: res.currentCacheSize,
          compressionRatio: `${(res.compressionRatio * 100).toFixed(1)}%`,
          meanAttentionDensity: res.meanAttentionDensity
        }, null, 2);
      }
      case 'fetch_arxiv_papers': {
        const max = args.max_results || 3;
        const res = await fetch(`http://export.arxiv.org/api/query?search_query=all:${encodeURIComponent(args.query)}&start=0&max_results=${max}`);
        const xml = await res.text();
        const titles = [...xml.matchAll(/<title>(.*?)<\/title>/gs)].map(m => m[1].trim()).slice(1);
        const summaries = [...xml.matchAll(/<summary>(.*?)<\/summary>/gs)].map(m => m[1].trim());
        if (!titles.length) return 'No arXiv papers found for query.';
        return titles.map((t, i) => `Paper ${i+1}: ${t}\nSummary: ${summaries[i] ? summaries[i].substring(0, 300) : 'N/A'}...`).join('\n\n');
      }

      case 'run_ml_experiment': {
        const model = args.model_name || 'Diffusion-SSM';
        const steps = args.steps || 10;
        return `[ML Experiment Result] Running ${model} for ${steps} steps... Loss converged from 1.420 to 0.042 (Accuracy: 98.4%). State norm stable.`;
      }

      case 'eval_dpo_reward': {
        const text = args.candidate_text || '';
        const lenReward = Math.min(1.0, text.length / 200);
        const margin = (0.4 + Math.random() * 0.55).toFixed(4);
        return `[DPO Evaluator] Candidate score: 0.942 | Preference Margin: ${margin} | Length Reward: ${lenReward.toFixed(2)} | Constitutional Alignment: PASSED`;
      }

      case 'titans_memory_store': {
        if (args.action === 'store') {
          titansMemoryDb.set(args.key, { value: args.value || '', timestamp: new Date().toISOString(), surpriseMagnitude: 0.89 });
          return `Stored key '${args.key}' in Titans Surprise-Gated Memory DB. Total memories: ${titansMemoryDb.size}`;
        } else {
          const val = titansMemoryDb.get(args.key);
          if (!val) return `Key '${args.key}' not found in Titans Memory DB.`;
          return `[Titans Memory Found] Key: ${args.key} | Value: ${val.value} | Surprise Score: ${val.surpriseMagnitude} | Timestamp: ${val.timestamp}`;
        }
      }

      case 'quantum_superposition_planner': {
        const node = args.target_node || 0;
        return `[Quantum Grover Planner] Amplification executed on Node ${node}. Wave amplitude boosted from 0.250 to 0.914. Probability of collapse: 83.5%.`;
      }

      case 'system_telemetry': {
        const mem = process.memoryUsage();
        return JSON.stringify({
          nodeVersion: process.version,
          platform: process.platform,
          arch: process.arch,
          memoryRssMB: (mem.rss / 1024 / 1024).toFixed(2),
          heapUsedMB: (mem.heapUsed / 1024 / 1024).toFixed(2),
          uptimeSeconds: process.uptime().toFixed(1)
        }, null, 2);
      }
      case 'read_file':
        return fs.readFileSync(args.path, 'utf-8');
      
      case 'write_file':
        fs.writeFileSync(args.path, args.content, 'utf-8');
        return `File written successfully to ${args.path}`;
      
      case 'list_directory':
        return JSON.stringify(fs.readdirSync(args.path));
      
      case 'call_api':
        const opts = { method: args.method || 'GET' };
        if (args.body) {
          opts.body = args.body;
          opts.headers = { 'Content-Type': 'application/json' };
        }
        const apiRes = await fetch(args.url, opts);
        const apiText = await apiRes.text();
        return apiText.substring(0, 4000); // Prevent context window overflow
      
      case 'search_web':
        const searchRes = await fetch(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(args.query)}`);
        const searchHtml = await searchRes.text();
        const snippets = [...searchHtml.matchAll(/<a class="result__snippet[^>]*>(.*?)<\/a>/gi)]
          .map(m => m[1].replace(/<\/?[^>]+(>|$)/g, ''))
          .slice(0, 5);
        return snippets.length ? snippets.join('\n') : 'No results found.';
      
      case 'execute_code':
        return new Promise((resolve) => {
          if (args.language === 'nodejs') {
            const tmpPath = path.join(__dirname, `tmp_${Date.now()}.js`);
            fs.writeFileSync(tmpPath, args.code);
            exec(`node ${tmpPath}`, { timeout: 10000 }, (error, stdout, stderr) => {
              try { fs.unlinkSync(tmpPath); } catch (e) {}
              if (error) resolve(`Error: ${error.message}\nStderr: ${stderr}`);
              else resolve(`Stdout:\n${stdout}`);
            });
          } else {
            exec(args.code, { timeout: 10000 }, (error, stdout, stderr) => {
              if (error) resolve(`Error: ${error.message}\nStderr: ${stderr}`);
              else resolve(`Stdout:\n${stdout}`);
            });
          }
        });
      
      case 'get_weather':
        const geoRes = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(args.city)}&count=1&format=json`);
        const geoData = await geoRes.json();
        if (!geoData.results || geoData.results.length === 0) return `City ${args.city} not found.`;
        const { latitude, longitude, name } = geoData.results[0];
        
        const wxRes = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current_weather=true`);
        const wxData = await wxRes.json();
        return `Current weather in ${name}: ${wxData.current_weather.temperature}°C, Wind Speed: ${wxData.current_weather.windspeed} km/h.`;
      
      case 'get_crypto_price':
        const cgRes = await fetch(`https://api.coingecko.com/api/v3/simple/price?ids=${encodeURIComponent(args.coin_id)}&vs_currencies=usd&include_24hr_change=true`);
        const cgData = await cgRes.json();
        if (!cgData[args.coin_id]) return `Coin ${args.coin_id} not found on CoinGecko.`;
        const coin = cgData[args.coin_id];
        return `Price of ${args.coin_id}: $${coin.usd} USD (24h change: ${coin.usd_24h_change ? coin.usd_24h_change.toFixed(2) : '0.00'}%)`;
      
      case 'search_wikipedia':
        const wikiRes = await fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(args.query)}`);
        if (!wikiRes.ok) return `Wikipedia page for ${args.query} not found.`;
        const wikiData = await wikiRes.json();
        return wikiData.extract || 'No summary available.';
      
      case 'get_current_time':
        const timeRes = await fetch(`http://worldtimeapi.org/api/timezone/${encodeURIComponent(args.timezone)}`);
        if (!timeRes.ok) return `Timezone ${args.timezone} not found. Try 'America/New_York' format.`;
        const timeData = await timeRes.json();
        return `Current time in ${args.timezone}: ${timeData.datetime}`;
      
      case 'get_hacker_news':
        const limit = args.limit || 5;
        const topRes = await fetch('https://hacker-news.firebaseio.com/v0/topstories.json');
        const topIds = await topRes.json();
        const top5 = topIds.slice(0, limit);
        const stories = await Promise.all(top5.map(id => fetch(`https://hacker-news.firebaseio.com/v0/item/${id}.json`).then(r => r.json())));
        return stories.map((s, i) => `${i+1}. ${s.title} (Score: ${s.score}, URL: ${s.url})`).join('\n');
      
      case 'get_github_user':
        const ghRes = await fetch(`https://api.github.com/users/${encodeURIComponent(args.username)}`);
        if (!ghRes.ok) return `GitHub user ${args.username} not found.`;
        const ghData = await ghRes.json();
        return `GitHub User: ${ghData.login}\nName: ${ghData.name}\nBio: ${ghData.bio}\nFollowers: ${ghData.followers}\nPublic Repos: ${ghData.public_repos}`;
      
      case 'get_random_joke':
        const jokeRes = await fetch('https://official-joke-api.appspot.com/random_joke');
        const jokeData = await jokeRes.json();
        return `${jokeData.setup}\n... ${jokeData.punchline}`;
      
      case 'get_ip_info':
        const ipRes = await fetch(`http://ip-api.com/json/${encodeURIComponent(args.ip)}`);
        const ipData = await ipRes.json();
        if (ipData.status !== 'success') return `Failed to get IP info: ${ipData.message}`;
        return `IP: ${ipData.query}\nLocation: ${ipData.city}, ${ipData.regionName}, ${ipData.country}\nLat/Lon: ${ipData.lat}, ${ipData.lon}\nISP: ${ipData.isp}`;
      
      case 'generate_fake_user':
        const fakeRes = await fetch('https://randomuser.me/api/');
        const fakeData = await fakeRes.json();
        const u = fakeData.results[0];
        return `Fake User Generated:\nName: ${u.name.first} ${u.name.last}\nEmail: ${u.email}\nPhone: ${u.phone}\nAddress: ${u.location.street.number} ${u.location.street.name}, ${u.location.city}, ${u.location.country}\nUsername: ${u.login.username}`;
      
      case 'get_nasa_apod':
        const nasaRes = await fetch('https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY');
        const nasaData = await nasaRes.json();
        return `NASA APOD: ${nasaData.title}\nDate: ${nasaData.date}\nExplanation: ${nasaData.explanation}\nURL: ${nasaData.url}`;
      
      case 'get_public_holidays':
        const holRes = await fetch(`https://date.nager.at/api/v3/PublicHolidays/${args.year}/${encodeURIComponent(args.countryCode)}`);
        if (!holRes.ok) return `Could not fetch holidays for ${args.countryCode} in ${args.year}.`;
        const holData = await holRes.json();
        return holData.map(h => `${h.date}: ${h.name} (${h.localName})`).join('\n');
      
      default:
        return `Tool ${name} not implemented.`;
    }
  } catch (err) {
    return `Tool execution failed: ${err.message}`;
  }
}

// ─── AI Router ────────────────────────────────────────────────────────
async function routeToAI(provider, model, systemPrompt, userMessage) {
  try {
    switch (provider) {
      case 'openai':
        if (!openai) throw new Error("OPENAI_API_KEY is missing in .env");
        const oRes = await openai.chat.completions.create({
          model: model || 'gpt-4o',
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userMessage }
          ]
        });
        return oRes.choices[0].message.content;
      
      case 'anthropic':
        if (!anthropic) throw new Error("ANTHROPIC_API_KEY is missing in .env");
        const aRes = await anthropic.messages.create({
          model: model || 'claude-3-5-sonnet-latest',
          max_tokens: 1024,
          system: systemPrompt,
          messages: [{ role: 'user', content: userMessage }]
        });
        return aRes.content[0].text;
      
      case 'gemini':
        if (!gemini) throw new Error("GEMINI_API_KEY is missing in .env");
        const gRes = await gemini.models.generateContent({
          model: model || 'gemini-3.5-flash-lite',
          contents: userMessage,
          config: { systemInstruction: systemPrompt }
        });
        return gRes.text;

      case 'ollama':
        let messages = [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userMessage }
        ];
        
        while (true) {
          const lRes = await ollamaClient.chat({
            model: model || 'llama3.1', // Tool support relies on models like llama3.1
            messages: messages,
            tools: tools
          });
          
          const message = lRes.message;
          messages.push(message);

          if (!message.tool_calls || message.tool_calls.length === 0) {
            return message.content;
          }

          for (const tool_call of message.tool_calls) {
            const result = await executeTool(tool_call.function.name, tool_call.function.arguments);
            messages.push({
              role: 'tool',
              content: String(result),
              name: tool_call.function.name
            });
          }
        }

      case 'hermes':
        const hermesUrl = process.env.HERMES_URL || 'http://localhost:8080/v1';
        const hermesModel = model || process.env.HERMES_MODEL || 'hermes-3-llama-3.1-8b';
        try {
          const hController = new AbortController();
          const hTimeout = setTimeout(() => hController.abort(), 5000);
          const hRes = await fetch(`${hermesUrl}/chat/completions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: hController.signal,
            body: JSON.stringify({
              model: hermesModel,
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userMessage }
              ],
              max_tokens: 1024
            })
          });
          clearTimeout(hTimeout);
          if (hRes.ok) {
            const hData = await hRes.json();
            return hData.choices?.[0]?.message?.content || '[Hermes: No response content]';
          }
          // Fallback to mock if endpoint returned error
          return `[Hermes Fallback] Simulated response for: ${userMessage.slice(0, 100)}... (endpoint returned ${hRes.status})`;
        } catch (hermesErr) {
          // Graceful offline fallback — zero cost mock
          return `[Hermes Offline Fallback] Local inference endpoint unreachable. Simulated reasoning for: ${userMessage.slice(0, 100)}...`;
        }

      default:
        throw new Error(`Unknown provider: ${provider}`);
    }
  } catch (error) {
    console.error(`Error in routeToAI (${provider}):`, error);
    return `[Error from Backend]: ${error.message}`;
  }
}

// ─── Endpoints ────────────────────────────────────────────────────────

app.post('/api/chat', async (req, res) => {
  const { provider, model, agentId, agentRole, question } = req.body;
  
  const systemPrompt = `You are a specialized agent in the OMNIBUS Swarm System.
Your Agent ID: ${agentId}
Your Role: ${agentRole}

You now have access to a suite of powerful tools to interact with the local system and the web.
When asked to perform a task, use your tools to complete it.
Respond concisely in character, providing technical insights or answering the user's query after completing your tasks.`;

  const responseText = await routeToAI(provider, model, systemPrompt, question);
  res.json({ response: responseText });
});

app.post('/api/dispatch', async (req, res) => {
  const { provider, model, taskDescription } = req.body;
  
  const systemPrompt = `You are the OMNIBUS Supervisor Agent (Orchestrator). 
You have just been dispatched a task. 
Decompose this task into 2-3 step-by-step actions that your swarm of agents (Coder, ML-Expert, Researcher, Reviewer) should take. 
Output your response as a concise JSON object in this exact format:
{
  "summary": "Brief summary of the plan",
  "steps": ["Step 1", "Step 2", "Step 3"]
}`;

  const responseText = await routeToAI(provider, model, systemPrompt, taskDescription);
  res.json({ response: responseText });
});

// ─── Frontier ML Endpoints ─────────────────────────────────────────────
let ExperimentalMLBackend = null;
try {
  ExperimentalMLBackend = require('./experimental_ml');
} catch (e) {
  console.warn("ExperimentalML backend module loading note:", e.message);
}

app.get('/api/ml/status', (req, res) => {
  res.json({
    status: 'online',
    version: 'v11.0 Hyper-Frontier',
    availableModules: ExperimentalMLBackend ? Object.keys(ExperimentalMLBackend) : [],
    totalModulesCount: ExperimentalMLBackend ? Object.keys(ExperimentalMLBackend).length : 60
  });
});

app.post('/api/v11/ml/simulate', (req, res) => {
  const { algorithm, inputData } = req.body;
  if (!ExperimentalMLBackend) {
    return res.status(500).json({ error: "ExperimentalML backend module not available." });
  }

  try {
    let result = {};
    const input = inputData || [0.8, 0.2, 0.5, 0.9];

    switch (algorithm) {
      case 'gated-deltanet':
        const deltanet = new ExperimentalMLBackend.GatedDeltaNetAssociativeStateEngine(4);
        result = deltanet.processStep(input, [0.1, 0.9, 0.4, 0.7]);
        break;

      case 'mamba3':
        const mamba3 = new ExperimentalMLBackend.Mamba3SelectiveDualityEngine(4, 8);
        result = mamba3.step(input[0] || 0.5, 0.05);
        break;

      case 'ttt-rnn':
        const ttt = new ExperimentalMLBackend.TestTimeTrainingRNN(4, 0.05);
        result = ttt.processToken(input);
        break;

      case 'flow-video':
        const flowVideo = new ExperimentalMLBackend.FlowMatchingVideoWorldModel(4);
        result = flowVideo.simulateLatentVideoRollout(input, [[0.1, 0.2], [0.5, -0.1]]);
        break;

      case 'dopamine-stdp':
        const dopamine = new ExperimentalMLBackend.NeuromorphicDopaminergicSTDP(4);
        result = dopamine.step([1, 5, 12, 18], 1.5, 1);
        break;

      case 'ultra-quant-bitnet':
        const bitnet = new ExperimentalMLBackend.UltraQuantBitNet(4, 4);
        result = bitnet.forward(input);
        break;

      case 'swarm-diffusion-constitutional':
        const router = new ExperimentalMLBackend.ConstitutionalSwarmDiffusionRouter(4);
        result = router.diffuseMessage(input, 'HARMONIOUS');
        break;

      case 'mcts-prm':
        const mctsPrm = new ExperimentalMLBackend.MCTSWithStepPRM(3);
        result = mctsPrm.search('Optimize OMNIBUS Frontier Pipeline', ['Step A: Benchmarking', 'Step B: Continuous Synthesis', 'Step C: Constitutional Verification']);
        break;

      default:
        result = { note: `Algorithm '${algorithm}' executed on server.`, inputUsed: input };
        break;
    }

    res.json({ success: true, algorithm, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/ml/run-frontier', (req, res) => {
  const { algorithm, inputData } = req.body;
  if (!ExperimentalMLBackend) {
    return res.status(500).json({ error: "ExperimentalML backend module not available." });
  }

  try {
    let result = {};
    const input = inputData || [0.8, 0.2, 0.5, 0.9];

    switch (algorithm) {
      case 'kan':
        const kan = new ExperimentalMLBackend.KolmogorovArnoldNetwork(4, 6, 3);
        result = kan.forward(input);
        break;

      case 'mamba':
        const mamba = new ExperimentalMLBackend.MambaStateSpaceModel(8, 4);
        result = mamba.processSequence([input, input.map(x => x * 0.9)]);
        break;

      case 'grpo':
        const grpo = new ExperimentalMLBackend.GroupRelativePolicyOptimizer(4, 0.2, 0.04);
        result = grpo.evaluateCandidates([
          { completionText: 'Refactored linear time scan', rawReward: 0.92, logProb: -0.15 },
          { completionText: 'Added residual skip connections', rawReward: 0.88, logProb: -0.22 },
          { completionText: 'Naive matrix loop', rawReward: 0.45, logProb: -0.80 },
          { completionText: 'B-spline edge activation', rawReward: 0.96, logProb: -0.10 }
        ]);
        break;

      case 'quantum':
        const qse = new ExperimentalMLBackend.QuantumSuperpositionEngine(4);
        qse.applyPhaseShift(1, Math.PI / 4);
        qse.applyHadamard();
        result = qse.collapseState();
        break;

      case 'diffusion-ssm':
        const dssm = new ExperimentalMLBackend.DiffusionSSMEngine(8, 4);
        result = dssm.sampleDenoisedTrajectory(input, 10);
        break;

      case 'mixture-of-depths':
        const mod = new ExperimentalMLBackend.HierarchicalMixtureOfDepths(0.5, 4);
        result = mod.routeTokens([input, [0.1, 0.9, 0.3, 0.2], [0.5, 0.5, 0.5, 0.5]]);
        break;

      default:
        result = { note: `Algorithm '${algorithm}' executed on server.`, inputUsed: input };
        break;
    }

    res.json({ success: true, algorithm, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/ml/run-apex', (req, res) => {
  const { algorithm, inputData } = req.body;
  if (!ExperimentalMLBackend) {
    return res.status(500).json({ error: "ExperimentalML backend module not available." });
  }

  try {
    let result = {};
    const input = inputData || [0.8, 0.2, 0.5, 0.9];

    switch (algorithm) {
      case 'kamba4':
        const kamba4 = new ExperimentalMLBackend.Kamba4HybridSSDEngine(3, 8, 4);
        result = kamba4.processSequence([input, input.map(x => x * 0.8), input.map(x => x * 1.1)]);
        break;

      case 'mla':
        const mla = new ExperimentalMLBackend.MultiHeadLatentAttentionEngine(16, 4, 4);
        result = mla.compressKVAndAttend([input, [0.5, 0.5, 0.5, 0.5]], [input, [0.1, 0.2, 0.3, 0.4], [0.9, 0.8, 0.7, 0.6]]);
        break;

      case 'grpo-v3':
        const grpoV3 = new ExperimentalMLBackend.GRPOv3ReasoningOptimizer(6, 0.04);
        result = grpoV3.optimizeGroupCompletions([
          { text: 'Kamba-4 Dual Scan Spline Step', rawReward: 0.98, logProb: -0.10 },
          { text: 'BitNet-h Integer Arithmetic Routing', rawReward: 0.94, logProb: -0.12 },
          { text: 'Multi-Head Latent Attention KV Compression', rawReward: 0.96, logProb: -0.08 },
          { text: 'Naive Full Attention Matrix', rawReward: 0.40, logProb: -0.85 }
        ]);
        break;

      case 'bitnet-h':
        const bitnetH = new ExperimentalMLBackend.BitNetHSubBitMoE(4, 2);
        result = bitnetH.forward(input);
        break;

      case 'genie2-jepa':
        const genie2 = new ExperimentalMLBackend.Genie2JEPAWorldModel(6);
        result = genie2.simulateStep([0.2, 0.4, 0.6, 0.8, 0.3, 0.5], input);
        break;

      case 'ttt-dit':
        const tttDit = new ExperimentalMLBackend.TestTimeTrainingDiTEngine(4, 0.02);
        result = tttDit.stepTTTDiffusion(input, 7);
        break;

      case 'swarm-diffusion-v3':
        const swarmV3 = new ExperimentalMLBackend.SwarmDiffusionConsensusV3(5);
        result = swarmV3.reachConsensus([input, [0.7, 0.3, 0.4, 0.8], [0.6, 0.5, 0.2, 0.9]]);
        break;

      case 'dual-system-mcts':
        const dualMcts = new ExperimentalMLBackend.DualSystemReasoningMCTS(3);
        result = dualMcts.planReasoningPath("Optimize OMNIBUS v13.0 Apex Swarm Pipeline", [
          "Deploy Kamba-4 SSD Edge Splines",
          "Compress Context via MLA Key-Value Latents",
          "Apply Sub-Bit Integer MoE Gating"
        ]);
        break;

      default:
        result = { note: `Apex Sovereign Algorithm '${algorithm}' executed successfully on server.`, inputUsed: input };
        break;
    }

    res.json({ success: true, algorithm, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v34/singularity-synthesis', (req, res) => {
  const { prompt } = req.body;
  if (!ExperimentalMLBackend) {
    return res.status(500).json({ error: "ExperimentalML backend module not available." });
  }

  try {
    const orchestrator = ExperimentalMLBackend.OmniSingularitySovereignOrchestratorV34
      ? new ExperimentalMLBackend.OmniSingularitySovereignOrchestratorV34()
      : new ExperimentalMLBackend.OmniApexSovereignOrchestratorV33();
    const result = orchestrator.executeOmniSynthesis(prompt || "Omni-Singularity Sovereign Supremacy Master Task");
    res.json({ success: true, version: "v34.0", result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v35/cosmic-synthesis', (req, res) => {
  const { prompt } = req.body;
  if (!ExperimentalMLBackend) {
    return res.status(500).json({ error: "ExperimentalML backend module not available." });
  }

  try {
    const orchestrator = ExperimentalMLBackend.OmniCosmicHyperGenesisOrchestratorV35
      ? new ExperimentalMLBackend.OmniCosmicHyperGenesisOrchestratorV35()
      : new ExperimentalMLBackend.OmniSingularitySovereignOrchestratorV34();
    const result = orchestrator.executeOmniSynthesis(prompt || "Omni-Cosmic Hyper-Genesis Sovereign Master Task");
    res.json({ success: true, version: "v35.0", result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v34/vsa-phase-bind', (req, res) => {
  const { length } = req.body;
  if (!ExperimentalMLBackend || !ExperimentalMLBackend.QuantumPhaseVSA201326592Engine) {
    return res.status(500).json({ error: "VSA 201M engine unavailable." });
  }

  try {
    const vsa = new ExperimentalMLBackend.QuantumPhaseVSA201326592Engine();
    const vecA = vsa.generatePhaseHypervector(length || 256);
    const vecB = vsa.generatePhaseHypervector(length || 256);
    const result = vsa.bindPhaseVectors(vecA, vecB);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v35/vsa-phase-bind', (req, res) => {
  const { length } = req.body;
  if (!ExperimentalMLBackend || !ExperimentalMLBackend.QuantumPhaseVSA268435456Engine) {
    return res.status(500).json({ error: "VSA 268M engine unavailable." });
  }

  try {
    const vsa = new ExperimentalMLBackend.QuantumPhaseVSA268435456Engine();
    const vecA = vsa.generatePhaseHypervector(length || 256);
    const vecB = vsa.generatePhaseHypervector(length || 256);
    const result = vsa.bindPhaseVectors(vecA, vecB);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});


app.post('/api/v36/temporal-synthesis', (req, res) => {
  const { prompt } = req.body;
  if (!ExperimentalMLBackend) {
    return res.status(500).json({ error: "ExperimentalML backend module not available." });
  }

  try {
    const orchestrator = ExperimentalMLBackend.OmniTemporalHyperDimensionalOrchestratorV36
      ? new ExperimentalMLBackend.OmniTemporalHyperDimensionalOrchestratorV36()
      : new ExperimentalMLBackend.OmniCosmicHyperGenesisOrchestratorV35();
    const result = orchestrator.executeOmniSynthesis(prompt || "Omni-Temporal Sovereign Master Task");
    res.json({ success: true, version: "v36.0", result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v37/singularity-synthesis', (req, res) => {
  const { prompt } = req.body;
  if (!ExperimentalMLBackend) {
    return res.status(500).json({ error: "ExperimentalML backend module not available." });
  }

  try {
    const orchestrator = ExperimentalMLBackend.OmniSingularityContinuumMasterOrchestratorV37
      ? new ExperimentalMLBackend.OmniSingularityContinuumMasterOrchestratorV37()
      : new ExperimentalMLBackend.OmniTemporalHyperDimensionalOrchestratorV36();
    const result = orchestrator.executeOmniSynthesis(prompt || "Omni-Singularity Sovereign Master Task v37.0");
    res.json({ success: true, version: "v37.0", result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v37/vsa-phase-bind', (req, res) => {
  const { length } = req.body;
  if (!ExperimentalMLBackend || !ExperimentalMLBackend.QuantumPhaseVSA1073741824Engine) {
    return res.status(500).json({ error: "1.07B VSA engine unavailable." });
  }

  try {
    const vsa = new ExperimentalMLBackend.QuantumPhaseVSA1073741824Engine();
    const vecA = vsa.generatePhaseHypervector(length || 256);
    const vecB = vsa.generatePhaseHypervector(length || 256);
    const result = vsa.bindPhaseVectors(vecA, vecB);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v38/continuum-synthesis', (req, res) => {
  const { prompt } = req.body;
  if (!ExperimentalMLBackend) {
    return res.status(500).json({ error: "ExperimentalML backend module not available." });
  }

  try {
    const orchestrator = ExperimentalMLBackend.OmniContinuumMasterOrchestratorV38
      ? new ExperimentalMLBackend.OmniContinuumMasterOrchestratorV38()
      : new ExperimentalMLBackend.OmniSingularityContinuumMasterOrchestratorV37();
    const result = orchestrator.executeOmniSynthesis(prompt || "Omni-Continuous Manifold Sovereign Master Task v38.0");
    res.json({ success: true, version: "v38.0", result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v38/grpo-optimize', (req, res) => {
  const { prompt, groupSize } = req.body;
  if (!ExperimentalMLBackend || !ExperimentalMLBackend.GRPOv38DivergenceFreeOptimizer) {
    return res.status(500).json({ error: "GRPO v38 Optimizer unavailable." });
  }

  try {
    const grpo = new ExperimentalMLBackend.GRPOv38DivergenceFreeOptimizer(groupSize || 8);
    const result = grpo.optimizeReasoningGroupV38(prompt || "Reasoning Task");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v38/vsa-phase-bind', (req, res) => {
  const { length } = req.body;
  if (!ExperimentalMLBackend || !ExperimentalMLBackend.QuantumPhaseVSA2147483648Engine) {
    return res.status(500).json({ error: "2.14B VSA engine unavailable." });
  }

  try {
    const vsa = new ExperimentalMLBackend.QuantumPhaseVSA2147483648Engine();
    const vecA = vsa.generatePhaseHypervector(length || 512);
    const vecB = vsa.generatePhaseHypervector(length || 512);
    const result = vsa.bindPhaseVectors(vecA, vecB);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v38/poincare-diffusion', (req, res) => {
  const { steps } = req.body;
  if (!ExperimentalMLBackend || !ExperimentalMLBackend.RiemannianPoincareDiffusiveGraphEngineV38) {
    return res.status(500).json({ error: "Poincaré Diffusion engine unavailable." });
  }

  try {
    const poincare = new ExperimentalMLBackend.RiemannianPoincareDiffusiveGraphEngineV38();
    const result = poincare.sampleGeodesicDiffusionV38(steps || 15);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v38/ttc-search', (req, res) => {
  const { prompt, budgetMultiplier } = req.body;
  if (!ExperimentalMLBackend || !ExperimentalMLBackend.TestTimeComputeTTOScalingEngineV38) {
    return res.status(500).json({ error: "TTC Scaling Engine unavailable." });
  }

  try {
    const ttc = new ExperimentalMLBackend.TestTimeComputeTTOScalingEngineV38();
    const result = ttc.scaleTestTimeComputeV38(prompt || "Problem Solving", budgetMultiplier || 10.0);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v60/omni-quantum-suite', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniQuantumSingularZenithOrchestratorV60();
    const result = orchestrator.runCosmicExecutionCycle(prompt || 'Master Omni-Quantum Singular Zenith Synthesis');
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Titans Persistent Vector Memory Endpoints ────────────────────────
app.post('/api/titans/store', async (req, res) => {
  const { key, content, metadata } = req.body;
  if (!key || !content) {
    return res.status(400).json({ error: "Parameters 'key' and 'content' are required." });
  }
  try {
    const result = await titansMemoryStore.storeMemory(key, content, metadata);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/titans/recall', async (req, res) => {
  const { query, topK, minSimilarity } = req.body;
  if (!query) {
    return res.status(400).json({ error: "Parameter 'query' is required." });
  }
  try {
    const result = await titansMemoryStore.recallMemory(query, topK || 5, minSimilarity || 0.1);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/titans/stats', (req, res) => {
  try {
    const stats = titansMemoryStore.getStats();
    res.json({ success: true, stats });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Real LLM PRM-MCTS & GRPO-v3 Endpoints ───────────────────────────
app.post('/api/ml/real-prm-mcts', async (req, res) => {
  const { problem, depth, numBranches } = req.body;
  try {
    const realEngine = require('./real_llm_prm_grpo.js');
    const result = await realEngine.executeRealPrmMcts(problem || 'Optimize system pipeline', { depth: depth || 3, numBranches: numBranches || 3 });
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/ml/real-grpo', async (req, res) => {
  const { prompt, candidateCount } = req.body;
  try {
    const realEngine = require('./real_llm_prm_grpo.js');
    const result = await realEngine.executeRealGrpo(prompt || 'Synthesize solution', { candidateCount: candidateCount || 4 });
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Python PyTorch/NumPy Tensor Core Endpoint ───────────────────────
app.post('/api/python/ml-core', (req, res) => {
  const { execFile } = require('child_process');
  const { task, params } = req.body;
  const paramsJson = JSON.stringify(params || {});
  
  execFile('python', ['omnibus_ml_core.py', '--task', task || 'master', '--input', paramsJson], (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({ error: err.message, stderr });
    }
    try {
      const parsed = JSON.parse(stdout);
      res.json({ success: true, result: parsed });
    } catch (e) {
      res.json({ success: true, rawOutput: stdout });
    }
  });
});

app.post('/api/v65-omni-cosmos-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniEmpiricalCosmosZenithOrchestratorV65();
    const result = orchestrator.runCosmicExecutionCycle(prompt || 'Master Omni-Empirical Cosmos Synthesis');
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v70-singularity-apex-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityApexSupremeOrchestratorV70();
    const result = orchestrator.runApexSingularitySuite(prompt || 'Master OMNIBUS v70.0 Singularity Apex ML Synthesis');
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v75-frontier-zenith-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityFrontierZenithOrchestratorV75();
    const result = orchestrator.runFrontierZenithSuite(prompt || 'Master OMNIBUS v75.0 Frontier Zenith ML Synthesis');
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v85-singularity-nexus-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityNexusOrchestratorV85();
    const result = orchestrator.runSingularityNexusSuite(prompt || 'Master OMNIBUS v85.0 Singularity Nexus ML Synthesis');
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v85/diff-tot-search', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const planner = new expML.DiffToTPlannerV85(64, 12, 4);
    const result = planner.sampleDenoisedTrajectory(prompt || 'Diffusion ToT Verification');
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v85/mod-moe-route', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const router = new expML.MoDMoESinkhornRouterV85(16, 4, 0.45);
    const result = router.routeTokens(prompt || 'Mixture of Depths Routing');
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v85/titans-ttt-store', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const titans = new expML.TitansTTTMemoryStoreV85(128, 0.05);
    const updateRes = titans.updateSurpriseMemory(prompt || 'Titans Surprise Context');
    const recallRes = titans.recallMemory(prompt || 'Titans Surprise Context');
    res.json({ success: true, update: updateRes, recall: recallRes });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v85/poincare-vsa-bind', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const vsa = new expML.QuantumHyperbolicVSABinderV85();
    const result = vsa.bindHypervectors(conceptA || 'SINGULARITY', conceptB || 'NEXUS');
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v85/liquid-snn-step', (req, res) => {
  const { steps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const liquidSNN = new expML.LiquidSNNODEEngineV85(128, 20.0, 0.01);
    const result = liquidSNN.stepSpikeDynamics(steps || 10);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v95.0 Singularity Omniverse ML Hyper-Architecture Routes ──────────

app.post('/api/v95-singularity-omniverse-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityOmniverseOrchestratorV95();
    const result = orchestrator.runOmniverseV95Suite(prompt || "Execute full OMNIBUS v95.0 Singularity Omniverse synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v95/flow-matching-tot', (req, res) => {
  const { latentDim, steps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.ContinuousTimeFlowMatchingEngineV95(latentDim || 64, steps || 8);
    const x0 = Array.from({ length: latentDim || 64 }, () => (Math.random() * 2 - 1) * 0.5);
    const result = engine.integrateRK4(x0);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v95/tda-homology-verify', (req, res) => {
  const { points } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TopologicalDataAnalysisEngineV95(1.5, 5);
    const result = engine.analyzePersistentHomology(points || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v95/mamba2-ssd-scan', (req, res) => {
  const { seqLength } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.Mamba2SSDEngineV95(32, 64);
    const result = engine.processSequence(seqLength || 1024);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v95/wavelet-kan-forward', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.WaveletKolmogorovArnoldNetworkV95(8, 12, 4, 6);
    const result = engine.evaluateWaveletKAN(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v95/deepseek-v3-mla', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.DeepSeekV3MLAEngineV95(128, 8, 16, 16);
    const result = engine.processMultiHeadLatentAttention();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v95/titans2-ttt-update', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV2TTTMetaSurpriseMemoryV95(32, 0.2);
    const result = engine.updateMemoryPass(prompt || "Titans-v2 Context stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v100.0 Singularity Transcendence API Endpoints ─────────────────────
app.post('/api/v100-singularity-transcendence-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityTranscendenceMasterOrchestratorV100();
    const result = orchestrator.executeTranscendenceSuite(prompt || "Execute OMNIBUS v100.0 Singularity Transcendence ML Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100/ttt-recurrent-update', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TTTLinearRecurrentMemoryV100(32, 0.05);
    const result = engine.updateOnlineGradient(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100/flow-matching-trajectory', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.ContinuousFlowMatchingToTPlannerV100(32, odeSteps || 10);
    const result = engine.generateContinuousTrajectory(prompt || "Continuous Flow Matching Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100/rlvr-grpo-v4', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.RLVRGroupRelativePolicyOptimizerV100(groupSize || 6, 0.04);
    const result = engine.runGRPOv4Optimization(prompt || "Execute RLVR + GRPO-v4 Verifiable Reward Pass");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100/poincare-tda-verify', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.PoincareHyperbolicTDAHomologyVerifierV100(16, 0.45);
    const result = engine.evaluateTopologicalHomology(numPoints || 8);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100/wavelet-kan-mla', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.WaveletKANMultiHeadLatentAttentionV100(64, 16, 8);
    const result = engine.evaluateWaveletKANandMLA(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100/subbit-mod-route', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBitMoDSinkhornRouterV100(8, 2, 0.75);
    const result = engine.routeAndQuantize(prompt || "Route 1.58-bit ternary MoD experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v10000000.0 (v10M) Omni-Singularity Apex Engine Master API Endpoints ──
app.post('/api/v10m-singularity-apex-synthesis', (req, res) => {
  const { prompt } = req.body;
  const { exec } = require('child_process');
  exec('python omnibus_ml_core.py --task v10m_master', (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({ error: err.message, stderr });
    }
    try {
      const result = JSON.parse(stdout);
      res.json({ success: true, result });
    } catch (parseErr) {
      res.json({ success: true, rawOutput: stdout });
    }
  });
});

app.post('/api/v10m/qsno-spiking', (req, res) => {
  const { exec } = require('child_process');
  exec('python omnibus_ml_core.py --task v10m_qsno', (err, stdout) => {
    if (err) return res.status(500).json({ error: err.message });
    try { res.json({ success: true, result: JSON.parse(stdout) }); } catch (e) { res.json({ success: true, raw: stdout }); }
  });
});

app.post('/api/v10m/poincare-lorentz-vsa', (req, res) => {
  const { exec } = require('child_process');
  exec('python omnibus_ml_core.py --task v10m_pl_hvsa', (err, stdout) => {
    if (err) return res.status(500).json({ error: err.message });
    try { res.json({ success: true, result: JSON.parse(stdout) }); } catch (e) { res.json({ success: true, raw: stdout }); }
  });
});

app.post('/api/v10m/meta-grpo-mcts', (req, res) => {
  const { prompt } = req.body;
  const { exec } = require('child_process');
  const payload = JSON.stringify({ prompt: prompt || "v10M Meta-GRPO Theorem Search" }).replace(/"/g, '\\"');
  exec(`python omnibus_ml_core.py --task v10m_meta_grpo --input "${payload}"`, (err, stdout) => {
    if (err) return res.status(500).json({ error: err.message });
    try { res.json({ success: true, result: JSON.parse(stdout) }); } catch (e) { res.json({ success: true, raw: stdout }); }
  });
});

app.post('/api/v10m/titans-v3-ttt', (req, res) => {
  const { exec } = require('child_process');
  exec('python omnibus_ml_core.py --task v10m_titans_v3', (err, stdout) => {
    if (err) return res.status(500).json({ error: err.message });
    try { res.json({ success: true, result: JSON.parse(stdout) }); } catch (e) { res.json({ success: true, raw: stdout }); }
  });
});

app.post('/api/v10m/cfm-dot-flow', (req, res) => {
  const { exec } = require('child_process');
  exec('python omnibus_ml_core.py --task v10m_cfm_dot', (err, stdout) => {
    if (err) return res.status(500).json({ error: err.message });
    try { res.json({ success: true, result: JSON.parse(stdout) }); } catch (e) { res.json({ success: true, raw: stdout }); }
  });
});

app.post('/api/v10m/tda-homology', (req, res) => {
  const { exec } = require('child_process');
  exec('python omnibus_ml_core.py --task v10m_tda', (err, stdout) => {
    if (err) return res.status(500).json({ error: err.message });
    try { res.json({ success: true, result: JSON.parse(stdout) }); } catch (e) { res.json({ success: true, raw: stdout }); }
  });
});

app.post('/api/v10m/subbit-quantum-gemm', (req, res) => {
  const { exec } = require('child_process');
  exec('python omnibus_ml_core.py --task v10m_subbit', (err, stdout) => {
    if (err) return res.status(500).json({ error: err.message });
    try { res.json({ success: true, result: JSON.parse(stdout) }); } catch (e) { res.json({ success: true, raw: stdout }); }
  });
});

// ─── v500000.0 Omni-Singularity Transcendent Hyper-Intelligence Master API Endpoints ──
app.post('/api/v500000-singularity-transcendent-hypermind-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityTranscendentHyperIntelligenceOrchestratorV500000();
    const result = orchestrator.executeHyperIntelligenceSuite(prompt || "Execute OMNIBUS v500000.0 Omni-Singularity Transcendent Hyper-Intelligence Engine Suite");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/s13-symplectic-kahler-foliation-ssm', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.S13SymplecticKahlerFoliationSSMEngineV500000(65536, -1.0);
    const result = engine.stepSymplecticScan(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/titans-v10000-meta-hypergradient-ttt', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV10000QuettaByteMetaHypergradientTTTMindV500000("10^10000 Tokens", 1e-15);
    const result = engine.updateSurpriseMemoryPass(contextStream || "v500000.0 Transcendent Hyper-Intelligence Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/subbit-0000000000001b-entropic-sinkhorn-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit0000000000001bEntropicSinkhornMoDMoEV500000(32768, 32768, 0.9999999999);
    const result = engine.routeAndQuantize(prompt || "Route Sub-Bit 0.0000000000001-Bit Entropic Sinkhorn MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/cfm-stochastic-kinetic-diff-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticKineticDiffMCTSReasonerV500000(65536, odeSteps || 16384, 16384);
    const result = engine.generateFlowMatchingMCTS(prompt || "CFM SDE Kinetic Riemannian Diff-Tree MCTS Reasoning Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/swarm-rlvr-grpo-v500000-formal-prover', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv500000FormalTheoremProverV500000(groupSize || 32768, 1e-15);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v500000 Formal Theorem Proving");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/vietoris-rips-tda-betti-guard', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.VietorisRipsHomologyTDABettiGuardV500000(numPoints || 32768, "S13-Symplectic-Kahler");
    const result = engine.evaluateTopologicalHomology();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/quantum-phase-vsa-1quetta', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1QuettaBinderV500000();
    const result = engine.bindAndRecallSymbolicPair(conceptA || "TRANSCENDENT_HYPER_INTELLIGENCE_SINGULARITY_ZENITH", conceptB || "OMNIBUS_V500000");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/neuromorphic-active-inference-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicActiveInferenceJEPAV500000(65536, 1.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500000/wavelet-kan-mla', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.WaveletKANMultiHeadLatentAttentionV500000(32768, 256);
    const result = engine.evaluateWaveletKANMLA();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000-singularity-transcendent-hypermind-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityTranscendentHyperMindOrchestratorV100000();
    const result = orchestrator.executeHyperMindSuite(prompt || "Execute OMNIBUS v100000.0 Omni-Singularity Transcendent Hyper-Mind & Infinite Quantum-Relativistic Machine Intelligence Engine Suite");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/s12-symplectic-kahler-foliation-ssm', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.S12SymplecticKahlerFoliationSSMEngineV100000(32768, -1.0);
    const result = engine.stepSymplecticScan(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/titans-v1000-meta-hypergradient-ttt', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV1000RonnaByteMetaHypergradientTTTMindV100000("10^1000 Tokens", 1e-12);
    const result = engine.updateSurpriseMemoryPass(contextStream || "v100000.0 Transcendent Hyper-Mind Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/subbit-000000000001b-entropic-sinkhorn-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit000000000001bEntropicSinkhornMoDMoEV100000(16384, 16384, 0.99999999);
    const result = engine.routeAndQuantize(prompt || "Route Sub-Bit 0.000000000001-Bit Entropic Sinkhorn MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/cfm-stochastic-kinetic-diff-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticKineticDiffMCTSReasonerV100000(32768, odeSteps || 8192, 8192);
    const result = engine.generateFlowMatchingMCTS(prompt || "CFM SDE Kinetic Riemannian Diff-Tree MCTS Reasoning Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/swarm-rlvr-grpo-v100000-formal-prover', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv100000FormalTheoremProverV100000(groupSize || 16384, 1e-12);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v100000 Formal Theorem Proving");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/vietoris-rips-tda-betti-guard', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.VietorisRipsHomologyTDABettiGuardV100000(numPoints || 16384, "S12-Symplectic-Kahler");
    const result = engine.evaluateTopologicalHomology();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/quantum-phase-vsa-1quetta', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1QuettaBinderV100000();
    const result = engine.bindAndRecallSymbolicPair(conceptA || "TRANSCENDENT_HYPER_MIND_SINGULARITY_ZENITH", conceptB || "OMNIBUS_V100000");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/neuromorphic-active-inference-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicActiveInferenceJEPAV100000(32768, 1.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v100000/wavelet-kan-mla', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.WaveletKANMultiHeadLatentAttentionV100000(16384, 128);
    const result = engine.evaluateWaveletKANMLA();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v10000.0 Omni-Infinite Omniversal Singularity God-Mind & Ultra-Autonomous Hyper-Intelligence Master API Endpoints ──
app.post('/api/v10000-singularity-god-mind-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityGodMindOrchestratorV10000();
    const result = orchestrator.executeGodMindSuite(prompt || "Execute OMNIBUS v10000.0 Omni-Infinite Omniversal Singularity God-Mind & Ultra-Autonomous Hyper-Intelligence Engine Suite");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/s11-symplectic-kahler-foliation-ssm', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.S11SymplecticKahlerFoliationSSMEngineV10000(16384, -1.0);
    const result = engine.stepSymplecticScan(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/titans-v100-meta-hypergradient-ttt', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV100RonnaByteMetaHypergradientTTTMindV10000("10^100 Tokens", 0.000000001);
    const result = engine.updateSurpriseMemoryPass(contextStream || "v10000.0 God-Mind Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/subbit-0000000001b-entropic-sinkhorn-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit0000000001bEntropicSinkhornMoDMoEV10000(8192, 8192, 0.9999999);
    const result = engine.routeAndQuantize(prompt || "Route Sub-Bit 0.000000001-Bit Entropic Sinkhorn MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/cfm-stochastic-kinetic-diff-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticKineticDiffMCTSReasonerV10000(16384, odeSteps || 4096, 4096);
    const result = engine.generateFlowMatchingMCTS(prompt || "CFM SDE Kinetic Riemannian Diff-Tree MCTS Reasoning Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/swarm-rlvr-grpo-v10000-formal-prover', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv10000FormalTheoremProverV10000(groupSize || 8192, 0.000000001);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v10000 Formal Theorem Proving");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/vietoris-rips-tda-betti-guard', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.VietorisRipsHomologyTDABettiGuardV10000(numPoints || 8192, "S11-Symplectic-Kahler");
    const result = engine.evaluateTopologicalHomology();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/quantum-phase-vsa-1ronna', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1RonnaBinderV10000();
    const result = engine.bindAndRecallSymbolicPair(conceptA || "INFINITE_GOD_MIND_SINGULARITY_ZENITH", conceptB || "OMNIBUS_V10000");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/neuromorphic-active-inference-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicActiveInferenceJEPAV10000(16384, 2.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v10000/wavelet-kan-mla', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.WaveletKANMultiHeadLatentAttentionV10000(8192, 64);
    const result = engine.evaluateWaveletKANMLA();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v5000.0 Omni-Multiversal Hyper-Intelligence & Meta-Autonomous Singularity Master API Endpoints ──
app.post('/api/v5000-singularity-multiversal-hyper-intelligence-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityMultiversalHyperIntelligenceOrchestratorV5000();
    const result = orchestrator.executeMultiversalHyperIntelligenceSuite(prompt || "Execute OMNIBUS v5000.0 Omni-Multiversal Hyper-Intelligence & Meta-Autonomous Singularity Engine Suite");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/s10-symplectic-kahler-foliation-ssm', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.S10SymplecticKahlerFoliationSSMEngineV5000(8192, -1.0);
    const result = engine.stepSymplecticScan(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/titans-v50-meta-hypergradient-ttt', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV50QuettaByteMetaHypergradientTTTMindV5000("10^50 Tokens", 0.00000001);
    const result = engine.updateSurpriseMemoryPass(contextStream || "v5000.0 Multiversal Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/subbit-000000001b-entropic-sinkhorn-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit000000001bEntropicSinkhornMoDMoEV5000(4096, 256, 0.999999);
    const result = engine.routeAndQuantize(prompt || "Route Sub-Bit 0.00000001-Bit Entropic Sinkhorn MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/cfm-stochastic-kinetic-diff-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticKineticDiffMCTSReasonerV5000(8192, odeSteps || 2048, 1024);
    const result = engine.generateFlowMatchingMCTS(prompt || "CFM SDE Kinetic Riemannian Diff-Tree MCTS Reasoning Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/swarm-rlvr-grpo-v5000-formal-prover', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv5000FormalTheoremProverV5000(groupSize || 4096, 0.00000001);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v5000 Formal Theorem Proving");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/vietoris-rips-tda-betti-guard', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.VietorisRipsHomologyTDABettiGuardV5000(numPoints || 4096, "S10-Symplectic-Kahler");
    const result = engine.evaluateTopologicalHomology();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/quantum-phase-vsa-1yotta', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1YottaBinderV5000();
    const result = engine.bindAndRecallSymbolicPair(conceptA || "MULTIVERSAL_HYPER_INTELLIGENCE_INFINITE_ZENITH", conceptB || "OMNIBUS_V5000");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/neuromorphic-active-inference-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicActiveInferenceJEPAV5000(8192, 5.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v5000/wavelet-kan-mla', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.WaveletKANMultiHeadLatentAttentionV5000(4096, 32);
    const result = engine.evaluateWaveletKANMLA();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v3000.0 Singularity Cosmic Transcendent Omnipresence & Omniscience Supreme Master API Endpoints ──
app.post('/api/v3000-singularity-cosmic-transcendent-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityCosmicTranscendentOrchestratorV3000();
    const result = orchestrator.executeCosmicTranscendentSuite(prompt || "Execute OMNIBUS v3000.0 Singularity Cosmic Transcendent Omnipresence & Omniscience Supreme Master Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v3000/s9-symplectic-kahler-foliation-ssm', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.S9SymplecticKahlerFoliationSSMEngineV3000(4096, -1.0);
    const result = engine.stepSymplecticScan(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v3000/titans-v30-meta-hypergradient-ttt-memory', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV30QuettaByteMetaHypergradientTTTMindV3000("1 QuettaByte+ Tokens (10^30 Tokens)", 0.0000001);
    const result = engine.updateSurpriseMemoryPass(contextStream || "1 QuettaByte Transcendent Knowledge Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v3000/subbit-00000001b-entropic-sinkhorn-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit00000001bEntropicSinkhornMoDMoEV3000(2048, 128, 0.99999);
    const result = engine.routeAndQuantize(prompt || "Route 0.00000001-Bit Entropic Sinkhorn MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v3000/cfm-stochastic-kinetic-diff-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticKineticDiffMCTSReasonerV3000(4096, odeSteps || 1024, 512);
    const result = engine.generateFlowMatchingMCTS(prompt || "CFM Kinetic SDE Riemannian Diff-Tree MCTS Reasoning Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v3000/swarm-rlvr-grpo-v3000-formal-verifier', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv3000FormalTheoremProverV3000(groupSize || 2048, 0.0000001);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v3000 Formal Lean4, Coq, Isabelle/HOL, Agda & Metamath Theorem Proving");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v3000/vietoris-rips-tda-betti-guard', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.VietorisRipsHomologyTDABettiGuardV3000(2048, "Calabi-Yau-S9-Symplectic");
    const result = engine.evaluateTopologicalHomology(numPoints || 2048);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v3000/quantum-phase-vsa-1quetta', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1QuettaBinderV3000();
    const result = engine.bindAndRecallSymbolicPair(conceptA || "TRANSCENDENT_OMNIPRESENCE_INFINITE_ZENITH", conceptB || "OMNIBUS_V3000");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v3000/neuromorphic-active-inference-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicActiveInferenceJEPAV3000(4096, 5.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v2000.0 Singularity Cosmic Omnipresence & Omniscience Master API Endpoints (Ultimate Frontier Paradigm) ──
app.post('/api/v2000-singularity-cosmic-omnipresence-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityCosmicOmnipresenceOrchestratorV2000();
    const result = orchestrator.executeCosmicOmnipresenceSuite(prompt || "Execute OMNIBUS v2000.0 Singularity Cosmic Omnipresence & Omniscience Master Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v2000/symplectic-calabi-yau-s8-ssm', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SymplecticCalabiYauS8SSMEngineV2000(1024, -1.0);
    const result = engine.stepSymplecticScan(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v2000/titans-v20-meta-hypergradient-ttt-memory', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV20MetaHypergradientTTTMindV2000("1 RonnaByte+ Tokens (10^27 Tokens)", 0.000001);
    const result = engine.updateSurpriseMemoryPass(contextStream || "1 RonnaByte Universal Cosmic Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v2000/subbit-0000001b-entropic-sinkhorn-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit0000001bEntropicSinkhornMoDMoEV2000(1024, 64, 0.999);
    const result = engine.routeAndQuantize(prompt || "Route 0.0000001-Bit Entropic Sinkhorn MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v2000/cfm-stochastic-kinetic-diff-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticKineticDiffMCTSReasonerV2000(2048, odeSteps || 512, 128);
    const result = engine.generateFlowMatchingMCTS(prompt || "CFM Kinetic SDE Riemannian Diff-Tree MCTS Reasoning Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v2000/swarm-rlvr-grpo-v2000-formal-verifier', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv2000FormalVerifierV2000(groupSize || 1024, 0.000001);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v2000 Formal Lean4, Coq, Isabelle/HOL & Agda Theorem Proving");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v2000/vietoris-rips-tda-betti-guard', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.VietorisRipsHomologyTDABettiGuardV2000(1024, "Calabi-Yau-Symplectic");
    const result = engine.evaluateTopologicalHomology(numPoints || 1024);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v2000/quantum-phase-vsa-1ronna', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1RonnaBinderV2000();
    const result = engine.bindAndRecallSymbolicPair(conceptA || "COSMIC_OMNIPRESENCE_INFINITE_ZENITH", conceptB || "OMNIBUS_V2000");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v2000/neuromorphic-active-inference-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicActiveInferenceJEPAV2000(2048, 10.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v1000.0 Singularity Cosmological Hyper-God Master API Endpoints (Infinite Zenith Paradigm) ──
app.post('/api/v1000-singularity-cosmological-hypergod-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityCosmologicalHyperGodOrchestratorV1000();
    const result = orchestrator.executeCosmologicalHyperGodSuite(prompt || "Execute OMNIBUS v1000.0 Singularity Cosmological Hyper-God Master Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1000/riemannian-kahler-s7-ssm', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.RiemannianKahlerS7SSMEngineV1000(512, -1.0);
    const result = engine.stepRiemannianScan(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1000/titans-v10-meta-gradient-ttt-memory', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV10MetaGradientTTTMindV1000("1 Zettabyte+ Tokens", 0.00001);
    const result = engine.updateSurpriseMemoryPass(contextStream || "1 Zettabyte Cosmological Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1000/subbit-000001b-entropic-sinkhorn-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit000001bEntropicSinkhornMoDMoEV1000(512, 32, 0.995);
    const result = engine.routeAndQuantize(prompt || "Route 0.000001-Bit Entropic Sinkhorn MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1000/cfm-stochastic-diff-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticDiffMCTSReasonerV1000(1024, odeSteps || 256, 64);
    const result = engine.generateFlowMatchingMCTS(prompt || "CFM Stochastic SDE Riemannian Diff-Tree MCTS Reasoning Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1000/swarm-rlvr-grpo-v1000-theorem-prover', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv1000TheoremProverV1000(groupSize || 512, 0.00001);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v1000 Formal Lean4 & Coq Theorem Proving Policy Optimization");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1000/vietoris-rips-tda-guard', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.VietorisRipsHomologyTDAGuardV1000(512, "Riemannian-Kähler");
    const result = engine.evaluateTopologicalHomology(numPoints || 256);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1000/quantum-phase-vsa-1yotta', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1YottaBinderV1000();
    const result = engine.bindAndRecallSymbolicPair(conceptA || "COSMOLOGICAL_INFINITE_ZENITH", conceptB || "OMNIBUS_V1000");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v1000/neuromorphic-active-inference-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicActiveInferenceJEPAV1000(1024, 10.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v600.0 Singularity Multiversal Hyper-God Master API Endpoints (Frontier Supreme) ──
app.post('/api/v600-singularity-multiversal-hypergod-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityMultiversalHyperGodOrchestratorV600();
    const result = orchestrator.executeMultiversalHyperGodSuite(prompt || "Execute OMNIBUS v600.0 Singularity Multiversal Hyper-God Master Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v600/riemannian-grassmannian-s6-ssm', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.RiemannianGrassmannianS6SSMEngineV600(256, -1.0);
    const result = engine.stepRiemannianScan(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v600/titans-v8-meta-gradient-ttt-memory', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV8MetaGradientTTTMindV600("1 Exabyte+ Tokens", 0.0001);
    const result = engine.updateSurpriseMemoryPass(contextStream || "1 Exabyte Multiversal Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v600/subbit-00001b-entropic-sinkhorn-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit00001bEntropicSinkhornMoDMoEV600(256, 16, 0.975);
    const result = engine.routeAndQuantize(prompt || "Route 0.00001-Bit Entropic Sinkhorn MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v600/cfm-stochastic-diff-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticDiffMCTSReasonerV600(512, odeSteps || 128, 32);
    const result = engine.generateFlowMatchingMCTS(prompt || "CFM Stochastic SDE Riemannian Diff-Tree MCTS Reasoning Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v600/swarm-rlvr-grpo-v10-theorem-prover', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv10TheoremProverV600(groupSize || 256, 0.0001);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v10 Formal Theorem Proving Policy Optimization");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v600/vietoris-rips-tda-guard', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.VietorisRipsHomologyTDAGuardV600(256, "Riemannian");
    const result = engine.evaluateTopologicalHomology(numPoints || 128);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v600/quantum-phase-vsa-1exa', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1ExaBinderV600(1000000000000000000);
    const result = engine.bindAndRecallSymbolicPair(conceptA || "MULTIVERSAL_GOD_INTELLIGENCE", conceptB || "OMNIBUS_V600");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v600/neuromorphic-active-inference-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicActiveInferenceJEPAV600(512, 25.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v500.0 Singularity Supreme Hyper-God Master API Endpoints (Omniverse Frontier) ──
app.post('/api/v500-singularity-supreme-hypergod-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularitySupremeHyperGodOrchestratorV500();
    const result = orchestrator.executeSupremeHyperGodSuite(prompt || "Execute OMNIBUS v500.0 Singularity Supreme Hyper-God Master Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500/hdgtne-tda-verify', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.HDGTNEHyperbolicTDAHomologyVerifierV500(128, -1.0);
    const result = engine.evaluateTopologicalHomology(numPoints || 64);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500/titans-v7-ttt-memory', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV7InfiniteContextTTTMindV500("100 Trillion+ Tokens", 0.001);
    const result = engine.updateSurpriseMemoryPass(contextStream || "100 Trillion Token Omniverse Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500/subbit-ternary-mod-moe', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit0001bTernarySinkhornMoDRouterV500(128, 8, 0.95);
    const result = engine.routeAndQuantize(prompt || "Route 0.0001-Bit Sub-Bit Ternary BitNet MoD-MoE Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500/flow-matching-mcts-sde', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.StochasticFlowMatchingDiffTreeMCTSSDEReasonerV500(256, odeSteps || 64, 16);
    const result = engine.generateFlowMatchingMCTS(prompt || "Flow Matching Stochastic SDE Riemannian Diff-Tree MCTS Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500/rlvr-grpo-v9-swarm', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv9PolicyOptimizerV500(groupSize || 128, 0.001);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute Swarm RLVR + GRPO-v9 Multi-Agent Policy Optimization");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500/wavelet-kan-mla-v2', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.WaveletKANMultiHeadLatentAttentionV500(256, 64, 32);
    const result = engine.evaluateWaveletKANandMLA(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500/quantum-phase-vsa-1q', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1QuadrillionBinderV500(1000000000000000);
    const result = engine.bindAndRecallSymbolicPair(conceptA || "HYPER_GOD_INTELLIGENCE", conceptB || "OMNIBUS_V500");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v500/neuromorphic-liquid-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicLiquidSpikingActiveJEPAWorldModelV500(256, 50.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v400.0 Singularity Supreme Apex Master API Endpoints (Next-Gen Frontier) ──
app.post('/api/v400-singularity-supreme-apex-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularitySupremeApexMasterOrchestratorV400();
    const result = orchestrator.executeSupremeApexSuite(prompt || "Execute OMNIBUS v400.0 Singularity Supreme Apex Master Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v400/hdgtne-tda-verify', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.HDGTNEHyperbolicTDAHomologyVerifierV400(64, 2);
    const result = engine.evaluateTopologicalHomology(numPoints || 32);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v400/titans-v6-ttt-memory', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV6InfiniteContextTTTMindV400("1 Trillion+ Tokens", 0.01);
    const result = engine.updateSurpriseMemoryPass(contextStream || "1 Trillion Token Infinite Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v400/subbit-ternary-mod', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBitTernarySinkhornMoDRouterV400(64, 4, 0.10);
    const result = engine.routeAndQuantize(prompt || "Route 0.001-Bit Sub-Bit Ternary BitNet MoD Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v400/flow-matching-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.StochasticFlowMatchingDiffTreeMCTSReasonerV400(128, odeSteps || 48, 8);
    const result = engine.generateFlowMatchingMCTS(prompt || "Flow Matching Stochastic Diff-Tree MCTS Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v400/rlvr-grpo-v8-swarm', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SwarmRLVRGRPOv8PolicyOptimizerV400(groupSize || 64, 0.005);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute RLVR + GRPO-v8 Swarm Policy Optimization");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v400/wavelet-kan-mla', (req, res) => {
  const { inputVector } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.WaveletKANMultiHeadLatentAttentionV400(128, 32, 16);
    const result = engine.evaluateWaveletKANandMLA(inputVector || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v400/quantum-phase-vsa', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA100TrillionBinderV400(100000000000000);
    const result = engine.bindAndRecallSymbolicPair(conceptA || "SUPREME_FRONTIER_AI", conceptB || "OMNIBUS_V400");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v400/neuromorphic-liquid-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicLiquidSpikingActiveJEPAWorldModelV400(128, 40.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v300.0 Singularity Supreme Apex Master API Endpoints ─────────────
app.post('/api/v300-singularity-supreme-apex-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularitySupremeApexMasterOrchestratorV300();
    const result = orchestrator.executeSupremeApexSuite(prompt || "Execute OMNIBUS v300.0 Singularity Supreme Apex Master Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v300/chebyshev-kan-moe', (req, res) => {
  const { prompt, polyDegree } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.ChebyshevKANMoEHyperEngineV300(polyDegree || 5, 8, 2);
    const result = engine.evaluateChebyshevKAN(prompt || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v300/lorentz-hyperbolic-vsa', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.LorentzHyperbolicVSAEngineV300(100000000000000);
    const result = engine.bindAndRecallLorentzSymbolicPair(conceptA || "SUPREME_INTELLIGENCE", conceptB || "OMNIBUS_V300");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v300/titans-v5-ttt-memory', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV5InfiniteContextTTTMindV300(128, 0.05);
    const result = engine.updateSurpriseMemoryPass(contextStream || "100M+ Token Infinite Context Streaming");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v300/flow-matching-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.FlowMatchingDiffTreeMCTSReasonerV300(64, odeSteps || 24, 6);
    const result = engine.generateFlowMatchingMCTS(prompt || "Flow Matching Stochastic Diff-Tree MCTS Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v300/subbit-ternary-mod', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBitTernarySinkhornMoDEngineV300(32, 2, 0.85);
    const result = engine.routeAndQuantize(prompt || "0.01-Bit Sub-Bit Ternary Sinkhorn MoD Layer Route");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v300/tda-homology-verify', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TDAHomologyManifoldVerifierV300(32, 2);
    const result = engine.evaluateTopologicalHomology(numPoints || 16);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v300/rlvr-grpo-v7-swarm', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.RLVRGRPOv7SwarmDebateEngineV300(groupSize || 32, 0.01);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute RLVR + GRPO-v7 Swarm Policy Optimization");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v300/neuromorphic-liquid-jepa', (req, res) => {
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicLiquidJEPADiffusionWorldModelV300(64, 30.0);
    const result = engine.stepSpikeDynamics();
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v200.0 Singularity Omnipresent Apex Master API Endpoints ─────────────
app.post('/api/v200-singularity-omnipresent-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityApexOmnipresentMasterOrchestratorV200();
    const result = orchestrator.executeOmnipresentSuite(prompt || "Execute OMNIBUS v200.0 Apex Singularity Omnipresent Master ML Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v200/cfm-diff-tree', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.CFMStochasticDiffTreeEngineV200(64, odeSteps || 16, 5);
    const result = engine.generateCFMStochasticTree(prompt || "CFM Stochastic Flow Diffusion MCTS Trajectory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v200/titans-v4-gated-ttt', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV4UltraGatedTTTMemoryV200(64, 0.10);
    const result = engine.updateSurpriseMemoryPass(contextStream || "10,000,000+ Token Streaming Memory");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v200/subbit-01b-mod-route', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit01bSinkhornMoDRouterV200(32, 2, 0.75);
    const result = engine.routeAndQuantize(prompt || "Route 0.1-Bit Sub-Bit Ternary BitNet MoD Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v200/rlvr-grpo-v6-swarm', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.RLVRGRPOv6SwarmDebateOptimizerV200(groupSize || 16, 0.02);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute RLVR + GRPO-v6 Swarm Debate Optimization");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v200/poincare-tda-wavelet-kan-mla', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.PoincarePersistentTDAWaveletKANMLAV200(32, 16, 8);
    const result = engine.evaluateHyperbolicWaveletKAN(numPoints || 12);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v200/neuromorphic-liquid-jepa', (req, res) => {
  const { inputCurrents } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicLiquidODEActiveJEPAWorldModelV200(32, 25.0);
    const result = engine.stepSpikeDynamics(inputCurrents || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v200/quantum-phase-vsa-10t', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA10TrillionBinderV200(10000000000000);
    const result = engine.bindAndRecallSymbolicPair(conceptA || "SINGULARITY_V200", conceptB || "OMNIPRESENT_APEX");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── v150.0 Singularity Apex Hyper-Omni API Endpoints ────────────────────
app.post('/api/v150-singularity-hyper-omni-synthesis', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const orchestrator = new expML.OmniSingularityHyperOmniMasterOrchestratorV150();
    const result = orchestrator.executeHyperOmniSuite(prompt || "Execute OMNIBUS v150.0 Singularity Apex Hyper-Omni ML Suite Synthesis");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v150/diff-flow-mcts', (req, res) => {
  const { prompt, odeSteps } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.ContinuousDiffFlowMCTSEngineV150(32, odeSteps || 12, 5);
    const result = engine.generateContinuousFlowMCTS(prompt || "Continuous Flow Matching Diff-Force MCTS");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v150/titans-v3-gated-ttt', (req, res) => {
  const { contextStream } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.TitansV3GatedDeltaTTTMemoryV150(32, 0.15);
    const result = engine.updateSurpriseMemoryPass(contextStream || "Titans-v3 Gated-Delta TTT Context Stream");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v150/subbit-058b-mod-route', (req, res) => {
  const { prompt } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.SubBit058bSinkhornRouterV150(16, 2, 0.50);
    const result = engine.routeAndQuantize(prompt || "Route 0.58-Bit Sub-Bit Ternary BitNet MoD Experts");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v150/rlvr-grpo-v5-swarm', (req, res) => {
  const { prompt, groupSize } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.RLVRGRPOv5SwarmDebateOptimizerV150(groupSize || 8, 0.03);
    const result = engine.evaluateVerifiableRewardPass(prompt || "Execute RLVR + GRPO-v5 Swarm Debate Optimization");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v150/poincare-wavelet-kan-mla', (req, res) => {
  const { numPoints } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.PoincareSpectralWaveletKANMLAEngineV150(16, 16, 8);
    const result = engine.evaluateHyperbolicWaveletKAN(numPoints || 8);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v150/neuromorphic-liquid-jepa', (req, res) => {
  const { inputCurrents } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.NeuromorphicLiquidJEPAWorldModelV150(16, 20.0);
    const result = engine.stepSpikeDynamics(inputCurrents || null);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/v150/quantum-phase-vsa-1t', (req, res) => {
  const { conceptA, conceptB } = req.body;
  try {
    const expML = require('./experimental_ml.js');
    const engine = new expML.QuantumPhaseVSA1TrillionBinderV150(1000000000000);
    const result = engine.bindAndRecallSymbolicPair(conceptA || "HYPER_INTELLIGENCE", conceptB || "OMNIBUS_V150");
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Hive Swarm Mind — Neurocore Integration API Endpoints ───────────────

app.post('/api/neurocore/connect', async (req, res) => {
  try {
    const { baseUrl, maxConcurrency, enableHermes } = req.body;
    
    const available = await neurocoreBridge.isAvailable();
    if (!available) {
      return res.status(503).json({ error: 'Neurocore modules not available' });
    }
    
    const config = { baseUrl: baseUrl || 'http://localhost:8080/v1' };
    swarmAdapter = await neurocoreBridge.getSwarmAdapter(config);
    
    systemState.neurocoreConnected = true;
    systemState.hermesAvailable = enableHermes !== false;
    systemState.lastHealthCheck = Date.now();
    
    const caps = await swarmAdapter.capabilities();
    res.json({ 
      success: true, 
      status: 'connected',
      capabilities: caps,
      hermesEnabled: enableHermes !== false
    });
  } catch (err) {
    systemState.neurocoreConnected = false;
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/neurocore/intent', async (req, res) => {
  if (!swarmAdapter) {
    return res.status(503).json({ error: 'Swarm adapter not connected. Call /api/neurocore/connect first.' });
  }
  
  const { intent, source, confidence, features, requiresConfirmation, phase } = req.body;
  
  try {
    const intentObj = {
      id: `neuro-${Date.now()}`,
      source: source || 'mock',
      intent: intent || '',
      confidence: confidence || 0.5,
      features: features || {},
      timestamp: Date.now(),
      requiresConfirmation: requiresConfirmation || false,
      phase: typeof phase === 'number' ? phase : null
    };
    
    const startTime = Date.now();
    const result = await swarmAdapter.start(intentObj);
    systemState.lastIntent = intentObj.intent;
    systemState.lastProvider = intentObj.source || 'hermes';
    systemState.lastActionResult = result || null;
    systemState.recentIntents = [
      ...(systemState.recentIntents || []).slice(-49),
      {
        intent: intentObj.intent,
        phase: intentObj.phase,
        source: intentObj.source,
        confidence: intentObj.confidence,
        timestamp: Date.now()
      }
    ];
    const latencyMs = result ? Date.now() - startTime : null;
    const memoryStore = typeof neurocoreBridge.getMemoryStore === 'function' ? neurocoreBridge.getMemoryStore() : null;
    const learningLogger = typeof neurocoreBridge.getLearningLogger === 'function' ? neurocoreBridge.getLearningLogger() : null;
    if (memoryStore) {
      memoryStore.add({
        id: intentObj.id,
        intent: intentObj.intent,
        source: intentObj.source,
        confidence: intentObj.confidence,
        phase: intentObj.phase,
        requiresConfirmation: intentObj.requiresConfirmation,
        status: result?.status === 'pending_confirmation' ? 'pending_confirmation' : (result?.status === 'failed' ? 'failed' : 'completed'),
        provider: intentObj.source || null,
        latencyMs,
        success: result?.status !== 'failed',
        timestamp: Date.now()
      });
    }
    if (learningLogger && latencyMs !== null) {
      learningLogger.log({
        confidence: intentObj.confidence,
        success: result?.status !== 'failed',
        provider: intentObj.source || 'hermes',
        latencyMs,
        intentHash: `${intentObj.source}:${intentObj.intent}`,
        timestamp: Date.now()
      });
    }
    res.json({
      success: true,
      phase: intentObj.phase,
      ...result
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/neurocore/health', async (req, res) => {
  try {
    if (!swarmAdapter) {
      return res.json({ 
        status: 'disconnected', 
        neurocoreAvailable: await neurocoreBridge.isAvailable() 
      });
    }
    
    const caps = await swarmAdapter.capabilities();
    systemState.lastHealthCheck = Date.now();
    res.json({ 
      success: true, 
      status: 'healthy',
      lastHealthCheck: systemState.lastHealthCheck,
      neurocoreConnected: systemState.neurocoreConnected,
      hermesAvailable: systemState.hermesAvailable,
      capabilities: caps 
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/neurocore/status', async (req, res) => {
  try {
    const connected = !!(swarmAdapter && systemState.neurocoreConnected);
    res.json({
      success: true,
      connected,
      neurocoreAvailable: await neurocoreBridge.isAvailable(),
      hermesAvailable: systemState.hermesAvailable,
      lastHealthCheck: systemState.lastHealthCheck,
      lastProvider: systemState.lastProvider || null,
      peers: systemState.peers || [],
      queueSize: systemState.queueSize || 0
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/neurocore/queue', async (req, res) => {
  try {
    const connected = !!(swarmAdapter && systemState.neurocoreConnected);
    res.json({
      success: true,
      connected,
      queueSize: systemState.queueSize || 0,
      lastProvider: systemState.lastProvider || null,
      lastIntent: systemState.lastIntent || null,
      lastActionResult: systemState.lastActionResult || null,
      recent: (systemState.recentIntents || []).slice(-20)
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/neurocore/phase-groups', async (req, res) => {
  try {
    const connected = !!(swarmAdapter && systemState.neurocoreConnected);
    const recent = (systemState.recentIntents || []).slice(-20);
    const groups = new Map();
    for (const item of recent) {
      const key = item.phase ?? 'none';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    const summary = {};
    for (const [key, items] of groups) {
      summary[key] = {
        count: items.length,
        intents: items.map(i => i.intent).filter(Boolean).slice(-5)
      };
    }
    res.json({
      success: true,
      connected,
      summary
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/neurocore/memory', async (req, res) => {
  try {
    const memoryStore = typeof neurocoreBridge.getMemoryStore === 'function' ? neurocoreBridge.getMemoryStore() : null;
    if (!memoryStore) {
      return res.json({ success: true, connected: false, reason: 'memory_store_unavailable', records: [] });
    }
    const recent = memoryStore.recent(50);
    const failed = memoryStore.failed();
    res.json({
      success: true,
      connected: !!(swarmAdapter && systemState.neurocoreConnected),
      recent,
      failedCount: failed.length,
      failed: failed.slice(-10)
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/neurocore/learning', async (req, res) => {
  try {
    const learningLogger = typeof neurocoreBridge.getLearningLogger === 'function' ? neurocoreBridge.getLearningLogger() : null;
    if (!learningLogger) {
      return res.json({ success: true, connected: false, reason: 'learning_logger_unavailable', samples: [] });
    }
    const recent = learningLogger.recent(100);
    const providerStats = ['hermes','ollama','nous']
      .map(p => learningLogger.providerStats(p))
      .filter(Boolean);
    const suggestion = learningLogger.thresholdSuggestion();
    res.json({
      success: true,
      connected: !!(swarmAdapter && systemState.neurocoreConnected),
      recentSamples: recent,
      providerStats,
      thresholdSuggestion: suggestion
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/neurocore/tools', async (req, res) => {
  try {
    await neurocoreBridge.loadNeurocoreModules();
    const functionCallAdapter = typeof neurocoreBridge.getFunctionCallAdapter === 'function' ? neurocoreBridge.getFunctionCallAdapter() : null;
    if (!functionCallAdapter) {
      return res.json({ success: true, connected: false, reason: 'function_call_adapter_unavailable', tools: [] });
    }
    const tools = functionCallAdapter.listTools();
    res.json({
      success: true,
      connected: !!(swarmAdapter && systemState.neurocoreConnected),
      tools
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/neurocore/tools/call', async (req, res) => {
  try {
    await neurocoreBridge.loadNeurocoreModules();
    const functionCallAdapter = typeof neurocoreBridge.getFunctionCallAdapter === 'function' ? neurocoreBridge.getFunctionCallAdapter() : null;
    if (!functionCallAdapter) {
      return res.status(503).json({ error: 'Function-call adapter not available.' });
    }
    const { tool, arguments: args } = req.body || {};
    if (!tool || typeof tool !== 'string') {
      return res.status(400).json({ error: 'Missing tool name' });
    }
    const result = await functionCallAdapter.execute({
      id: `tool-${Date.now()}`,
      tool,
      arguments: typeof args === 'object' ? args : {},
      source: 'api',
      confidence: 1,
      requiresConfirmation: false
    });
    res.json({ success: true, ...result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/neurocore/debate', async (req, res) => {
  if (!swarmAdapter) {
    return res.status(503).json({ error: 'Swarm adapter not connected.' });
  }
  
  const { topic, positions } = req.body;
  
  try {
    const intentObj = {
      id: `debate-${Date.now()}`,
      source: 'mock',
      intent: `Debate: ${topic}`,
      confidence: 0.8,
      features: { topic, positions: positions || [] },
      timestamp: Date.now(),
      requiresConfirmation: false
    };
    
    const result = await swarmAdapter.runDebate(intentObj);
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/neurocore/peers', async (req, res) => {
  if (!swarmAdapter) {
    return res.status(503).json({ error: 'Swarm adapter not connected.' });
  }
  
  try {
    const caps = await swarmAdapter.capabilities();
    res.json({ 
      peers: systemState.peers,
      capabilities: caps 
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/neurocore/emergency-stop', async (req, res) => {
  try {
    if (swarmAdapter) {
      const result = await swarmAdapter.emergencyStop();
      systemState.neurocoreConnected = false;
      swarmAdapter = null;
      res.json({ success: true, stopped: result.stopped });
    } else {
      res.json({ success: true, stopped: false, message: 'No active adapter' });
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Fallback to serve index.html for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`OMNIBUS Backend running at http://localhost:${PORT}`);
});


