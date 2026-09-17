"""Four-row placement, independent fault detection and small physical bundles."""

import csv
from dataclasses import replace
import json

import pytest

from benes_layout.config import Config
from benes_layout.layout import build_layout
from benes_layout.pad_routing import pad_slots
from benes_layout.metrics import pad_banks
from benes_layout.geometry import rectangle
from benes_layout.verify import verify_manifest, verify_gds, VerificationError
from benes_layout.workflow import verify_bundle
from benes_layout.cli import main


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, 0.0005, 34])
def test_invalid_stagger(value):
    with pytest.raises(ValueError, match="stagger"):
        Config(pad_rows=4, pad_row_stagger=value)


@pytest.mark.parametrize("rows,bands", [(1, 1), (2, 1), (3, 1), (4, 3)])
def test_stagger_scope(rows, bands):
    with pytest.raises(ValueError):
        Config(pad_rows=rows, fold_bands=bands, pad_row_stagger=25)


def test_slot_extents_and_partial_columns():
    cfg = Config(pad_rows=4, pad_row_stagger=25)
    slots, bounds = pad_slots(cfg, 832, 0, 100)
    assert bounds == [-10417.5, 10417.5]
    assert [sum(s["row"] == r for s in slots) for r in range(4)] == [208] * 4
    for count in (1, 2, 3, 5, 6, 7):
        slots, bounds = pad_slots(cfg, count, 0, 100)
        assert len(slots) == count
        assert {(s["column"], s["row"]) for s in slots} == {
            (i // 4, i % 4) for i in range(count)
        }
        assert bounds[0] == min(s["px"] for s in slots) - 30
        assert bounds[1] == max(s["px"] for s in slots) + 30
        assert bounds[0] == -bounds[1]


@pytest.mark.parametrize(
    "n,offset", [(1, 0), (1, 25), (4, 25), (5, 0), (5, 25), (16, 25)]
)
def test_four_row_physical(tmp_path, n, offset):
    lib, m = build_layout(Config(active_ports=n, pad_rows=4, pad_row_stagger=offset))
    verify_manifest(m)
    path = tmp_path / "layout.gds"
    names = lib.write_gds(m["top"], path)
    checks = verify_gds(path, m, names)
    assert checks["via_count"] == 3 * len(m["electrical"])
    assert all(c["kind"] != "turn" for c in m["cells"].values())
    for side in ("north", "south"):
        bank = {
            (e["pad_column"], e["pad_row"]): e
            for e in m["electrical"]
            if e["side"] == side
        }
        for (col, row), e in bank.items():
            if (col, row + 1) in bank:
                b = bank[col, row + 1]
                assert b["pad"][0] - e["pad"][0] == pytest.approx(offset)
                assert b["pad"][1] - e["pad"][1] == pytest.approx(
                    100 if side == "north" else -100
                )
    for bank in pad_banks(m).values():
        assert bank["height_um"] == 60 + 100 * (min(4, len(m["instances"])) - 1)


@pytest.mark.parametrize(
    "defect", ["offset", "missing", "duplicate", "pad_shape", "bounds", "metadata"]
)
def test_pad_contract_faults(defect):
    lib, m = build_layout(Config(active_ports=5, pad_rows=4, pad_row_stagger=25))
    e = next(e for e in m["electrical"] if e["pad_row"] == 3)
    if defect == "offset":
        e["pad"][0] += 1
        ref = next(
            r
            for r in lib.cells[e["side"].upper() + "_PADS"].refs
            if r["id"] == e["net"]
        )
        ref["x"] += 1  # Manifest and polygons agree, but the requested offset is wrong.
    elif defect == "missing":
        m["electrical"].remove(e)
    elif defect == "duplicate":
        e["pad_row"] = 2
    elif defect == "pad_shape":
        lib.cells["PAD"].polygons[0]["points"] = rectangle(-29, -30, 30, 30)
    elif defect == "bounds":
        m["die_bbox"][3] = max(v["pad"][1] for v in m["electrical"])
    else:
        e["pad_row_offset"] = 0
    m["cells"] = lib.export()
    with pytest.raises(VerificationError):
        verify_manifest(m)


@pytest.mark.parametrize("defect", ["missing_via", "foreign_pad_via", "spacing"])
def test_actual_metal_faults(tmp_path, defect):
    lib, m = build_layout(Config(active_ports=5, pad_rows=4, pad_row_stagger=25))
    bank = sorted(
        (e for e in m["electrical"] if e["side"] == "south"), key=lambda e: e["tx"]
    )
    e = bank[0]
    cell = lib.cells[e["cell"]]
    if defect == "missing_via":
        cell.refs.pop()
    elif defect == "foreign_pad_via":
        other = next(
            v for v in bank if v["pad_column"] == e["pad_column"] and v["pad_row"] == 1
        )
        lib.ref(cell, lib.via(), other["vias"][-1][0], e["pad"][1])
    else:
        # Approach the adjacent trunk with a one-um gap, preserving connectivity.
        lib.poly(cell, "M2", rectangle(e["tx"] - 2.5, -20, bank[1]["tx"] - 3.5, -15))
    m["cells"] = lib.export()
    path = tmp_path / "bad.gds"
    names = lib.write_gds(m["top"], path)
    with pytest.raises(VerificationError):
        verify_gds(path, m, names)


def test_cli_exports_and_report_tamper(tmp_path):
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
                "--candidates",
                "1",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    assert (out / "pads_detail.png").is_file()
    rows = list(csv.DictReader((out / "pads.csv").open()))
    assert len(rows) == 40
    assert all(float(r["row_offset_um"]) == 25 * int(r["row"]) for r in rows)
    verify_bundle(out)
    report = json.loads((out / "report.json").read_text())
    report["metrics"]["pad_banks"]["north"]["width_um"] += 1
    (out / "report.json").write_text(json.dumps(report))
    with pytest.raises(VerificationError, match="pad bank report"):
        verify_bundle(out)


def test_optical_geometry_unchanged():
    cfg = Config(active_ports=5, pad_rows=3)
    _, base = build_layout(cfg)
    _, changed = build_layout(replace(cfg, pad_rows=4, pad_row_stagger=25))
    assert base["network"] == changed["network"]
    assert base["instances"] == changed["instances"]
    assert base["routes"] == changed["routes"]
    assert base["interfaces"] == changed["interfaces"]


def test_configured_pad_size_with_half_grid_edges(tmp_path):
    cfg = Config(active_ports=5, pad_rows=4, pad_row_stagger=25, pad_size=60.001)
    lib, m = build_layout(cfg)
    verify_manifest(m)
    path = tmp_path / "sized.gds"
    names = lib.write_gds(m["top"], path)
    verify_gds(path, m, names)
