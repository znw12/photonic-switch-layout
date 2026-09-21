from itertools import permutations
import random
import pytest
from benes_layout.config import Config
from benes_layout.network import Network


def test_exact_config_preserves_legacy_hash(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    # Frozen compact-GSG configuration from 49ec22c, before AS-Benes was added.
    fixture = Path(__file__).resolve().parent / "fixtures" / "compact_gsg_legacy_config.json"
    monkeypatch.chdir(tmp_path)
    assert not Path("output").exists()
    data = json.loads(fixture.read_text())
    cfg = Config(**data)
    assert json.loads(json.dumps(cfg.to_dict())) == data
    assert cfg.digest == (
        "6df086d8f368c692394e3fdbda42d76ec1f2f13418644f849a3a0b8823f20e19"
    )
    assert "topology" not in Config().to_dict()
    for n in (1, 2, 3, 5, 13, 25, 100, 128):
        cfg = Config(active_ports=n, topology="as-benes")
        assert cfg.internal_ports == n
    for n in (0, -1, 1.5, True):
        with pytest.raises(ValueError):
            Config(active_ports=n, topology="as-benes")
    with pytest.raises(ValueError):
        Config(active_ports=100, internal_ports=128, topology="as-benes")
    with pytest.raises(ValueError):
        Config(internal_ports=100)


def test_exact_counts():
    for n, count in (
        (1, 0),
        (2, 1),
        (3, 3),
        (5, 8),
        (13, 39),
        (25, 99),
        (100, 596),
        (128, 832),
    ):
        net = Network(Config(active_ports=n, topology="as-benes"))
        assert len(net.switches) == count
        assert all(sorted(b["permutation"]) == list(range(n)) for b in net.boundaries)
        assert len(net.bypasses) + 2 * count == net.depth * n


@pytest.mark.parametrize("n", range(2, 9))
def test_exhaustive_exact_permutations(n):
    net = Network(Config(active_ports=n, topology="as-benes"))
    for pi in permutations(range(n)):
        net.verify(net.solve(enumerate(pi)))


def test_exact100_requests():
    net = Network(Config(active_ports=100, topology="as-benes"))
    for i in range(100):
        for j in range(100):
            net.verify(net.solve([(i, j)]))
    patterns = [list(range(100)), list(reversed(range(100)))]
    patterns.extend([(i + k) % 100 for i in range(100)] for k in range(100))
    rng = random.Random(17)
    for _ in range(100):
        p = list(range(100))
        rng.shuffle(p)
        patterns.append(p)
    for pi in patterns:
        net.verify(net.solve(enumerate(pi)))


def test_corrupt_requests_and_bypass():
    net = Network(Config(active_ports=5, topology="as-benes"))
    for pairs in ([(0, 1), (1, 1)], [(0, 1), (0, 2)], [(5, 1)], [(0, True)]):
        with pytest.raises(ValueError):
            net.solve(pairs)
    settings = net.solve([(4, 0)])
    settings["states"].pop(next(iter(settings["states"])))
    with pytest.raises(ValueError):
        net.verify(settings)
    settings = net.solve(enumerate(range(5)))
    net.boundaries[0]["permutation"][4] = 0
    with pytest.raises(ValueError):
        net.verify(settings)


def physical_config(n=5, pitch=35):
    from dataclasses import replace

    return replace(
        Config.load("examples/benes/exact100-balanced/n100.json"),
        active_ports=n,
        internal_ports=n,
        input_map=None,
        output_map=None,
        lane_pitch=pitch,
        mzi_height=2 * pitch,
        terminal_offsets=(pitch / 2,) * 2,
    )


@pytest.mark.parametrize(
    "n,pitch,side", [(5, 34, "R"), (7, 35, "L"), (12, 34, "R"), (13, 35, "L")]
)
@pytest.mark.parametrize("pad_distribution", ["central", "routing"])
def test_exact_physical_roundtrip(tmp_path, n, pitch, side, pad_distribution):
    from dataclasses import replace
    from benes_layout.as_layout import build
    from benes_layout.as_verify import verify_manifest, verify_gds

    cfg = replace(physical_config(n, pitch), pad_distribution=pad_distribution)
    net = Network(cfg)
    lib, m = build(cfg, dict(id="test", exits=side * net.depth, pad_phase=0))
    verify_manifest(m)
    names = lib.write_gds(m["top"], tmp_path / "layout.gds")
    result = verify_gds(tmp_path / "layout.gds", m, names)
    assert result["electrical_nets"] == len(net.switches) + 1
    assert len(m["ground_rails"]) < 2 * len(net.switches)
    assert all(
        not any(
            s["layer"] == "M1" and s["start"][0] == s["end"][0] for s in e["segments"]
        )
        and e["pad"] not in e["vias"]
        for e in m["electrical"]
    )
    assert (
        m["electrical_plan"]["channel_levels"]
        <= m["electrical_plan"]["channel_ordering"]["level_budget"]
    )
    assert all(
        v["extra_bypass_bends"] == 0
        for v in [c["metadata"] for c in m["cells"].values()]
        if "extra_bypass_bends" in v
    )


def test_as_hierarchy_and_shared_g():
    from benes_layout.as_geometry import variants, ground_column
    from benes_layout.geometry import Library

    lib = Library(physical_config())
    devices = variants(lib)
    for pin in ("i0", "i1", "o0", "o1"):
        assert devices["L"].ports[pin] == devices["R"].ports[pin]
    cell = ground_column(lib, "L", [0, 2])
    assert len(cell.metadata["rails"]) == 3
    assert len([r for r in cell.refs if r["cell"] == "VIA"]) == 3
    separated = ground_column(lib, "L", [0, 3])
    assert len(separated.metadata["rails"]) == 4
    assert len(separated.metadata["runs"]) == 2


@pytest.mark.parametrize(
    "fault", ["missing_contact", "duplicate_contact", "bypass", "radius"]
)
def test_as_manifest_rejects_faults(fault):
    from benes_layout.as_layout import build
    from benes_layout.as_verify import verify_manifest

    _, m = build(physical_config())
    if fault in ("missing_contact", "duplicate_contact"):
        ground = next(c for c in m["cells"].values() if c["kind"] == "ground_column")
        if fault == "missing_contact":
            ground["refs"].pop()
        else:
            ground["refs"].append(dict(ground["refs"][0]))
    elif fault == "bypass":
        r = next(r for r in m["routes"] if r["row"] == 4)
        r["dest"] = 0
    else:
        arc = next(c for c in m["cells"].values() if c["kind"] == "bend")
        arc["metadata"]["arc"]["radius"] = 10
    with pytest.raises(ValueError):
        verify_manifest(m)


@pytest.mark.parametrize("fault", ["ground_open", "signal_ground_short"])
def test_as_readback_detects_conductor_faults(tmp_path, fault):
    from benes_layout.as_layout import build
    from benes_layout.as_verify import verify_gds
    from benes_layout.geometry import rectangle

    lib, m = build(physical_config())
    if fault == "ground_open":
        lib.cells["GROUND"].polygons.pop(0)
    else:
        inst = m["instances"][0]
        x, y = inst["x"], inst["y"]
        lib.poly(lib.cells["GROUND"], "M1", rectangle(x + 500, y - 5, x + 510, y + 20))
    m["cells"] = lib.export()
    names = lib.write_gds(m["top"], tmp_path / "fault.gds")
    with pytest.raises(ValueError):
        verify_gds(tmp_path / "fault.gds", m, names)


def test_as_candidate_budget_and_controls():
    from benes_layout.as_workflow import candidates

    cfg = Config.load("examples/benes/exact100-balanced/n100.json")
    choices = candidates(cfg)
    assert choices == candidates(cfg)
    assert len(choices) <= 18
    assert {v["lane_pitch"] for v in choices if v["control"]} == {34, 35}


def test_channel_vertical_precedence_and_cycle():
    from benes_layout.as_channel import channel_levels

    sources = [0, 15, 30, 45, 60]
    targets = [5, 55, 105, 155, 205]
    levels = channel_levels(sources, targets)
    for i, x in enumerate(sources):
        for j, y in enumerate(targets):
            if i != j and abs(x - y) < 14.002:
                assert levels[i] < levels[j]
    with pytest.raises(ValueError):
        channel_levels([0, 50], [50, 0])


@pytest.mark.parametrize("targets", [[100, 150, 200, 250], [-250, -200, -150, -100]])
def test_ordered_channel_avoids_foreign_vertical_legs(targets):
    from benes_layout.as_channel import channel_levels

    sources = [0, 20, 40, 60]
    levels = channel_levels(sources, targets, ordered=True)
    for i, (source, target) in enumerate(zip(sources, targets)):
        lo, hi = sorted((source, target))
        for j in range(len(sources)):
            if i == j:
                continue
            assert not (lo < sources[j] < hi and levels[i] < levels[j])
            assert not (lo < targets[j] < hi and levels[i] > levels[j])
    with pytest.raises(ValueError, match="monotone"):
        channel_levels(sources, list(reversed(targets)), ordered=True)


def test_routing_pad_fit_preserves_pitch_and_width():
    from benes_layout.as_channel import aligned_slots

    cfg = physical_config()
    sources = [200, 210, 220, 230, 1000, 1010, 1020, 1030]
    fitted = aligned_slots(sources, 1500, cfg)
    xs = [v["px"] for v in fitted]
    assert fitted == aligned_slots(sources, 1500, cfg)
    assert xs[0] >= 70 and xs[-1] <= 1430
    assert all(b - a >= 50 for a, b in zip(xs, xs[1:]))
    for row in (0, 1):
        rr = xs[row::2]
        assert all(b - a >= 100 for a, b in zip(rr, rr[1:]))
    uniform = [575 + i * 50 for i in range(len(xs))]
    assert sum((x - s) ** 2 for x, s in zip(xs, sources)) < sum(
        (x - s) ** 2 for x, s in zip(uniform, sources)
    )
    with pytest.raises(ValueError, match="fit"):
        aligned_slots(sources, 300, cfg)


def test_aligned_pad_spacing_fault_is_rejected():
    from dataclasses import replace
    from benes_layout.as_layout import build
    from benes_layout.as_verify import verify_manifest

    _, m = build(replace(physical_config(), pad_distribution="routing"))
    es = sorted(
        (e for e in m["electrical"] if e["side"] == "north"), key=lambda e: e["tx"]
    )
    es[1]["pad"][0] = es[0]["pad"][0] + 30
    with pytest.raises(ValueError, match="pitch"):
        verify_manifest(m)


def test_large_direction_search_is_bounded():
    from benes_layout.as_workflow import direction_patterns

    assert len(direction_patterns(13)) == 8192
    patterns = direction_patterns(25)
    assert len(patterns) == 8192
    assert "R" * 25 in patterns and "L" * 25 in patterns


def test_exact_bundle_workflow(tmp_path):
    import json
    from benes_layout.workflow import generate, verify_bundle

    cfg = physical_config()
    choice = dict(id="integration", exits="RLLRL", pad_phase=0, lane_pitch=35)
    report = generate(cfg, tmp_path, [(0, 4), (4, 0)], choices=[choice])
    assert report["success"]
    assert verify_bundle(tmp_path)["electrical_nets"] == 9
    assert (tmp_path / "mzi_l.png").exists() and (tmp_path / "mzi_r.png").exists()
    assert report["metrics"]["extents_um"]["die"]
    saved = json.loads((tmp_path / "report.json").read_text())
    saved["metrics"]["signal_turns"] += 1
    (tmp_path / "report.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        verify_bundle(tmp_path)


def test_exact_cli_default_output(monkeypatch):
    from benes_layout.cli import main
    import benes_layout.workflow as workflow

    captured = []

    def generate(cfg, out, pairs):
        captured.append((cfg.topology, out))
        return {"summary": {}}

    monkeypatch.setattr(workflow, "generate", generate)
    main(["generate", "--config", "examples/benes/exact100-balanced/n100.json"])
    main(["generate", "--n", "4"])
    assert captured == [
        ("as-benes", "output/benes/exact100-balanced/n100"),
        ("benes", "output/benes/n100"),
    ]
