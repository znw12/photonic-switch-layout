"""Independent graph, spatial and readback checks for the Beneš engine."""

from collections import Counter, defaultdict
from bisect import bisect_left, bisect_right
from math import hypot, pi, sqrt

from shapely.geometry import Point, Polygon, box
from shapely.affinity import translate, rotate
from shapely.strtree import STRtree
from shapely.ops import unary_union

# These reviewed helpers only construct polygons, transform cells, and hash
# JSON; they have no architecture-specific behavior.
from waksman_layout.verify import (
    VerificationError,
    require,
    cell_geometries,
    _kpoly,
    _region_shapes,
    normalized_hash,
)
from .config import Config
from .network import Network, switch_id
from .geometry import arc_polygon, snap, rectangle, point


def verify_pad_banks(m):
    """Reconstruct the four-row placement contract independently of the router."""
    cfg = Config(**m["config"])
    if cfg.pad_rows != 4:
        return
    cells, tol = m["cells"], 2 * cfg.grid
    count = len(Network(cfg).switches)
    pitch = snap(cfg.pad_pitch * m["candidate"]["pad"])
    half = cfg.pad_size / 2
    require(
        cells["PAD"]["polygons"]
        == [
            dict(
                layer="M2",
                points=[
                    [snap(x), snap(y)] for x, y in rectangle(-half, -half, half, half)
                ],
            )
        ],
        "pad polygon differs from configured square",
    )
    all_bounds = []
    for side, sign in (("north", 1), ("south", -1)):
        bank = [e for e in m["electrical"] if e["side"] == side]
        require(len(bank) == count, "pad bank coverage mismatch")
        slots = [(e["pad_column"], e["pad_row"]) for e in bank]
        require(
            len(set(slots)) == count
            and set(slots) == {(i // 4, i % 4) for i in range(count)},
            "duplicate or missing pad slot",
        )
        origin = next(
            e["pad"] for e in bank if (e["pad_column"], e["pad_row"]) == (0, 0)
        )
        for e in bank:
            row, col = e["pad_row"], e["pad_column"]
            require(
                abs(e["pad_row_offset"] - row * cfg.pad_row_stagger) < tol,
                "pad row offset metadata mismatch",
            )
            require(
                abs(e["pad"][0] - (origin[0] + col * pitch + row * cfg.pad_row_stagger))
                < tol
                and abs(e["pad"][1] - (origin[1] + sign * row * cfg.pad_row_pitch))
                < tol,
                "pad stagger or row placement mismatch",
            )
            require(len(e["vias"]) == 3, "four-row net requires three vias")
            require(
                box(
                    e["pad"][0] - half,
                    e["pad"][1] - half,
                    e["pad"][0] + half,
                    e["pad"][1] + half,
                )
                .buffer(tol)
                .covers(
                    Point(e["vias"][-1]).buffer(
                        cfg.via_size / 2 + cfg.via_enclosure, cap_style=3
                    )
                ),
                "pad via landing outside assigned pad",
            )
        group = side.upper() + "_PADS"
        require(cells[group]["polygons"] == [], "unexpected pad group polygons")
        actual = Counter(
            (r["cell"], r["x"], r["y"], r["angle"], r["id"])
            for r in cells[group]["refs"]
        )
        expected = Counter(("PAD", *e["pad"], 0, e["net"]) for e in bank)
        require(actual == expected, "pad hierarchy differs from assigned slots")
        roots = [r for r in cells[m["top"]]["refs"] if r["cell"] == group]
        require(
            len(roots) == 1
            and [roots[0]["x"], roots[0]["y"], roots[0]["angle"]] == [0, 0, 0],
            "pad bank root transform mismatch",
        )
        bounds = [
            min(e["pad"][0] for e in bank) - half,
            min(e["pad"][1] for e in bank) - half,
            max(e["pad"][0] for e in bank) + half,
            max(e["pad"][1] for e in bank) + half,
        ]
        require(
            box(*m["die_bbox"]).buffer(tol).covers(box(*bounds)), "pad bank outside die"
        )
        all_bounds.append(bounds)
    combined = [
        min(b[0] for b in all_bounds),
        min(b[1] for b in all_bounds),
        max(b[2] for b in all_bounds),
        max(b[3] for b in all_bounds),
    ]
    require(
        all(abs(a - b) < tol for a, b in zip(combined, m["extents"]["pads"])),
        "reported pad extent mismatch",
    )


def optical_objects(m):
    """Flatten only to optical black boxes, preserving explicit crossing cells."""
    objects = []

    def visit(name, x=0, y=0, angle=0):
        c = m["cells"][name]
        if c["kind"] in (
            "straight",
            "exchange",
            "mzi",
            "termination",
            "meander",
            "fan_lane",
            "turn",
        ):
            objects.append((name, snap(x), snap(y), angle % 360))
            return
        for r in c["refs"]:
            require(r["angle"] % 90 == 0, "unexpected group rotation")
            at = point(x, y, angle, [r["x"], r["y"]])
            visit(r["cell"], *at, (angle + r["angle"]) % 360)

    visit(m["top"])
    return objects


def spatial_objects(m):
    shape = cell_geometries(m["cells"])
    objs = optical_objects(m)
    geoms, ports = [], []
    cfg = Config(**m["config"])
    for name, x, y, angle in objs:
        c = m["cells"][name]
        geoms.append(translate(rotate(shape(name, "WG"), angle, origin=(0, 0)), x, y))
        ports.append(
            {
                tuple(point(x, y, angle, v))
                for key, v in c["ports"].items()
                if key not in cfg.terminal_names
            }
        )
    return objs, geoms, ports


def verify_manifest(m):
    cfg, cells = Config(**m["config"]), m["cells"]
    verify_pad_banks(m)
    net = Network(cfg)
    tol = cfg.grid * 2
    require(
        m["network"] == net.export(),
        "complete Beneš graph differs from canonical topology",
    )
    inst = {i["id"]: i for i in m["instances"]}
    require(
        len(m["instances"]) == len(inst) == len(net.switches)
        and set(inst) == set(net.switches),
        "missing, duplicated or bypassed MZI",
    )
    require(len(m["stages"]) == net.depth, "missing stage")
    if cfg.pad_rows > 1:
        bands = m.get("bands", [])
        require(len(bands) == cfg.fold_bands, "fold band count mismatch")
        require(
            [s for b in bands for s in b["stages"]] == list(range(net.depth)),
            "fold bands must contain consecutive complete stages",
        )
        for b, band in enumerate(bands):
            require(
                band["y"] == snap(b * ((net.p - 1) * cfg.lane_pitch + cfg.fold_gap)),
                "fold band pitch mismatch",
            )
            for s in band["stages"]:
                require(
                    m["stages"][s]["band"] == b
                    and m["stages"][s]["angle"] == 180 * (b % 2),
                    "fold stage transform mismatch",
                )
    for s in range(net.depth):
        stage = [i for i in inst.values() if i["stage"] == s]
        require(
            len(stage) == net.p // 2
            and {i["row"] for i in stage} == set(range(0, net.p, 2)),
            "stage is not a complete regular array",
        )
        for i in stage:
            require(
                i.get("angle", 0) in cells[i["cell"]]["metadata"]["allowed_transforms"],
                "MZI transform not permitted by component",
            )
            require(
                net.switches[i["id"]]["stage"] == s and i["pin_flip"] in (0, 1),
                "logical-to-physical stage/pin map corrupted",
            )
            require(
                [i["x"], i["y"]]
                == point(
                    m["stages"][s]["x"],
                    m["stages"][s].get("origin_y", 0),
                    m["stages"][s].get("angle", 0),
                    [0, i["row"] * cfg.lane_pitch],
                )
                and i.get("angle", 0) == m["stages"][s].get("angle", 0),
                "instance disagrees with regular placement",
            )
    interface = {(v["side"], v["internal"]): v for v in m["interfaces"]}
    require(
        len(interface) == len(m["interfaces"]) == 2 * net.p,
        "interface coverage mismatch",
    )
    for side, mapping in (("west", cfg.input_map), ("east", cfg.output_map)):
        for lane in range(net.p):
            expected = mapping.index(lane) if lane in mapping else None
            require(
                interface[side, lane]["active"] == expected,
                "active/spare mapping mismatch",
            )
            if cfg.pad_rows > 1:
                extra = cfg.termination_length if net.p > cfg.active_ports else 0
                x = (
                    m["die_bbox"][0] + cfg.margin + extra
                    if side == "west"
                    else m["die_bbox"][2] - cfg.margin - extra
                )
                require(
                    abs(interface[side, lane]["position"][0] - x) < tol,
                    "optical interface recessed behind die envelope",
                )
    expected_top_ports = {
        f"{'in' if side=='west' else 'out'}_{v['active']}": [
            *v["position"],
            180 if side == "west" else 0,
        ]
        for (side, lane), v in interface.items()
        if v["active"] is not None
    }
    require(
        cells[m["top"]]["ports"] == expected_top_ports,
        "external optical port map mismatch",
    )
    term = {(t["side"], t["internal"]): t for t in m["terminations"]}
    spares = {k for k, v in interface.items() if v["active"] is None}
    require(
        set(term) == spares and len(m["terminations"]) == len(spares),
        "missing or extra spare termination",
    )
    for key, t in term.items():
        require(
            [t["x"], t["y"]] == interface[key]["position"],
            "termination disconnected from spare interface",
        )
        require(
            cells[t["cell"]]["kind"] == "termination", "invalid termination component"
        )

    def endpoint(label):
        if label.startswith(("in:", "out:")):
            side = "west" if label.startswith("in:") else "east"
            return interface[side, int(label.split(":")[1])]["position"]
        sid, pin = label.rsplit(":", 1)
        i = inst[sid]
        actual = pin[0] + str(int(pin[1]) ^ i["pin_flip"])
        at = cells[i["cell"]]["ports"][actual]
        return point(i["x"], i["y"], i.get("angle", 0), at)

    expected = {}
    for lane in range(net.p):
        expected[f"in:{lane}"] = f"{switch_id(0,lane//2)}:i{lane%2}"
    for s in range(net.depth):
        for lane in range(net.p):
            to = net.boundaries[s]["permutation"][lane] if s < net.depth - 1 else lane
            expected[f"{switch_id(s,lane//2)}:o{lane%2}"] = (
                f"{switch_id(s+1,to//2)}:i{to%2}"
                if s < net.depth - 1
                else f"out:{lane}"
            )
    require(
        len(m["routes"]) == len(expected)
        and {r["source"] for r in m["routes"]} == set(expected),
        "missing or duplicate optical edge",
    )
    used = set()
    for route in m["routes"]:
        require(
            route["target"] == expected[route["source"]],
            "incorrect optical edge destination",
        )
        last = endpoint(route["source"])
        require(
            hypot(last[0] - route["start"][0], last[1] - route["start"][1]) < tol,
            "route source moved",
        )
        totals = dict(length=0.0, crossings=0, bends=0, angle=0.0)
        for part in route["pieces"]:
            c = cells[part["cell"]]
            pair = [part["entry"], part["exit"]]
            track = [t for t in c["tracks"] if t["ports"] == pair]
            require(len(track) == 1, "invalid crossing/component through transfer")
            if c["kind"] == "exchange":
                require(
                    pair in (["w0", "e1"], ["w1", "e0"]),
                    "crossing is not a paired through path",
                )
            for key in totals:
                totals[key] += track[0][key]
            a, b = c["ports"][part["entry"]], c["ports"][part["exit"]]
            start = point(part["x"], part["y"], part.get("angle", 0), a)
            require(
                hypot(last[0] - start[0], last[1] - start[1]) <= tol, "optical path gap"
            )
            last = point(part["x"], part["y"], part.get("angle", 0), b)
            used.add(
                (
                    part["cell"],
                    snap(part["x"]),
                    snap(part["y"]),
                    part.get("angle", 0) % 360,
                )
            )
        end = endpoint(route["target"])
        require(
            hypot(last[0] - end[0], last[1] - end[1]) <= tol
            and hypot(last[0] - route["end"][0], last[1] - route["end"][1]) <= tol,
            "unconnected optical target",
        )
        require(
            all(abs(totals[k] - route[k]) < tol for k in totals),
            "incorrect optical metric",
        )
    for c in cells.values():
        if c["kind"] == "straight":
            length = c["ports"]["e"][0]
            expected_poly = [
                [snap(x), snap(y)]
                for x, y in rectangle(0, -cfg.wg_width / 2, length, cfg.wg_width / 2)
            ]
            require(
                [p["points"] for p in c["polygons"] if p["layer"] == "WG"]
                == [expected_poly],
                "straight polygon width/centerline mismatch",
            )
            require(
                c["ports"] == {"w": [0, 0, 180], "e": [length, 0, 0]},
                "straight interface contract corrupted",
            )
            require(
                c["tracks"]
                == [
                    dict(
                        ports=["w", "e"],
                        length=length,
                        min_radius=None,
                        bends=0,
                        angle=0,
                        crossings=0,
                    )
                ],
                "straight centerline metrics corrupted",
            )
        if c["kind"] in ("bend", "turn"):
            a = c["metadata"]["arc"]
            require(a["radius"] >= cfg.radius, "bend radius too small")
            polys = [p for p in c["polygons"] if p["layer"] == "WG"]
            expected_poly = [
                [snap(x), snap(y)]
                for x, y in arc_polygon(
                    *a["center"],
                    a["radius"],
                    a["start"],
                    a["end"],
                    cfg.wg_width,
                    cfg.chord_error,
                )
            ]
            require(
                len(polys) == 1 and polys[0]["points"] == expected_poly,
                "bend polygon differs from analytic centerline radius",
            )
            track = c["tracks"][0]
            angle = abs(a["end"] - a["start"])
            require(
                abs(track["length"] - a["radius"] * angle) < tol
                and abs(track["angle"] - angle) < 1e-10
                and track["bends"] == 1
                and track["crossings"] == 0
                and track["min_radius"] == a["radius"],
                "bend centerline metrics corrupted",
            )
        if c["kind"] == "exchange":
            length = pi * cfg.radius / 2 + (
                cfg.lane_pitch - 2 * cfg.radius * (1 - 1 / sqrt(2))
            ) * sqrt(2)
            for t in c["tracks"]:
                require(
                    abs(t["length"] - length) < tol
                    and t["crossings"] == 1
                    and t["bends"] == 2
                    and t["angle"] == pi / 2
                    and t["min_radius"] == cfg.radius,
                    "exchange centerline metrics corrupted",
                )
        if c["kind"] in ("meander", "fan_lane"):
            for key in ("length", "crossings", "bends", "angle"):
                value = sum(cells[r["cell"]]["tracks"][0][key] for r in c["refs"])
                require(
                    abs(value - c["tracks"][0][key]) < tol,
                    "meander centerline metrics corrupted",
                )
            if c["kind"] == "fan_lane":
                require(
                    len(c["tracks"]) == 2
                    and c["tracks"][0]["ports"] == ["w", "e"]
                    and c["tracks"][1] == {**c["tracks"][0], "ports": ["e", "w"]},
                    "fan reverse transfer corrupted",
                )
        if c["kind"] == "crossing":
            require(
                c["metadata"]["through"] == [["w", "e"], ["s", "n"]],
                "crossing pairing corrupted",
            )
        if c["kind"] == "mzi":
            require(
                c["metadata"]["bar"] == [["i0", "o0"], ["i1", "o1"]]
                and c["metadata"]["cross"] == [["i0", "o1"], ["i1", "o0"]],
                "MZI contract corrupted",
            )
    objs, geoms, ports = spatial_objects(m)
    actual = Counter(objs)
    expected_objs = Counter(used)
    expected_objs.update(
        (i["cell"], i["x"], i["y"], i.get("angle", 0)) for i in inst.values()
    )
    expected_objs.update((t["cell"], t["x"], t["y"], 0) for t in term.values())
    require(
        actual == expected_objs,
        "optical hierarchy differs from connected route/component inventory",
    )
    die = box(*m["die_bbox"])
    tree = STRtree(geoms)
    for i, g in enumerate(geoms):
        require(
            g.is_valid and g.geom_type == "Polygon",
            "disconnected/invalid optical primitive geometry",
        )
        require(die.buffer(tol).covers(g), "optical geometry outside die")
        for at in ports[i]:
            require(
                g.buffer(tol).covers(Point(at)),
                "optical polygon does not reach declared port",
            )
        for j in tree.query(g, predicate="dwithin", distance=cfg.wg_clearance - tol):
            j = int(j)
            if j <= i:
                continue
            common = ports[i] & ports[j]
            require(
                bool(common),
                f"unintended optical intersection/clearance: {objs[i]}, {objs[j]}",
            )
            require(
                g.intersection(geoms[j]).area < cfg.wg_width * tol * 4,
                "overlapping connected waveguides",
            )
            exempt = unary_union(
                [Point(v).buffer(2 * (cfg.wg_clearance + cfg.wg_width)) for v in common]
            )
            require(
                g.difference(exempt).distance(geoms[j].difference(exempt))
                >= cfg.wg_clearance - tol,
                "clearance violation away from connected endpoint",
            )
    expected_nets = {
        f"{sid}:{name}" for sid in net.switches for name in cfg.terminal_names
    }
    require(
        {e["net"] for e in m["electrical"]} == expected_nets
        and len(m["electrical"]) == len(expected_nets),
        "terminal-pad coverage mismatch",
    )
    for side in ("north", "south"):
        group = sorted(
            (e for e in m["electrical"] if e["side"] == side), key=lambda e: e["pad"][0]
        )
        require(len(group) == len(net.switches), "unbalanced pad banks")
        rows = sorted({e["pad"][1] for e in group})
        require(len(rows) == min(cfg.pad_rows, len(group)), "incorrect pad row count")
        require(
            all(b - a >= cfg.pad_row_pitch - tol for a, b in zip(rows, rows[1:])),
            "pad row spacing violation",
        )
        for y in rows:
            row = [e for e in group if e["pad"][1] == y]
            require(
                all(
                    b["pad"][0] - a["pad"][0] >= cfg.pad_pitch - tol
                    for a, b in zip(row, row[1:])
                ),
                "pad pitch violation",
            )
        require(
            (
                min(rows) - cfg.pad_size / 2
                > (net.p - 1) * cfg.lane_pitch + m.get("bands", [{"y": 0}])[-1]["y"]
                if side == "north"
                else max(rows) + cfg.pad_size / 2 < 0
            ),
            "pad bank lies on incorrect chip side",
        )
    for e in m["electrical"]:
        require(
            e["net"] == f"{e['instance']}:{e['terminal']}",
            "net identifier differs from its terminal",
        )
        i = inst[e["instance"]]
        at = cells[i["cell"]]["ports"][e["terminal"]]
        require(
            [e["x"], e["y"]] == point(i["x"], i["y"], i.get("angle", 0), at),
            "electrical source not at MZI terminal",
        )
    return {
        "manifest_geometry_passed": True,
        "logical_edges": len(expected),
        "optical_objects": len(objs),
        "mzi_count": len(inst),
        "spare_terminations": len(term),
        "switch_depth_min": net.depth,
        "switch_depth_max": net.depth,
    }


def verify_gds(path, m, names):
    import klayout.db as kdb

    cfg = Config(**m["config"])
    verify_pad_banks(m)
    ly = kdb.Layout()
    ly.read(str(path))
    dbu = ly.dbu
    require(abs(dbu - cfg.grid) < 1e-12, "database unit mismatch")
    require(
        len(ly.top_cells()) == 1 and ly.top_cell().name == names[m["top"]],
        "unexpected GDS top",
    )
    top = ly.top_cell()
    bounds = top.dbbox()
    require(
        all(
            abs(a - b) <= 2 * dbu
            for a, b in zip(
                [bounds.left, bounds.bottom, bounds.right, bounds.top], m["die_bbox"]
            )
        ),
        "GDS full extent differs from die bounds",
    )
    actual = {c.name: c for c in ly.each_cell()}
    require(
        set(actual) == set(names.values()) and set(names) == set(m["cells"]),
        "GDS cell inventory mismatch",
    )
    for name, model in m["cells"].items():
        cell = actual[names[name]]
        for layer, pair in cfg.layers.items():
            expected = kdb.Region()
            for poly in model["polygons"]:
                if poly["layer"] == layer:
                    expected.insert(_kpoly(poly["points"], dbu, kdb))
            region = kdb.Region(cell.shapes(ly.layer(*pair)))
            require(
                (expected ^ region).is_empty(), f"GDS polygon mismatch: {name}/{layer}"
            )
        expected_refs = Counter(
            (names[r["cell"]], snap(r["x"]), snap(r["y"]), round(r["angle"] % 360, 6))
            for r in model["refs"]
        )
        actual_refs = Counter()
        for inst in cell.each_inst():
            for tr in inst.cell_inst.each_cplx_trans():
                require(
                    not tr.is_mirror() and abs(tr.mag - 1) < 1e-12,
                    "unsupported transform",
                )
                actual_refs[
                    (
                        ly.cell(inst.cell_index).name,
                        snap(tr.disp.x * dbu),
                        snap(tr.disp.y * dbu),
                        round(tr.angle % 360, 6),
                    )
                ] += 1
        require(
            expected_refs == actual_refs, f"GDS reference/transform mismatch: {name}"
        )
    regions = {
        key: kdb.Region(top.begin_shapes_rec(ly.layer(*cfg.layers[key]))).merged()
        for key in ("M1", "M2", "VIA")
    }
    parts = {key: _region_shapes(r, dbu) for key, r in regions.items()}
    trees = {key: STRtree(v) for key, v in parts.items()}
    n1, n2 = len(parts["M1"]), len(parts["M2"])
    parent = list(range(n1 + n2))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for via in parts["VIA"]:
        x0, y0, x1, y1 = via.bounds
        require(
            x1 - x0 >= cfg.via_size - 2 * dbu
            and y1 - y0 >= cfg.via_size - 2 * dbu
            and via.area >= cfg.via_size**2 - 4 * cfg.via_size * dbu,
            "via cut below configured size",
        )
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
                len(hits[layer]) == 1, f"via open or insufficient {layer} enclosure"
            )
        parent[root(n1 + hits["M2"][0])] = root(hits["M1"][0])

    def conductor(layer, at):
        found = trees[layer].query(Point(at), predicate="intersects")
        require(len(found) == 1, f"terminal/pad open on {layer}: {at}")
        return int(found[0]) + (n1 if layer == "M2" else 0)

    assigned = {}
    for e in m["electrical"]:
        a, b = conductor("M1", [e["x"], e["y"]]), conductor("M2", e["pad"])
        require(root(a) == root(b), f"electrical open: {e['net']}")
        require(root(a) not in assigned, f"electrical short: {e['net']}")
        assigned[root(a)] = e["net"]
    require(
        len({root(i) for i in range(n1 + n2)}) == len(assigned),
        "unassigned conductor island",
    )
    require(
        len(parts["VIA"]) == sum(len(e["vias"]) for e in m["electrical"]),
        "via count mismatch",
    )
    die = box(*m["die_bbox"])
    for key, shapes in parts.items():
        for i, g in enumerate(shapes):
            require(die.buffer(dbu * 2).covers(g), f"{key} outside die")
            if key != "VIA":
                for j in trees[key].query(
                    g, predicate="dwithin", distance=cfg.metal_spacing - dbu * 2
                ):
                    require(int(j) == i, f"{key} conductor spacing violation")
        if key != "VIA":
            require(
                regions[key].width_check(round(cfg.metal_width / dbu) - 2).is_empty(),
                f"{key} minimum width violation",
            )
    objs, wgs, _ = spatial_objects(m)
    optical_tree = STRtree(wgs)
    windows = {(snap(v["x"]), snap(v["y"])) for v in m["overpasses"]}
    window_rows = defaultdict(list)
    for x, y in windows:
        window_rows[y].append(x)
    for row in window_rows.values():
        row.sort()
    for layer in ("M1", "M2", "VIA"):
        distance = (
            cfg.optical_metal_clearance
            + (cfg.via_enclosure if layer == "VIA" else 0)
            - dbu * 2
        )
        for metal in parts[layer]:
            for j in optical_tree.query(metal, predicate="dwithin", distance=distance):
                j = int(j)
                name, x, y, angle = objs[j]
                kind = m["cells"][name]["kind"]
                if layer == "M1" and kind == "mzi":
                    continue  # Declared placeholder electrode region.
                require(
                    layer == "M2" and kind == "straight",
                    f"{layer} violates optical {kind} keepout",
                )
                conflict = metal.intersection(wgs[j].buffer(distance))
                # Each conflict must be inside declared straight-WG overpass
                # windows. No exemption is made for bends/devices or for vias.
                hits = []
                row = window_rows[snap(y)]
                if not conflict.is_empty:
                    lo = bisect_left(row, conflict.bounds[0] - cfg.metal_width)
                    hi = bisect_right(row, conflict.bounds[2] + cfg.metal_width)
                    for vx in row[lo:hi]:
                        hits.append(
                            box(
                                vx - cfg.metal_width / 2 - cfg.optical_metal_clearance,
                                y - cfg.wg_width / 2 - cfg.optical_metal_clearance,
                                vx + cfg.metal_width / 2 + cfg.optical_metal_clearance,
                                y + cfg.wg_width / 2 + cfg.optical_metal_clearance,
                            )
                        )
                require(
                    conflict.difference(unary_union(hits)).area < dbu * dbu,
                    "unapproved M2 optical overpass",
                )
    return {
        "gds_readback_passed": True,
        "electrical_extraction_passed": True,
        "metal_regions": {"M1": n1, "M2": n2},
        "via_count": len(parts["VIA"]),
        "gds_cells": len(actual),
        "cell_references": sum(len(c["refs"]) for c in m["cells"].values()),
    }
