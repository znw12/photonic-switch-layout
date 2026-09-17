"""Compact staged/folded Beneš floorplan with globally aligned escape corridors."""

from math import ceil
from .geometry import Library, snap, rectangle, validate_components, point
from .network import Network, switch_id
from .folds import fan_lane, return_turn
from .pad_routing import route_pads


def build_reshaped(cfg, candidate=None, component_factory=None):
    candidate = candidate or dict(
        id="compact", gap=1.0, row_order="normal", pad=1.0, corridor=1.0
    )
    if not cfg.insulated_m2_overpasses:
        raise ValueError(
            "this routing profile requires declared insulated M2 overpasses"
        )
    lib, net = Library(cfg), Network(cfg)
    lib.mzi().metadata["allowed_transforms"] = [0, 180]
    if component_factory:
        component_factory(lib)
    validate_components(lib)
    if 180 not in lib.mzi().metadata["allowed_transforms"] and cfg.fold_bands > 1:
        raise ValueError("folding requires an MZI permitting 180-degree rotation")
    top = lib.cell("BENES_CHIP", "chip")
    groups = {}
    for name in (
        "FABRIC",
        "INTERSTAGE",
        "IO_ADAPTERS",
        "SPARE_TERMINATIONS",
        "ELECTRICAL_FANOUT",
        "NORTH_PADS",
        "SOUTH_PADS",
    ):
        groups[name] = lib.cell(name, "group")
        lib.ref(top, groups[name])
    p, pitch = net.p, cfg.lane_pitch
    h = (p - 1) * pitch
    nb = cfg.fold_bands
    # Center longer bands to balance the two exposed large shuffle boundaries.
    sizes = [net.depth // nb] * nb
    order = sorted(range(nb), key=lambda b: (abs(b - (nb - 1) / 2), b))
    for b in order[: net.depth % nb]:
        sizes[b] += 1
    k = max(sizes)
    bands = []
    stages = []
    for b, count in enumerate(sizes):
        first = len(stages)
        bands.append(
            dict(
                band=b,
                y=snap(b * (h + cfg.fold_gap)),
                stages=list(range(first, first + count)),
            )
        )
        for j in range(count):
            stages.append(
                dict(
                    stage=len(stages),
                    band=b,
                    column=j if b % 2 == 0 else k - 1 - j,
                    angle=180 if b % 2 else 0,
                    y=bands[-1]["y"],
                )
            )
    landing = cfg.via_size + 2 * cfg.via_enclosure
    step = snap(
        (max(landing, cfg.metal_width) + cfg.metal_spacing + 2 * cfg.grid)
        * candidate["corridor"]
    )
    keep = cfg.optical_metal_clearance + landing / 2 + cfg.wg_width / 2 + 2 * cfg.grid
    count = p // 2
    corridors = {}
    for col in range(k):
        for direction in (0, 180):
            ss = [s for s in stages if s["column"] == col and s["angle"] == direction]
            corridors[col, direction] = (
                snap(2 * keep + len(ss) * count * step) if ss else snap(2 * keep)
            )
            for rank, s in enumerate(ss):
                s["trunk_rank"] = rank
    widths = []
    for s in range(net.depth):
        widths.append(
            lib.shuffle_block(
                net.boundaries[s]["size"], net.boundaries[s]["inverse"]
            ).metadata["width"]
            if s < net.depth - 1
            else 0.0
        )
    gaps = [0.0] * (k + 1)
    for s in stages:
        boundary = s["column"] + (s["angle"] == 0)
        gaps[boundary] = max(gaps[boundary], widths[s["stage"]])
    gaps = [snap((g + cfg.margin) * candidate["gap"]) for g in gaps]
    xs = []
    cursor = gaps[0]
    for col in range(k):
        x = snap(cursor + corridors[col, 180])
        xs.append(x)
        cursor = snap(x + cfg.mzi_length + corridors[col, 0] + gaps[col + 1])
    right = cursor
    wing = (
        2 * cfg.radius
        + 2 * (p - 1) * cfg.bundle_pitch
        + cfg.fold_gap / 2
        + cfg.wg_width / 2
        if nb > 1
        else 0.0
    )
    pad_span = (ceil(len(net.switches) / cfg.pad_rows) - 1) * snap(
        cfg.pad_pitch * candidate["pad"]
    ) + cfg.pad_size
    io_left = snap(min(-wing, right / 2 - pad_span / 2))
    io_right = snap(max(right + wing, right / 2 + pad_span / 2))
    for s in stages:
        col = s["column"]
        reverse = s["angle"] == 180
        s["x"] = snap(xs[col] + (cfg.mzi_length if reverse else 0))
        s["origin_y"] = snap(s["y"] + (h if reverse else 0))
        sign = -1 if reverse else 1
        s["escape_start"] = snap(s["x"] + sign * cfg.mzi_length)
        s["escape_end"] = snap(s["escape_start"] + sign * corridors[col, s["angle"]])
        s["route_end"] = snap(s["escape_end"] + sign * widths[s["stage"]])
        s["trunk_xs"] = [
            snap(
                s["escape_start"] + sign * (keep + (s["trunk_rank"] * count + i) * step)
            )
            for i in range(count)
        ]
        s["end"] = right if not reverse else 0.0
    m = dict(
        config=cfg.to_dict(),
        candidate=candidate,
        network=net.export(),
        top=top.name,
        instances=[],
        routes=[],
        electrical=[],
        overpasses=[],
        interfaces=[],
        terminations=[],
        stages=stages,
        bands=bands,
        crossing_count=0,
        floorplan="reshaped",
    )
    terminals = []
    reverse_rows = candidate["row_order"] == "reverse"

    def physical(lane):
        return p - 1 - lane if reverse_rows else lane

    for s in stages:
        stage_cell = lib.cell(f"STAGE_{s['stage']:02}", "stage")
        lib.ref(groups["FABRIC"], stage_cell, s["x"], s["origin_y"], s["angle"])
        terms = []
        for index in range(count):
            sid = switch_id(s["stage"], index)
            row = p - 2 - 2 * index if reverse_rows else 2 * index
            lib.ref(stage_cell, lib.mzi(), 0, row * pitch, id=sid)
            at = point(s["x"], s["origin_y"], s["angle"], [0, row * pitch])
            m["instances"].append(
                dict(
                    id=sid,
                    cell="MZI",
                    x=at[0],
                    y=at[1],
                    stage=s["stage"],
                    row=row,
                    pin_flip=int(reverse_rows),
                    angle=s["angle"],
                )
            )
            for name in cfg.terminal_names:
                pos = point(*at, s["angle"], lib.mzi().ports[name])
                terms.append(
                    dict(
                        net=f"{sid}:{name}",
                        instance=sid,
                        terminal=name,
                        x=pos[0],
                        y=pos[1],
                    )
                )
        terms.sort(key=lambda t: (t["y"], t["net"]))
        for side, bank in (("south", terms[:count]), ("north", terms[count:])):
            # Increasing y order ensures terminal horizontal M1 runs cannot meet vias.
            for i, t in enumerate(bank):
                terminals.append({**t, "side": side, "tx": s["trunk_xs"][i]})

    def new_route(source, target, start):
        route = dict(
            source=source,
            target=target,
            start=start,
            pieces=[],
            length=0.0,
            crossings=0,
            bends=0,
            angle=0.0,
        )
        m["routes"].append(route)
        return route

    def piece(route, cell, x, y, entry="w", exit="e", angle=0):
        track = next(t for t in cell.tracks if t["ports"] == [entry, exit])
        route["pieces"].append(
            dict(
                cell=cell.name,
                x=snap(x),
                y=snap(y),
                entry=entry,
                exit=exit,
                angle=angle,
            )
        )
        for key in ("length", "crossings", "bends", "angle"):
            route[key] += track[key]

    def placed(parent, route, cell, x, y, entry="w", exit="e", angle=0):
        lib.ref(parent, cell, x, y, angle, id=route["source"])
        piece(route, cell, x, y, entry, exit, angle)

    def straight(parent, route, a, b):
        if a == b:
            return
        if abs(a[1] - b[1]) > cfg.grid:
            raise ValueError("non-horizontal escape")
        angle = 0 if b[0] > a[0] else 180
        placed(parent, route, lib.straight(abs(b[0] - a[0])), *a, angle=angle)

    for lane in range(p):
        y = physical(lane) * pitch
        route = new_route(
            f"in:{lane}", f"{switch_id(0,lane//2)}:i{lane%2}", [io_left, y]
        )
        route["end"] = [stages[0]["x"], y]
        straight(groups["IO_ADAPTERS"], route, route["start"], route["end"])
    for si, s in enumerate(stages):
        parent = lib.cell(f"ROUTING_{si:02}", "interstage")
        lib.ref(groups["INTERSTAGE"], parent)
        angle = s["angle"]
        last = si == net.depth - 1
        nxt = stages[si + 1] if not last else None
        folding = not last and nxt["band"] != s["band"]
        if not last:
            boundary = net.boundaries[si]
            block = lib.shuffle_block(boundary["size"], boundary["inverse"])
            for base in range(0, p, boundary["size"]):
                at = point(s["escape_end"], s["origin_y"], angle, [0, base * pitch])
                lib.ref(parent, block, *at, angle)
        for lane in range(p):
            row = physical(lane)
            dest = net.boundaries[si]["permutation"][lane] if not last else lane
            target = (
                f"{switch_id(si+1,dest//2)}:i{dest%2}" if not last else f"out:{lane}"
            )
            start = point(s["escape_start"], s["origin_y"], angle, [0, row * pitch])
            route = new_route(f"{switch_id(si,lane//2)}:o{lane%2}", target, start)
            at = point(s["escape_end"], s["origin_y"], angle, [0, row * pitch])
            straight(parent, route, start, at)
            if not last:
                base, local = divmod(row, boundary["size"])
                base *= boundary["size"]
                for part in block.tracks[local]["pieces"]:
                    pos = point(
                        s["escape_end"],
                        s["origin_y"],
                        angle,
                        [part["x"], base * pitch + part["y"]],
                    )
                    piece(
                        route,
                        lib.cells[part["cell"]],
                        *pos,
                        part["entry"],
                        part["exit"],
                        angle,
                    )
            output_row = physical(dest)
            at = point(s["route_end"], s["origin_y"], angle, [0, output_row * pitch])
            if folding:
                edge = right if angle == 0 else 0.0
                straight(parent, route, at, [edge, at[1]])
                up = angle == 0
                fan = fan_lane(lib, output_row, up)
                placed(parent, route, fan, edge, s["origin_y"], angle=angle)
                pos = point(edge, s["origin_y"], angle, fan.ports["e"])
                radius = (
                    cfg.fold_gap / 2
                    + ((p - 1 - output_row) if up else output_row) * cfg.bundle_pitch
                )
                turn = return_turn(lib, radius, left=not up)
                placed(parent, route, turn, *pos)
                incoming = fan_lane(lib, p - 1 - output_row, not up)
                incoming_y = nxt["y"] if angle == 0 else nxt["y"] + h
                placed(parent, route, incoming, edge, incoming_y, "e", "w", angle)
                end = point(
                    nxt["x"], nxt["origin_y"], nxt["angle"], [0, output_row * pitch]
                )
                straight(parent, route, [edge, end[1]], end)
            else:
                end = (
                    point(
                        nxt["x"], nxt["origin_y"], nxt["angle"], [0, output_row * pitch]
                    )
                    if nxt
                    else [io_right, at[1]]
                )
                straight(parent, route, at, end)
            route["end"] = end
    for side, mapping in (("west", cfg.input_map), ("east", cfg.output_map)):
        active = {v: i for i, v in enumerate(mapping)}
        for lane in range(p):
            at = [
                io_left if side == "west" else io_right,
                (0 if side == "west" else bands[-1]["y"]) + physical(lane) * pitch,
            ]
            m["interfaces"].append(
                dict(side=side, internal=lane, active=active.get(lane), position=at)
            )
            if lane in active:
                top.ports[f"{'in' if side=='west' else 'out'}_{active[lane]}"] = [
                    *at,
                    180 if side == "west" else 0,
                ]
            else:
                cell = lib.termination(side)
                tid = f"spare_{side}_{lane}"
                lib.ref(groups["SPARE_TERMINATIONS"], cell, *at, id=tid)
                m["terminations"].append(
                    dict(
                        id=tid,
                        cell=cell.name,
                        side=side,
                        internal=lane,
                        x=at[0],
                        y=at[1],
                    )
                )
    extra = cfg.termination_length if p > cfg.active_ports else 0
    edge = (cfg.mzi_height - pitch) / 2
    optical = [io_left - extra, -edge, io_right + extra, bands[-1]["y"] + h + edge]
    pads = route_pads(lib, m, groups, terminals, step=step, optical_bounds=optical)
    m["die_bbox"] = [
        snap(min(optical[0], pads[0]) - cfg.margin),
        snap(pads[1] - cfg.margin),
        snap(max(optical[2], pads[2]) + cfg.margin),
        snap(pads[3] + cfg.margin),
    ]
    m["width"] = snap(m["die_bbox"][2] - m["die_bbox"][0])
    m["height"] = snap(m["die_bbox"][3] - m["die_bbox"][1])
    m["extents"] = dict(
        core=optical,
        fanout=[optical[0], pads[1], optical[2], pads[3]],
        pads=pads,
        terminations=(
            [
                io_left - cfg.termination_length,
                0,
                io_right + cfg.termination_length,
                bands[-1]["y"] + h,
            ]
            if m["terminations"]
            else None
        ),
    )
    m["crossing_count"] = sum(r["crossings"] for r in m["routes"]) // 2
    frame = lib.cell("DIE_OUTLINE", "outline")
    lib.ref(top, frame)
    a, b, c, d = m["die_bbox"]
    for rect in (
        (a, b, c, b + 1),
        (a, d - 1, c, d),
        (a, b, a + 1, d),
        (c - 1, b, c, d),
    ):
        lib.poly(frame, "OUTLINE", rectangle(*rect))
    reachable = set()

    def visit(name):
        if name in reachable:
            return
        reachable.add(name)
        for ref in lib.cells[name].refs:
            visit(ref["cell"])

    visit(top.name)
    lib.cells = {k: v for k, v in lib.cells.items() if k in reachable}
    m["cells"] = lib.export()
    return lib, m
