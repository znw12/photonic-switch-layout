"""Independent explicit-graph, analytic geometry and GDS conductor checks."""

from collections import Counter, defaultdict
from math import hypot, cos, sin
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely import set_precision
from .config import Config
from .network import Network
from .geometry import point, snap, arc_polygon, rectangle
from .verify import require, spatial_objects, cell_geometries, _kpoly, _region_shapes
from .interstage_verify import verify_segment, verify_arc_ports, verify_crossing


def track(c, entry, exit):
    matches = [t for t in c["tracks"] if t["ports"] == [entry, exit]]
    require(len(matches) == 1, "missing or ambiguous optical transfer")
    return matches[0]


def validate_device(c, cells, cfg, shapes):
    md = c["metadata"]
    name = c["name"]
    tol = 2 * cfg.grid
    wg = shapes(name, "WG")
    require(
        wg.is_valid and wg.geom_type == "MultiPolygon" and len(wg.geoms) == 2,
        "AS MZI rails open or shorted",
    )
    require(
        abs(wg.bounds[0]) <= tol and abs(wg.bounds[2] - 1000) <= tol,
        "MZI length changed",
    )
    require(
        md["active_x"] == [160, 840] and md["active_length_um"] == 680,
        "active electrode length changed",
    )
    rails = sorted(wg.geoms, key=lambda g: g.centroid.y)
    require(
        rails[0].distance(rails[1]) >= cfg.coupler_gap - tol, "coupler gap violated"
    )
    for i, path in enumerate(md["optical_paths"]):
        last = [0, i * cfg.lane_pitch]
        length = 0
        bends = 0
        for seg in path:
            a, b = seg["start"], seg["end"]
            require(
                hypot(a[0] - last[0], a[1] - last[1]) < tol,
                "MZI centerline disconnected",
            )
            if seg["kind"] == "arc":
                r = seg["radius"]
                aa, bb = seg["start_angle"], seg["end_angle"]
                cx, cy = seg["center"]
                require(r >= cfg.radius, "MZI radius below configured minimum")
                samples = [
                    [
                        cx + r * cos(aa + (bb - aa) * j / 40),
                        cy + r * sin(aa + (bb - aa) * j / 40),
                    ]
                    for j in range(41)
                ]
                length += r * abs(bb - aa)
                bends += 1
            else:
                samples = [
                    [a[0] + (b[0] - a[0]) * j / 20, a[1] + (b[1] - a[1]) * j / 20]
                    for j in range(21)
                ]
                length += hypot(b[0] - a[0], b[1] - a[1])
            require(
                all(rails[i].buffer(tol).covers(Point(p)) for p in samples),
                "MZI geometry misses analytic centerline",
            )
            last = b
        require(
            hypot(last[0] - 1000, last[1] - i * cfg.lane_pitch) < tol and bends == 8,
            "MZI endpoints/bends changed",
        )
        for j in (0, 1):
            require(
                abs(track(c, f"i{i}", f"o{j}")["length"] - length) < tol,
                "MZI metric changed",
            )
    side = md["exit_side"]
    sx = 820 if side == "R" else 180
    gx = 780 if side == "R" else 220
    ex = 1000 if side == "R" else 0
    mid = cfg.lane_pitch / 2
    half = cfg.metal_width / 2
    expected = [
        dict(
            layer="M1",
            points=rectangle(
                160, mid - cfg.gsg_signal_width / 2, 840, mid + cfg.gsg_signal_width / 2
            ),
        ),
        dict(
            layer="M2",
            points=rectangle(min(sx, ex), mid - half, max(sx, ex), mid + half),
        ),
    ]
    require(c["polygons"] == expected, "MZI S metal differs from local contract")
    require(
        c["ports"]
        == {
            "i0": [0, 0, 180],
            "i1": [0, cfg.lane_pitch, 180],
            "o0": [1000, 0, 0],
            "o1": [1000, cfg.lane_pitch, 0],
            "G": [gx, mid, 90],
            "S": [ex, mid, 0 if side == "R" else 180],
        },
        "MZI ports changed",
    )
    require(md["internal_vias"] == [[sx, mid]], "MZI must own one S via only")
    require(
        [(r["x"], r["y"]) for r in c["refs"] if r["cell"] == "VIA"] == [(sx, mid)],
        "MZI via ownership corrupted",
    )
    local = (cfg.gsg_gap - cfg.mzi_wg_width) / 2
    require(
        shapes(name, "M1").distance(wg) >= local - tol,
        "S electrode optical clearance violated",
    )


def verify_manifest(m):
    cfg = Config(**m["config"])
    net = Network(cfg)
    cells = m["cells"]
    tol = 2 * cfg.grid
    require(m["network"] == net.export(), "AS graph differs from configuration")
    require(
        len(m["instances"]) == len(net.switches)
        and {i["id"] for i in m["instances"]} == set(net.switches),
        "MZI inventory mismatch",
    )
    require(len(m["stages"]) == net.depth, "column inventory mismatch")
    stages = m["stages"]
    origin = -(net.p - 1) * cfg.lane_pitch / 2
    shapes = cell_geometries(cells)
    for name, c in cells.items():
        if c["kind"] == "mzi":
            validate_device(c, cells, cfg, shapes)
        elif c["kind"] == "segment":
            verify_segment(c, cfg)
        elif c["kind"] == "bend":
            verify_arc_ports(c, cfg)
            a = c["metadata"]["arc"]
            r = a["radius"]
            require(r >= cfg.radius, "bend radius below minimum")
            expected = [
                [snap(x), snap(y)]
                for x, y in arc_polygon(
                    *a["center"], r, a["start"], a["end"], cfg.wg_width, cfg.chord_error
                )
            ]
            require(
                c["polygons"] == [dict(layer="WG", points=expected)],
                "arc geometry differs from radius",
            )
        elif c["kind"] == "crossing":
            verify_crossing(c, cfg)
    expected_objects = Counter()
    for i in m["instances"]:
        v = net.switches[i["id"]]
        s = stages[v["stage"]]
        require(
            i["row"] == v["row"]
            and i["stage"] == v["stage"]
            and i["x"] == s["x"]
            and abs(i["y"] - (origin + v["row"] * cfg.lane_pitch)) < tol,
            "MZI placement mismatch",
        )
        require(i["cell"] == "AS_MZI_" + s["exit_side"], "column exit mismatch")
        expected_objects[(i["cell"], i["x"], i["y"], 0)] += 1
    require(
        [(b["stage"], b["row"]) for b in m["bypasses"]]
        == [(b["stage"], b["row"]) for b in net.bypasses],
        "bypass inventory mismatch",
    )
    for b in m["bypasses"]:
        require(
            b["x"] == stages[b["stage"]]["x"]
            and abs(b["y"] - origin - b["row"] * cfg.lane_pitch) < tol,
            "bypass placement mismatch",
        )
        c = cells[b["cell"]]
        require(
            c["ports"] == {"w": [0, 0, 180], "e": [1000, 0, 0]},
            "bypass must traverse the device column",
        )
        require(
            shapes(b["cell"], "WG").equals(
                box(0, -cfg.wg_width / 2, 1000, cfg.wg_width / 2)
            ),
            "bypass geometry changed",
        )
        expected_objects[(b["cell"], b["x"], b["y"], 0)] += 1
    require(
        len(m["routes"]) == (net.depth - 1) * net.p, "interstage route count mismatch"
    )
    seen = set()
    crossings = Counter()
    crossing_pairs = defaultdict(list)
    physical_joints = []
    instances = {i["id"]: i for i in m["instances"]}
    bypasses = {(b["stage"], b["row"]): b for b in m["bypasses"]}

    def column_object(s, row):
        slot = net.slots[s].get(row)
        item = instances[slot[0]] if slot else bypasses[s, row]
        return (item["cell"], item["x"], item["y"], 0)

    for route in m["routes"]:
        s, row, dest = route["stage"], route["row"], route["dest"]
        require((s, row) not in seen, "duplicate optical route")
        seen.add((s, row))
        require(
            net.boundaries[s]["permutation"][row] == dest,
            "route bypass/permutation mismatch",
        )
        last = [stages[s]["x"] + 1000, origin + row * cfg.lane_pitch]
        direction = 0
        previous = column_object(s, row)
        for part in route["pieces"]:
            c = cells[part["cell"]]
            angle = part.get("angle", 0)
            a = point(part["x"], part["y"], angle, c["ports"][part["entry"]])
            b = point(part["x"], part["y"], angle, c["ports"][part["exit"]])
            require(hypot(a[0] - last[0], a[1] - last[1]) <= tol, "optical route gap")
            incoming = (c["ports"][part["entry"]][2] + angle + 180) % 360
            require(
                abs((incoming - direction + 180) % 360 - 180) < 0.01,
                "optical route tangent mismatch",
            )
            track(c, part["entry"], part["exit"])
            direction = (c["ports"][part["exit"]][2] + angle) % 360
            last = b
            obj = (c["name"], part["x"], part["y"], angle % 360)
            physical_joints.append((previous, obj))
            previous = obj
            if c["kind"] == "crossing":
                crossings[obj] += 1
                crossing_pairs[obj].append(frozenset((part["entry"], part["exit"])))
            else:
                expected_objects[obj] += 1
        require(
            hypot(
                last[0] - stages[s + 1]["x"], last[1] - origin - dest * cfg.lane_pitch
            )
            <= tol
            and abs(direction) < 0.01,
            "optical route misses destination",
        )
        physical_joints.append((previous, column_object(s + 1, dest)))
    require(
        all(n == 2 for n in crossings.values()),
        "crossing does not have paired transfers",
    )
    require(
        all(
            set(v) == {frozenset(("w", "e")), frozenset(("s", "n"))}
            for v in crossing_pairs.values()
        ),
        "crossing paired paths are duplicated or switched",
    )
    expected_objects.update({k: 1 for k in crossings})
    require(m["crossing_count"] == len(crossings), "crossing count mismatch")
    require(len(m["interfaces"]) == 2 * net.p, "optical IO count mismatch")
    for side in ("west", "east"):
        bank = [v for v in m["interfaces"] if v["side"] == side]
        require(
            sorted(v["internal"] for v in bank) == list(range(net.p)),
            "IO index mismatch",
        )
        for v in bank:
            c = cells[v["cell"]]
            row = v["internal"]
            y = origin + row * cfg.lane_pitch
            target = (
                [stages[0]["x"], y] if side == "west" else [stages[-1]["x"] + 1000, y]
            )
            require(
                c["ports"]["e" if side == "west" else "w"][:2] == target,
                "IO misses column",
            )
            require(
                c["ports"]["w" if side == "west" else "e"][:2] == v["position"],
                "external optical port misses geometry",
            )
            expected_objects[(v["cell"], 0, 0, 0)] += 1
            physical_joints.append(
                (
                    (v["cell"], 0, 0, 0),
                    column_object(0 if side == "west" else net.depth - 1, row),
                )
            )
    objs, geoms, ports = spatial_objects(m)
    # Rigid transforms of unions can leave sub-grid collapsed rings at tangent
    # overlaps. Evaluate on the same 1 nm grid as the emitted GDS polygons.
    geoms = [set_precision(g, cfg.grid) for g in geoms]
    require(
        Counter(objs) == expected_objects,
        "optical hierarchy differs from connected route inventory",
    )
    placed = dict(zip(objs, geoms))
    for a, b in physical_joints:
        require(
            placed[a].distance(placed[b]) < 1e-8,
            "optical polygons disconnected at route joint",
        )
    tree = STRtree(geoms)
    die = box(*m["die_bbox"])
    for i, g in enumerate(geoms):
        require(
            g.is_valid and not g.is_empty and die.buffer(tol).covers(g),
            "invalid/outside optical geometry",
        )
        require(
            all(g.buffer(tol).covers(Point(v)) for v in ports[i]),
            "optical primitive misses port",
        )
        for j in tree.query(g, predicate="dwithin", distance=cfg.wg_clearance - tol):
            j = int(j)
            if j <= i:
                continue
            common = {
                ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                for a in ports[i]
                for b in ports[j]
                if hypot(a[0] - b[0], a[1] - b[1]) <= tol
            }
            require(
                bool(common),
                f"unintended optical contact/clearance: {objs[i]} / {objs[j]}",
            )
            require(
                g.intersection(geoms[j]).area < cfg.wg_width * tol * 4,
                "overlapping connected waveguides",
            )
            exempt = unary_union(
                [Point(v).buffer(2 * (cfg.wg_clearance + cfg.wg_width)) for v in common]
            )
            a, b = g.difference(exempt), geoms[j].difference(exempt)
            require(
                a.is_empty or b.is_empty or a.distance(b) >= cfg.wg_clearance - tol,
                "optical clearance away from endpoint",
            )
    # Ground ownership is reconstructed from real adjacent rows, not copied counts.
    expected_rails = []
    for s in stages:
        rows = sorted(
            v["row"] for v in net.switches.values() if v["stage"] == s["stage"]
        )
        runs = []
        for row in rows:
            if not runs or row != runs[-1][-1] + 2:
                runs.append([])
            runs[-1].append(row)
        gx = s["x"] + (780 if s["exit_side"] == "R" else 220)
        for run in runs:
            ys = [origin + (r + 0.5) * cfg.lane_pitch for r in run]
            hw = cfg.gsg_signal_width / 2
            gap = cfg.gsg_gap
            gw = cfg.gsg_ground_width
            bounds = (
                [(ys[0] - hw - gap - gw, ys[0] - hw - gap)]
                + [(a + hw + gap, b - hw - gap) for a, b in zip(ys, ys[1:])]
                + [(ys[-1] + hw + gap, ys[-1] + hw + gap + gw)]
            )
            for a, b in bounds:
                expected_rails.append(
                    (
                        s["stage"],
                        tuple(map(snap, [s["x"] + 160, a, s["x"] + 840, b])),
                        (snap(gx), snap((a + b) / 2)),
                    )
                )
    actual = [
        (v["stage"], tuple(v["bounds"]), tuple(v["contact"])) for v in m["ground_rails"]
    ]
    require(actual == expected_rails, "shared ground contact inventory changed")
    for s in stages:
        col = cells[f"AS_COLUMN_{s['stage']}"]
        gs = [r for r in col["refs"] if cells[r["cell"]]["kind"] == "ground_column"]
        require(len(gs) == 1, "column ground ownership duplicated")
        g = cells[gs[0]["cell"]]
        selected = [v for v in m["ground_rails"] if v["stage"] == s["stage"]]
        expected = [
            dict(
                layer="M1",
                points=[
                    [snap(x - s["x"]), snap(y - origin)]
                    for x, y in rectangle(*v["bounds"])
                ],
            )
            for v in selected
        ]
        require(
            g["polygons"] == expected,
            "ground rail polygon differs from allowed sharing",
        )
        require(
            Counter((r["cell"], r["x"], r["y"]) for r in g["refs"])
            == Counter(
                ("VIA", snap(v["contact"][0] - s["x"]), snap(v["contact"][1] - origin))
                for v in selected
            ),
            "shared G via missing/duplicated",
        )
    expected_signals = {sid + ":S" for sid in net.switches}
    require(
        {e["net"] for e in m["electrical"] if e["terminal"] == "S"} == expected_signals,
        "signal pad inventory mismatch",
    )
    taps = min(cfg.ground_pads_per_side, net.depth)
    half = cfg.pad_size / 2
    require(
        cells["PAD"]["polygons"]
        == [dict(layer="M2", points=rectangle(-half, -half, half, half))],
        "pad size/layer differs from configuration",
    )
    require(
        sum(e["terminal"] == "G" for e in m["electrical"]) == 2 * taps,
        "G pad inventory mismatch",
    )
    for side in ("north", "south"):
        es = [e for e in m["electrical"] if e["side"] == side]
        sign = 1 if side == "north" else -1
        require(
            len(es)
            == len(expected_signals) // 2
            + taps
            + (len(expected_signals) % 2 if side == "north" else 0),
            "bank imbalance",
        )
        origins = {
            snap(e["pad"][0] - 100 * e["pad_column"] - 50 * e["pad_row"]) for e in es
        }
        require(len(origins) == 1, "pad half-pitch grid violated")
        require(
            Counter((e["pad_column"], e["pad_row"]) for e in es)
            == Counter((i // 2, i % 2) for i in range(len(es))),
            "pad slot missing/duplicated",
        )
        for e in es:
            require(
                e["pad"][1]
                == snap(
                    sign
                    * (
                        m["electrical_plan"]["pad_base_y"]
                        + e["pad_row"] * cfg.pad_row_pitch
                    )
                ),
                "pad row position changed",
            )
    for e in m["electrical"]:
        c = cells[e["cell"]]
        expected = []
        for seg in e["segments"]:
            a, b = seg["start"], seg["end"]
            h = cfg.metal_width / 2
            require(a[0] == b[0] or a[1] == b[1], "non Manhattan electrical route")
            expected.append(
                dict(
                    layer=seg["layer"],
                    points=[
                        [snap(x), snap(y)]
                        for x, y in rectangle(
                            min(a[0], b[0]) - h,
                            min(a[1], b[1]) - h,
                            max(a[0], b[0]) + h,
                            max(a[1], b[1]) + h,
                        )
                    ],
                )
            )
        require(
            c["polygons"] == expected, "electrical route metadata differs from metal"
        )
        require(
            Counter((r["cell"], r["x"], r["y"]) for r in c["refs"])
            == Counter(("VIA", *at) for at in e["vias"]),
            "electrical via inventory mismatch",
        )
    return dict(
        manifest_geometry_passed=True,
        mzi_count=len(net.switches),
        bypass_count=len(net.bypasses),
        crossings=len(crossings),
        optical_objects=len(objs),
        ground_contacts=len(expected_rails),
    )


def verify_gds(path, m, names, windows_path=None):
    import klayout.db as kdb

    cfg = Config(**m["config"])
    ly = kdb.Layout()
    ly.read(str(path))
    dbu = ly.dbu
    tol = 2 * dbu
    require(abs(dbu - cfg.grid) < 1e-12, "GDS database unit mismatch")
    require(
        len(ly.top_cells()) == 1 and ly.top_cell().name == names[m["top"]],
        "GDS top mismatch",
    )
    actual = {c.name: c for c in ly.each_cell()}
    top = ly.top_cell()
    require(
        set(actual) == set(names.values()) and set(names) == set(m["cells"]),
        "GDS hierarchy inventory mismatch",
    )
    for name, c in m["cells"].items():
        cell = actual[names[name]]
        for layer, pair in cfg.layers.items():
            expected = kdb.Region()
            for p in c["polygons"]:
                if p["layer"] == layer:
                    expected.insert(_kpoly(p["points"], dbu, kdb))
            require(
                (expected ^ kdb.Region(cell.shapes(ly.layer(*pair)))).is_empty(),
                f"GDS polygon mismatch {name}/{layer}",
            )
        refs = Counter(
            (names[r["cell"]], r["x"], r["y"], r["angle"] % 360) for r in c["refs"]
        )
        got = Counter()
        for inst in cell.each_inst():
            for tr in inst.cell_inst.each_cplx_trans():
                require(not tr.is_mirror() and tr.mag == 1, "unexpected GDS transform")
                got[
                    (
                        ly.cell(inst.cell_index).name,
                        snap(tr.disp.x * dbu),
                        snap(tr.disp.y * dbu),
                        round(tr.angle % 360, 6),
                    )
                ] += 1
        require(refs == got, "GDS cell references differ")
    regions = {
        k: kdb.Region(top.begin_shapes_rec(ly.layer(*cfg.layers[k]))).merged()
        for k in ("M1", "M2", "VIA")
    }
    parts = {k: _region_shapes(v, dbu) for k, v in regions.items()}
    trees = {k: STRtree(v) for k, v in parts.items()}
    n1, n2 = len(parts["M1"]), len(parts["M2"])
    parent = list(range(n1 + n2))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for via in parts["VIA"]:
        require(
            via.area >= cfg.via_size**2 - 4 * cfg.via_size * dbu, "via cut undersized"
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
            require(len(hits[layer]) == 1, f"via open/enclosure on {layer}")
        parent[root(n1 + hits["M2"][0])] = root(hits["M1"][0])

    def conductor(layer, at):
        found = trees[layer].query(Point(at), predicate="intersects")
        require(len(found) == 1, f"electrode/pad open on {layer} at {at}")
        return root(int(found[0]) + (n1 if layer == "M2" else 0))

    assigned = {}
    net_roots = {}
    for e in m["electrical"]:
        a, b = conductor("M2", [e["x"], e["y"]]), conductor("M2", e["pad"])
        net = "GND" if e["terminal"] == "G" else e["net"]
        require(a == b, f"electrical open {net}")
        require(
            a not in assigned or assigned[a] == net,
            f"electrical short {net} / {assigned.get(a)}",
        )
        require(net not in net_roots or net_roots[net] == a, "common G disconnected")
        assigned[a] = net
        net_roots[net] = a
    for inst in m["instances"]:
        md = m["cells"][inst["cell"]]["metadata"]
        for terminal, points in md["electrical_probes"].items():
            for at in points:
                require(
                    conductor("M1", point(inst["x"], inst["y"], 0, at))
                    == net_roots["GND" if terminal == "G" else inst["id"] + ":S"],
                    "electrode disconnected/wrong net",
                )
    require(len(net_roots) == len(m["instances"]) + 1, "independent net count mismatch")
    require(
        len({root(i) for i in range(n1 + n2)}) == len(assigned),
        "floating conductor island",
    )
    expected_vias = (
        len(m["instances"])
        + len(m["ground_rails"])
        + len(m["ground_network"]["vias"])
        + sum(len(e["vias"]) for e in m["electrical"])
    )
    require(len(parts["VIA"]) == expected_vias, "physical via count mismatch")
    die = box(*m["die_bbox"])
    for layer, ps in parts.items():
        for i, g in enumerate(ps):
            require(die.buffer(tol).covers(g), "metal outside die")
            if layer != "VIA":
                for j in trees[layer].query(
                    g, predicate="dwithin", distance=cfg.metal_spacing - tol
                ):
                    require(
                        int(j) == i,
                        f"{layer} conductor spacing violation near {g.bounds} / {ps[int(j)].bounds}",
                    )
        if layer != "VIA":
            require(
                regions[layer].width_check(round(cfg.metal_width / dbu) - 2).is_empty(),
                f"{layer} minimum width violated",
            )
    # Passive M2 is explicitly insulated; only column G strips can traverse a
    # device. M1 and vias never receive this exemption.
    objs, wgs, _ = spatial_objects(m)
    wgs = [set_precision(g, cfg.grid) for g in wgs]
    optree = STRtree(wgs)
    shapes = cell_geometries(m["cells"])
    windows = []
    for layer in ("M1", "M2", "VIA"):
        distance = (
            cfg.optical_metal_clearance
            + (cfg.via_enclosure if layer == "VIA" else 0)
            - tol
        )
        for metal in parts[layer]:
            for j in optree.query(metal, predicate="dwithin", distance=distance):
                j = int(j)
                name, x, y, angle = objs[j]
                c = m["cells"][name]
                wg = wgs[j]
                if c["kind"] == "mzi":
                    local = (cfg.gsg_gap - cfg.mzi_wg_width) / 2 + (
                        cfg.via_enclosure if layer == "VIA" else 0
                    )
                    localrails = [
                        r
                        for r in m["ground_rails"]
                        if abs(r["bounds"][0] - x - 160) < tol
                        and r["bounds"][1] <= wg.bounds[3] + distance
                        and r["bounds"][3] >= wg.bounds[1] - distance
                    ]
                    if layer != "M2":
                        require(
                            metal.distance(wg) >= local - tol,
                            f"{layer} enters MZI waveguide",
                        )
                        # Every permitted M1/via overlap is inside approved
                        # local active electrodes/contact rails only.
                        allowed = (
                            box(
                                x + 160,
                                y + cfg.lane_pitch / 2 - 10,
                                x + 840,
                                y + cfg.lane_pitch / 2 + 10,
                            )
                            if layer == "M1"
                            else box(
                                x
                                + (820 if c["metadata"]["exit_side"] == "R" else 180)
                                - 2.5,
                                y + cfg.lane_pitch / 2 - 2.5,
                                x
                                + (820 if c["metadata"]["exit_side"] == "R" else 180)
                                + 2.5,
                                y + cfg.lane_pitch / 2 + 2.5,
                            )
                        )
                        for rail in localrails:
                            allowed = allowed.union(
                                box(*rail["bounds"])
                                if layer == "M1"
                                else Point(rail["contact"]).buffer(
                                    cfg.via_size / 2, cap_style=3
                                )
                            )
                        require(
                            metal.intersection(wg.buffer(distance))
                            .difference(allowed.buffer(tol))
                            .area
                            < dbu * dbu,
                            "unauthorized M1/via device overlap",
                        )
                    else:
                        gx = x + (780 if c["metadata"]["exit_side"] == "R" else 220)
                        sx = x + (820 if c["metadata"]["exit_side"] == "R" else 180)
                        from shapely.affinity import translate

                        allowed = translate(shapes(name, "M2"), xoff=x, yoff=y).union(
                            box(
                                gx - cfg.metal_width / 2,
                                -m["electrical_plan"]["ground_y"],
                                gx + cfg.metal_width / 2,
                                m["electrical_plan"]["ground_y"],
                            )
                        )
                        landing = cfg.via_size / 2 + cfg.via_enclosure
                        for rail in localrails:
                            if abs(rail["contact"][0] - gx) < tol:
                                allowed = allowed.union(
                                    Point(rail["contact"]).buffer(landing, cap_style=3)
                                )
                        require(
                            metal.intersection(wg.buffer(distance))
                            .difference(allowed.buffer(tol))
                            .area
                            < dbu * dbu,
                            "unauthorized M2 device overlap",
                        )
                elif layer == "M2":
                    require(
                        c["kind"] in ("straight", "segment", "bend", "crossing")
                        and cfg.share_interstage
                        and cfg.insulated_m2_overpasses,
                        "unauthorized passive overpass",
                    )
                    windows.append(
                        dict(
                            optical=list(objs[j]),
                            bbox=list(metal.intersection(wg.buffer(distance)).bounds),
                        )
                    )
                else:
                    require(
                        False,
                        f"{layer} violates passive optical keepout near {objs[j]}",
                    )
    bb = top.dbbox()
    require(
        all(
            abs(a - b) <= tol
            for a, b in zip([bb.left, bb.bottom, bb.right, bb.top], m["die_bbox"])
        ),
        "GDS die extent mismatch",
    )
    import hashlib
    import json

    if windows_path is not None:
        from pathlib import Path

        Path(windows_path).write_text(
            json.dumps(windows, sort_keys=True, indent=2) + "\n"
        )
    window_hash = hashlib.sha256(
        json.dumps(windows, sort_keys=True).encode()
    ).hexdigest()
    return dict(
        gds_readback_passed=True,
        electrical_extraction_passed=True,
        electrical_nets=len(net_roots),
        independent_signals=len(m["instances"]),
        shared_ground_nets=1,
        via_count=len(parts["VIA"]),
        passive_m2_overpass_count=len(windows),
        passive_m2_overpass_digest=window_hash,
        gds_cells=len(actual),
        cell_references=sum(len(c["refs"]) for c in m["cells"].values()),
    )
