from dataclasses import replace
import json

import pytest

from benes_layout import Config, Network
from benes_layout.geometry import rectangle
from benes_layout.layout import build_layout
from benes_layout.metrics import uniformity, realized, objective, mzi_track
from benes_layout.verify import (
    verify_manifest,
    verify_gds,
    VerificationError,
    normalized_hash,
)
from benes_layout.equalize import apply_equalization
from benes_layout.workflow import candidates, generate, verify_bundle


@pytest.mark.parametrize(
    "n,row",
    [(1, "normal"), (2, "normal"), (4, "normal"), (5, "reverse"), (16, "normal")],
)
def test_physical_readback(tmp_path, n, row):
    cfg = Config(active_ports=n)
    choice = dict(id="test", gap=1.0, row_order=row, pad=1.0, corridor=1.0)
    lib, m = build_layout(cfg, choice)
    a = verify_manifest(m)
    names = lib.write_gds(m["top"], tmp_path / "layout.gds")
    b = verify_gds(tmp_path / "layout.gds", m, names)
    assert a["switch_depth_min"] == a["switch_depth_max"] == Network(cfg).depth
    assert b["via_count"] == 3 * len(m["electrical"])
    assert a["spare_terminations"] == 2 * (cfg.internal_ports - n)


def test_components_and_changed_geometry(tmp_path):
    for kind in ("mzi", "crossing", "termination"):

        def factory(lib):
            if kind == "mzi":
                lib.mzi().ports.pop("i1")
            elif kind == "crossing":
                lib.crossing().metadata["through"] = [["w", "n"], ["s", "e"]]
            else:
                lib.termination("west").ports["opt"] = [0, 1, 0]

        with pytest.raises(ValueError, match="port|contract|crossing"):
            build_layout(Config(active_ports=4), component_factory=factory)
    cfg = Config(
        active_ports=5,
        mzi_length=1400,
        pad_pitch=120,
        input_map=(7, 0, 2, 4, 6),
        output_map=(1, 3, 5, 6, 7),
    )
    lib, m = build_layout(cfg)
    verify_manifest(m)
    names = lib.write_gds(m["top"], tmp_path / "larger.gds")
    verify_gds(tmp_path / "larger.gds", m, names)


@pytest.mark.parametrize(
    "defect",
    [
        "prune",
        "bypass",
        "spare_map",
        "termination",
        "gap",
        "crossing",
        "radius",
        "arc_polygon",
        "intersection",
    ],
)
def test_optical_faults(defect):
    _, m = build_layout(Config(active_ports=5))
    if defect == "prune":
        m["instances"].pop()
    elif defect == "bypass":
        m["routes"][0]["target"] = "out:0"
    elif defect == "spare_map":
        m["interfaces"][0]["active"] = None
    elif defect == "termination":
        m["terminations"].pop()
    elif defect == "gap":
        m["routes"][0]["pieces"][0]["x"] += 1
    elif defect == "crossing":
        m["cells"]["CROSSING"]["metadata"]["through"] = [["w", "n"], ["s", "e"]]
    elif defect == "radius":
        m["cells"]["BEND_NE"]["metadata"]["arc"]["radius"] = 19
    elif defect == "arc_polygon":
        m["cells"]["BEND_NE"]["polygons"][0]["points"][0][0] += 1
    else:
        c = m["cells"][m["routes"][0]["pieces"][0]["cell"]]
        c["polygons"].append(dict(layer="WG", points=rectangle(50, -1, 51, 160)))
    with pytest.raises(VerificationError):
        verify_manifest(m)


@pytest.mark.parametrize(
    "defect", ["via", "via_size", "short", "enclosure", "width", "window"]
)
def test_electrical_faults_detected_from_actual_polygons(tmp_path, defect):
    lib, m = build_layout(Config(active_ports=4))
    e = m["electrical"][0]
    c = lib.cells[e["cell"]]
    if defect == "via":
        c.refs.pop(0)
    elif defect == "via_size":
        for poly in lib.cells["VIA"].polygons:
            if poly["layer"] == "VIA":
                poly["points"] = rectangle(-1, -1, 1, 1)
    elif defect == "short":
        a, b = m["electrical"][:2]
        lib.poly(
            c,
            "M1",
            rectangle(
                a["x"] + 1, min(a["y"], b["y"]) - 2, a["x"] + 6, max(a["y"], b["y"]) + 2
            ),
        )
    elif defect == "enclosure":
        for poly in lib.cells["VIA"].polygons:
            if poly["layer"] == "M1":
                poly["points"] = rectangle(-2.5, -2.5, 2.5, 2.5)
    elif defect == "width":
        poly = next(poly for poly in c.polygons if poly["layer"] == "M2")
        x = e["vias"][0][0]
        ys = [v[1] for v in poly["points"]]
        poly["points"] = rectangle(x - 0.5, min(ys), x + 0.5, max(ys))
    else:
        m["overpasses"] = []
    m["cells"] = lib.export()  # Defect agrees with manifest: extraction must catch it.
    names = lib.write_gds(m["top"], tmp_path / "bad.gds")
    with pytest.raises(VerificationError):
        verify_gds(tmp_path / "bad.gds", m, names)


@pytest.mark.parametrize("defect", ["polygon", "transform"])
def test_gds_diff_detects_export_fault(tmp_path, defect):
    import klayout.db as kdb

    lib, m = build_layout(Config(active_ports=4))
    path = tmp_path / "bad.gds"
    names = lib.write_gds(m["top"], path)
    ly = kdb.Layout()
    ly.read(str(path))
    if defect == "polygon":
        ly.cell(names["CROSSING"]).shapes(ly.layer(1, 0)).clear()
    else:
        instance = next(ly.cell(names["STAGE_00"]).each_inst())
        instance.transform(kdb.Trans(1000, 0))
    ly.write(str(path))
    with pytest.raises(VerificationError, match="mismatch"):
        verify_gds(path, m, names)


def test_dag_extrema_against_exhaustive_paths_and_known_lengths():
    cfg = Config(active_ports=4)
    _, m = build_layout(cfg)
    rs = {r["source"]: r for r in m["routes"]}
    samples = []

    def walk(source, total):
        r = rs[source]
        values = {k: total[k] + r[k] for k in total}
        if r["target"].startswith("out:"):
            samples.append(values)
            return
        sid, pin = r["target"].split(":")
        for out in range(2):
            t = mzi_track(m, sid, int(pin[1]), out)
            walk(f"{sid}:o{out}", {k: values[k] + t[k] for k in values})

    for i in range(4):
        walk(f"in:{i}", dict(length=0.0, crossings=0, bends=0, angle=0.0))
    got = uniformity(m)["metrics"]
    for key, v in got.items():
        assert v["min"] == pytest.approx(min(p[key] for p in samples))
        assert v["max"] == pytest.approx(max(p[key] for p in samples))
        assert len(v["max_witness"]) == 4
    assert got["length"]["min"] == pytest.approx(m["width"] - 2 * cfg.margin)
    assert (got["crossings"]["min"], got["crossings"]["max"]) == (0, 2)
    stats = realized(m, Network(cfg).solve(enumerate(range(4))))
    assert len(stats["paths"]) == 4 and all(p["switches"] == 3 for p in stats["paths"])


def test_area_priority_and_all_ties():
    m = {
        "config": {"grid": 0.001},
        "width": 100.0,
        "height": 10.0,
        "routes": [{"length": 100}],
    }
    metrics = {"metrics": {k: {"spread": 50} for k in ("length", "crossings", "bends")}}
    perfect = {"metrics": {k: {"spread": 0} for k in metrics["metrics"]}}
    assert objective(m, metrics, "a") < objective({**m, "width": 100.001}, perfect, "b")
    previous = objective(m, metrics, "z")
    for key in ("length", "crossings", "bends"):
        metrics["metrics"][key]["spread"] -= 1
        new = objective(m, metrics, "z")
        assert new < previous
        previous = new
    assert objective(m, metrics, "a") < objective(m, metrics, "z")
    shorter = {**m, "routes": [{"length": 99}]}
    assert objective(shorter, metrics, "z") < previous


def test_equalization_fixed_bounds_and_residual(tmp_path):
    cfg = Config(active_ports=16, equalize=True)
    choice = dict(id="room", gap=1.4, row_order="normal", pad=1.0, corridor=1.0)
    lib, m = build_layout(cfg, choice)
    bounds = list(m["die_bbox"])
    s = Network(cfg).solve(enumerate(range(16)))
    report = apply_equalization(lib, m, s)
    assert m["die_bbox"] == bounds and report["die_bounds_preserved"]
    assert any(c["added_um"] > 0 for c in report["changes"])
    assert 0 < report["residual_spread_um"] < report["before_spread_um"]
    verify_manifest(m)
    names = lib.write_gds(m["top"], tmp_path / "matched.gds")
    verify_gds(tmp_path / "matched.gds", m, names)
    lib, m = build_layout(cfg)
    report = apply_equalization(lib, m, s)
    assert report["residual_spread_um"] > 0


def test_bundle_baseline_fallback_and_repeatability(tmp_path):
    cfg = Config(active_ports=4, max_candidates=1)
    a = generate(cfg, tmp_path / "a", [(0, 3)])
    b = generate(cfg, tmp_path / "b", [(0, 3)])
    assert a["normalized_hash"] == b["normalized_hash"]
    assert a["uniformity"] == b["uniformity"] and a["realized"] == b["realized"]
    assert not a["baseline_comparison"]["improvement_found"]
    verify_bundle(tmp_path / "a")
    assert set(p.name for p in (tmp_path / "a").iterdir()) == {
        "config.json",
        "manifest.json",
        "network.json",
        "settings.json",
        "cell_names.json",
        "pads.csv",
        "ports.csv",
        "layout.gds",
        "preview.png",
        "detail.png",
        "report.json",
    }


def test_candidate_provenance_and_failure(tmp_path):
    cfg = Config(active_ports=4)
    assert candidates(cfg) == candidates(cfg)
    assert candidates(cfg)[0]["baseline"]
    bad = replace(cfg, insulated_m2_overpasses=False)
    with pytest.raises(ValueError, match="baseline"):
        generate(bad, tmp_path, [(0, 0)])
    report = json.loads((tmp_path / "report.json").read_text())
    assert not report["success"] and all(c["reason"] for c in report["candidates"])
    assert not (tmp_path / "layout.gds").exists()
