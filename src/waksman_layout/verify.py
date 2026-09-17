"""Independent graph, spatial, and GDS-readback checks for the demonstrator.

These are explicit placeholder-technology checks, not a foundry DRC deck.
Readback reconciles cell polygons/transforms and extracts actual conductor
regions rather than trusting successful-router flags.
"""

from collections import Counter
from functools import lru_cache
from math import hypot
import hashlib
import json

from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
from shapely.affinity import translate, rotate
from shapely.strtree import STRtree

from .config import Config
from .network import Network
from .layout import terminal_target


class VerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def cell_geometries(cells):
    @lru_cache(None)
    def shape(name, layer):
        c = cells[name]
        polys = [Polygon(p["points"]) for p in c["polygons"] if p["layer"] == layer]
        for ref in c["refs"]:
            g = shape(ref["cell"], layer)
            if not g.is_empty:
                polys.append(
                    translate(
                        rotate(g, ref["angle"], origin=(0, 0)), ref["x"], ref["y"]
                    )
                )
        return unary_union(polys)

    return shape


def verify_manifest(m):
    cfg = Config(**m["config"])
    net = Network(cfg.n)
    cells = m["cells"]
    tol = cfg.grid * 2
    require(len(m["instances"]) == len(net.switches), "MZI instance count mismatch")
    placements = {i["id"]: i for i in m["instances"]}
    require(
        set(placements) == set(net.switches), "MZI identifiers differ from topology"
    )
    expected_sources = {f"in:{i}" for i in range(cfg.n)} | {
        f"{sid}:o{p}" for sid in net.switches for p in range(2)
    }
    require(
        {r["source"] for r in m["routes"]} == expected_sources,
        "missing or extra optical route",
    )
    require(len(m["routes"]) == len(expected_sources), "duplicate optical route")

    def endpoint(port):
        if port.startswith("in:"):
            return (0, int(port[3:]) * cfg.lane_pitch)
        if port.startswith("out:"):
            return (m["width"] - 2 * cfg.margin, int(port[4:]) * cfg.lane_pitch)
        sid, pin = port.rsplit(":", 1)
        inst = placements[sid]
        p = cells[inst["cell"]]["ports"][pin]
        return (inst["x"] + p[0], inst["y"] + p[1])

    def close(a, b):
        return hypot(a[0] - b[0], a[1] - b[1]) <= tol

    objects = {}
    for route in m["routes"]:
        require(
            route["target"] == terminal_target(net, route["source"]),
            f"wrong destination: {route['source']}",
        )
        last = endpoint(route["source"])
        require(
            close(last, route["start"]), f"source location mismatch: {route['source']}"
        )
        length = 0
        crossings = 0
        for part in route["pieces"]:
            c = cells[part["cell"]]
            pair = [part["entry"], part["exit"]]
            tracks = [t for t in c["tracks"] if t["ports"] == pair]
            require(
                len(tracks) == 1, f"invalid component transfer: {part['cell']} {pair}"
            )
            if c["kind"] == "swap":
                require(
                    pair in (["w0", "e1"], ["w1", "e0"]),
                    "swapped crossing through-pair",
                )
                require(tracks[0]["min_radius"] >= cfg.radius, "undersized bend")
                crossings += 1
            p = c["ports"][part["entry"]]
            q = c["ports"][part["exit"]]
            start = (part["x"] + p[0], part["y"] + p[1])
            end = (part["x"] + q[0], part["y"] + q[1])
            require(
                close(last, start),
                f"optical gap on {route['source']} at {start}; previous {last}",
            )
            last = end
            length += tracks[0]["length"]
            objects[(part["cell"], part["x"], part["y"])] = part
        require(
            close(last, endpoint(route["target"])),
            f"unconnected destination: {route['target']}",
        )
        require(close(last, route["end"]), "route end coordinate mismatch")
        require(
            abs(length - route["length"]) < tol and crossings == route["crossings"],
            "route metrics mismatch",
        )
    if "CROSSING" in cells:
        c = cells["CROSSING"]
        require(
            c["metadata"]["through"] == [["w", "e"], ["s", "n"]],
            "crossing mapping must join opposite ports",
        )
    if "SWAP" in cells:
        c = cells["SWAP"]
        width = c["ports"]["e0"][0]
        p = cfg.lane_pitch
        r = cfg.radius
        # Inspect the actual annular arc vertices, not only radius metadata.
        for index, (cx, cy) in [
            (0, (0, r)),
            (1, (0, p - r)),
            (6, (width, p - r)),
            (7, (width, r)),
        ]:
            for x, y in c["polygons"][index]["points"]:
                distance = hypot(x - cx, y - cy)
                require(
                    min(
                        abs(distance - (r - cfg.wg_width / 2)),
                        abs(distance - (r + cfg.wg_width / 2)),
                    )
                    <= tol,
                    "bend geometry does not match the declared minimum radius",
                )
    if "MZI" in cells:
        c = cells["MZI"]
        require(
            c["metadata"]["bar"] == [["i0", "o0"], ["i1", "o1"]]
            and c["metadata"]["cross"] == [["i0", "o1"], ["i1", "o0"]],
            "MZI transfer contract mismatch",
        )
    shape = cell_geometries(cells)
    # Check actual primitive polygons cover their declared interfaces, including
    # the snapped connections inside the explicit 45-degree swap tile.
    for name, c in cells.items():
        if c["kind"] not in ("straight", "swap", "mzi", "crossing"):
            continue
        g = shape(name, "WG")
        require(g.is_valid, f"invalid waveguide polygon in {name}")
        for pname, p in c["ports"].items():
            if pname in cfg.terminal_names:
                continue
            require(
                g.buffer(tol).covers(Point(p[:2])),
                f"geometry does not reach {name}:{pname}",
            )
        require(
            g.geom_type == "Polygon", f"disconnected optical geometry inside {name}"
        )
    # Spatial index of route cells and device cells. Interior coupling/crossing
    # is local to each declared cell; it never exempts collisions between cells.
    geoms = []
    ports = []
    ids = []
    for (name, x, y), part in objects.items():
        geoms.append(translate(shape(name, "WG"), x, y))
        ids.append(f"{name}@{x},{y}")
        ports.append(
            {
                (round(x + p[0], 3), round(y + p[1], 3))
                for p in cells[name]["ports"].values()
            }
        )
    for sid, inst in placements.items():
        name = inst["cell"]
        x = inst["x"]
        y = inst["y"]
        geoms.append(translate(shape(name, "WG"), x, y))
        ids.append(sid)
        ports.append(
            {
                (round(x + p[0], 3), round(y + p[1], 3))
                for k, p in cells[name]["ports"].items()
                if k not in cfg.terminal_names
            }
        )
    tree = STRtree(geoms)
    for i, g in enumerate(geoms):
        for j in tree.query(g, predicate="dwithin", distance=cfg.wg_clearance - tol):
            j = int(j)
            if j <= i:
                continue
            if ports[i] & ports[j]:
                require(
                    g.intersection(geoms[j]).area < cfg.wg_width * tol * 4,
                    f"overlapping connected optical cells: {ids[i]}, {ids[j]}",
                )
            else:
                raise VerificationError(
                    f"optical clearance/intersection: {ids[i]}, {ids[j]}"
                )
    expected_nets = {
        f"{sid}:{name}" for sid in net.switches for name in cfg.terminal_names
    }
    require(
        {e["net"] for e in m["electrical"]} == expected_nets,
        "missing/extra terminal-pad net",
    )
    require(len(m["electrical"]) == len(expected_nets), "duplicate electrical net")
    die = box(*m["die_bbox"])
    for e in m["electrical"]:
        require(e["side"] in ("north", "south"), "pad placed on wrong side")
        expected_y = (
            (cfg.n - 1) * cfg.lane_pitch + cfg.margin + cfg.pad_size / 2
            if e["side"] == "north"
            else -cfg.margin - cfg.pad_size / 2
        )
        require(abs(e["pad"][1] - expected_y) < tol, "pad not in its north/south bank")
        px, py = e["pad"]
        require(
            die.covers(
                box(
                    px - cfg.pad_size / 2,
                    py - cfg.pad_size / 2,
                    px + cfg.pad_size / 2,
                    py + cfg.pad_size / 2,
                )
            ),
            "pad outside die",
        )
    for g in geoms:
        require(die.buffer(tol).covers(g), "optical geometry outside die")
    return {
        "logical_edges": len(m["routes"]),
        "optical_objects": len(geoms),
        "mzi_count": len(placements),
        "electrical_nets": len(expected_nets),
        "manifest_geometry_passed": True,
    }


def _kpoly(points, dbu, kdb):
    return kdb.Polygon([kdb.Point(round(x / dbu), round(y / dbu)) for x, y in points])


def _region_shapes(region, dbu):
    shapes = []
    for p in region.each():
        hull = [(v.x * dbu, v.y * dbu) for v in p.each_point_hull()]
        holes = [
            [(v.x * dbu, v.y * dbu) for v in p.each_point_hole(i)]
            for i in range(p.holes())
        ]
        shapes.append(Polygon(hull, holes))
    return shapes


def verify_gds(path, m, cell_names):
    import klayout.db as kdb

    cfg = Config(**m["config"])
    ly = kdb.Layout()
    ly.read(str(path))
    dbu = ly.dbu
    require(abs(dbu - cfg.grid) < 1e-12, "GDS database grid mismatch")
    require(len(ly.top_cells()) == 1, "GDS must have a single top cell")
    top = ly.top_cell()
    require(top.name == cell_names[m["top"]], "wrong GDS top cell")
    require(set(cell_names) == set(m["cells"]), "GDS cell mapping incomplete")
    actual_cells = {cell.name: cell for cell in ly.each_cell()}
    require(
        set(actual_cells) == set(cell_names.values()), "unexpected or missing GDS cells"
    )
    for name, model in m["cells"].items():
        cell = actual_cells[cell_names[name]]
        for layer, pair in cfg.layers.items():
            expected = kdb.Region()
            for p in model["polygons"]:
                if p["layer"] == layer:
                    expected.insert(_kpoly(p["points"], dbu, kdb))
            actual = kdb.Region(cell.shapes(ly.layer(*pair)))
            require(
                (expected ^ actual).is_empty(),
                f"GDS polygon mismatch: {name}/{layer} (gap, short, enclosure, or shape defect)",
            )
        expected_refs = Counter(
            (
                cell_names[r["cell"]],
                round(r["x"], 3),
                round(r["y"], 3),
                round(r["angle"] % 360, 6),
            )
            for r in model["refs"]
        )
        actual_refs = Counter()
        for instance in cell.each_inst():
            for tr in instance.cell_inst.each_cplx_trans():
                require(
                    not tr.is_mirror() and abs(tr.mag - 1) < 1e-12,
                    "unsupported instance transform",
                )
                actual_refs[
                    (
                        ly.cell(instance.cell_index).name,
                        round(tr.disp.x * dbu, 3),
                        round(tr.disp.y * dbu, 3),
                        round(tr.angle % 360, 6),
                    )
                ] += 1
        require(
            actual_refs == expected_refs, f"GDS hierarchy/transform mismatch: {name}"
        )
    # Extract actual metal connected components from the reopened GDS.
    regions = {
        layer: kdb.Region(top.begin_shapes_rec(ly.layer(*cfg.layers[layer]))).merged()
        for layer in ("M1", "M2", "VIA")
    }
    parts = {layer: _region_shapes(regions[layer], dbu) for layer in regions}
    die = box(*m["die_bbox"])
    for layer, shapes in parts.items():
        for shape in shapes:
            require(die.buffer(dbu * 2).covers(shape), f"{layer} outside die")
    trees = {layer: STRtree(parts[layer]) for layer in parts}
    n1 = len(parts["M1"])
    n2 = len(parts["M2"])
    parent = list(range(n1 + n2))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(a, b):
        parent[root(b)] = root(a)

    for via in parts["VIA"]:
        hits = {}
        for layer in ("M1", "M2"):
            hits[layer] = [
                int(i)
                for i in trees[layer].query(via)
                if parts[layer][int(i)]
                .buffer(dbu * 0.1)
                .covers(via.buffer(cfg.via_enclosure, join_style=2))
            ]
            require(
                len(hits[layer]) == 1,
                f"via missing conductor or insufficient {layer} enclosure",
            )
        join(hits["M1"][0], n1 + hits["M2"][0])

    def conductor(layer, point):
        ids = [int(i) for i in trees[layer].query(Point(point), predicate="intersects")]
        require(len(ids) == 1, f"terminal/pad open at {point} on {layer}")
        return ids[0] + (n1 if layer == "M2" else 0)

    assigned = {}
    for e in m["electrical"]:
        a = conductor("M1", (e["x"], e["y"]))
        b = conductor("M2", e["pad"])
        require(root(a) == root(b), f"electrical open: {e['net']}")
        r = root(a)
        require(
            r not in assigned, f"electrical short: {e['net']} and {assigned.get(r)}"
        )
        assigned[r] = e["net"]
    require(
        len({root(i) for i in range(n1 + n2)}) == len(assigned),
        "unassigned electrical conductor island",
    )
    require(len(parts["VIA"]) == len(m["electrical"]), "missing or extra vias")
    for layer in ("M1", "M2"):
        for i, g in enumerate(parts[layer]):
            for j in trees[layer].query(
                g, predicate="dwithin", distance=cfg.metal_spacing - dbu * 2
            ):
                require(int(j) == i, f"{layer} conductor spacing violation")
    # Validate metal/optical interaction against explicit local exceptions.
    wg = cell_geometries(m["cells"])
    route_optics = wg("OPTICAL_ROUTING", "WG")
    overpass_boxes = [
        box(
            w["x"] - cfg.metal_width / 2 - cfg.optical_metal_clearance,
            w["y"] - cfg.wg_width / 2 - cfg.optical_metal_clearance,
            w["x"] + cfg.metal_width / 2 + cfg.optical_metal_clearance,
            w["y"] + cfg.wg_width / 2 + cfg.optical_metal_clearance,
        )
        for w in m["overpasses"]
    ]
    # M1 device interiors are approved electrode zones; outside, it must clear
    # routing waveguides. M2 intersects waveguides only in reserved windows.
    metal1 = unary_union(parts["M1"])
    metal2 = unary_union(parts["M2"])
    require(
        metal1.distance(route_optics) >= cfg.optical_metal_clearance - dbu * 2
        or metal1.is_empty,
        "M1 violates optical routing clearance",
    )
    if not metal2.is_empty:
        conflict = metal2.intersection(
            route_optics.buffer(cfg.optical_metal_clearance - dbu * 2)
        )
        require(
            conflict.difference(unary_union(overpass_boxes)).area < dbu * dbu,
            "unapproved M2 optical overlap",
        )
    for via in parts["VIA"]:
        require(
            via.distance(route_optics)
            >= cfg.optical_metal_clearance + cfg.via_enclosure - dbu * 2,
            "via in optical keepout",
        )
    return {
        "gds_readback_passed": True,
        "electrical_extraction_passed": True,
        "metal_regions": {"M1": n1, "M2": n2},
        "via_count": len(parts["VIA"]),
        "gds_cells": len(actual_cells),
    }


def normalized_hash(m):
    stable = {k: v for k, v in m.items() if k not in ("timings", "versions")}
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
