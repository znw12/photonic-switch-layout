import itertools
import json
import random

import pytest

from benes_layout import Config, Network


@pytest.mark.parametrize("p", [2, 4, 8, 128, 1024])
def test_complete_counts_and_depth(p):
    net = Network(Config(active_ports=p))
    assert len(net.switches) == p // 2 * (2 * (p.bit_length() - 1) - 1)
    for boundary in net.boundaries:
        assert sorted(boundary["permutation"]) == list(range(p))
    s = net.solve(enumerate(range(p)))
    assert net.verify(s)["switch_depth"] == net.depth


@pytest.mark.parametrize("p", [2, 4, 8])
def test_exhaustive_permutations(p):
    net = Network(p)
    for perm in itertools.permutations(range(p)):
        net.verify(net.solve(enumerate(perm)))


def test_hundred_pairs_and_full_permutations():
    net = Network(100)
    for a in range(100):
        for b in range(100):
            net.verify(net.solve([(a, b)]))
    rng = random.Random(17)
    perms = [list(range(100)), list(reversed(range(100)))]
    perms += [[(a + k) % 100 for a in range(100)] for k in range(100)]
    for _ in range(100):
        p = list(range(100))
        rng.shuffle(p)
        perms.append(p)
    for p in perms:
        net.verify(net.solve(enumerate(p)))


def test_mapping_round_trip_and_spares():
    cfg = Config(active_ports=5, input_map=(7, 1, 2, 3, 4), output_map=(0, 6, 5, 4, 3))
    assert Config(**json.loads(json.dumps(cfg.to_dict()))).digest == cfg.digest
    net = Network(cfg)
    for p in itertools.permutations(range(5)):
        s = net.solve(enumerate(p))
        net.verify(s)
        assert s == net.solve(enumerate(p))
    for a in range(5):
        for b in range(5):
            net.verify(net.solve([(a, b)]))
    s["states"][next(iter(s["states"]))] ^= 1
    with pytest.raises(ValueError, match="expected output"):
        net.verify(s)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"active_ports": 0},
        {"internal_ports": 100},
        {"internal_ports": 64},
        {"radius": 19},
        {"pad_pitch": 5},
        {"input_map": (0, 0)},
        {"terminal_offsets": (1, 2)},
        {"grid": 1},
        {"max_candidates": 0},
    ],
)
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


@pytest.mark.parametrize(
    "pairs",
    [
        [(0, 0), (0, 1)],
        [(0, 0), (1, 0)],
        [(100, 0)],
        [(0, 100)],
        [(True, 0)],
        [(0, -1)],
    ],
)
def test_invalid_request(pairs):
    with pytest.raises(ValueError):
        Network(100).solve(pairs)


def test_single_port():
    net = Network(1)
    assert net.p == 2
    net.verify(net.solve([(0, 0)]))
