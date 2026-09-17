"""Stage-local pad routing, independent defects, and tighter optical lanes."""

import csv
from dataclasses import replace
import json

import pytest

from benes_layout.cli import main
from benes_layout.config import Config
from benes_layout.geometry import rectangle
from benes_layout.layout import build_layout
from benes_layout.metrics import pad_banks
from benes_layout.verify import verify_manifest, verify_gds, VerificationError
from benes_layout.workflow import verify_bundle


def profile(n=5, pitch=60, **kwargs):
    return Config(
        active_ports=n,
        pad_rows=4,
        pad_row_stagger=25,
        pad_distribution="stage",
        lane_pitch=pitch,
        **kwargs,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pad_distribution": "invalid"},
        {"pad_distribution": "stage"},
        {"pad_distribution": "stage", "pad_rows": 3},
        {"pad_distribution": "stage", "pad_rows": 4, "fold_bands": 3},
    ],
)
def test_invalid_distribution(kwargs):
    with pytest.raises(ValueError, match="distribution"):
        Config(**kwargs)
    assert Config().pad_distribution == "central"


@pytest.mark.parametrize("n,pitch", [(1, 60), (4, 60), (5, 60), (16, 60), (5, 80)])
def test_physical_groups(tmp_path, n, pitch):
    cfg = profile(n, pitch)
    lib, m = build_layout(cfg)
    verify_manifest(m)
    path = tmp_path / "layout.gds"
    names = lib.write_gds(m["top"], path)
    checks = verify_gds(path, m, names)
    assert checks["via_count"] == 3 * len(m["electrical"])
    for side in pad_banks(m).values():
        assert len(side["groups"]) == len(m["stages"])
        for group in side["groups"]:
            assert group["pad_count"] == cfg.internal_ports // 2
            assert group["row_counts"] == [
                sum(i % 4 == r for i in range(cfg.internal_ports // 2))
                for r in range(4)
            ]


def test_optical_geometry_preserved_and_lane_compaction():
    cfg = profile(16, 80)
    _, base = build_layout(replace(cfg, pad_distribution="central"))
    _, distributed = build_layout(cfg)
    _, compact = build_layout(replace(cfg, lane_pitch=60))
    for field in ("network", "instances", "routes", "interfaces", "terminations"):
        assert base[field] == distributed[field]
    assert compact["network"] == distributed["network"]
    assert compact["crossing_count"] == distributed["crossing_count"]
    assert compact["width"] < distributed["width"]
    assert compact["height"] < distributed["height"]


@pytest.mark.parametrize(
    "defect",
    [
        "stage",
        "duplicate",
        "offset",
        "group_extent",
        "row_alignment",
        "pad_shape",
        "bounds",
    ],
)
def test_group_contract_faults(defect):
    lib, m = build_layout(profile())
    e = next(e for e in m["electrical"] if e["pad_group"] == 1 and e["pad_row"] == 1)
    if defect == "stage":
        e["pad_group"] = e["stage"] = 0
    elif defect == "duplicate":
        e["pad_row"] = 0
    elif defect == "offset":
        e["pad"][0] += 1
        ref = next(
            r
            for r in lib.cells[e["side"].upper() + "_PADS"].refs
            if r["id"] == e["net"]
        )
        ref["x"] += 1
    elif defect == "group_extent":
        m["pad_groups"][1]["x_bounds"][0] += 1
    elif defect == "row_alignment":
        for other in m["electrical"]:
            if other["side"] == e["side"] and other["pad_group"] == 1:
                other["pad"][1] += 1
    elif defect == "pad_shape":
        lib.cells["PAD"].polygons[0]["points"] = rectangle(-29, -30, 30, 30)
    else:
        m["die_bbox"][3] = max(e["pad"][1] for e in m["electrical"])
    m["cells"] = lib.export()
    with pytest.raises(VerificationError):
        verify_manifest(m)


@pytest.mark.parametrize("defect", ["missing_via", "short", "spacing"])
def test_group_gds_faults(tmp_path, defect):
    lib, m = build_layout(profile())
    bank = sorted(
        (e for e in m["electrical"] if e["side"] == "south"), key=lambda e: e["tx"]
    )
    first, second = bank[:2]
    cell = lib.cells[first["cell"]]
    if defect == "missing_via":
        cell.refs.pop()
    else:
        # A physical M2 connection or insufficient gap between adjacent trunks.
        gap = 0 if defect == "short" else 1
        lib.poly(
            cell, "M2", rectangle(first["tx"] - 2.5, -20, second["tx"] - 2.5 - gap, -15)
        )
    m["cells"] = lib.export()
    path = tmp_path / "bad.gds"
    names = lib.write_gds(m["top"], path)
    with pytest.raises(VerificationError):
        verify_gds(path, m, names)


def test_reject_groups_that_do_not_fit():
    with pytest.raises(ValueError, match="stage pad group"):
        build_layout(profile(16, pad_pitch=3000))


def test_cli_bundle_and_group_report(tmp_path):
    out = tmp_path / "bundle"
    assert (
        main(
            [
                "generate",
                "--n",
                "5",
                "--pad-rows",
                "4",
                "--pad-row-stagger",
                "25",
                "--pad-distribution",
                "stage",
                "--lane-pitch",
                "60",
                "--candidates",
                "1",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    verify_bundle(out)
    assert (out / "pads_detail.png").is_file()
    with (out / "pads.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 40
    assert {int(r["pad_group"]) for r in rows} == set(range(5))
    report = json.loads((out / "report.json").read_text())
    assert report["summary"]["lane_pitch_um"] == 60
    assert report["summary"]["pad_distribution"] == "stage"
    report["metrics"]["pad_banks"]["north"]["groups"][0]["pad_count"] += 1
    (out / "report.json").write_text(json.dumps(report))
    with pytest.raises(VerificationError, match="pad bank report"):
        verify_bundle(out)
