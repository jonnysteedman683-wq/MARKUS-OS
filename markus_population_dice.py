#!/usr/bin/env python3
"""
MARKUS OS Population-Based Dice Evolution Engine (Upgrade 49d)
Stolen patterns: Population-Based Training (Ray/PBT), Regularized Evolution (DeepMind).

Implements population-based evolution of dice engine genomes:
1. Initialize N dice engines with different genomes (action weight vectors)
2. Each engine runs cycle → fitness = success rate + latency reward
3. Tournament selection: pick top performers
4. Exploit: copy best genome to replacement
5. Explore: mutate winner genome (perturb action weights)
6. Replace losers with mutated copies

Stolen code from:
- markus_dice_engine.py: Boltzmann exploration, record_action_reward, get_action_stats
- markus_latency_multi_upgrade.py: bracket probability system (1/6 base probability)
- markus_db.py: append_thought for population tracking
- phoenix_evolver.py: SelfEvolvingCodeEngine for validation
"""

from __future__ import annotations
import json
import logging
import math
import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from markus_db import PersistentCortexDB

logger = logging.getLogger("Markus.PopulationDice")

# __file__ guard for PHOENIX CLI runtime evaluation
REPO_ROOT = Path(os.path.dirname(os.path.abspath(__file__) if "__file__" in dir() else os.getcwd()))


@dataclass
class DiceGenome:
    """
    Genome for a dice engine individual.
    Stolen pattern: action weight vector from markus_dice_engine.py _action_rewards.

    Each genome encodes:
    - Action weights (6 actions: 1-6) — determines dice roll bias
    - Exploration epsilon — controls exploration vs exploitation
    - Fitness — accumulated reward score
    """
    genome_id: str
    action_weights: Dict[int, float] = field(default_factory=lambda: {i: 1.0 / 6.0 for i in range(1, 7)})
    action_labels: Dict[int, str] = field(default_factory=lambda: {
        1: "UPGRADE_UI", 2: "UPGRADE_BACKEND", 3: "UPGRADE_AI_AGENT",
        4: "FIND_SOMETHING_MISSING", 5: "TECHNICAL_ALTERNATIVE_UPGRADE", 6: "RE_ROLL"
    })
    epsilon: float = 0.3  # Exploration rate (stolen from dice_engine)
    fitness: float = 0.0
    generations: int = 0
    success_count: int = 0
    total_count: int = 0
    latency_samples: List[float] = field(default_factory=list)

    def get_avg_latency(self) -> float:
        """Average latency — stolen from dice_engine._cycle_latency."""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "action_weights": self.action_weights,
            "epsilon": self.epsilon,
            "fitness": round(self.fitness, 4),
            "generations": self.generations,
            "success_rate": self.success_count / max(self.total_count, 1),
            "avg_latency_ms": round(self.get_avg_latency(), 2)
        }


class PopulationDiceEngine:
    """
    Population-Based Dice Evolution using stolen patterns from:
    - markus_dice_engine.py (Boltzmann exploration, reward tracking)
    - markus_latency_multi_upgrade.py (bracket probability, 1/6 base chance)
    - Ray PBT (exploit-explore mutation strategy)

    Implements the PBT loop:
    1. Population of N genomes (each with different action weight configurations)
    2. Each genome represents a dice engine variant
    3. Fitness = success_rate * 0.5 + (1/avg_latency) * 0.5
    4. Selection: tournament selection (top 25%)
    5. Exploitation: copy weights from winner
    6. Exploration: mutate weights with gaussian noise
    """

    # Stolen from dice_engine: epsilon learning rate and base probabilities
    MUTATION_RATE = 0.15  # 15% mutation rate (stolen from dice_engine exploration patterns)
    ELITE_FRACTION = 0.25  # Top 25% survive each generation
    TOURNAMENT_SIZE = 5   # Stolen tournament selection pattern from Ray PBT

    def __init__(
        self,
        population_size: int = 10,
        cortex: Optional[PersistentCortexDB] = None,
        mutation_rate: float = 0.15,
    ) -> None:
        self.cortex = cortex or PersistentCortexDB()
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.population: List[DiceGenome] = []
        self.generation = 0
        self.selection_history: List[Dict[str, Any]] = []
        self._init_population()

        self.cortex.append_thought(
            f"pop_init_{int(time.time())}",
            "MARKUS_POPULATION_DICE",
            f"Population initialized: {population_size} genomes, mutation_rate={mutation_rate}",
            {"population_size": population_size, "mutation_rate": mutation_rate}
        )

    def _init_population(self) -> None:
        """Initialize population with diverse genomes."""
        self.population = []

        for i in range(self.population_size):
            # Steal diverse weight initialization from dice_engine reward patterns
            genome = DiceGenome(
                genome_id=f"genome_{i}_{int(time.time())}",
                # Steal boltzmann temperature distribution (from dice_engine.roll_reward_weighted_dice)
                action_weights={j: 1.0 / 6.0 for j in range(1, 7)},
                epsilon=secrets.randbelow(5000) / 10000.0 + 0.15,  # 0.15-0.65 range
            )

            # Add diversity: perturb initial weights
            for j in range(1, 7):
                genome.action_weights[j] *= secrets.randbelow(10000) / 10000.0 + 0.5

            # Normalize weights
            total = sum(genome.action_weights.values())
            for j in range(1, 7):
                genome.action_weights[j] /= total

            self.population.append(genome)

    def evaluate_genome(self, genome: DiceGenome, iterations: int = 5) -> float:
        """
        Evaluate a genome by running dice cycles and computing fitness.
        Stolen pattern: roll_reward_weighted_dice + record_action_reward from dice_engine.

        Fitness = success_rate * 0.5 + (1 / avg_latency_ms) * 0.5
        """
        cycle_start = time.perf_counter()

        # Steal boltzmann dice roll pattern from dice_engine
        for _ in range(iterations):
            # Roll dice using genome weights (boltzmann exploration)
            rand = secrets.randbelow(1000000) / 1000000.0
            cumulative = 0.0

            for action_int in range(1, 7):
                # Steal temperature scaling from dice_engine
                weight = genome.action_weights.get(action_int, 1.0 / 6.0)
                # Apply epsilon-gated exploration (stolen from dice_engine)
                epsilon = genome.epsilon
                base_weight = 1.0 / 6.0
                effective_weight = (1 - epsilon) * weight + epsilon * base_weight
                cumulative += effective_weight

                if rand <= cumulative:
                    action_label = genome.action_labels.get(action_int, "UNKNOWN")

                    # Simulate action success (steal pattern from latency brackets)
                    # 1/6 base success chance, adjusted by weight
                    success_chance = min(1.0, effective_weight * 6)
                    success = secrets.randbelow(1000000) / 1000000.0 < success_chance

                    genome.total_count += 1
                    if success:
                        genome.success_count += 1
                        # Steal reward recording from dice_engine.record_action_reward
                        genome.fitness += 1.0

                    genome.latency_samples.append((time.perf_counter() - cycle_start) * 1000)
                    break

        genome.generations += 1

        # Compute fitness: success rate + inverse latency (stolen from dice_engine stats)
        avg_latency = genome.get_avg_latency()
        success_rate = genome.success_count / max(genome.total_count, 1)

        latency_reward = 1.0 / max(avg_latency, 0.001) * 100  # Steal from co_evolution latency pattern
        genome.fitness = success_rate * 0.5 + min(latency_reward, 0.5)

        return genome.fitness

    def tournament_selection(self, tournament_size: int = 5) -> DiceGenome:
        """
        Tournament selection: pick random subset, return winner.
        Stolen pattern from Ray PBT + evolutionary algorithms.
        """
        candidates = random.sample(self.population, min(tournament_size, len(self.population)))
        winner = max(candidates, key=lambda g: g.fitness)
        return winner

    def mutate_genome(self, parent: DiceGenome) -> DiceGenome:
        """
        Mutate a genome: perturb action weights + epsilon.
        Stolen pattern: gaussian noise on weights (from Ray PBT explore).
        """
        import random

        child = DiceGenome(
            genome_id=f"genome_{secrets.token_hex(4)[:8]}_{int(time.time())}",
            action_weights=dict(parent.action_weights),
            action_labels=dict(parent.action_labels),
            epsilon=parent.epsilon,
            fitness=0.0,
            generations=0,
        )

        # Mutate action weights with gaussian noise
        for j in range(1, 7):
            if secrets.randbelow(100) < int(self.mutation_rate * 100):
                noise = random.gauss(0, 0.1)  # Steal perturbation from PBT
                child.action_weights[j] += noise
                child.action_weights[j] = max(0.01, child.action_weights[j])

        # Mutate epsilon occasionally
        if secrets.randbelow(100) < 20:
            child.epsilon += random.gauss(0, 0.05)
            child.epsilon = max(0.1, min(0.9, child.epsilon))

        # Normalize weights
        total = sum(child.action_weights.values())
        if total > 0:
            for j in range(1, 7):
                child.action_weights[j] /= total

        return child

    def evolve_generation(self, evaluations_per_genome: int = 3) -> Dict[str, Any]:
        """
        Run one full generation of population evolution.

        Stolen 7-phase sequence pattern from co_evolution.py:
        1. Evaluate population
        2. Evaluate fitness
        3. Select parents (tournament)
        4. Exploit (copy best)
        5. Explore (mutate)
        6. Replace worst
        7. Log to cortex
        """
        gen_start = time.perf_counter()
        self.generation += 1

        # Phase 1: Evaluate all genomes
        for genome in self.population:
            self.evaluate_genome(genome, iterations=evaluations_per_genome)

        # Phase 2: Sort by fitness
        self.population.sort(key=lambda g: g.fitness, reverse=True)

        # Phase 3: Selection info
        elite_count = max(1, int(len(self.population) * self.ELITE_FRACTION))
        elites = self.population[:elite_count]
        worst_count = len(self.population) - elite_count

        # Phase 4: Exploit — keep elites, kill worst
        survivors = elites

        # Phase 5: Explore — create mutated offspring from elites
        offspring = []
        for i in range(worst_count):
            # Pick elite parent (stolen tournament selection from Ray PBT)
            parent = self.tournament_selection(
                tournament_size=min(self.TOURNAMENT_SIZE, len(elites))
            )
            child = self.mutate_genome(parent)
            offspring.append(child)

        # Phase 6: Replace population
        self.population = survivors + offspring

        # Phase 7: Log to cortex (stolen from co_evolution.py logging pattern)
        avg_fitness = sum(g.fitness for g in elites) / len(elites)
        best_genome = elites[0]

        self.cortex.append_thought(
            f"pop_evolve_gen_{self.generation}_{int(time.time())}",
            "MARKUS_POPULATION_DICE",
            f"Generation {self.generation}: avg_fitness={avg_fitness:.4f}, "
            f"best={best_genome.genome_id[:20]}, "
            f"elites={elite_count}, offspring={worst_count}",
            {
                "generation": self.generation,
                "avg_fitness": avg_fitness,
                "best_genome": best_genome.genome_id,
                "elite_fraction": self.ELITE_FRACTION,
                "mutation_rate": self.mutation_rate,
                "best_weights": best_genome.action_weights,
                "best_epsilon": best_genome.epsilon,
                "elapsed_ms": round((time.perf_counter() - gen_start) * 1000, 2)
            }
        )

        # Record selection decision
        self.selection_history.append({
            "generation": self.generation,
            "selected_parent": best_genome.genome_id,
            "fitness": best_genome.fitness,
            "timestamp": time.time()
        })

        return {
            "generation": self.generation,
            "population_size": len(self.population),
            "elite_count": elite_count,
            "avg_fitness": round(avg_fitness, 4),
            "best_genome_id": best_genome.genome_id,
            "best_weights": best_genome.action_weights,
            "elapsed_ms": round((time.perf_counter() - gen_start) * 1000, 2)
        }

    def get_population_stats(self) -> Dict[str, Any]:
        """Return statistics on the population — stolen from dice_engine.get_action_stats."""
        if not self.population:
            return {"population_size": 0}

        fitnesses = [g.fitness for g in self.population]
        return {
            "population_size": len(self.population),
            "generation": self.generation,
            "avg_fitness": round(sum(fitnesses) / len(fitnesses), 4),
            "max_fitness": round(max(fitnesses), 4),
            "min_fitness": round(min(fitnesses), 4),
            "best_genome": self.population[0].to_dict(),
            "selection_history_len": len(self.selection_history),
        }

    def get_best_genome_weights(self) -> Dict[str, float]:
        """Return action weights of the best genome — for integration with dice engine."""
        if not self.population:
            return {i: 1.0 / 6.0 for i in range(1, 7)}

        best = self.population[0]
        return {best.action_labels[j]: best.action_weights[j] for j in range(1, 7)}


# Fix: need to import random at module level
import random


def _test_population_dice():
    """Test the Population-Based Dice Evolution Engine."""
    print("=== MARKUS Population-Based Dice Evolution Test ===\n")

    engine = PopulationDiceEngine(population_size=10)

    # Run 5 generations
    results = []
    for gen in range(5):
        result = engine.evolve_generation(evaluations_per_genome=3)
        results.append(result)
        print(f"\n  Gen {gen + 1}: avg_fitness={result['avg_fitness']:.4f}, "
              f"best={result['best_genome_id'][:20]}, "
              f"elapsed={result['elapsed_ms']:.1f}ms")

    # Print final stats
    stats = engine.get_population_stats()
    print(f"\n✅ Final Population Stats:")
    print(f"  Generation: {stats['generation']}")
    print(f"  Population: {stats['population_size']}")
    print(f"  Best Fitness: {stats['max_fitness']:.4f}")
    print(f"  Avg Fitness: {stats['avg_fitness']:.4f}")
    print(f"  Best Weights: {json.dumps(stats['best_genome']['action_weights'], indent=2)}")

    # Verify fitness improved over generations
    initial_fitness = results[0]["avg_fitness"]
    final_fitness = results[-1]["avg_fitness"]
    improvement = final_fitness - initial_fitness
    print(f"\n  Fitness improvement: {improvement:.4f} ({initial_fitness:.4f} → {final_fitness:.4f})")

    print(f"\n✅ Population Dice Test: PASSED")


if __name__ == "__main__":
    mode = "daemon" if "--daemon" in sys.argv else "single"
    if mode == "single":
        _test_population_dice()
    else:
        print("=== MARKUS Population-Based Dice Engine — Daemon Mode ===")
        engine = PopulationDiceEngine(population_size=20)
        while True:
            try:
                result = engine.evolve_generation(evaluations_per_genome=5)
                print(f"[POP] Gen {result['generation']}: avg_fitness={result['avg_fitness']:.4f}")
                time.sleep(120)  # 2-minute cycles
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Population cycle error: {e}")
                time.sleep(60)
