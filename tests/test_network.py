import copy
import itertools
import random
import pytest

from waksman_layout.network import Network, switch_count
from waksman_layout.config import Config


@pytest.mark.parametrize(
    "n,count",
    [
        (1, 0),
        (2, 1),
        (3, 3),
        (16, 49),
        (25, 94),
        (100, 573),
        (101, 580),
        (256, 1793),
        (1024, 9217),
    ],
)
def test_counts(n, count):
    assert switch_count(n) == count
    assert len(Network(n).switches) == count


@pytest.mark.parametrize("n", range(1, 8))
def test_all_small_permutations(n):
    net = Network(n)
    for p in itertools.permutations(range(n)):
        net.verify(net.solve(enumerate(p)))


def test_all_hundred_single_pairs():
    net = Network(100)
    for i in range(100):
        for j in range(100):
            s = net.solve([(i, j)])
            assert s["active"] == [(i, j)] and len(s["inactive"]) == 99
            net.verify(s)


@pytest.mark.parametrize("n", [25, 100, 101, 256, 1024])
def test_full_permutations(n):
    net = Network(n)
    rng = random.Random(17)
    samples = [list(range(n)), list(reversed(range(n)))]
    samples.extend(
        [[(i + k) % n for i in range(n)] for k in range(n if n == 100 else 3)]
    )
    for _ in range(100):
        p = list(range(n))
        rng.shuffle(p)
        samples.append(p)
    for p in samples:
        net.verify(net.solve(enumerate(p)))


def test_corrupted_state():
    net = Network(4)
    s = net.solve(enumerate(range(4)))
    broken = copy.deepcopy(s)
    sid = next(iter(broken["states"]))
    broken["states"][sid] ^= 1
    with pytest.raises(ValueError, match="expected output"):
        net.verify(broken)
    assert s == net.solve(enumerate(range(4)))


@pytest.mark.parametrize(
    "pairs", [[(0, 1), (0, 2)], [(0, 1), (2, 1)], [(0, 4)], [(0, -1)], [(True, 1)]]
)
def test_bad_requests(pairs):
    with pytest.raises(ValueError):
        Network(4).solve(pairs)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(n=0),
        dict(n=2.5),
        dict(radius=19),
        dict(pad_pitch=20),
        dict(metal_width=-1),
        dict(terminal_offsets=(1, 2)),
    ],
)
def test_bad_config(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_layer_collision():
    layers = Config().layers.copy()
    layers["M2"] = layers["M1"]
    with pytest.raises(ValueError, match="distinct"):
        Config(layers=layers)


def test_truncated_solution_is_not_verification():
    net = Network(4)
    s = net.solve([(0, 1)])
    s["permutation"] = s["permutation"][:1]
    with pytest.raises(ValueError, match="complete permutation"):
        net.verify(s)
