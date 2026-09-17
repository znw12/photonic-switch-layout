"""Physical tests for multirow pads and folded, rotated Beneš stages."""

import pytest

from benes_layout.config import Config
from benes_layout.layout import build_layout
from benes_layout.verify import (
    verify_manifest,
    verify_gds,
    VerificationError,
    normalized_hash,
)
from benes_layout.workflow import verify_bundle
from benes_layout.pad_routing import fanout_levels
from benes_layout.cli import main


@pytest.mark.parametrize(
    "override",
    [
        dict(pad_rows=0),
        dict(pad_rows=4),
        dict(pad_rows=True),
        dict(fold_bands=2),
        dict(fold_bands=15),
        dict(fold_bands=3),
        dict(pad_rows=2, pad_row_pitch=62),
        dict(pad_rows=2, fold_bands=3, bundle_pitch=5),
        dict(pad_rows=2, fold_bands=3, fold_gap=30),
    ],
)
def test_invalid_parameters(override):
    with pytest.raises(ValueError):
        Config(**override)


@pytest.mark.parametrize(
    "n,rows,bands,order",
    [
        (1, 2, 1, "normal"),
        (4, 3, 1, "normal"),
        (5, 2, 3, "normal"),
        (5, 3, 3, "reverse"),
        (16, 3, 5, "normal"),
    ],
)
def test_physical_small(tmp_path, n, rows, bands, order):
    cfg = Config(active_ports=n, pad_rows=rows, fold_bands=bands)
    choice = dict(id="test", gap=1.0, row_order=order, pad=1.0, corridor=1.0)
    lib, m = build_layout(cfg, choice)
    checks = verify_manifest(m)
    path = tmp_path / "layout.gds"
    names = lib.write_gds(m["top"], path)
    result = verify_gds(path, m, names)
    assert checks["switch_depth_min"] == checks["switch_depth_max"]
    assert result["via_count"] == 3 * len(m["electrical"])
    assert len(m["bands"]) == bands
    assert all(
        len({e["pad"][1] for e in m["electrical"] if e["side"] == side})
        == min(rows, len(m["instances"]))
        for side in ("north", "south")
    )
    if bands > 1:
        assert any(i["angle"] == 180 for i in m["instances"])
        assert all(
            c["metadata"]["arc"]["radius"] >= 20
            for c in m["cells"].values()
            if c["kind"] == "turn"
        )
        assert "CROSSING" in m["cells"]
    _, again = build_layout(cfg, choice)
    assert normalized_hash(m) == normalized_hash(again)


@pytest.mark.parametrize(
    "defect", ["rotation", "row", "turn_radius", "fan_metric", "fan_gap"]
)
def test_folded_optical_faults(defect):
    _, m = build_layout(Config(active_ports=5, pad_rows=3, fold_bands=3))
    if defect == "rotation":
        next(i for i in m["instances"] if i["angle"] == 180)["angle"] = 0
    elif defect == "row":
        m["electrical"][0]["pad"][1] = m["electrical"][1]["pad"][1] + 1
    elif defect == "turn_radius":
        next(c for c in m["cells"].values() if c["kind"] == "turn")["metadata"]["arc"][
            "radius"
        ] = 19
    elif defect == "fan_metric":
        next(c for c in m["cells"].values() if c["kind"] == "fan_lane")["tracks"][0][
            "length"
        ] += 1
    else:
        next(
            part
            for r in m["routes"]
            for part in r["pieces"]
            if m["cells"][part["cell"]]["kind"] == "fan_lane"
        )["x"] += 1
    with pytest.raises(VerificationError):
        verify_manifest(m)


@pytest.mark.parametrize("defect", ["pad_via", "underpad_short", "overpass"])
def test_multirow_electrical_faults(tmp_path, defect):
    lib, m = build_layout(Config(active_ports=5, pad_rows=3, fold_bands=3))
    e = m["electrical"][0]
    cell = lib.cells[e["cell"]]
    if defect == "pad_via":
        cell.refs.pop()
    elif defect == "underpad_short":
        # M1 stems may pass below other M2 pads only when there is no joining via.
        neighbor = next(
            v
            for v in m["electrical"]
            if v["side"] == e["side"]
            and v["pad_column"] == e["pad_column"]
            and v["pad_row"] > e["pad_row"]
        )
        lib.ref(cell, lib.via(), neighbor["vias"][-1][0], e["pad"][1])
    else:
        m["overpasses"] = []
    m["cells"] = lib.export()
    path = tmp_path / "bad.gds"
    names = lib.write_gds(m["top"], path)
    with pytest.raises(VerificationError):
        verify_gds(path, m, names)


def test_fanout_dag_and_cycle():
    levels = fanout_levels([0, 20, 40], [10, 30, 50], 5)
    assert len(levels) == 3 and min(levels) >= 0
    with pytest.raises(ValueError, match="ordering"):
        fanout_levels([30, 0], [0, 30], 5)


def test_cli_bundle(tmp_path):
    path = tmp_path / "bundle"
    assert (
        main(
            [
                "generate",
                "--n",
                "5",
                "--pad-rows",
                "3",
                "--fold-bands",
                "3",
                "--candidates",
                "1",
                "--out",
                str(path),
            ]
        )
        == 0
    )
    assert verify_bundle(path)["electrical_extraction_passed"]
    assert main(["compare", str(path), "--out", str(tmp_path / "comparison")]) == 0
    import json

    result = json.loads((tmp_path / "comparison" / "comparison.json").read_text())
    assert result["results"][0]["pad_rows"] == 3
    assert result["results"][0]["pareto_width_area"]
    assert (
        main(["generate", "--pad-rows", "4", "--out", str(tmp_path / "invalid")]) == 2
    )
