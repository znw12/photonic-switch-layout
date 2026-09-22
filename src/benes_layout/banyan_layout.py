"""Sparse Banyan physical graph with explicit pin terminations."""

from math import pi
from .geometry import Library, snap, point
from .network import Network
from .as_geometry import variants, ground_column
from .as_layout import assign_banks, placement as base_placement, complete_layout
from .banyan_geometry import masked_shuffle, io_adapter, terminal_keep
from .interstage import segment, shift_dimensions


def profile(cfg):
    from dataclasses import replace
    from .as_layout import profile as as_profile

    # Validate the identical physical contract without changing this network.
    as_profile(
        replace(
            cfg,
            topology="as-benes",
            internal_ports=cfg.active_ports,
            input_map=None,
            output_map=None,
        )
    )
    if cfg.topology != "pruned-banyan":
        raise ValueError("Banyan layout requires pruned-banyan configuration")


def port_keeps(cfg, net, exits, bank_map):
    """Straight terminal corridors; electrical placement excludes their bodies."""
    keep = terminal_keep(cfg)
    return tuple(
        [
            (
                keep
                if any(
                    t["stage"] == s and t["pin"][0] == direction
                    for t in net.terminations
                )
                else 0
            )
            for s in range(net.depth)
        ]
        for direction in ("i", "o")
    )


def placement(cfg, net, widths, exits, bank_map, pad_phase=0):
    ins, outs = port_keeps(cfg, net, exits, bank_map)
    widths = [w + outs[s] + ins[s + 1] for s, w in enumerate(widths)]
    stages, width, grids, step = base_placement(
        cfg, net, widths, exits, bank_map, pad_phase, input_keeps=ins, output_keeps=outs
    )
    # Shift the entire floorplan if the first input corridor needs more room.
    shift = max(0, ins[0] + cfg.margin - stages[0]["x"])
    if shift:
        for stage in stages:
            stage["x"] = snap(stage["x"] + shift)
            stage["trunk_xs"] = [snap(x + shift) for x in stage["trunk_xs"]]
        width += shift
    delta = max((row - i) * cfg.lane_pitch for i, row in enumerate(cfg.output_map))
    fanwidth = shift_dimensions(delta, cfg.radius, max_angle=pi / 4)[0]
    width = max(
        width, stages[-1]["x"] + cfg.mzi_length + outs[-1] + fanwidth + cfg.margin
    )
    return stages, snap(width), grids, step


def build(cfg, candidate=None):
    profile(cfg)
    lib, net = Library(cfg), Network(cfg)
    candidate = candidate or dict(id="banyan-right", exits="R" * net.depth, pad_phase=0)
    exits = candidate["exits"]
    if len(exits) != net.depth or any(v not in "LR" for v in exits):
        raise ValueError("invalid column exit directions")
    devs = variants(lib)
    blocks = [
        [masked_shuffle(lib, b["size"], b["active"]) for b in bd["blocks"]]
        for bd in net.boundaries
    ]
    widths = [max((b.metadata["width"] for b in group), default=0) for group in blocks]
    bank_map = assign_banks(net)
    stages, width, grids, step = placement(
        cfg, net, widths, exits, bank_map, candidate.get("pad_phase", 0)
    )
    ins, outs = port_keeps(cfg, net, exits, bank_map)
    p = cfg.lane_pitch
    origin = snap(-(net.p - 1) * p / 2)
    top = lib.cell("PRUNED_BANYAN_CHIP", "chip")
    groups = {
        name: lib.cell(name, "group")
        for name in (
            "FABRIC",
            "INTERSTAGE",
            "IO_ADAPTERS",
            "TERMINATIONS",
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
        terminations=[],
        ground_rails=[],
        bypasses=[],
        crossing_count=0,
        floorplan="pruned-banyan",
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
        for bank in ("south", "north"):
            ts = sorted(
                (t for t in terminals if t["stage"] == s and t["side"] == bank),
                key=lambda t: t["y"],
                reverse=bank == "north",
            )
            for t, tx in zip(ts, stage["trunk_xs"]):
                t["tx"] = tx
    for s, boundary in enumerate(net.boundaries):
        left = snap(stages[s]["x"] + cfg.mzi_length)
        right = stages[s + 1]["x"]
        cell = lib.cell(f"BANYAN_ROUTING_{s}", "routing")
        lib.ref(groups["INTERSTAGE"], cell, left, origin)
        span = snap(right - left)
        for desc, block in zip(boundary["blocks"], blocks[s]):
            base = desc["base"]
            lib.ref(cell, block, outs[s], base * p)
            m["crossing_count"] += block.metadata["crossing_count"]
            for t in block.tracks:
                row = base + int(t["ports"][0][1:])
                dest = base + int(t["ports"][1][1:])
                pieces = []
                lead = segment(lib, [0, row * p], [outs[s], row * p])
                if lead:
                    lib.ref(cell, lead)
                    pieces.append(
                        dict(
                            cell=lead.name,
                            x=left,
                            y=origin,
                            angle=0,
                            entry="w",
                            exit="e",
                        )
                    )
                pieces += [
                    {
                        **v,
                        "x": snap(left + outs[s] + v["x"]),
                        "y": snap(origin + base * p + v["y"]),
                    }
                    for v in t["pieces"]
                ]
                tail = segment(
                    lib, [outs[s] + block.metadata["width"], dest * p], [span, dest * p]
                )
                if tail:
                    lib.ref(cell, tail)
                if tail:
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
    instances = {i["id"]: i for i in m["instances"]}
    for term in net.terminations:
        inst = instances[term["switch"]]
        pin = devs[exits[term["stage"]]].ports[term["pin"]]
        at = point(inst["x"], inst["y"], 0, pin)
        side = "west" if term["pin"].startswith("i") else "east"
        cell = lib.termination(side)
        extent = (ins if side == "west" else outs)[term["stage"]]
        tx = snap(
            at[0] + (-1 if side == "west" else 1) * (extent - cfg.termination_length)
        )
        lead = (
            segment(lib, [tx, at[1]], at)
            if side == "west"
            else segment(lib, at, [tx, at[1]])
        )
        pieces = []
        if lead:
            lib.ref(groups["TERMINATIONS"], lead)
            pieces = [dict(cell=lead.name, x=0, y=0, angle=0, entry="w", exit="e")]
        lib.ref(groups["TERMINATIONS"], cell, tx, at[1], id=term["id"])
        m["terminations"].append(
            {
                **term,
                "cell": cell.name,
                "x": tx,
                "y": at[1],
                "angle": 0,
                "side": side,
                "pieces": pieces,
            }
        )
    for side, mapping in (("west", cfg.input_map), ("east", cfg.output_map)):
        for active, row in enumerate(mapping):
            y = snap(origin + row * p)
            if side == "west":
                cell = io_adapter(lib, 0, y, stages[0]["x"], y)
            else:
                start = snap(stages[-1]["x"] + cfg.mzi_length)
                # Straight approach protects the unused final-column outputs.
                cell = lib.cell(f"BANYAN_OUTPUT_{active}", "adapter")
                lead = segment(lib, [start, y], [start + outs[-1], y])
                if lead:
                    lib.ref(cell, lead)
                fan = io_adapter(
                    lib, start + outs[-1], y, width, snap(origin + active * p)
                )
                lib.ref(cell, fan)
                pieces = (
                    [dict(cell=lead.name, x=0, y=0, angle=0, entry="w", exit="e")]
                    if lead
                    else []
                ) + fan.tracks[0]["pieces"]
                cell.ports = {"w": [start, y, 180], "e": fan.ports["e"]}
                cell.tracks = [
                    dict(
                        ports=["w", "e"],
                        pieces=pieces,
                        **{
                            k: (lead.tracks[0][k] if lead else 0) + fan.tracks[0][k]
                            for k in ("length", "bends", "angle", "crossings")
                        },
                    )
                ]
            lib.ref(groups["IO_ADAPTERS"], cell)
            m["interfaces"].append(
                dict(
                    side=side,
                    internal=row,
                    active=active,
                    position=cell.ports["w" if side == "west" else "e"][:2],
                    cell=cell.name,
                )
            )
    return complete_layout(lib, net, m, groups, terminals, grids, width)
