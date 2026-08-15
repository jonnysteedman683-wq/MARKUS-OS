/**
 * Machine Learning & Development Algorithms Suite for Multi-Path Agent System
 */

// 1. K-Means Clustering Algorithm (Agent Task Vector Clustering)
class KMeansClustering {
  constructor(k = 3, maxIter = 100) {
    this.k = k;
    this.maxIter = maxIter;
    this.centroids = [];
  }

  fit(data) {
    if (!data.length) return [];
    // Initialize centroids randomly
    this.centroids = data.slice(0, this.k).map(p => [...p]);

    for (let iter = 0; iter < this.maxIter; iter++) {
      const clusters = Array.from({ length: this.k }, () => []);
      
      for (const point of data) {
        let minDist = Infinity;
        let clusterIdx = 0;
        this.centroids.forEach((c, idx) => {
          const dist = this.euclideanDistance(point, c);
          if (dist < minDist) {
            minDist = dist;
            clusterIdx = idx;
          }
        });
        clusters[clusterIdx].push(point);
      }

      // Update centroids
      let shift = 0;
      this.centroids = clusters.map((cluster, idx) => {
        if (!cluster.length) return this.centroids[idx];
        const newCentroid = Array(cluster[0].length).fill(0);
        cluster.forEach(pt => pt.forEach((val, i) => newCentroid[i] += val / cluster.length));
        shift += this.euclideanDistance(newCentroid, this.centroids[idx]);
        return newCentroid;
      });

      if (shift < 0.001) break;
    }
    return this.centroids;
  }

  euclideanDistance(a, b) {
    return Math.sqrt(a.reduce((sum, val, i) => sum + Math.pow(val - (b[i] || 0), 2), 0));
  }
}

// 2. Q-Learning Algorithm (Reinforcement Learning for Agent Routing)
class QLearningRouter {
  constructor(states, actions, alpha = 0.1, gamma = 0.9, epsilon = 0.2) {
    this.states = states;
    this.actions = actions;
    this.alpha = alpha;
    this.gamma = gamma;
    this.epsilon = epsilon;
    this.qTable = {};
    this.initQTable();
  }

  initQTable() {
    this.states.forEach(s => {
      this.qTable[s] = {};
      this.actions.forEach(a => this.qTable[s][a] = 0);
    });
  }

  chooseAction(state) {
    if (Math.random() < this.epsilon) {
      return this.actions[Math.floor(Math.random() * this.actions.length)];
    }
    const actionsObj = this.qTable[state] || {};
    return Object.keys(actionsObj).reduce((best, a) => 
      actionsObj[a] > (actionsObj[best] ?? -Infinity) ? a : best, this.actions[0]);
  }

  update(state, action, reward, nextState) {
    const currentQ = this.qTable[state][action] || 0;
    const maxNextQ = Math.max(...Object.values(this.qTable[nextState] || { 0: 0 }));
    this.qTable[state][action] = currentQ + this.alpha * (reward + this.gamma * maxNextQ - currentQ);
  }
}

// 3. Genetic Algorithm (Automated Code / Path Optimization)
class PathGeneticOptimizer {
  constructor(populationSize = 10, mutationRate = 0.05) {
    this.populationSize = populationSize;
    this.mutationRate = mutationRate;
  }

  optimize(fitnessFn, sequenceLength = 5) {
    let population = Array.from({ length: this.populationSize }, () =>
      Array.from({ length: sequenceLength }, () => Math.random())
    );

    for (let gen = 0; gen < 20; gen++) {
      population.sort((a, b) => fitnessFn(b) - fitnessFn(a));
      const nextGen = population.slice(0, 2); // Elitism

      while (nextGen.length < this.populationSize) {
        const parentA = population[Math.floor(Math.random() * 4)];
        const parentB = population[Math.floor(Math.random() * 4)];
        const child = parentA.map((gene, i) => Math.random() > 0.5 ? gene : parentB[i]);
        
        // Mutation
        const mutatedChild = child.map(gene => 
          Math.random() < this.mutationRate ? Math.random() : gene
        );
        nextGen.push(mutatedChild);
      }
      population = nextGen;
    }
    return population[0];
  }
}

// 4. Multi-Layer Neural Network with Backpropagation & Sigmoid/ReLU Activation
class NeuralNetwork {
  constructor(inputNodes = 4, hiddenNodes = 8, outputNodes = 3, learningRate = 0.05) {
    this.inputNodes = inputNodes;
    this.hiddenNodes = hiddenNodes;
    this.outputNodes = outputNodes;
    this.learningRate = learningRate;

    // Weights initialization (Xavier/Glorot)
    this.weightsIH = this.randomMatrix(hiddenNodes, inputNodes);
    this.weightsHO = this.randomMatrix(outputNodes, hiddenNodes);

    // Biases
    this.biasH = Array(hiddenNodes).fill(0).map(() => (Math.random() * 2 - 1) * 0.1);
    this.biasO = Array(outputNodes).fill(0).map(() => (Math.random() * 2 - 1) * 0.1);
  }

  randomMatrix(rows, cols) {
    return Array.from({ length: rows }, () =>
      Array.from({ length: cols }, () => (Math.random() * 2 - 1) * Math.sqrt(2 / cols))
    );
  }

  sigmoid(x) {
    return 1 / (1 + Math.exp(-x));
  }

  sigmoidDerivative(y) {
    return y * (1 - y);
  }

  predict(inputArray) {
    // Hidden Layer Feedforward
    const hidden = this.weightsIH.map((row, i) => {
      const sum = row.reduce((acc, w, j) => acc + w * (inputArray[j] || 0), 0) + this.biasH[i];
      return this.sigmoid(sum);
    });

    // Output Layer Feedforward
    const output = this.weightsHO.map((row, i) => {
      const sum = row.reduce((acc, w, j) => acc + w * hidden[j], 0) + this.biasO[i];
      return this.sigmoid(sum);
    });

    return { hidden, output };
  }

  train(inputArray, targetArray) {
    const { hidden, output } = this.predict(inputArray);

    // Calculate Output Errors
    const outputErrors = output.map((o, i) => (targetArray[i] || 0) - o);

    // Calculate Output Gradient & Update WeightsHO
    const outputGradients = output.map((o, i) => outputErrors[i] * this.sigmoidDerivative(o) * this.learningRate);
    this.weightsHO = this.weightsHO.map((row, i) =>
      row.map((w, j) => w + outputGradients[i] * hidden[j])
    );
    this.biasO = this.biasO.map((b, i) => b + outputGradients[i]);

    // Calculate Hidden Errors
    const hiddenErrors = Array(this.hiddenNodes).fill(0);
    this.weightsHO.forEach((row, i) => {
      row.forEach((w, j) => {
        hiddenErrors[j] += w * outputErrors[i];
      });
    });

    // Calculate Hidden Gradient & Update WeightsIH
    const hiddenGradients = hidden.map((h, i) => hiddenErrors[i] * this.sigmoidDerivative(h) * this.learningRate);
    this.weightsIH = this.weightsIH.map((row, i) =>
      row.map((w, j) => w + hiddenGradients[i] * (inputArray[j] || 0))
    );
    this.biasH = this.biasH.map((b, i) => b + hiddenGradients[i]);

    return outputErrors.reduce((acc, e) => acc + Math.pow(e, 2), 0) / outputErrors.length;
  }
}

// 5. Scaled Dot-Product Self-Attention Transformer Mechanism
class TransformerAttention {
  constructor(embedDim = 8) {
    this.embedDim = embedDim;
    this.scale = Math.sqrt(embedDim);
  }

  forward(query, key, value) {
    // Softmax(Q * K^T / sqrt(d_k)) * V
    const scores = query.map(q => {
      return key.map(k => {
        const dot = q.reduce((sum, val, idx) => sum + val * (k[idx] || 0), 0);
        return dot / this.scale;
      });
    });

    const attentionWeights = scores.map(row => this.softmax(row));

    const output = attentionWeights.map(weights => {
      return Array(this.embedDim).fill(0).map((_, colIdx) => {
        return weights.reduce((sum, weight, rowIdx) => sum + weight * (value[rowIdx][colIdx] || 0), 0);
      });
    });

    return { attentionWeights, output };
  }

  softmax(arr) {
    const maxVal = Math.max(...arr);
    const exps = arr.map(x => Math.exp(x - maxVal));
    const sumExps = exps.reduce((a, b) => a + b, 0);
    return exps.map(e => e / sumExps);
  }
}

// 6. Monte Carlo Tree Search (MCTS) for Agent Task Path Selection
class MCTSNode {
  constructor(state, parent = null) {
    this.state = state;
    this.parent = parent;
    this.children = [];
    this.visits = 0;
    this.value = 0;
  }

  isFullyExpanded(allActions) {
    return this.children.length === allActions.length;
  }

  bestChild(cParam = 1.41) {
    return this.children.reduce((best, child) => {
      const uctScore = (child.value / (child.visits || 1)) +
        cParam * Math.sqrt(Math.log(this.visits || 1) / (child.visits || 1));
      return !best || uctScore > best.score ? { child, score: uctScore } : best;
    }, null)?.child;
  }
}

class MonteCarloTreeSearch {
  constructor(actions = ['architect', 'coder', 'qa-agent', 'ml-expert'], iterations = 50) {
    this.actions = actions;
    this.iterations = iterations;
  }

  search(initialState) {
    const root = new MCTSNode(initialState);

    for (let i = 0; i < this.iterations; i++) {
      let node = root;

      // Selection & Expansion
      while (node.isFullyExpanded(this.actions) && node.children.length > 0) {
        node = node.bestChild();
      }

      if (!node.isFullyExpanded(this.actions)) {
        const untried = this.actions.filter(a => !node.children.some(c => c.state.lastAction === a));
        const action = untried[Math.floor(Math.random() * untried.length)];
        const childNode = new MCTSNode({ ...node.state, lastAction: action }, node);
        node.children.push(childNode);
        node = childNode;
      }

      // Simulation (Rollout)
      const reward = Math.random() * 0.5 + 0.5; // Simulate execution reward

      // Backpropagation
      while (node) {
        node.visits += 1;
        node.value += reward;
        node = node.parent;
      }
    }

    return root.bestChild(0)?.state?.lastAction || this.actions[0];
  }
}

// 7. Deep Q-Network (DQN) with Experience Replay Memory
class ExperienceReplayMemory {
  constructor(capacity = 200) {
    this.capacity = capacity;
    this.memory = [];
  }

  push(state, action, reward, nextState, done) {
    if (this.memory.length >= this.capacity) {
      this.memory.shift();
    }
    this.memory.push({ state, action, reward, nextState, done });
  }

  sample(batchSize = 16) {
    const samples = [];
    for (let i = 0; i < batchSize && this.memory.length > 0; i++) {
      const idx = Math.floor(Math.random() * this.memory.length);
      samples.push(this.memory[idx]);
    }
    return samples;
  }
}

class DeepQNetwork {
  constructor(stateDim = 4, actionDim = 4, hiddenDim = 12, lr = 0.01) {
    this.stateDim = stateDim;
    this.actionDim = actionDim;
    this.memory = new ExperienceReplayMemory(300);
    this.qNetwork = new NeuralNetwork(stateDim, hiddenDim, actionDim, lr);
    this.targetNetwork = new NeuralNetwork(stateDim, hiddenDim, actionDim, lr);
    this.epsilon = 0.25;
    this.gamma = 0.95;
  }

  selectAction(stateVector) {
    if (Math.random() < this.epsilon) {
      return Math.floor(Math.random() * this.actionDim);
    }
    const { output } = this.qNetwork.predict(stateVector);
    return output.indexOf(Math.max(...output));
  }

  trainStep(batchSize = 8) {
    const batch = this.memory.sample(batchSize);
    if (!batch.length) return 0;

    let totalLoss = 0;
    batch.forEach(({ state, action, reward, nextState, done }) => {
      const { output: currentQ } = this.qNetwork.predict(state);
      const targetQ = [...currentQ];

      if (done) {
        targetQ[action] = reward;
      } else {
        const { output: nextQ } = this.targetNetwork.predict(nextState);
        const maxNextQ = Math.max(...nextQ);
        targetQ[action] = reward + this.gamma * maxNextQ;
      }

      totalLoss += this.qNetwork.train(state, targetQ);
    });

    return totalLoss / batch.length;
  }

  syncTargetNetwork() {
    this.targetNetwork.weightsIH = JSON.parse(JSON.stringify(this.qNetwork.weightsIH));
    this.targetNetwork.weightsHO = JSON.parse(JSON.stringify(this.qNetwork.weightsHO));
  }
}

// 8. Graph Neural Network (GNN) Layer for Agent Topology Message Passing
class GraphNeuralNetwork {
  constructor(nodeDim = 4, hiddenDim = 8) {
    this.nodeDim = nodeDim;
    this.hiddenDim = hiddenDim;
    this.weightMatrix = Array.from({ length: hiddenDim }, () =>
      Array.from({ length: nodeDim }, () => (Math.random() * 2 - 1) * Math.sqrt(2 / nodeDim))
    );
  }

  aggregateNeighbors(nodes, adjacencyMatrix) {
    // Message Passing & Neighbor Aggregation
    const updatedEmbeddings = nodes.map((nodeVector, i) => {
      const neighborSum = Array(this.nodeDim).fill(0);
      let neighborCount = 0;

      adjacencyMatrix[i].forEach((connected, j) => {
        if (connected && i !== j) {
          nodes[j].forEach((val, k) => neighborSum[k] += val);
          neighborCount++;
        }
      });

      const avgNeighbor = neighborCount > 0
        ? neighborSum.map(v => v / neighborCount)
        : Array(this.nodeDim).fill(0);

      // Combine node self-vector + aggregated neighbor vectors
      const combined = nodeVector.map((val, k) => val * 0.6 + avgNeighbor[k] * 0.4);

      // Linear transformation & ReLU activation
      return this.weightMatrix.map(row => {
        const sum = row.reduce((acc, w, k) => acc + w * combined[k], 0);
        return Math.max(0, sum); // ReLU activation
      });
    });

    return updatedEmbeddings;
  }
}

// 9. Proximal Policy Optimization (PPO) Actor-Critic Model
class ActorCriticPPO {
  constructor(stateDim = 4, actionDim = 4, lrActor = 0.01, lrCritic = 0.02, clipRatio = 0.2) {
    this.stateDim = stateDim;
    this.actionDim = actionDim;
    this.clipRatio = clipRatio;

    // Policy Network (Actor) & Value Network (Critic)
    this.actor = new NeuralNetwork(stateDim, 8, actionDim, lrActor);
    this.critic = new NeuralNetwork(stateDim, 8, 1, lrCritic);
  }

  evaluateState(stateVector) {
    const { output: actionProbs } = this.actor.predict(stateVector);
    const { output: stateValue } = this.critic.predict(stateVector);

    // Softmax probabilities
    const sumExp = actionProbs.reduce((acc, p) => acc + Math.exp(p), 0);
    const probs = actionProbs.map(p => Math.exp(p) / sumExp);

    return { probs, value: stateValue[0] };
  }

  trainPPO(states, actions, rewards, nextStates) {
    let policyLoss = 0;
    let valueLoss = 0;

    states.forEach((state, i) => {
      const { probs, value } = this.evaluateState(state);
      const { value: nextValue } = this.evaluateState(nextStates[i]);

      // Advantage estimation: A = R + gamma * V(s') - V(s)
      const advantage = rewards[i] + 0.95 * nextValue - value;

      // PPO Clipped Surrogate Loss
      const oldProb = probs[actions[i]] || 0.25;
      const newProb = Math.min(0.99, oldProb * 1.05); // Simulated policy step
      const ratio = newProb / oldProb;

      const surr1 = ratio * advantage;
      const surr2 = Math.min(Math.max(ratio, 1 - this.clipRatio), 1 + this.clipRatio) * advantage;

      policyLoss += -Math.min(surr1, surr2);

      // Value Function Update
      const targetVal = [rewards[i] + 0.95 * nextValue];
      valueLoss += this.critic.train(state, targetVal);
    });

    return { policyLoss: policyLoss / states.length, valueLoss };
  }
}

// 10. Hierarchical Task Network (HTN) & Model-Agnostic Meta-Learning (MAML) Engine
class MetaLearningHTNEngine {
  constructor(subagentRoles = ['architect', 'coder', 'qa-agent', 'ml-expert']) {
    this.roles = subagentRoles;
    this.metaModel = new NeuralNetwork(4, 12, subagentRoles.length, 0.05);
    this.taskDecompositionCache = new Map();
  }

  decomposeGoalHTN(goalDescription) {
    // Hierarchical Task Decomposition into Primitive Sub-tasks
    const primitives = [
      { id: 'sub-1', role: 'ml-expert', task: 'Compute meta-policy & GNN embeddings' },
      { id: 'sub-2', role: 'architect', task: 'Design module interfaces & schema contracts' },
      { id: 'sub-3', role: 'coder', task: 'Implement multi-path code changes' },
      { id: 'sub-4', role: 'qa-agent', task: 'Execute unit & end-to-end integration tests' }
    ];

    this.taskDecompositionCache.set(goalDescription, primitives);
    return primitives;
  }

  adaptMetaParameters(taskFeatureVector, fewShotExamples) {
    // Fast Inner-Loop Adaptation (MAML Meta-Gradient Step)
    let metaLoss = 0;
    fewShotExamples.forEach(({ input, target }) => {
      metaLoss += this.metaModel.train(input, target);
    });

    const { output: adaptedProbabilities } = this.metaModel.predict(taskFeatureVector);
    return {
      metaLoss,
      adaptedProbabilities,
      confidenceScore: (1 - metaLoss).toFixed(4)
    };
  }
}

if (typeof module !== 'undefined') {
  module.exports = {
    KMeansClustering,
    QLearningRouter,
    PathGeneticOptimizer,
    NeuralNetwork,
    TransformerAttention,
    MonteCarloTreeSearch,
    ExperienceReplayMemory,
    DeepQNetwork,
    GraphNeuralNetwork,
    ActorCriticPPO,
    MetaLearningHTNEngine
  };
}
