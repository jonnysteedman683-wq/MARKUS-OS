const fs = require('fs');
const path = require('path');
const OpenAI = require('openai');
const ollamaModule = require('ollama');
const ollamaClient = ollamaModule.default || ollamaModule;

class TitansVectorMemoryStore {
  constructor(options = {}) {
    this.filePath = options.filePath || path.join(__dirname, 'titans_vector_store.json');
    this.embeddingDim = options.embeddingDim || 256;
    this.surpriseThreshold = options.surpriseThreshold || 0.25;
    this.learningRate = options.learningRate || 0.15;
    this.memories = [];
    this.loadFromDisk();
  }

  loadFromDisk() {
    try {
      if (fs.existsSync(this.filePath)) {
        const raw = fs.readFileSync(this.filePath, 'utf8');
        const parsed = JSON.parse(raw);
        this.memories = Array.isArray(parsed.memories) ? parsed.memories : [];
        console.log(`[Titans Memory Store] Loaded ${this.memories.length} persistent vector memories from disk.`);
      } else {
        this.memories = [];
        this.saveToDisk();
      }
    } catch (err) {
      console.error(`[Titans Memory Store] Error loading vector store from disk: ${err.message}`);
      this.memories = [];
    }
  }

  saveToDisk() {
    try {
      const data = {
        updatedAt: new Date().toISOString(),
        totalMemories: this.memories.length,
        memories: this.memories
      };
      fs.writeFileSync(this.filePath, JSON.stringify(data, null, 2), 'utf8');
    } catch (err) {
      console.error(`[Titans Memory Store] Error saving vector store to disk: ${err.message}`);
    }
  }

  /**
   * Deterministic 256-dimensional semantic hypervector generator (Fallback vectorizer)
   */
  generateFallbackHypervector(text) {
    const dim = this.embeddingDim;
    const vec = new Array(dim).fill(0);
    const normalized = text.toLowerCase().trim();
    
    // Character n-gram hashing for semantic distance
    for (let i = 0; i < normalized.length; i++) {
      const charCode = normalized.charCodeAt(i);
      const idx1 = (charCode * 31 + i) % dim;
      const idx2 = (charCode * 53 + i * 17) % dim;
      vec[idx1] += Math.sin(i + charCode) * 0.5;
      vec[idx2] += Math.cos(i * 1.3 + charCode) * 0.5;
    }

    // Word hashing
    const words = normalized.split(/\s+/);
    words.forEach((w, wIdx) => {
      let hash = 0;
      for (let c = 0; c < w.length; c++) {
        hash = (hash << 5) - hash + w.charCodeAt(c);
        hash |= 0;
      }
      const p1 = Math.abs(hash) % dim;
      const p2 = Math.abs(hash * 37) % dim;
      vec[p1] += 1.0 / (wIdx + 1);
      vec[p2] += 0.5;
    });

    // L2 Normalize
    let norm = 0;
    for (let i = 0; i < dim; i++) norm += vec[i] * vec[i];
    norm = Math.sqrt(norm) || 1.0;
    return vec.map(v => v / norm);
  }

  /**
   * Generates embedding vector via OpenAI, Ollama, or Fallback Vectorizer
   */
  async getEmbedding(text) {
    // 1. Try OpenAI if API Key present
    if (process.env.OPENAI_API_KEY) {
      try {
        const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
        const res = await openai.embeddings.create({
          model: 'text-embedding-3-small',
          input: text
        });
        if (res?.data?.[0]?.embedding) {
          return { vector: res.data[0].embedding, provider: 'openai-text-embedding-3-small' };
        }
      } catch (e) {
        console.warn(`[Titans Memory] OpenAI embedding failed, trying Ollama: ${e.message}`);
      }
    }

    // 2. Try Ollama local embeddings
    try {
      const res = await ollamaClient.embeddings({
        model: 'nomic-embed-text',
        prompt: text
      });
      if (res && res.embedding && res.embedding.length > 0) {
        return { vector: res.embedding, provider: 'ollama-nomic-embed-text' };
      }
    } catch (e) {
      // Ollama embedding model might not be pulled or active
    }

    // 3. Fallback: High-dimensional deterministic hypervector
    const vector = this.generateFallbackHypervector(text);
    return { vector, provider: 'titans-local-hypervector-256' };
  }

  /**
   * Cosine Similarity between two vectors
   */
  cosineSimilarity(vecA, vecB) {
    if (!vecA || !vecB || vecA.length !== vecB.length) return 0;
    let dot = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < vecA.length; i++) {
      dot += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }
    const denom = Math.sqrt(normA) * Math.sqrt(normB);
    return denom === 0 ? 0 : dot / denom;
  }

  /**
   * Store a fact or key-value context with Titans surprise gating
   */
  async storeMemory(key, content, metadata = {}) {
    const textToEmbed = `${key}: ${content}`;
    const { vector, provider } = await this.getEmbedding(textToEmbed);

    // Calculate maximum similarity against existing memories to gauge "Surprise"
    let maxSim = 0;
    let nearestMemory = null;

    for (const mem of this.memories) {
      if (mem.vector && mem.vector.length === vector.length) {
        const sim = this.cosineSimilarity(vector, mem.vector);
        if (sim > maxSim) {
          maxSim = sim;
          nearestMemory = mem;
        }
      }
    }

    // Titans Surprise Metric: S = 1.0 - maxSimilarity
    const surprise = 1.0 - maxSim;
    const isNovel = surprise >= this.surpriseThreshold;

    // Check if key already exists (update existing)
    const existingIdx = this.memories.findIndex(m => m.key.toLowerCase() === key.toLowerCase());

    const memoryEntry = {
      id: existingIdx >= 0 ? this.memories[existingIdx].id : `mem_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      key,
      content,
      metadata,
      provider,
      vector,
      surpriseScore: parseFloat(surprise.toFixed(4)),
      retentionScore: parseFloat((maxSim * (1 - this.learningRate) + surprise * this.learningRate).toFixed(4)),
      accessCount: existingIdx >= 0 ? (this.memories[existingIdx].accessCount || 0) + 1 : 1,
      createdAt: existingIdx >= 0 ? this.memories[existingIdx].createdAt : new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    if (existingIdx >= 0) {
      this.memories[existingIdx] = memoryEntry;
    } else {
      this.memories.push(memoryEntry);
    }

    this.saveToDisk();

    return {
      status: isNovel ? 'NOVEL_MEMORY_STORED' : 'INCREMENTAL_MEMORY_UPDATED',
      memory: memoryEntry,
      surpriseMetric: surprise.toFixed(4),
      nearestSimilarity: maxSim.toFixed(4),
      totalMemories: this.memories.length
    };
  }

  /**
   * Recall memories matching query text using vector search & surprise ranking
   */
  async recallMemory(queryText, topK = 5, minSimilarity = 0.0) {
    if (this.memories.length === 0) {
      return { query: queryText, results: [], totalStored: 0 };
    }

    const { vector, provider } = await this.getEmbedding(queryText);

    // Calculate similarity scores
    const scored = this.memories.map(mem => {
      let sim = 0;
      if (mem.vector && mem.vector.length === vector.length) {
        sim = this.cosineSimilarity(vector, mem.vector);
      } else {
        // Fallback string matching if dimension mismatch (e.g., provider change)
        const qLower = queryText.toLowerCase();
        const kLower = mem.key.toLowerCase();
        const cLower = mem.content.toLowerCase();
        if (kLower.includes(qLower) || cLower.includes(qLower)) sim = 0.75;
      }

      return {
        id: mem.id,
        key: mem.key,
        content: mem.content,
        metadata: mem.metadata,
        similarity: parseFloat(sim.toFixed(4)),
        surpriseScore: mem.surpriseScore,
        retentionScore: mem.retentionScore,
        createdAt: mem.createdAt,
        updatedAt: mem.updatedAt
      };
    });

    // Filter & Sort by similarity descending
    const results = scored
      .filter(s => s.similarity >= minSimilarity)
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, topK);

    // Update access counts for recalled memories
    results.forEach(res => {
      const target = this.memories.find(m => m.id === res.id);
      if (target) {
        target.accessCount = (target.accessCount || 0) + 1;
        target.lastAccessedAt = new Date().toISOString();
      }
    });
    this.saveToDisk();

    return {
      query: queryText,
      queryProvider: provider,
      topK,
      recalledCount: results.length,
      totalStored: this.memories.length,
      results
    };
  }

  /**
   * Telemetry stats for Titans Vector Memory Store
   */
  getStats() {
    const avgSurprise = this.memories.length > 0
      ? (this.memories.reduce((acc, m) => acc + (m.surpriseScore || 0), 0) / this.memories.length).toFixed(4)
      : '0.0000';

    return {
      totalMemories: this.memories.length,
      filePath: this.filePath,
      avgSurpriseScore: avgSurprise,
      embeddingDim: this.embeddingDim,
      providersUsed: Array.from(new Set(this.memories.map(m => m.provider || 'unknown')))
    };
  }

  clearStore() {
    this.memories = [];
    this.saveToDisk();
    return { status: 'STORE_CLEARED', totalMemories: 0 };
  }
}

module.exports = TitansVectorMemoryStore;
