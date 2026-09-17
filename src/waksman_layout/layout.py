"""Constructive channel routing with explicit permutation crossings.

Each switch column owns an electrical escape corridor. M1 escapes are at
distinct y tracks, M2 trunks at distinct pad x coordinates. Opposite-bank
trunks may reuse x only when their y intervals are disjoint. This channel
strategy avoids relying on an unrestricted router to discover a legal fanout.
"""

from collections import defaultdict
from dataclasses import replace
from math import ceil

from .config import Config
from .geometry import Library, rectangle, snap, validate_mzi
from .network import Network


class RoutingError(ValueError):
    pass


def terminal_target(net: Network, source: str):
    """Collapse single-wire bypass ports without consulting physical placement."""
    current = source
    while current in net.successor:
        current = net.successor[current]
    return current


def swap_schedule(current: list[str], desired: list[str]):
    """Parallel odd-even adjacent exchanges; ordering is never silently sorted."""
    rank = {wire: i for i, wire in enumerate(desired)}
    work = current.copy()
    schedule = []
    for phase in range(len(work) + 1):
        pairs = []
        for i in range(phase % 2, len(work) - 1, 2):
            if rank[work[i]] > rank[work[i + 1]]:
                work[i], work[i + 1] = work[i + 1], work[i]
                pairs.append(i)
        if pairs:
            schedule.append(pairs)
        if work == desired:
            return schedule
    raise RoutingError("permutation scheduling failed")


def build_layout(
    cfg: Config, factor: float = 1.0, assignment: str | None = None, mzi_factory=None
):
    net = Network(cfg.n)
    lib = Library(cfg)
    if net.switches:
        component = mzi_factory(lib) if mzi_factory else lib.mzi()
        if component.name != "MZI" or lib.cells.get("MZI") is not component:
            raise ValueError("MZI factory must register and return a cell named MZI")
        validate_mzi(component, cfg)
    top = lib.cell("CHIP", "chip")
    optics = lib.cell("OPTICAL_ROUTING", "group")
    electric = lib.cell("ELECTRICAL_FANOUT", "group")
    north = lib.cell("NORTH_PADS", "group")
    south = lib.cell("SOUTH_PADS", "group")
    for cell in (optics, electric, north, south):
        lib.ref(top, cell)
    parents = {}

    def hierarchy(node, parent):
        cell = lib.cell(node.id.replace("/", "_"), "subnetwork")
        parents[node.id] = cell
        lib.ref(parent, cell, id=node.id)
        for child in node.children:
            hierarchy(child, cell)

    hierarchy(net.root, top)
    manifest = {
        "config": cfg.to_dict(),
        "config_hash": cfg.digest,
        "network": net.export(),
        "instances": [],
        "routes": [],
        "electrical": [],
        "overpasses": [],
        "pad_assignment": assignment or cfg.pad_assignment,
        "factor": factor,
        "stages": [],
        "swap_columns": 0,
        "crossing_count": 0,
    }
    routes = {}
    current = [f"in:{i}" for i in range(cfg.n)]
    pitch = cfg.lane_pitch

    def new_route(source, x, y):
        routes[source] = {
            "source": source,
            "target": terminal_target(net, source),
            "start": [snap(x), snap(y)],
            "pieces": [],
            "length": 0.0,
            "crossings": 0,
        }

    for i, source in enumerate(current):
        new_route(source, 0, i * pitch)

    def piece(source, cell, x, y, entry, exit):
        route = routes[source]
        route["pieces"].append(
            dict(cell=cell.name, x=snap(x), y=snap(y), entry=entry, exit=exit)
        )
        track = next(t for t in cell.tracks if t["ports"] == [entry, exit])
        route["length"] += track["length"]
        if cell.kind == "swap":
            route["crossings"] += 1

    def straight_column(x, length, skip=()):
        if length <= 0:
            return
        c = lib.straight(length)
        for row, source in enumerate(current):
            if row in skip:
                continue
            lib.ref(optics, c, x, row * pitch, id=f"{source}@{x}")
            piece(source, c, x, row * pitch, "w", "e")

    def reorder(x, desired):
        nonlocal current
        schedule = swap_schedule(current, desired)
        manifest["swap_columns"] += len(schedule)
        if manifest["swap_columns"] > cfg.max_swap_columns:
            raise RoutingError(
                f"max_swap_columns exhausted; unresolved boundary targets: {desired[:8]}"
            )
        if not schedule:
            return x
        swap = lib.swap()
        width = swap.metadata["width"]
        for pairs in schedule:
            used = set()
            for row in pairs:
                lib.ref(
                    optics,
                    swap,
                    x,
                    row * pitch,
                    id=f"swap_{manifest['crossing_count']}",
                )
                piece(current[row], swap, x, row * pitch, "w0", "e1")
                piece(current[row + 1], swap, x, row * pitch, "w1", "e0")
                current[row], current[row + 1] = current[row + 1], current[row]
                used.update((row, row + 1))
                manifest["crossing_count"] += 1
            straight_column(x, width, used)
            x = snap(x + width)
        if current != desired:
            raise RoutingError("boundary ordering mismatch")
        return x

    stages = defaultdict(list)
    for sid, info in net.switches.items():
        stages[info["stage"]].append((sid, info))
    x = 0.0
    straight_column(x, cfg.margin)
    x += cfg.margin
    y_s = -cfg.margin - cfg.pad_size / 2
    y_n = (cfg.n - 1) * pitch + cfg.margin + cfg.pad_size / 2
    for stage in range(net.columns):
        devices = sorted(stages[stage], key=lambda p: p[1]["row"])
        fixed = {}
        source_for_target = {routes[source]["target"]: source for source in current}
        for sid, info in devices:
            for pin in range(2):
                fixed[info["row"] + pin] = source_for_target[f"{sid}:i{pin}"]
        free = iter(source for source in current if source not in fixed.values())
        desired = [fixed[row] if row in fixed else next(free) for row in range(cfg.n)]
        x = reorder(x, desired)
        stage_x = x
        occupied = set()
        terminals = []
        for sid, info in devices:
            row = info["row"]
            cell = lib.mzi()
            lib.ref(parents[info["parent"]], cell, x, row * pitch, id=sid)
            manifest["instances"].append(
                dict(id=sid, cell="MZI", x=x, y=row * pitch, stage=stage, row=row)
            )
            for pin in range(2):
                incoming = current[row + pin]
                routes[incoming]["end"] = [x, (row + pin) * pitch]
                manifest["routes"].append(routes[incoming])
                source = f"{sid}:o{pin}"
                current[row + pin] = source
                new_route(source, x + cfg.mzi_length, (row + pin) * pitch)
            for name, offset in zip(cfg.terminal_names, cfg.terminal_offsets):
                terminals.append(
                    dict(
                        net=f"{sid}:{name}",
                        instance=sid,
                        terminal=name,
                        x=x + cfg.mzi_length,
                        y=row * pitch + offset,
                    )
                )
            occupied.update((row, row + 1))
        straight_column(x, cfg.mzi_length, occupied)
        x += cfg.mzi_length
        if terminals:
            if not cfg.insulated_m2_overpasses:
                raise RoutingError(
                    f"stage {stage}: north/south escape requires explicit insulated M2 overpasses"
                )
            terminals.sort(key=lambda t: (t["y"], t["net"]))
            mode = manifest["pad_assignment"]
            if mode == "nearest":
                half = len(terminals) // 2
                groups = {"south": terminals[:half], "north": terminals[half:]}
            elif mode == "split" and len(cfg.terminal_names) == 2:
                low = cfg.terminal_names[
                    cfg.terminal_offsets.index(min(cfg.terminal_offsets))
                ]
                groups = {
                    "south": [t for t in terminals if t["terminal"] == low],
                    "north": [t for t in terminals if t["terminal"] != low],
                }
            else:
                raise RoutingError("unsupported terminal split assignment")
            max_bank = max(map(len, groups.values()))
            pad_pitch = snap(cfg.pad_pitch * factor)
            escape = (
                cfg.optical_metal_clearance
                + cfg.via_size / 2
                + cfg.via_enclosure
                + cfg.pad_size / 2
            )
            corridor = snap(2 * escape + (max_bank - 1) * pad_pitch)
            straight_column(x, corridor)
            for side, group in groups.items():
                pad_y = y_n if side == "north" else y_s
                bank = north if side == "north" else south
                for index, terminal in enumerate(group):
                    px = snap(x + escape + index * pad_pitch)
                    py = terminal["y"]
                    w = cfg.metal_width
                    route_cell = lib.cell(
                        f"E_{len(manifest['electrical'])}", "electrical_route"
                    )
                    lib.poly(route_cell, "M1", rectangle(x, py - w / 2, px, py + w / 2))
                    lib.poly(
                        route_cell,
                        "M2",
                        rectangle(
                            px - w / 2, min(py, pad_y), px + w / 2, max(py, pad_y)
                        ),
                    )
                    lib.ref(route_cell, lib.via(), px, py)
                    lib.ref(electric, route_cell, id=terminal["net"])
                    lib.ref(bank, lib.pad(), px, pad_y, id=terminal["net"])
                    manifest["electrical"].append(
                        {
                            **terminal,
                            "cell": route_cell.name,
                            "side": side,
                            "pad": [px, pad_y],
                            "via": [px, py],
                        }
                    )
                    for row in range(cfg.n):
                        wy = row * pitch
                        if min(py, pad_y) < wy < max(py, pad_y):
                            manifest["overpasses"].append(
                                dict(net=terminal["net"], x=px, y=wy)
                            )
            manifest["stages"].append(
                dict(stage=stage, x=stage_x, escape_start=x, escape_end=x + corridor)
            )
            x = snap(x + corridor)
        else:
            manifest["stages"].append(
                dict(stage=stage, x=stage_x, escape_start=x, escape_end=x)
            )
    desired = sorted(current, key=lambda s: int(routes[s]["target"].split(":")[1]))
    x = reorder(x, desired)
    straight_column(x, cfg.margin)
    x = snap(x + cfg.margin)
    for row, source in enumerate(current):
        routes[source]["end"] = [x, row * pitch]
        manifest["routes"].append(routes[source])
    manifest["width"] = x + 2 * cfg.margin
    manifest["height"] = y_n - y_s + cfg.pad_size
    manifest["die_bbox"] = [
        -cfg.margin,
        y_s - cfg.pad_size / 2,
        x + cfg.margin,
        y_n + cfg.pad_size / 2,
    ]
    manifest["core_bbox"] = [
        0,
        -(cfg.mzi_height - pitch) / 2,
        x,
        (cfg.n - 1) * pitch + (cfg.mzi_height - pitch) / 2,
    ]
    frame = lib.cell("DIE_OUTLINE", "outline")
    lib.ref(top, frame)
    a, b, c, d = manifest["die_bbox"]
    for rect in [
        (a, b, c, b + 1),
        (a, d - 1, c, d),
        (a, b, a + 1, d),
        (c - 1, b, c, d),
    ]:
        lib.poly(frame, "OUTLINE", rectangle(*rect))
    for row in range(cfg.n):
        top.ports[f"in_{row}"] = [0, row * pitch, 180]
        top.ports[f"out_{row}"] = [x, row * pitch, 0]
    manifest["cells"] = lib.export()
    manifest["top"] = "CHIP"
    return lib, manifest
