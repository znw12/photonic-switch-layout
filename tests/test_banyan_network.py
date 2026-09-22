"""Independent parent path/state/flow oracles for the blocking topology."""

from copy import deepcopy
from itertools import permutations, product
import random
import pytest
from benes_layout.config import Config
from benes_layout.network import Network
from benes_layout.banyan_network import BlockingError


def net(n):
    return Network(Config(topology="pruned-banyan", active_ports=n))


def enumerate_parent(n):
    # Enumerate binary switch decisions, deriving the split arithmetically.
    result = {}
    for a in range(n.p):
        for decisions in product((0, 1), repeat=n.depth):
            lane, path, edges = a, [], []
            for s, pin in enumerate(decisions):
                row = lane // 2 * 2
                path.append((s, row))
                lane = row + pin
                if s < n.depth - 1:
                    size = n.p >> s
                    base, local = divmod(lane, size)
                    dest = base * size + local // 2 + (local % 2) * (size // 2)
                    edges.append((s, lane, dest))
                    lane = dest
            result.setdefault((a, lane), []).append((path, edges))
    return result


@pytest.mark.parametrize("size", [2, 3, 5, 7, 8, 12, 13, 100, 128])
def test_parent_union_and_unique_pairs(size):
    n = net(size)
    oracle = enumerate_parent(n)
    switches, edges = set(), set()
    for a in n.cfg.input_map:
        for b in n.cfg.output_map:
            assert len(oracle[a, b]) == 1
            path, links = oracle[a, b][0]
            switches.update(path)
            edges.update(links)
            solved = n.path(a, n.cfg.output_map.index(b))
            assert [
                (v["stage"], n.switches[v["switch"]]["row"]) for v in solved
            ] == path
    assert switches == {(v["stage"], v["row"]) for v in n.switches.values()}
    assert edges == {
        (s, a, b) for s, bd in enumerate(n.boundaries) for a, b in bd["edges"]
    }
    assert n.verify(n.solve(n.reference))["connections"] == size
    if size == 100:
        x = n.export()
        assert x["stage_switch_counts"] == [50, 50, 52, 56, 64, 64, 64]
        assert x["boundary_lane_counts"] == [100, 100, 104, 112, 128, 128]
        assert [b["graph_crossings"] for b in n.boundaries] == [
            1225,
            600,
            312,
            168,
            96,
            32,
        ]
        assert x["graph_crossings"] == 2433
        assert len(n.switches) == 400
        assert sum(t["pin"][0] == "i" for t in n.terminations) == 28
        assert sum(t["pin"][0] == "o" for t in n.terminations) == 28


def test_independent_maxflow_selection_counterexample():
    import networkx as nx

    n = net(100)
    graph = nx.DiGraph()
    for s in range(n.depth):
        for row in range(n.p):
            graph.add_edge(("i", s, row), ("q", s, row // 2), capacity=1)
            graph.add_edge(("q", s, row // 2), ("o", s, row), capacity=1)
            if s < n.depth - 1:
                size = n.p >> s
                base, local = divmod(row, size)
                dest = base * size + local // 2 + (local % 2) * (size // 2)
                graph.add_edge(("o", s, row), ("i", s + 1, dest), capacity=1)
    for row in range(100):
        graph.add_edge("source", ("i", 0, row), capacity=1)
    for outputs, expected in ((n.cfg.output_map, 100), (range(100), 79)):
        g = graph.copy()
        for row in outputs:
            g.add_edge(("o", n.depth - 1, row), "sink", capacity=1)
        assert nx.maximum_flow_value(g, "source", "sink") == expected


def state_oracle(n):
    # Walk every physical state, without the solver's reachability/conflict logic.
    reachable = set()
    ids = list(n.switches)
    links = [dict(b["edges"]) for b in n.boundaries]
    outputs = {v: i for i, v in enumerate(n.cfg.output_map)}
    for bits in product((0, 1), repeat=len(ids)):
        states = dict(zip(ids, bits))
        mapping = []
        for a in n.cfg.input_map:
            lane = a
            for s in range(n.depth):
                sid, pin = n.slots[s][lane]
                lane = n.switches[sid]["row"] + (pin ^ states[sid])
                if s < n.depth - 1:
                    lane = links[s].get(lane)
                    if lane is None:
                        break
            mapping.append(outputs.get(lane))
        if None not in mapping:
            reachable.add(tuple(mapping))
    return reachable


@pytest.mark.parametrize("size", range(2, 9))
def test_all_small_permutations_against_states(size):
    n = net(size)
    allowed = state_oracle(n)
    for perm in permutations(range(size)):
        pairs = list(enumerate(perm))
        if perm in allowed:
            assert n.verify(n.solve(pairs))["connections"] == size
        else:
            with pytest.raises(BlockingError) as exc:
                n.solve(pairs)
            assert exc.value.diagnostic["stage"] >= 0


def test_all_10000_single_requests_and_seeded_load():
    n = net(100)
    for a, b in product(range(100), repeat=2):
        s = n.solve([(a, b)])
        assert len(s["states"]) == 400
        assert n.verify(s)["actual_mzi_counts"] == {7: 1}
    rng = random.Random(17)
    for _ in range(100):
        pairs = rng.sample(n.reference, rng.randrange(101))
        solved = n.solve(pairs)
        assert solved == n.solve(reversed(pairs))
        n.verify(solved)
        targets = list(range(100))
        rng.shuffle(targets)
        pairs = list(enumerate(targets))
        try:
            n.verify(n.solve(pairs))
        except BlockingError as exc:
            a, b = exc.diagnostic["requests"]
            sid = exc.diagnostic["switch"]
            pa = next(v for v in n.path(*a) if v["switch"] == sid)
            pb = next(v for v in n.path(*b) if v["switch"] == sid)
            assert pa["input"] ^ pa["output"] != pb["input"] ^ pb["output"]
    assert n.solve([])["dark_active_inputs"] == list(range(100))


@pytest.mark.parametrize("size", [0, -1, True, 1, 3.5])
def test_invalid_scale(size):
    with pytest.raises(ValueError):
        net(size)


def test_invalid_maps_and_parent():
    for args in (
        dict(internal_ports=256),
        dict(output_map=tuple(range(100))),
        dict(input_map=tuple(reversed(range(100)))),
    ):
        with pytest.raises(ValueError):
            Config(topology="pruned-banyan", **args)


@pytest.mark.parametrize(
    "pairs",
    [[[0, 0], [0, 1]], [[0, 0], [1, 0]], [[0, 100]], [[True, 1]], [[1]], [None]],
)
def test_invalid_requests(pairs):
    with pytest.raises(ValueError):
        net(100).solve(pairs)


def test_verifier_corruptions():
    n = net(5)
    good = n.solve(n.reference)
    for mutate in (
        lambda s: s["states"].pop(next(iter(s["states"]))),
        lambda s: s["states"].update({next(iter(s["states"])): 2}),
        lambda s: s.update(dark_active_inputs=[0]),
        lambda s: s.update(rearrangeable=True),
        lambda s: s.update(paths=[]),
    ):
        s = deepcopy(good)
        mutate(s)
        with pytest.raises(ValueError):
            n.verify(s)
    n.boundaries[0]["edges"][0][1] ^= 1
    with pytest.raises(ValueError):
        n.verify(good)
    n = net(5)
    for sid in n.switches:
        s = deepcopy(good)
        s["states"][sid] ^= 1
        try:
            n.verify(s)
        except ValueError:
            break
    else:
        pytest.fail("corrupt states were accepted")


def test_active_path_into_termination_is_rejected():
    n = net(5)
    for pair in n.reference:
        good = n.solve([pair])
        for sid in n.switches:
            broken = deepcopy(good)
            broken["states"][sid] ^= 1
            dest, _ = n.trace(n.cfg.input_map[pair[0]], broken["states"])
            if dest is None:
                with pytest.raises(ValueError, match="termination"):
                    n.verify(broken)
                return
    pytest.fail("fixture did not exercise an active path into a termination")
