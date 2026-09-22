"""Sparse port ownership and optical geometry; shared strict GDS extraction."""

from collections import Counter, defaultdict
from math import hypot
from shapely import set_precision
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from .geometry import point, rectangle
from .verify import require, spatial_objects
from .as_verify import track, verify_manifest, verify_gds


def verify_optics(m, net, cfg, shapes):
    cells, stages = m["cells"], m["stages"]
    tol = 2 * cfg.grid
    origin = -(net.p - 1) * cfg.lane_pitch / 2
    expected = Counter()
    joints = []
    crossings = Counter()
    transfers = defaultdict(list)
    ownership = Counter()
    instances = {i["id"]: i for i in m["instances"]}

    def obj(i):
        return i["cell"], i["x"], i["y"], i.get("angle", 0) % 360

    def pin(s, row, direction):
        require(row in net.slots[s], f"missing switch {s}/{row}")
        sid, index = net.slots[s][row]
        inst = instances[sid]
        p = f"{direction}{index}"
        ownership[sid, p] += 1
        return point(
            inst["x"], inst["y"], inst.get("angle", 0), cells[inst["cell"]]["ports"][p]
        ), obj(inst)

    for inst in m["instances"]:
        sw = net.switches[inst["id"]]
        stage = stages[sw["stage"]]
        require(
            inst["row"] == sw["row"]
            and inst["stage"] == sw["stage"]
            and inst["x"] == stage["x"]
            and abs(inst["y"] - origin - sw["row"] * cfg.lane_pitch) < tol
            and inst["angle"] == 0
            and inst["cell"] == "AS_MZI_" + stage["exit_side"],
            "Banyan MZI placement mismatch",
        )
        expected[obj(inst)] += 1
    require(m["bypasses"] == [], "pruned lanes must not become bypasses")

    def walk(pieces, start, end, previous=None, following=None):
        last = start
        direction = 0
        for part in pieces:
            c = cells[part["cell"]]
            angle = part.get("angle", 0)
            require(
                c["kind"] in ("segment", "bend", "crossing"),
                "unexpected optical path primitive",
            )
            a = point(part["x"], part["y"], angle, c["ports"][part["entry"]])
            b = point(part["x"], part["y"], angle, c["ports"][part["exit"]])
            incoming = (c["ports"][part["entry"]][2] + angle + 180) % 360
            require(
                hypot(a[0] - last[0], a[1] - last[1]) <= tol, "Banyan optical route gap"
            )
            require(
                abs((incoming - direction + 180) % 360 - 180) < 0.01,
                "Banyan optical tangent mismatch",
            )
            track(c, part["entry"], part["exit"])
            current = obj(part)
            if previous:
                joints.append((previous, current))
            if c["kind"] == "crossing":
                crossings[current] += 1
                transfers[current].append(frozenset((part["entry"], part["exit"])))
            else:
                expected[current] += 1
            previous = current
            last = b
            direction = (c["ports"][part["exit"]][2] + angle) % 360
        require(
            hypot(last[0] - end[0], last[1] - end[1]) <= tol and abs(direction) < 0.01,
            "Banyan route misses destination",
        )
        if following:
            joints.append((previous, following))

    desired = {(s, a, b) for s, bd in enumerate(net.boundaries) for a, b in bd["edges"]}
    require(
        Counter((r["stage"], r["row"], r["dest"]) for r in m["routes"])
        == Counter(desired),
        "Banyan effective edge inventory mismatch",
    )
    for route in m["routes"]:
        start, source = pin(route["stage"], route["row"], "o")
        end, dest = pin(route["stage"] + 1, route["dest"], "i")
        walk(route["pieces"], start, end, source, dest)
    require(
        len(m["interfaces"]) == 2 * cfg.active_ports,
        "Banyan external IO count mismatch",
    )
    for side, mapping in (("west", cfg.input_map), ("east", cfg.output_map)):
        bank = sorted(
            (i for i in m["interfaces"] if i["side"] == side), key=lambda i: i["active"]
        )
        require(
            [(i["active"], i["internal"]) for i in bank] == list(enumerate(mapping)),
            "Banyan IO mapping mismatch",
        )
        for interface in bank:
            row = interface["internal"]
            c = cells[interface["cell"]]
            require(
                c["kind"] == "adapter" and len(c["tracks"]) == 1,
                "invalid Banyan IO adapter",
            )
            t = track(c, "w", "e")
            west, east = c["ports"]["w"], c["ports"]["e"]
            external = west if side == "west" else east
            require(
                external[:2] == interface["position"]
                and abs(external[1] - origin - interface["active"] * cfg.lane_pitch)
                < tol
                and external[2] == (180 if side == "west" else 0),
                "Banyan external port placement/orientation",
            )
            at, device = pin(
                0 if side == "west" else net.depth - 1,
                row,
                "i" if side == "west" else "o",
            )
            require(
                (east if side == "west" else west)[:2] == at, "Banyan IO misses MZI"
            )
            walk(
                t["pieces"],
                west,
                east,
                None if side == "west" else device,
                device if side == "west" else None,
            )
    expected_terms = {t["id"]: t for t in net.terminations}
    require(
        len(m["terminations"]) == len(expected_terms)
        and {t["id"] for t in m["terminations"]} == set(expected_terms),
        "Banyan termination inventory mismatch",
    )
    for term in m["terminations"]:
        logical = expected_terms[term["id"]]
        require(
            all(term.get(k) == v for k, v in logical.items()),
            "Banyan termination binding changed",
        )
        c = cells[term["cell"]]
        side = "west" if term["pin"][0] == "i" else "east"
        a, b = (
            (-cfg.termination_length, 0)
            if side == "west"
            else (0, cfg.termination_length)
        )
        require(
            c["kind"] == "termination"
            and term["side"] == side
            and term["angle"] == 0
            and c["ports"] == {"opt": [0, 0, 0 if side == "west" else 180]}
            and c["polygons"]
            == [
                dict(
                    layer="WG",
                    points=rectangle(a, -cfg.wg_width / 2, b, cfg.wg_width / 2),
                )
            ]
            and c["metadata"]
            == dict(
                placeholder=True, reflectionless=False, length=cfg.termination_length
            ),
            "Banyan termination geometry/orientation changed",
        )
        at, device = pin(term["stage"], term["row"], term["pin"][0])
        expected[obj(term)] += 1
        tip = [term["x"], term["y"]]
        walk(
            term["pieces"],
            tip if side == "west" else at,
            at if side == "west" else tip,
            obj(term) if side == "west" else device,
            device if side == "west" else obj(term),
        )
    require(
        ownership
        == Counter((sid, p) for sid in net.switches for p in ("i0", "i1", "o0", "o1")),
        "every MZI pin must have exactly one owner",
    )
    require(
        all(n == 2 for n in crossings.values())
        and all(
            set(v) == {frozenset(("w", "e")), frozenset(("s", "n"))}
            for v in transfers.values()
        ),
        "Banyan crossing lacks two distinct through paths",
    )
    expected.update({k: 1 for k in crossings})
    require(m["crossing_count"] == len(crossings), "Banyan crossing count mismatch")
    objs, geoms, ports = spatial_objects(m)
    geoms = [set_precision(g, cfg.grid) for g in geoms]
    require(
        Counter(objs) == expected,
        "Banyan optical hierarchy differs from connected inventory",
    )
    placed = dict(zip(objs, geoms))
    for a, b in joints:
        require(
            placed[a].distance(placed[b]) < 1e-8,
            f"Banyan optical polygons disconnected: {a} / {b}",
        )
    tree = STRtree(geoms)
    die = box(*m["die_bbox"])
    for i, g in enumerate(geoms):
        require(
            g.is_valid and not g.is_empty and die.buffer(tol).covers(g),
            "Banyan invalid/outside optical geometry",
        )
        require(
            all(g.buffer(tol).covers(Point(v)) for v in ports[i]),
            "Banyan primitive misses port",
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
                f"Banyan unintended optical contact/clearance: {objs[i]} / {objs[j]}",
            )
            require(
                g.intersection(geoms[j]).area < cfg.wg_width * tol * 4,
                "Banyan overlapping connected waveguides",
            )
            exempt = unary_union(
                [Point(v).buffer(2 * (cfg.wg_clearance + cfg.wg_width)) for v in common]
            )
            a, b = g.difference(exempt), geoms[j].difference(exempt)
            require(
                a.is_empty or b.is_empty or a.distance(b) >= cfg.wg_clearance - tol,
                "Banyan optical clearance away from joint",
            )
    return crossings, objs
