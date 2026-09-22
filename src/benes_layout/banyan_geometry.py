"""Sparse continuous shuffle primitives and order-preserving external fanout."""

from collections import Counter
from copy import deepcopy
from math import pi
from .geometry import point, snap
from .interstage import (
    continuous,
    reverse_block,
    key,
    segment,
    arc,
    attach,
    shift_dimensions,
    METRICS,
)


def terminal_keep(cfg):
    return snap(cfg.termination_length + cfg.wg_clearance + cfg.wg_width + 2 * cfg.grid)


def masked_shuffle(lib, size, active, inverse=False):
    active = tuple(sorted(active))
    if len(set(active)) != len(active) or any(
        type(v) is not int or not 0 <= v < size for v in active
    ):
        raise ValueError("invalid shuffle track mask")
    name = key(
        "BANYAN_MASK_", [size, active, inverse, lib.cfg.lane_pitch, lib.cfg.radius]
    )
    if name in lib.cells:
        return lib.cells[name]
    source = continuous(lib, size, lib.cfg.lane_pitch)
    if inverse:
        source = reverse_block(lib, source, lib.cfg.lane_pitch)
    c = lib.cell(name, "shuffle")
    selected = [source.tracks[i] for i in active]

    def identity(p):
        return p["cell"], p["x"], p["y"], p.get("angle", 0)

    crossing_users = Counter(
        identity(p)
        for t in selected
        for p in t["pieces"]
        if lib.cells[p["cell"]].kind == "crossing"
    )
    placed = set()
    for i, t in zip(active, selected):
        pieces = []
        for original in t["pieces"]:
            p = deepcopy(original)
            child = lib.cells[p["cell"]]
            if child.kind == "crossing" and crossing_users[identity(p)] == 1:
                a = point(p["x"], p["y"], p.get("angle", 0), child.ports[p["entry"]])
                b = point(p["x"], p["y"], p.get("angle", 0), child.ports[p["exit"]])
                child = segment(lib, a, b)
                p = dict(cell=child.name, x=0, y=0, angle=0, entry="w", exit="e")
            obj = identity(p)
            if obj not in placed:
                lib.ref(c, child, p["x"], p["y"], p.get("angle", 0))
                placed.add(obj)
            pieces.append(p)
        totals = {
            k: sum(
                next(
                    v
                    for v in lib.cells[p["cell"]].tracks
                    if v["ports"] == [p["entry"], p["exit"]]
                )[k]
                for p in pieces
            )
            for k in METRICS
        }
        ports = deepcopy(t["ports"])
        c.tracks.append(dict(ports=ports, pieces=pieces, **totals))
        c.ports.update({port: deepcopy(source.ports[port]) for port in ports})
    c.metadata = {
        **deepcopy(source.metadata),
        "mode": "pruned-continuous",
        "active": list(active),
        "inverse": inverse,
        "crossing_count": sum(v == 2 for v in crossing_users.values()),
    }
    return c


def io_adapter(lib, x0, y0, x1, y1):
    """Two radius-limited arcs and tangent, monotonic in x; no label-only remap."""
    c = lib.cell(key("BANYAN_IO_", [x0, y0, x1, y1]), "adapter")
    parts = []
    delta = y1 - y0
    r = lib.cfg.radius
    w, angle, _ = shift_dimensions(delta, r, max_angle=pi / 4)
    if x1 - x0 < w - 2 * lib.cfg.grid:
        raise ValueError("insufficient width for external port compression")
    if delta:
        sign = 1 if delta > 0 else -1
        first = arc(
            lib, x0, y0 + sign * r, -sign * pi / 2, -sign * pi / 2 + sign * angle
        )
        last = arc(
            lib, x0 + w, y1 - sign * r, sign * pi / 2 + sign * angle, sign * pi / 2
        )
        attach(lib, c, parts, first)
        attach(lib, c, parts, segment(lib, first.ports["e"][:2], last.ports["w"][:2]))
        attach(lib, c, parts, last)
    attach(lib, c, parts, segment(lib, [snap(x0 + w), y1], [x1, y1]))
    c.ports = {"w": [x0, y0, 180], "e": [x1, y1, 0]}
    c.tracks = [
        dict(
            ports=["w", "e"],
            pieces=parts,
            **{
                k: sum(
                    next(
                        t
                        for t in lib.cells[p["cell"]].tracks
                        if t["ports"] == [p["entry"], p["exit"]]
                    )[k]
                    for p in parts
                )
                for k in METRICS
            },
        )
    ]
    return c
