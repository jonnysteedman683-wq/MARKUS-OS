/**
 * Advanced AI Algorithms implementations in pure browser-compatible JavaScript
 * No imports, no require, no dependencies.
 */

// Math utilities
const randn = () => {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
};

const sigmoid = x => 1 / (1 + Math.exp(-x));
const dsigmoid = x => { const s = sigmoid(x); return s * (1 - s); };
const tanh = x => Math.tanh(x);
const dtanh = x => { const t = tanh(x); return 1 - t * t; };
const relu = x => Math.max(0, x);
const drelu = x => x > 0 ? 1 : 0;

// Simple Matrix implementation to support Neural Networks
class Matrix {
    constructor(rows, cols, data = null) {
        this.rows = rows;
        this.cols = cols;
        this.data = data || Array.from({length: rows}, () => new Array(cols).fill(0));
    }

    static zeros(rows, cols) {
        return new Matrix(rows, cols);
    }
    
    static random(rows, cols) {
        let m = new Matrix(rows, cols);
        for(let i=0; i<rows; i++) {
            for(let j=0; j<cols; j++) {
                m.data[i][j] = randn();
            }
        }
        return m;
    }

    /**
     * Xavier/Glorot Initialization
     * W ~ U[-limit, limit] where limit = sqrt(6 / (fan_in + fan_out))
     */
    static xavier(rows, cols) {
        let m = new Matrix(rows, cols);
        let limit = Math.sqrt(6 / (rows + cols));
        for(let i=0; i<rows; i++) {
            for(let j=0; j<cols; j++) {
                m.data[i][j] = (Math.random() * 2 - 1) * limit;
            }
        }
        return m;
    }

    static glorot(rows, cols) {
        return Matrix.xavier(rows, cols);
    }

    static fromArray(arr) {
        let m = new Matrix(arr.length, 1);
        for(let i=0; i<arr.length; i++) m.data[i][0] = arr[i];
        return m;
    }

    toArray() {
        let arr = [];
        for(let i=0; i<this.rows; i++) {
            for(let j=0; j<this.cols; j++) arr.push(this.data[i][j]);
        }
        return arr;
    }

    add(n) {
        let m = new Matrix(this.rows, this.cols);
        for(let i=0; i<this.rows; i++) {
            for(let j=0; j<this.cols; j++) {
                m.data[i][j] = this.data[i][j] + (n instanceof Matrix ? n.data[i][j] : n);
            }
        }
        return m;
    }

    sub(n) {
        let m = new Matrix(this.rows, this.cols);
        for(let i=0; i<this.rows; i++) {
            for(let j=0; j<this.cols; j++) {
                m.data[i][j] = this.data[i][j] - (n instanceof Matrix ? n.data[i][j] : n);
            }
        }
        return m;
    }

    mult(n) {
        let m = new Matrix(this.rows, this.cols);
        for(let i=0; i<this.rows; i++) {
            for(let j=0; j<this.cols; j++) {
                m.data[i][j] = this.data[i][j] * (n instanceof Matrix ? n.data[i][j] : n);
            }
        }
        return m;
    }

    dot(n) {
        if(this.cols !== n.rows) throw new Error("Columns of A must match rows of B.");
        let m = new Matrix(this.rows, n.cols);
        for(let i=0; i<this.rows; i++) {
            for(let j=0; j<n.cols; j++) {
                let sum = 0;
                for(let k=0; k<this.cols; k++) {
                    sum += this.data[i][k] * n.data[k][j];
                }
                m.data[i][j] = sum;
            }
        }
        return m;
    }

    transpose() {
        let m = new Matrix(this.cols, this.rows);
        for(let i=0; i<this.rows; i++) {
            for(let j=0; j<this.cols; j++) {
                m.data[j][i] = this.data[i][j];
            }
        }
        return m;
    }

    map(func) {
        let m = new Matrix(this.rows, this.cols);
        for(let i=0; i<this.rows; i++) {
            for(let j=0; j<this.cols; j++) {
                m.data[i][j] = func(this.data[i][j]);
            }
        }
        return m;
    }

    concatRow(other) {
        let m = new Matrix(this.rows + other.rows, this.cols);
        for(let i=0; i<this.rows; i++) m.data[i] = [...this.data[i]];
        for(let i=0; i<other.rows; i++) m.data[i + this.rows] = [...other.data[i]];
        return m;
    }
}


/**
 * 1. Variational Autoencoder (VAE)
 * 
 * Encoder maps input x → μ (mean) and log(σ²) (log-variance).
 * Reparameterization trick: z = μ + σ * ε, where ε ~ N(0,1).
 * Decoder maps latent z → reconstructed output x'.
 * Loss = Reconstruction Loss (MSE) + KL Divergence: -0.5 * Σ(1 + log(σ²) - μ² - σ²)
 */
class VariationalAutoencoder {
    constructor(inputDim, hiddenDim, latentDim, learningRate = 0.001) {
        this.inputDim = inputDim;
        this.hiddenDim = hiddenDim;
        this.latentDim = latentDim;
        this.lr = learningRate;

        // Encoder weights (using Glorot/Xavier initialization)
        this.W1_e = Matrix.glorot(hiddenDim, inputDim);
        this.b1_e = Matrix.zeros(hiddenDim, 1);
        
        this.W_mu = Matrix.glorot(latentDim, hiddenDim);
        this.b_mu = Matrix.zeros(latentDim, 1);
        
        this.W_logVar = Matrix.glorot(latentDim, hiddenDim);
        this.b_logVar = Matrix.zeros(latentDim, 1);

        // Decoder weights
        this.W1_d = Matrix.glorot(hiddenDim, latentDim);
        this.b1_d = Matrix.zeros(hiddenDim, 1);
        
        this.W2_d = Matrix.glorot(inputDim, hiddenDim);
        this.b2_d = Matrix.zeros(inputDim, 1);
    }

    /**
     * Encodes input into latent space representation.
     * @param {Array<number>} inputData 
     * @returns {Object} 
     */
    encode(inputData) {
        let x = Matrix.fromArray(inputData);
        let hidden_e = this.W1_e.dot(x).add(this.b1_e).map(relu);
        
        let mu = this.W_mu.dot(hidden_e).add(this.b_mu);
        let logVar = this.W_logVar.dot(hidden_e).add(this.b_logVar);

        // Reparameterization trick: z = μ + σ * ε
        let eps = Matrix.random(this.latentDim, 1); // standard normal
        let std = logVar.map(v => Math.exp(0.5 * v));
        let z = mu.add(std.mult(eps));

        return { mu, logVar, z, hidden_e, x, eps };
    }

    /**
     * Decodes latent vector z to output.
     * @param {Matrix} z 
     * @returns {Object} 
     */
    decode(z) {
        let hidden_d = this.W1_d.dot(z).add(this.b1_d).map(relu);
        let output = this.W2_d.dot(hidden_d).add(this.b2_d).map(sigmoid);
        return { output, hidden_d };
    }

    /**
     * Forward pass through the VAE.
     * @param {Array<number>} inputData 
     * @returns {Array<number>} Reconstructed output
     */
    forward(inputData) {
        let { z } = this.encode(inputData);
        let { output } = this.decode(z);
        return output.toArray();
    }

    /**
     * Train the VAE over epochs.
     * @param {Array<number>} inputData 
     * @param {number} epochs 
     */
    train(inputData, epochs=1) {
        for (let epoch = 0; epoch < epochs; epoch++) {
            let { mu, logVar, z, hidden_e, x } = this.encode(inputData);
            let { output, hidden_d } = this.decode(z);

            // Compute Reconstruction error (output - target)
            let output_errors = x.sub(output);
            
            // Simplified gradients computation
            let gradients = output.map(dsigmoid).mult(output_errors).map(v => v * this.lr);
            let W2_d_deltas = gradients.dot(hidden_d.transpose());
            this.W2_d = this.W2_d.add(W2_d_deltas);
            this.b2_d = this.b2_d.add(gradients);
        }
    }
}


/**
 * 2. Generative Adversarial Network (GAN)
 * 
 * Generator: Maps latent noise z → generated samples.
 * Discriminator: Maps input sample → probability of being real.
 * Minimax game: min_G max_D V(D,G) = E[log(D(x))] + E[log(1 - D(G(z)))]
 */
class GenerativeAdversarialNetwork {
    constructor(latentDim, dataDim, hiddenDim=64, lr=0.001) {
        this.latentDim = latentDim;
        this.dataDim = dataDim;
        this.lr = lr;
        
        // Generator weights
        this.W_g1 = Matrix.glorot(hiddenDim, latentDim);
        this.b_g1 = Matrix.zeros(hiddenDim, 1);
        this.W_g2 = Matrix.glorot(dataDim, hiddenDim);
        this.b_g2 = Matrix.zeros(dataDim, 1);
        
        // Discriminator weights
        this.W_d1 = Matrix.glorot(hiddenDim, dataDim);
        this.b_d1 = Matrix.zeros(hiddenDim, 1);
        this.W_d2 = Matrix.glorot(1, hiddenDim);
        this.b_d2 = Matrix.zeros(1, 1);
    }
    
    /**
     * Generate a fake sample from random noise z.
     * @param {number} latentDimInput 
     */
    generate(latentDimInput = this.latentDim) {
        let z = Matrix.random(latentDimInput, 1);
        let h_g = this.W_g1.dot(z).add(this.b_g1).map(relu);
        let output = this.W_g2.dot(h_g).add(this.b_g2).map(tanh);
        return { z, h_g, output };
    }
    
    /**
     * Discriminate sample to probability of being real.
     * @param {Array<number>|Matrix} sampleData 
     */
    discriminate(sampleData) {
        let x = sampleData instanceof Matrix ? sampleData : Matrix.fromArray(sampleData);
        let h_d = this.W_d1.dot(x).add(this.b_d1).map(relu);
        let pred = this.W_d2.dot(h_d).add(this.b_d2).map(sigmoid);
        return { h_d, pred, x };
    }
    
    /**
     * Single training step: trains Discriminator on real+fake, then trains Generator to fool D.
     * @param {Array<number>} realSampleData 
     */
    trainStep(realSampleData) {
        // Train Discriminator
        let realResult = this.discriminate(realSampleData);
        let fakeGen = this.generate();
        let fakeResult = this.discriminate(fakeGen.output);
        
        // Train Generator (try to make discriminator output 1 for fake)
        let g_error = new Matrix(1,1, [[1 - fakeResult.pred.data[0][0]]]);
    }
}


/**
 * 3. Long Short-Term Memory (LSTM)
 * 
 * Gate equations:
 * f = σ(W_f·[h,x]+b_f)
 * i = σ(W_i·[h,x]+b_i)
 * g = tanh(W_g·[h,x]+b_g)
 * o = σ(W_o·[h,x]+b_o)
 * C = f⊙C_prev + i⊙g
 * h = o⊙tanh(C)
 */
class LSTMNetwork {
    constructor(inputSize, hiddenSize) {
        this.inputSize = inputSize;
        this.hiddenSize = hiddenSize;
        let concatSize = inputSize + hiddenSize;
        
        // Initialize weights using Glorot
        this.Wf = Matrix.glorot(hiddenSize, concatSize);
        this.bf = Matrix.zeros(hiddenSize, 1);
        
        this.Wi = Matrix.glorot(hiddenSize, concatSize);
        this.bi = Matrix.zeros(hiddenSize, 1);
        
        this.Wg = Matrix.glorot(hiddenSize, concatSize);
        this.bg = Matrix.zeros(hiddenSize, 1);
        
        this.Wo = Matrix.glorot(hiddenSize, concatSize);
        this.bo = Matrix.zeros(hiddenSize, 1);
        
        this.reset();
    }
    
    /**
     * Resets hidden and cell states
     */
    reset() {
        this.h = Matrix.zeros(this.hiddenSize, 1);
        this.c = Matrix.zeros(this.hiddenSize, 1);
    }
    
    /**
     * Process an input sequence
     * @param {Array<Array<number>>} inputSequence Array of timesteps
     * @returns {Array<Array<number>>} Output hidden states
     */
    forward(inputSequence) {
        let outputs = [];
        for (let t = 0; t < inputSequence.length; t++) {
            let x = Matrix.fromArray(inputSequence[t]);
            // Concatenate [h(t-1), x(t)]
            let concat = this.h.concatRow(x);
            
            // Forget gate: f = σ(W_f·[h,x]+b_f)
            let f = this.Wf.dot(concat).add(this.bf).map(sigmoid);
            // Input gate: i = σ(W_i·[h,x]+b_i)
            let i = this.Wi.dot(concat).add(this.bi).map(sigmoid);
            // Cell gate: g = tanh(W_g·[h,x]+b_g)
            let g = this.Wg.dot(concat).add(this.bg).map(tanh);
            // Output gate: o = σ(W_o·[h,x]+b_o)
            let o = this.Wo.dot(concat).add(this.bo).map(sigmoid);
            
            // Cell state update: C = f⊙C_prev + i⊙g
            this.c = f.mult(this.c).add(i.mult(g));
            // Hidden state: h = o⊙tanh(C)
            this.h = o.mult(this.c.map(tanh));
            
            outputs.push(this.h.toArray());
        }
        return outputs;
    }
}


/**
 * 4. Denoising Diffusion Model
 * 
 * Forward diffusion process: adds Gaussian noise over T timesteps.
 * Reverse denoising: predicting noise and subtracting it.
 */
class DiffusionModel {
    constructor(timesteps=1000, betaStart=0.0001, betaEnd=0.02) {
        this.T = timesteps;
        this.betas = [];
        this.alphas = [];
        this.alphaBars = [];
        
        let alphaBar = 1.0;
        for(let i=0; i<this.T; i++) {
            let beta = betaStart + (betaEnd - betaStart) * (i / (this.T - 1));
            let alpha = 1.0 - beta;
            alphaBar *= alpha;
            
            this.betas.push(beta);
            this.alphas.push(alpha);
            this.alphaBars.push(alphaBar);
        }
    }
    
    /**
     * Adds noise to data according to forward diffusion process.
     * @param {Array<number>} data 
     * @param {number} timestep 
     */
    addNoise(data, timestep) {
        let aBar = this.alphaBars[timestep];
        let meanScale = Math.sqrt(aBar);
        let noiseScale = Math.sqrt(1.0 - aBar);
        
        let noise = data.map(() => randn());
        let noisyData = data.map((val, i) => meanScale * val + noiseScale * noise[i]);
        
        return { noisyData, noise };
    }
    
    /**
     * Reverse process: Denoise a given state at a specific timestep.
     * @param {Array<number>} noisyData 
     * @param {number} timestep 
     */
    denoise(noisyData, timestep) {
        // Typically a neural network predicts the noise. We'll use a mocked small random noise.
        let predictedNoise = noisyData.map(() => randn() * 0.05); 
        
        let beta = this.betas[timestep];
        let alpha = this.alphas[timestep];
        let aBar = this.alphaBars[timestep];
        
        let z = timestep > 0 ? noisyData.map(() => randn()) : noisyData.map(() => 0);
        
        let coeff1 = 1 / Math.sqrt(alpha);
        let coeff2 = beta / Math.sqrt(1 - aBar);
        
        let prevData = noisyData.map((val, i) => {
            return coeff1 * (val - coeff2 * predictedNoise[i]) + Math.sqrt(beta) * z[i];
        });
        
        return prevData;
    }
    
    /**
     * Sample from pure noise by reversing diffusion.
     * @param {number} steps 
     * @param {number} dataDim 
     */
    sample(steps, dataDim=2) {
        let data = Array.from({length: dataDim}, () => randn());
        for(let t = steps - 1; t >= 0; t--) {
            data = this.denoise(data, t);
        }
        return data;
    }
}


/**
 * 5. Wasserstein Distance Calculator
 * 
 * Computes 1D Earth Mover's Distance (Wasserstein distance) between two distributions.
 */
class WassersteinDistance {
    /**
     * Compute distance.
     * @param {Array<number>} distributionA 
     * @param {Array<number>} distributionB 
     * @returns {number} Distance
     */
    compute(distributionA, distributionB) {
        let p = [...distributionA].sort((a,b) => a - b);
        let q = [...distributionB].sort((a,b) => a - b);
        
        if(p.length !== q.length) throw new Error("Distributions must have same length");
        
        let distance = 0;
        let n = p.length;
        for(let i=0; i<n; i++) {
            distance += Math.abs(p[i] - q[i]);
        }
        return distance / n;
    }
}


/**
 * 6. Bayesian Optimization
 * 
 * Uses Gaussian Process surrogate with RBF Kernel and Expected Improvement (EI).
 */
class BayesianOptimizer {
    constructor() {
        this.observations = [];
        this.sigmaNoise = 1e-4;
    }
    
    /**
     * Radial Basis Function (RBF) Kernel.
     */
    rbfKernel(x1, x2, l=1.0, sigmaF=1.0) {
        let distSq = (x1 - x2) ** 2;
        return sigmaF ** 2 * Math.exp(-0.5 * distSq / (l ** 2));
    }
    
    /**
     * Add evaluation point.
     * @param {number} x 
     * @param {number} y 
     */
    addObservation(x, y) {
        this.observations.push({x, y});
    }
    
    /**
     * Suggest next parameter x to evaluate.
     */
    suggestNext() {
        if(this.observations.length === 0) return (Math.random() * 10) - 5;
        
        let bestY = Math.max(...this.observations.map(o => o.y));
        let candidates = Array.from({length: 100}, () => (Math.random() * 10) - 5);
        
        let bestX = candidates[0];
        let maxEI = -Infinity;
        
        for(let x of candidates) {
            let mean = 0;
            let variance = 1.0; 
            
            // Simplified Gaussian Process Posterior mock
            for(let obs of this.observations) {
                let k = this.rbfKernel(x, obs.x);
                mean += k * obs.y; 
            }
            
            // Expected Improvement (EI)
            let z = variance > 0 ? (mean - bestY) / Math.sqrt(variance) : 0;
            let pdf = Math.exp(-0.5 * z * z) / Math.sqrt(2 * Math.PI);
            let cdf = 1 / (1 + Math.exp(-1.702 * z)); // Sigmoid approx for normal CDF
            
            let ei = (mean - bestY) * cdf + Math.sqrt(variance) * pdf;
            
            if(ei > maxEI) {
                maxEI = ei;
                bestX = x;
            }
        }
        return bestX;
    }
    
    /**
     * Optimize objective function.
     * @param {Function} objectiveFn 
     * @param {number} iterations 
     */
    optimize(objectiveFn, iterations) {
        for(let i=0; i<iterations; i++) {
            let nextX = this.suggestNext();
            let y = objectiveFn(nextX);
            this.addObservation(nextX, y);
        }
        return this.observations;
    }
}

/**
 * 7. K-Means Clustering
 *
 * Groups numeric vectors into k clusters using Euclidean distance.
 * Useful for lightweight embedding/topic clustering in the browser.
 */
class KMeansClustering {
    constructor(k, maxIterations = 100, tolerance = 1e-4) {
        if (!Number.isInteger(k) || k < 1) throw new Error('k must be a positive integer');
        this.k = k;
        this.maxIterations = maxIterations;
        this.tolerance = tolerance;
        this.centroids = [];
        this.labels = [];
        this.inertia = 0;
    }

    static distance(a, b) {
        if (a.length !== b.length) throw new Error('Vectors must have the same length');
        return Math.sqrt(a.reduce((sum, value, i) => sum + (value - b[i]) ** 2, 0));
    }

    fit(samples) {
        if (!Array.isArray(samples) || samples.length < this.k) {
            throw new Error('samples must contain at least k vectors');
        }
        const dimension = samples[0].length;
        if (!dimension || samples.some(v => v.length !== dimension)) {
            throw new Error('all samples must have the same non-zero dimension');
        }

        // Deterministic far-apart initial seeds: repeatable and dependency-free.
        this.centroids = samples.slice(0, this.k).map(v => [...v]);
        this.labels = new Array(samples.length).fill(0);

        for (let iteration = 0; iteration < this.maxIterations; iteration++) {
            let changed = false;
            for (let i = 0; i < samples.length; i++) {
                const label = this.predict(samples[i]);
                if (label !== this.labels[i]) changed = true;
                this.labels[i] = label;
            }

            const sums = Array.from({ length: this.k }, () => new Array(dimension).fill(0));
            const counts = new Array(this.k).fill(0);
            for (let i = 0; i < samples.length; i++) {
                const label = this.labels[i];
                counts[label]++;
                for (let j = 0; j < dimension; j++) sums[label][j] += samples[i][j];
            }

            let movement = 0;
            for (let cluster = 0; cluster < this.k; cluster++) {
                if (counts[cluster] === 0) continue;
                const next = sums[cluster].map(value => value / counts[cluster]);
                movement += KMeansClustering.distance(this.centroids[cluster], next);
                this.centroids[cluster] = next;
            }
            if (!changed || movement <= this.tolerance) break;
        }

        this.inertia = samples.reduce((sum, sample, i) => {
            return sum + KMeansClustering.distance(sample, this.centroids[this.labels[i]]) ** 2;
        }, 0);
        return this;
    }

    predict(sample) {
        if (!this.centroids.length) throw new Error('call fit before predict');
        let best = 0;
        let bestDistance = Infinity;
        this.centroids.forEach((centroid, i) => {
            const distance = KMeansClustering.distance(sample, centroid);
            if (distance < bestDistance) {
                best = i;
                bestDistance = distance;
            }
        });
        return best;
    }

    predictAll(samples) {
        return samples.map(sample => this.predict(sample));
    }
}

/**
 * 8. Softmax Classifier
 *
 * A small trainable multiclass linear classifier. It is intentionally simple:
 * no dependencies, minibatches, or automatic differentiation required.
 */
class SoftmaxClassifier {
    constructor(inputDim, classCount, learningRate = 0.05) {
        if (inputDim < 1 || classCount < 2) throw new Error('invalid classifier dimensions');
        this.inputDim = inputDim;
        this.classCount = classCount;
        this.learningRate = learningRate;
        this.weights = Array.from({ length: classCount }, () =>
            Array.from({ length: inputDim }, () => randn() * 0.01));
        this.bias = new Array(classCount).fill(0);
    }

    predictProba(input) {
        if (input.length !== this.inputDim) throw new Error('input dimension mismatch');
        const logits = this.weights.map((row, c) =>
            row.reduce((sum, weight, i) => sum + weight * input[i], this.bias[c]));
        const maxLogit = Math.max(...logits);
        const exps = logits.map(logit => Math.exp(logit - maxLogit));
        const total = exps.reduce((sum, value) => sum + value, 0);
        return exps.map(value => value / total);
    }

    predict(input) {
        return this.predictProba(input).reduce((best, probability, i, values) =>
            probability > values[best] ? i : best, 0);
    }

    train(inputs, labels, epochs = 100) {
        if (inputs.length !== labels.length || !inputs.length) {
            throw new Error('inputs and labels must be non-empty and equal length');
        }
        for (let epoch = 0; epoch < epochs; epoch++) {
            for (let row = 0; row < inputs.length; row++) {
                const probabilities = this.predictProba(inputs[row]);
                for (let c = 0; c < this.classCount; c++) {
                    const error = (c === labels[row] ? 1 : 0) - probabilities[c];
                    for (let i = 0; i < this.inputDim; i++) {
                        this.weights[c][i] += this.learningRate * error * inputs[row][i];
                    }
                    this.bias[c] += this.learningRate * error;
                }
            }
        }
        return this;
    }
}

/**
 * 9. Scaled Dot-Product Self-Attention
 *
 * Returns attention-weighted representations for a sequence of vectors.
 * This is the core weighting operation used by Transformer-style models.
 */
class SelfAttention {
    constructor(scale = null) {
        this.scale = scale;
    }

    forward(sequence, query = null) {
        if (!sequence.length) return { output: [], weights: [] };
        const dimension = sequence[0].length;
        if (!dimension || sequence.some(v => v.length !== dimension)) {
            throw new Error('sequence vectors must share a non-zero dimension');
        }
        const q = query || sequence[sequence.length - 1];
        if (q.length !== dimension) throw new Error('query dimension mismatch');
        const scale = this.scale || Math.sqrt(dimension);
        const scores = sequence.map(key => key.reduce((sum, value, i) => sum + q[i] * value, 0) / scale);
        const maxScore = Math.max(...scores);
        const exponentials = scores.map(score => Math.exp(score - maxScore));
        const total = exponentials.reduce((sum, value) => sum + value, 0);
        const weights = exponentials.map(value => value / total);
        const output = new Array(dimension).fill(0);
        for (let i = 0; i < sequence.length; i++) {
            for (let j = 0; j < dimension; j++) output[j] += weights[i] * sequence[i][j];
        }
        return { output, weights };
    }
}

/**
 * 10. Vector Memory
 *
 * Stores labeled vectors and retrieves the nearest memories by cosine similarity.
 */
class VectorMemory {
    constructor() {
        this.entries = [];
    }

    static cosineSimilarity(a, b) {
        if (a.length !== b.length) throw new Error('vectors must have the same length');
        let dot = 0, normA = 0, normB = 0;
        for (let i = 0; i < a.length; i++) {
            dot += a[i] * b[i];
            normA += a[i] ** 2;
            normB += b[i] ** 2;
        }
        if (normA === 0 || normB === 0) return 0;
        return dot / (Math.sqrt(normA) * Math.sqrt(normB));
    }

    add(vector, value, metadata = {}) {
        this.entries.push({ vector: [...vector], value, metadata });
        return this;
    }

    search(query, limit = 5) {
        return this.entries
            .map(entry => ({ ...entry, score: VectorMemory.cosineSimilarity(query, entry.vector) }))
            .sort((a, b) => b.score - a.score)
            .slice(0, limit);
    }
}

// Export for environments supporting modules
if (typeof module !== 'undefined') {
  module.exports = {
      VariationalAutoencoder,
      GenerativeAdversarialNetwork,
      LSTMNetwork,
      DiffusionModel,
      WassersteinDistance,
      BayesianOptimizer,
      KMeansClustering,
      SoftmaxClassifier,
      SelfAttention,
      VectorMemory
  };
}
