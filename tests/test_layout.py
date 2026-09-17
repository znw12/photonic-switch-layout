import copy
from dataclasses import replace
import json
import pytest

from waksman_layout.config import Config
from waksman_layout.geometry import rectangle
from waksman_layout.layout import build_layout, RoutingError
from waksman_layout.verify import (
    verify_manifest,
    verify_gds,
    VerificationError,
    normalized_hash,
)


@pytest.mark.parametrize("n", [1, 3, 4, 5, 16, 25])
def test_geometric_readback(tmp_path, n):
    lib, m = build_layout(Config(n=n))
    verify_manifest(m)
    path = tmp_path / "layout.gds"
    names = lib.write_gds("CHIP", path)
    r = verify_gds(path, m, names)
    assert r["via_count"] == len(m["electrical"])


def test_replacement_and_stable_ids():
    cfg = Config(n=4)
    _, a = build_layout(cfg)
    _, b = build_layout(replace(cfg, mzi_length=1200, terminal_offsets=(25.0, 45.0)))
    assert [i["id"] for i in a["instances"]] == [i["id"] for i in b["instances"]]

    def invalid(lib):
        c = lib.mzi()
        c.ports.pop("i1")
        return c

    with pytest.raises(ValueError, match="four optical ports"):
        build_layout(cfg, mzi_factory=invalid)


def test_bounded_failure():
    with pytest.raises(RoutingError, match="max_swap_columns"):
        build_layout(Config(n=16, max_swap_columns=1))
    with pytest.raises(RoutingError, match="overpasses"):
        build_layout(Config(n=4, insulated_m2_overpasses=False))


def test_repeatable_and_pad_budget():
    cfg = Config(n=100)
    _, a = build_layout(cfg)
    _, b = build_layout(cfg)
    assert normalized_hash(a) == normalized_hash(b)
    assert len(a["electrical"]) == 1146
    assert len(a["instances"]) == 573


@pytest.mark.parametrize("defect", ["gap", "wrong_crossing", "radius", "intersection"])
def test_optical_defects(defect):
    lib, m = build_layout(Config(n=4))
    if defect == "gap":
        m["routes"][0]["pieces"][0]["x"] += 1
    elif defect == "wrong_crossing":
        m["cells"]["CROSSING"]["metadata"]["through"] = [["w", "n"], ["s", "e"]]
    elif defect == "radius":
        m["cells"]["SWAP"]["tracks"][0]["min_radius"] = 10
    else:
        # An extra branch on a real straight segment crosses another channel;
        # endpoints/manifest still look correct, so spatial checking must fail.
        c = m["cells"]["WG_100p000"]
        c["polygons"].append({"layer": "WG", "points": rectangle(50, -1, 51, 160)})
    with pytest.raises(VerificationError):
        verify_manifest(m)


@pytest.mark.parametrize("defect", ["missing_via", "short", "enclosure"])
def test_actual_conductor_defects(tmp_path, defect):
    lib, m = build_layout(Config(n=4))
    if defect == "missing_via":
        lib.cells["E_0"].refs = []
    elif defect == "enclosure":
        for p in lib.cells["VIA"].polygons:
            if p["layer"] == "M1":
                p["points"] = rectangle(-2.5, -2.5, 2.5, 2.5)
    else:
        a, b = m["electrical"][:2]
        x = min(a["via"][0], b["via"][0])
        lib.poly(
            lib.cells["E_0"],
            "M1",
            rectangle(x - 2.5, min(a["y"], b["y"]), x + 2.5, max(a["y"], b["y"])),
        )
    # The manifest intentionally agrees with the modified polygons: actual
    # conductor extraction (not a file checksum) must still catch the defect.
    m["cells"] = lib.export()
    path = tmp_path / "bad.gds"
    names = lib.write_gds("CHIP", path)
    with pytest.raises(VerificationError, match="open|short|enclosure"):
        verify_gds(path, m, names)


def test_export_defect(tmp_path):
    import klayout.db as kdb

    lib, m = build_layout(Config(n=4))
    path = tmp_path / "bad.gds"
    names = lib.write_gds("CHIP", path)
    ly = kdb.Layout()
    ly.read(str(path))
    cell = ly.cell(names["WG_100p000"])
    cell.shapes(ly.layer(1, 0)).clear()
    ly.write(str(path))
    with pytest.raises(VerificationError, match="polygon mismatch"):
        verify_gds(path, m, names)


def test_one_terminal_profile(tmp_path):
    cfg = Config(n=4, terminal_names=("drive",), terminal_offsets=(40.0,))
    lib, m = build_layout(cfg)
    assert len(m["electrical"]) == 5
    verify_manifest(m)
    path = tmp_path / "one.gds"
    names = lib.write_gds("CHIP", path)
    verify_gds(path, m, names)


def test_split_bank_profile(tmp_path):
    lib, m = build_layout(Config(n=16, pad_assignment="split"))
    verify_manifest(m)
    path = tmp_path / "split.gds"
    names = lib.write_gds("CHIP", path)
    verify_gds(path, m, names)
