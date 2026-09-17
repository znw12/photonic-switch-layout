"""Regular stages, reusable Beneš shuffles and compact two-metal escape.

Trunks leave each stage at fine pitch. A second M1 fanout above/below the
optical fabric expands these to package pads; three explicit vias join each
terminal-pad net. This separates pad pitch from interstage optical routing.
"""

from .config import Config
from .geometry import Library, rectangle, snap, validate_components
from .network import Network, switch_id


def build_layout(cfg: Config, candidate=None, component_factory=None):
    candidate = candidate or dict(
        id="compact", gap=1.0, row_order="normal", pad=1.0, corridor=1.0
    )
    lib, net = Library(cfg), Network(cfg)
    if component_factory:
        component_factory(lib)
    validate_components(lib)
    if not cfg.insulated_m2_overpasses:
        raise ValueError(
            "this routing profile requires declared insulated M2 overpasses"
        )
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
    reverse = candidate["row_order"] == "reverse"

    def physical(lane):
        return p - 1 - lane if reverse else lane

    m = {
        "config": cfg.to_dict(),
        "candidate": candidate,
        "network": net.export(),
        "top": top.name,
        "instances": [],
        "routes": [],
        "electrical": [],
        "overpasses": [],
        "interfaces": [],
        "terminations": [],
        "stages": [],
        "crossing_count": 0,
    }

    def piece(route, cell, x, y, entry, exit):
        track = next(t for t in cell.tracks if t["ports"] == [entry, exit])
        part = dict(cell=cell.name, x=snap(x), y=snap(y), entry=entry, exit=exit)
        route["pieces"].append(part)
        for key in ("length", "crossings", "bends", "angle"):
            route[key] += track[key]

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

    def straight(parent, route, x, y, length):
        if length <= 0:
            return
        cell = lib.straight(snap(length))
        lib.ref(parent, cell, x, y, id=route["source"])
        piece(route, cell, x, y, "w", "e")

    guard = max(cfg.margin, cfg.termination_length + cfg.wg_clearance)
    pad_step = snap(cfg.pad_pitch * candidate["pad"])
    bank_count = p // 2
    landing = cfg.via_size + 2 * cfg.via_enclosure
    track_step = snap(max(landing, cfg.metal_width) + cfg.metal_spacing + 2 * cfg.grid)
    fanout_guard = cfg.margin
    fanout_height = fanout_guard + (bank_count - 1) * track_step
    optical_top = (p - 1) * pitch
    pad_n = snap(optical_top + fanout_height + cfg.margin + cfg.pad_size / 2)
    pad_s = snap(-fanout_height - cfg.margin - cfg.pad_size / 2)
    stage_xs = []
    cursor = guard
    for s in range(net.depth):
        stage_x = snap(cursor)
        pad_xs = [
            snap(cursor + cfg.pad_size / 2 + i * pad_step) for i in range(bank_count)
        ]
        escape_start = snap(stage_x + cfg.mzi_length)
        keep = cfg.optical_metal_clearance + landing / 2 + cfg.wg_width / 2
        trunks = []
        x = snap(escape_start + keep)
        # Trunks and pad stems are both M2, so they must have distinct x lanes
        # even outside the optical array. Candidate corridor factors vary this.
        min_dx = landing / 2 + cfg.metal_width / 2 + cfg.metal_spacing + 2 * cfg.grid
        while len(trunks) < bank_count:
            if all(abs(x - px) >= min_dx for px in pad_xs):
                trunks.append(x)
            x = snap(x + track_step * candidate["corridor"])
        escape_end = snap(trunks[-1] + keep)
        route_width = 0.0
        if s < net.depth - 1:
            boundary = net.boundaries[s]
            block = lib.shuffle_block(boundary["size"], boundary["inverse"])
            route_width = block.metadata["width"]
        minimum_end = max(
            escape_end + route_width + guard,
            pad_xs[-1] + cfg.pad_size / 2 + (pad_step - cfg.pad_size),
        )
        end = snap(stage_x + (minimum_end - stage_x) * candidate["gap"])
        stage_xs.append(stage_x)
        m["stages"].append(
            dict(
                stage=s,
                x=stage_x,
                escape_start=escape_start,
                escape_end=escape_end,
                route_end=escape_end + route_width,
                end=end,
                pad_xs=pad_xs,
                trunk_xs=trunks,
            )
        )
        cursor = end
    out_x = snap(cursor)
    for s, stage in enumerate(m["stages"]):
        stage_cell = lib.cell(f"STAGE_{s:02}", "stage")
        lib.ref(groups["FABRIC"], stage_cell, stage["x"], id=f"stage{s}")
        terminals = []
        for index in range(p // 2):
            sid = switch_id(s, index)
            row = p - 2 - 2 * index if reverse else 2 * index
            lib.ref(stage_cell, lib.mzi(), 0, row * pitch, id=sid)
            inst = dict(
                id=sid,
                cell="MZI",
                x=stage["x"],
                y=row * pitch,
                stage=s,
                row=row,
                pin_flip=int(reverse),
            )
            m["instances"].append(inst)
            for name, offset in zip(cfg.terminal_names, cfg.terminal_offsets):
                terminals.append(
                    dict(
                        net=f"{sid}:{name}",
                        instance=sid,
                        terminal=name,
                        x=stage["escape_start"],
                        y=snap(row * pitch + offset),
                    )
                )
        terminals.sort(key=lambda t: (t["y"], t["net"]))
        for side, group in (
            ("south", terminals[:bank_count]),
            ("north", terminals[bank_count:]),
        ):
            sign = 1 if side == "north" else -1
            for i, t in enumerate(group):
                tx, px = stage["trunk_xs"][i], stage["pad_xs"][i]
                fy = snap(
                    (optical_top if sign == 1 else 0)
                    + sign * (fanout_guard + i * track_step)
                )
                py = pad_n if sign == 1 else pad_s
                cell = lib.cell(f"NET_{s}_{side}_{i}", "electrical_route")
                w = cfg.metal_width

                def metal(layer, a, b):
                    if a[0] == b[0]:
                        lib.poly(
                            cell,
                            layer,
                            rectangle(
                                a[0] - w / 2,
                                min(a[1], b[1]),
                                a[0] + w / 2,
                                max(a[1], b[1]),
                            ),
                        )
                    else:
                        lib.poly(
                            cell,
                            layer,
                            rectangle(
                                min(a[0], b[0]),
                                a[1] - w / 2,
                                max(a[0], b[0]),
                                a[1] + w / 2,
                            ),
                        )

                metal("M1", (t["x"], t["y"]), (tx, t["y"]))
                metal("M2", (tx, t["y"]), (tx, fy))
                metal("M1", (tx, fy), (px, fy))
                metal("M2", (px, fy), (px, py))
                vias = [[tx, t["y"]], [tx, fy], [px, fy]]
                for v in vias:
                    lib.ref(cell, lib.via(), *v)
                lib.ref(groups["ELECTRICAL_FANOUT"], cell, id=t["net"])
                lib.ref(groups[side.upper() + "_PADS"], lib.pad(), px, py, id=t["net"])
                m["electrical"].append(
                    {
                        **t,
                        "cell": cell.name,
                        "side": side,
                        "pad": [px, py],
                        "vias": vias,
                        "fanout_y": fy,
                    }
                )
                for lane in range(p):
                    y = lane * pitch
                    if min(t["y"], fy) < y < max(t["y"], fy):
                        m["overpasses"].append(dict(net=t["net"], x=tx, y=y))
    # Every logical edge is recorded, including spare interfaces. Geometry uses
    # physical rows while endpoint labels retain the original logical identity.
    for lane in range(p):
        y = physical(lane) * pitch
        route = new_route(f"in:{lane}", f"{switch_id(0,lane//2)}:i{lane%2}", [0, y])
        straight(groups["IO_ADAPTERS"], route, 0, y, stage_xs[0])
        route["end"] = [stage_xs[0], y]
    for s, stage in enumerate(m["stages"]):
        parent = lib.cell(f"ROUTING_{s:02}", "interstage")
        lib.ref(groups["INTERSTAGE"], parent)
        if s < net.depth - 1:
            boundary = net.boundaries[s]
            block = lib.shuffle_block(boundary["size"], boundary["inverse"])
            for base in range(0, p, boundary["size"]):
                lib.ref(
                    parent, block, stage["escape_end"], base * pitch, id=f"block_{base}"
                )
        for lane in range(p):
            row = physical(lane)
            y = row * pitch
            source = f"{switch_id(s,lane//2)}:o{lane%2}"
            dest_lane = (
                net.boundaries[s]["permutation"][lane] if s < net.depth - 1 else lane
            )
            target = (
                f"{switch_id(s+1,dest_lane//2)}:i{dest_lane%2}"
                if s < net.depth - 1
                else f"out:{lane}"
            )
            route = new_route(source, target, [stage["escape_start"], y])
            straight(
                parent,
                route,
                stage["escape_start"],
                y,
                stage["escape_end"] - stage["escape_start"],
            )
            if s < net.depth - 1:
                size = boundary["size"]
                base, local = row // size * size, row % size
                track = block.tracks[local]
                for part in track["pieces"]:
                    piece(
                        route,
                        lib.cells[part["cell"]],
                        stage["escape_end"] + part["x"],
                        base * pitch + part["y"],
                        part["entry"],
                        part["exit"],
                    )
                end_y = physical(dest_lane) * pitch
                straight(
                    parent,
                    route,
                    stage["route_end"],
                    end_y,
                    stage["end"] - stage["route_end"],
                )
                route["end"] = [stage["end"], end_y]
            else:
                straight(
                    parent, route, stage["escape_end"], y, out_x - stage["escape_end"]
                )
                route["end"] = [out_x, y]
    for side, mapping in (("west", cfg.input_map), ("east", cfg.output_map)):
        active = {v: i for i, v in enumerate(mapping)}
        for lane in range(p):
            at = [0 if side == "west" else out_x, physical(lane) * pitch]
            item = dict(side=side, internal=lane, active=active.get(lane), position=at)
            m["interfaces"].append(item)
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
    m["crossing_count"] = sum(r["crossings"] for r in m["routes"]) // 2
    spare_extra = cfg.termination_length if p > cfg.active_ports else 0
    m["die_bbox"] = [
        snap(-spare_extra - cfg.margin),
        snap(pad_s - cfg.pad_size / 2 - cfg.margin),
        snap(out_x + spare_extra + cfg.margin),
        snap(pad_n + cfg.pad_size / 2 + cfg.margin),
    ]
    m["width"] = snap(m["die_bbox"][2] - m["die_bbox"][0])
    m["height"] = snap(m["die_bbox"][3] - m["die_bbox"][1])
    edge = (cfg.mzi_height - pitch) / 2
    m["extents"] = {
        "core": [
            stage_xs[0],
            -edge,
            m["stages"][-1]["escape_start"],
            optical_top + edge,
        ],
        "fanout": [stage_xs[0], -fanout_height, out_x, optical_top + fanout_height],
        "terminations": (
            [
                -cfg.termination_length,
                -cfg.wg_width / 2,
                out_x + cfg.termination_length,
                optical_top + cfg.wg_width / 2,
            ]
            if m["terminations"]
            else None
        ),
        "pads": [
            stage_xs[0],
            pad_s - cfg.pad_size / 2,
            max(v["pad"][0] for v in m["electrical"]) + cfg.pad_size / 2,
            pad_n + cfg.pad_size / 2,
        ],
    }
    a, b, c, d = m["die_bbox"]
    frame = lib.cell("DIE_OUTLINE", "outline")
    lib.ref(top, frame)
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
