from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest
from benes_layout.config import Config
from benes_layout.network import Network
from benes_layout.banyan_layout import build
from benes_layout.banyan_verify import verify_manifest, verify_gds


def config(n=5, pitch=34):
    return replace(
        Config.load("examples/benes/pruned-banyan/n100.json"),
        active_ports=n,
        internal_ports=1 << (n - 1).bit_length(),
        input_map=None,
        output_map=None,
        lane_pitch=pitch,
        mzi_height=2 * pitch,
        terminal_offsets=(pitch / 2,) * 2,
    )


@pytest.mark.parametrize(
    "n,pitch,side", [(5, 34, "R"), (7, 35, "L"), (12, 34, "R"), (13, 35, "L")]
)
def test_physical_roundtrip(tmp_path, n, pitch, side):
    cfg = config(n, pitch)
    net = Network(cfg)
    lib, m = build(cfg, dict(id="test", exits=side * net.depth, pad_phase=0))
    checks = verify_manifest(m)
    names = lib.write_gds(m["top"], tmp_path / "layout.gds")
    checks.update(verify_gds(tmp_path / "layout.gds", m, names))
    assert checks["electrical_nets"] == len(net.switches) + 1
    assert checks["crossings"] == net.export()["graph_crossings"]
    assert len(m["terminations"]) == len(net.terminations)
    assert len(m["interfaces"]) == 2 * n
    assert all(
        c["metadata"].get("reflectionless") is False
        for c in m["cells"].values()
        if c["kind"] == "termination"
    )


@pytest.mark.parametrize("inverse", [False, True])
@pytest.mark.parametrize(
    "active", [(0, 1, 2, 3, 4, 5, 6, 7), (1,), (2, 3), (1, 2, 4), (0, 7), ()]
)
def test_masked_shuffle(inverse, active):
    from benes_layout.geometry import Library, point
    from benes_layout.banyan_geometry import masked_shuffle
    from benes_layout.verify import optical_objects, cell_geometries
    from benes_layout.interstage_verify import (
        verify_arc_ports,
        verify_segment,
        verify_crossing,
    )
    from collections import Counter
    from math import hypot

    lib = Library(config(8))
    c = masked_shuffle(lib, 8, active, inverse)
    assert masked_shuffle(lib, 8, active, inverse) is c
    assert masked_shuffle(lib, 8, tuple(set(range(8)) - set(active)), inverse) is not c
    cells = lib.export()
    used = Counter()
    for t in c.tracks:
        at = c.ports[t["ports"][0]][:2]
        direction = 0
        for p in t["pieces"]:
            child = cells[p["cell"]]
            angle = p["angle"]
            a = point(p["x"], p["y"], angle, child["ports"][p["entry"]])
            b = point(p["x"], p["y"], angle, child["ports"][p["exit"]])
            assert hypot(a[0] - at[0], a[1] - at[1]) <= 0.002
            incoming = (child["ports"][p["entry"]][2] + angle + 180) % 360
            assert abs((incoming - direction + 180) % 360 - 180) < 0.01
            direction = (child["ports"][p["exit"]][2] + angle) % 360
            at = b
            used[p["cell"], p["x"], p["y"], angle] += 1
            if child["kind"] == "bend":
                verify_arc_ports(child, lib.cfg)
            elif child["kind"] == "segment":
                verify_segment(child, lib.cfg)
            elif child["kind"] == "crossing":
                verify_crossing(child, lib.cfg)
        end = c.ports[t["ports"][1]]
        assert hypot(at[0] - end[0], at[1] - end[1]) <= 0.002
    objects = optical_objects(dict(cells=cells, top=c.name, config=lib.cfg.to_dict()))
    assert Counter(objects) == Counter({k: 1 for k in used})
    assert all(
        v == 2 if cells[k[0]]["kind"] == "crossing" else v == 1 for k, v in used.items()
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_term",
        "duplicate_term",
        "rotated_term",
        "moved_term",
        "edge",
        "crossing",
        "radius",
        "ghost",
    ],
)
def test_optical_faults(fault):
    _, m = build(config())
    if fault == "missing_term":
        m["terminations"].pop()
    elif fault == "duplicate_term":
        m["terminations"].append(deepcopy(m["terminations"][0]))
    elif fault == "rotated_term":
        m["terminations"][0]["angle"] = 180
    elif fault == "moved_term":
        m["terminations"][0]["x"] += 1
    elif fault == "edge":
        m["routes"][0]["dest"] ^= 1
    elif fault == "crossing":
        c = next(c for c in m["cells"].values() if c["kind"] == "crossing")
        c["tracks"][0]["ports"] = ["w", "n"]
    elif fault == "radius":
        c = next(c for c in m["cells"].values() if c["kind"] == "bend")
        c["metadata"]["arc"]["radius"] = 19
    else:
        c = next(c for c in m["cells"].values() if c["kind"] == "crossing")
        m["cells"]["INTERSTAGE"]["refs"].append(dict(cell=c["name"], x=0, y=0, angle=0))
    with pytest.raises(ValueError):
        verify_manifest(m)


@pytest.mark.parametrize(
    "fault",
    [
        "ground_open",
        "signal_ground_short",
        "missing_via",
        "duplicate_via",
        "floating",
        "pad_spacing",
    ],
)
def test_electrical_faults(tmp_path, fault):
    from benes_layout.geometry import rectangle

    lib, m = build(config())
    if fault == "ground_open":
        lib.cells["GROUND"].polygons.pop(0)
    elif fault == "signal_ground_short":
        i = m["instances"][0]
        x, y = i["x"], i["y"]
        lib.poly(lib.cells["GROUND"], "M1", rectangle(x + 500, y - 5, x + 510, y + 20))
    elif fault in ("missing_via", "duplicate_via"):
        c = next(c for c in lib.cells.values() if c.kind == "ground_column")
        if fault == "missing_via":
            c.refs.pop()
        else:
            c.refs.append(deepcopy(c.refs[0]))
    elif fault == "floating":
        lib.poly(lib.cells["GROUND"], "M2", rectangle(1, 0, 8, 7))
    else:
        pads = lib.cells["NORTH_PADS"].refs
        pads[1]["x"] = pads[0]["x"] + 61
        pads[1]["y"] = pads[0]["y"]
    m["cells"] = lib.export()
    names = lib.write_gds(m["top"], tmp_path / "fault.gds")
    with pytest.raises(ValueError):
        verify_manifest(m)
        verify_gds(tmp_path / "fault.gds", m, names)
