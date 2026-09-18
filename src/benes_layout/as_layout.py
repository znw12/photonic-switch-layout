"""Single-band exact-size physical layout with column-owned shared grounds."""

from .geometry import Library, snap, rectangle, point
from .network import Network
from .as_geometry import shuffle, variants, ground_column
from .interstage import segment
from .as_channel import plan_channels


def profile(cfg):
    if not (
        cfg.topology == "as-benes"
        and cfg.active_ports >= 2
        and cfg.mzi_model == "paper-gsg"
        and cfg.lane_pitch in (34, 35)
        and cfg.pad_rows == 2
        and cfg.pad_pitch == 100
        and cfg.pad_row_stagger == 50
        and cfg.pad_size == 60
        and cfg.pad_row_pitch >= 70
        and cfg.share_interstage
        and cfg.crossing_model == "cosine"
        and cfg.ground_pads_per_side > 0
        and cfg.interstage_routing == "continuous"
        and cfg.insulated_m2_overpasses
    ):
        raise ValueError(
            "AS physical profile requires GSG, 34/35 um pitch, continuous optics and two staggered 100 um pad rows"
        )


def assign_banks(net):
    # Balanced banks even when an odd bypass makes individual columns uneven.
    items = sorted(
        net.switches.items(), key=lambda v: (v[1]["row"], v[1]["stage"], v[0])
    )
    south = {sid for sid, _ in items[: len(items) // 2]}
    return {sid: ("south" if sid in south else "north") for sid in net.switches}


def slots(count, center, cfg):
    raw = [
        dict(
            row=i % 2,
            column=i // 2,
            offset=(i % 2) * 50,
            px=(i // 2) * 100 + (i % 2) * 50,
        )
        for i in range(count)
    ]
    origin = snap(center - (raw[-1]["px"] if raw else 0) / 2)
    return [{**v, "px": snap(v["px"] + origin)} for v in raw]


def placement(cfg, net, widths, exits, bank_map, pad_phase=0):
    landing = cfg.via_size + 2 * cfg.via_enclosure
    step = snap((landing + cfg.metal_width) / 2 + cfg.metal_spacing + 2 * cfg.grid)
    keep = cfg.optical_metal_clearance + landing / 2 + cfg.wg_width / 2 + 2 * cfg.grid
    counts = [
        max(
            sum(
                v["stage"] == s and bank_map[sid] == bank
                for sid, v in net.switches.items()
            )
            for bank in ("south", "north")
        )
        for s in range(net.depth)
    ]
    taps = min(cfg.ground_pads_per_side, net.depth)
    bank_counts = {
        b: sum(x == b for x in bank_map.values()) + taps for b in ("south", "north")
    }
    pad_span = max((c - 1) * 50 + cfg.pad_size for c in bank_counts.values())
    width = max(
        pad_span + 2 * cfg.margin,
        sum(widths) + net.depth * cfg.mzi_length + 2 * cfg.margin,
    )
    for attempt in range(50):
        grids = {
            b: slots(n, width / 2 + pad_phase, cfg) for b, n in bank_counts.items()
        }
        stages = []
        cursor = cfg.margin
        prev_right = []
        for s in range(net.depth):
            # Right trunks of the previous column and left trunks of this one
            # occupy disjoint parts of their common gap.
            lo = cursor
            if s == 0:
                start = cfg.margin
            else:
                start = stages[-1]["x"] + cfg.mzi_length + max(widths[s - 1], 2 * keep)
                if prev_right:
                    start = max(start, prev_right[-1] + keep)
            left = []
            if exits[s] == "L":
                left = [snap(lo + keep + i * step) for i in range(counts[s])]
                start = max(start, left[-1] + keep)
            x = snap(start)
            if s:
                tail = x - (stages[-1]["x"] + cfg.mzi_length + widths[s - 1])
                minimum_tail = cfg.wg_clearance + cfg.wg_width + 2 * cfg.grid
                if cfg.grid < tail < minimum_tail:
                    x = snap(x + minimum_tail - tail)
            right = (
                [snap(x + cfg.mzi_length + keep + i * step) for i in range(counts[s])]
                if exits[s] == "R"
                else []
            )
            stages.append(
                dict(
                    stage=s,
                    x=x,
                    exit_side=exits[s],
                    trunk_xs=right if right else list(reversed(left)),
                )
            )
            cursor = snap((right[-1] if right else x + cfg.mzi_length) + keep)
            prev_right = right
        right_edge = snap(max(cursor, stages[-1]["x"] + cfg.mzi_length) + cfg.margin)
        target = max(right_edge, pad_span + 2 * cfg.margin + 2 * abs(pad_phase))
        if target <= width + 0.001:
            return stages, snap(width), grids, step
        width = snap(target + 2 * cfg.grid)
    raise ValueError("AS pad/trunk placement failed to converge")


def build(cfg, candidate=None):
    profile(cfg)
    lib, net = Library(cfg), Network(cfg)
    candidate = candidate or dict(id="as-right", exits="R" * net.depth, pad_phase=0)
    exits = candidate["exits"]
    if len(exits) != net.depth or any(v not in "LR" for v in exits):
        raise ValueError("invalid column exit directions")
    devs = variants(lib)
    blocks = [
        [shuffle(lib, b["size"], b["inverse"]) for b in boundary["blocks"]]
        for boundary in net.boundaries
    ]
    widths = [max((b.metadata["width"] for b in group), default=0) for group in blocks]
    bank_map = assign_banks(net)
    stages, width, grids, step = placement(
        cfg, net, widths, exits, bank_map, candidate.get("pad_phase", 0)
    )
    p = cfg.lane_pitch
    origin = snap(-(net.p - 1) * p / 2)
    top = lib.cell("AS_BENES_CHIP", "chip")
    groups = {
        name: lib.cell(name, "group")
        for name in (
            "FABRIC",
            "INTERSTAGE",
            "IO_ADAPTERS",
            "ELECTRICAL_FANOUT",
            "NORTH_PADS",
            "SOUTH_PADS",
            "GROUND",
        )
    }
    for cell in groups.values():
        lib.ref(top, cell)
    m = dict(
        config=cfg.to_dict(),
        candidate=candidate,
        top=top.name,
        network=net.export(),
        instances=[],
        stages=stages,
        routes=[],
        electrical=[],
        interfaces=[],
        ground_rails=[],
        bypasses=[],
        crossing_count=0,
        floorplan="as-benes",
        bands=[dict(band=0, y=origin, stages=list(range(net.depth)))],
    )
    terminals = []
    for stage in stages:
        s, x, side = stage["stage"], stage["x"], stage["exit_side"]
        stage.update(y=origin, origin_y=origin, angle=0, band=0)
        column = lib.cell(f"AS_COLUMN_{s}", "stage")
        lib.ref(groups["FABRIC"], column, x, origin)
        members = sorted(
            ((sid, v) for sid, v in net.switches.items() if v["stage"] == s),
            key=lambda it: it[1]["row"],
        )
        rows = [v["row"] for _, v in members]
        ground = ground_column(lib, side, rows)
        lib.ref(column, ground)
        for rail in ground.metadata["rails"]:
            m["ground_rails"].append(
                dict(
                    stage=s,
                    cell=ground.name,
                    bounds=[
                        snap(rail["bounds"][0] + x),
                        snap(rail["bounds"][1] + origin),
                        snap(rail["bounds"][2] + x),
                        snap(rail["bounds"][3] + origin),
                    ],
                    contact=point(x, origin, 0, rail["contact"]),
                    run=rail["run"],
                )
            )
        for sid, v in members:
            row = v["row"]
            dev = devs[side]
            y = snap(origin + row * p)
            lib.ref(column, dev, 0, row * p, id=sid)
            m["instances"].append(
                dict(id=sid, cell=dev.name, x=x, y=y, stage=s, row=row, angle=0)
            )
            at = point(x, y, 0, dev.ports["S"])
            terminals.append(
                dict(
                    net=sid + ":S",
                    instance=sid,
                    terminal="S",
                    electrical_net=sid + ":S",
                    stage=s,
                    source_layer="M2",
                    x=at[0],
                    y=at[1],
                    side=bank_map[sid],
                )
            )
        for by in (b for b in net.bypasses if b["stage"] == s):
            row = by["row"]
            c = lib.straight(cfg.mzi_length)
            lib.ref(column, c, 0, row * p, id=f"bypass_{s}_{row}")
            m["bypasses"].append(
                dict(stage=s, row=row, cell=c.name, x=x, y=snap(origin + row * p))
            )
        for bank in ("south", "north"):
            ts = sorted(
                (t for t in terminals if t["stage"] == s and t["side"] == bank),
                key=lambda t: t["y"],
                reverse=bank == "north",
            )
            for t, tx in zip(ts, stage["trunk_xs"]):
                t["tx"] = tx
    # Per-lane optical route pieces provide independent endpoint and metric checks.
    for s, boundary in enumerate(net.boundaries):
        left = snap(stages[s]["x"] + cfg.mzi_length)
        right = stages[s + 1]["x"]
        cell = lib.cell(f"AS_ROUTING_{s}", "routing")
        lib.ref(groups["INTERSTAGE"], cell, left, origin)
        used = set()
        span = right - left
        for desc, block in zip(boundary["blocks"], blocks[s]):
            base = desc["base"]
            lib.ref(cell, block, 0, base * p)
            m["crossing_count"] += sum(t["crossings"] for t in block.tracks) // 2
            for i, track in enumerate(block.tracks):
                row = base + i
                dest = base + desc["permutation"][i]
                used.add(row)
                pieces = [
                    {
                        **v,
                        "x": snap(left + v["x"]),
                        "y": snap(origin + base * p + v["y"]),
                    }
                    for v in track["pieces"]
                ]
                tail = segment(
                    lib, [block.metadata["width"], dest * p], [span, dest * p]
                )
                if tail:
                    lib.ref(cell, tail)
                    pieces.append(
                        dict(
                            cell=tail.name,
                            x=left,
                            y=origin,
                            angle=0,
                            entry="w",
                            exit="e",
                        )
                    )
                m["routes"].append(dict(stage=s, row=row, dest=dest, pieces=pieces))
        for row in set(range(net.p)) - used:
            c = segment(lib, [0, row * p], [span, row * p])
            lib.ref(cell, c)
            m["routes"].append(
                dict(
                    stage=s,
                    row=row,
                    dest=row,
                    pieces=[
                        dict(
                            cell=c.name, x=left, y=origin, angle=0, entry="w", exit="e"
                        )
                    ],
                )
            )
    for side, xx, endx in (
        ("west", 0, stages[0]["x"]),
        ("east", stages[-1]["x"] + cfg.mzi_length, width),
    ):
        for row in range(net.p):
            y = snap(origin + row * p)
            c = segment(lib, [xx, y], [endx, y])
            lib.ref(groups["IO_ADAPTERS"], c)
            m["interfaces"].append(
                dict(
                    side=side,
                    internal=row,
                    active=(cfg.input_map if side == "west" else cfg.output_map).index(
                        row
                    ),
                    position=[xx if side == "west" else endx, y],
                    cell=c.name,
                )
            )
    edge = max(abs(origin), abs(origin + (net.p - 1) * p)) + p / 2
    ground_y = snap(edge + cfg.margin / 2)
    ground_cell = groups["GROUND"]
    ground_segments = []
    ground_vias = []

    def wire(cell, layer, a, b, record):
        if a == b:
            return
        a, b = [snap(v) for v in a], [snap(v) for v in b]
        half = cfg.metal_width / 2
        lib.poly(
            cell,
            layer,
            rectangle(
                min(a[0], b[0]) - half,
                min(a[1], b[1]) - half,
                max(a[0], b[0]) + half,
                max(a[1], b[1]) + half,
            ),
        )
        record.append(dict(layer=layer, start=a, end=b))

    gxs = [snap(s["x"] + (780 if s["exit_side"] == "R" else 220)) for s in stages]
    for x in gxs:
        wire(ground_cell, "M2", [x, -ground_y], [x, ground_y], ground_segments)
    for sign in (-1, 1):
        wire(
            ground_cell,
            "M1",
            [gxs[0], sign * ground_y],
            [gxs[-1], sign * ground_y],
            ground_segments,
        )
        for x in gxs:
            lib.ref(ground_cell, lib.via(), x, sign * ground_y)
            ground_vias.append([x, sign * ground_y])
    from .local_ground import tap_stages

    taps = tap_stages(net.depth, min(cfg.ground_pads_per_side, net.depth))
    for bank, sign in (("north", 1), ("south", -1)):
        for s in taps:
            terminals.append(
                dict(
                    net=f"G_{bank}_{s}",
                    instance=None,
                    terminal="G",
                    electrical_net="GND",
                    source_layer="M2",
                    stage=s,
                    x=gxs[s],
                    y=sign * ground_y,
                    tx=gxs[s],
                    side=bank,
                )
            )
    # Vertical precedence prevents foreign trunks and pad stems at nearby x
    # from coexisting at the same y; no full-height stem exclusion is needed.
    banks = {
        b: sorted(
            (t for t in terminals if t["side"] == b), key=lambda t: (t["tx"], t["net"])
        )
        for b in ("south", "north")
    }
    grids, levels, channel_plan = plan_channels(banks, grids, width, cfg)
    level_step = cfg.via_size + 2 * cfg.via_enclosure + cfg.metal_spacing + 0.002
    maxlevel = max(max(v) for v in levels.values())
    fanbase = ground_y + level_step
    transfer = snap(fanbase + maxlevel * level_step)
    padbase = snap(
        transfer
        + cfg.pad_size / 2
        + cfg.via_size / 2
        + cfg.via_enclosure
        + cfg.metal_spacing
        + 2 * cfg.grid
    )
    for bank, sign in (("south", -1), ("north", 1)):
        for i, (t, slot, level) in enumerate(
            zip(banks[bank], grids[bank], levels[bank])
        ):
            tx, sx = t["tx"], slot["px"]
            fy = snap(sign * (fanbase + level * level_step))
            py = snap(sign * (padbase + slot["row"] * cfg.pad_row_pitch))
            cell = lib.cell(f"AS_NET_{bank}_{i}", "electrical_route")
            segments = []
            direct = abs(tx - sx) < cfg.grid
            wire(cell, "M2", [t["x"], t["y"]], [tx, t["y"]], segments)
            wire(cell, "M2", [tx, t["y"]], [tx, py if direct else fy], segments)
            via_points = []
            if not direct:
                wire(cell, "M1", [tx, fy], [sx, fy], segments)
                wire(cell, "M2", [sx, fy], [sx, py], segments)
                if (
                    abs(tx - sx)
                    < cfg.via_size + 2 * cfg.via_enclosure + cfg.metal_spacing
                ):
                    wire(cell, "M2", [tx, fy], [sx, fy], segments)
                    # A single landing on the continuous same-net bridge
                    # avoids duplicate/overlapping via cuts for close endpoints.
                    via_points.append([snap((tx + sx) / 2), fy])
                else:
                    via_points += [[tx, fy], [sx, fy]]
            # Half-pitch staggering leaves a clear M2 corridor to the outer
            # row. Keep the stem on the pad layer; no terminal underpass/vias.
            for at in via_points:
                lib.ref(cell, lib.via(), *at)
            lib.ref(groups["ELECTRICAL_FANOUT"], cell, id=t["net"])
            lib.ref(groups[bank.upper() + "_PADS"], lib.pad(), sx, py, id=t["net"])
            m["electrical"].append(
                {
                    **t,
                    "cell": cell.name,
                    "pad": [sx, py],
                    "pad_row": slot["row"],
                    "pad_column": slot["column"],
                    "pad_row_offset": slot["offset"],
                    "vias": via_points,
                    "segments": segments,
                    "direct_pad": direct,
                    "channel_level": level,
                }
            )
    m["ground_network"] = dict(
        net="GND",
        segments=ground_segments,
        vias=ground_vias,
        tap_stages=taps,
        ground_pads=2 * len(taps),
    )
    m["electrical_plan"] = dict(
        mode="as-two-row",
        pad_connection="direct-m2",
        pad_placement=cfg.pad_distribution,
        channel_ordering=channel_plan,
        channel_levels=maxlevel + 1,
        transfer_y=transfer,
        pad_base_y=padbase,
        ground_y=ground_y,
        pad_grids=grids,
        passive_m2_contract="insulated-placeholder-v1",
    )
    ymax = snap(padbase + cfg.pad_row_pitch + cfg.pad_size / 2 + cfg.margin)
    xmin = min(
        -3 * cfg.grid,
        min(v["px"] for ss in grids.values() for v in ss)
        - cfg.pad_size / 2
        - cfg.margin,
    )
    xmax = max(
        width + 3 * cfg.grid,
        max(v["px"] for ss in grids.values() for v in ss)
        + cfg.pad_size / 2
        + cfg.margin,
    )
    m.update(
        die_bbox=[snap(xmin), -ymax, snap(xmax), ymax],
        width=snap(xmax - xmin),
        height=snap(2 * ymax),
    )
    m["extents"] = dict(
        core=[0, origin - p / 2, width, -origin + p / 2],
        pads=[
            min(e["pad"][0] for e in m["electrical"]) - 30,
            -padbase - cfg.pad_row_pitch - 30,
            max(e["pad"][0] for e in m["electrical"]) + 30,
            padbase + cfg.pad_row_pitch + 30,
        ],
    )
    lib.poly(top, "OUTLINE", rectangle(*m["die_bbox"]))
    # Export exactly the reachable hierarchy (the assembled source MZI is a
    # verification fixture, not an extra fabricated device).
    reachable = set()

    def visit(name):
        if name in reachable:
            return
        reachable.add(name)
        for r in lib.cells[name].refs:
            visit(r["cell"])

    visit(top.name)
    lib.cells = {k: v for k, v in lib.cells.items() if k in reachable}
    m["cells"] = lib.export()
    return lib, m
