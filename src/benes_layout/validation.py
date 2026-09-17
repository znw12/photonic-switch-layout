"""Regenerate functional acceptance evidence without physical layout output."""

import argparse
import itertools
import random
import time

from .config import Config
from .network import Network
from .cli import save


def functional_report(seed=17):
    start = time.perf_counter()
    counts = {}
    for p in (2, 4, 8):
        net = Network(p)
        count = 0
        for permutation in itertools.permutations(range(p)):
            net.verify(net.solve(enumerate(permutation)))
            count += 1
        counts[str(p)] = count
    cfg = Config(active_ports=5, input_map=(7, 1, 2, 3, 4), output_map=(0, 6, 5, 4, 3))
    net = Network(cfg)
    for permutation in itertools.permutations(range(5)):
        net.verify(net.solve(enumerate(permutation)))
    net = Network(100)
    for a in range(100):
        for b in range(100):
            net.verify(net.solve([(a, b)]))
    rng = random.Random(seed)
    full_counts = {}
    for active in (100, 128):
        net = Network(active)
        permutations = [list(range(active)), list(reversed(range(active)))]
        permutations += [
            [(a + k) % active for a in range(active)] for k in range(active)
        ]
        for _ in range(100):
            p = list(range(active))
            rng.shuffle(p)
            permutations.append(p)
        for p in permutations:
            net.verify(net.solve(enumerate(p)))
        full_counts[str(active)] = len(permutations)
    return {
        "success": True,
        "seed": seed,
        "scope": "independent graph traversal of solver output; physical geometry checked separately",
        "exhaustive_permutations": counts,
        "padded_5_of_8_permutations": 120,
        "active_100_single_pairs": 10000,
        "full_permutations": full_counts,
        "random_permutations_per_full_size": 100,
        "duration_s": time.perf_counter() - start,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="output/benes/functional.json")
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    report = functional_report(args.seed)
    save(args.out, report)
    print(report)
