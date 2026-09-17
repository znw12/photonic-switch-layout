"""Reusable compression lanes and concentric return bends (all lengths in um)."""

from math import pi
from .geometry import arc_polygon, snap, rectangle


def fan_lane(lib, lane, up=False):
    cfg = lib.cfg
    p, pitch, q, r = cfg.internal_ports, cfg.lane_pitch, cfg.bundle_pitch, cfg.radius
    name = f"FAN_{'UP' if up else 'DOWN'}_{lane}"
    if name in lib.cells:
        return lib.cells[name]
    c = lib.cell(name, "fan_lane")
    h, dense = (p - 1) * pitch, (p - 1) * q
    width = snap(2 * r + dense)
    ys = lane * pitch
    yd = snap((h - dense if up else 0) + lane * q)
    count = p - 1 - lane if up else lane
    xs = snap(count * q)
    delta = abs(yd - ys)

    def straight(x, y, length, angle=0):
        if length > cfg.grid / 2:
            lib.ref(c, lib.straight(length), x, y, angle)

    if count == 0:
        straight(0, ys, width)
    else:
        straight(0, ys, xs)
        sign = 1 if up else -1
        a = lib.bend(name + "_A", xs, ys + sign * r, -sign * pi / 2, 0)
        b = lib.bend(
            name + "_B", xs + 2 * r, yd - sign * r, pi, pi / 2 if up else 3 * pi / 2
        )
        lib.ref(c, a)
        straight(xs + r, ys + sign * r, delta - 2 * r, sign * 90)
        lib.ref(c, b)
        straight(xs + 2 * r, yd, width - xs - 2 * r)
        # Two-grid overlaps at internal analytic joins absorb transform roundoff.
        w, eps = cfg.wg_width / 2, 2 * cfg.grid
        for x, y, vertical in (
            (xs, ys, False),
            (xs + r, ys + sign * r, True),
            (xs + r, yd - sign * r, True),
            (xs + 2 * r, yd, False),
        ):
            lib.poly(
                c,
                "WG",
                rectangle(
                    x - (w if vertical else eps),
                    y - (eps if vertical else w),
                    x + (w if vertical else eps),
                    y + (eps if vertical else w),
                ),
            )
    c.ports = {"w": [0, ys, 180], "e": [width, yd, 0]}
    metrics = dict(
        length=width + delta + (pi - 4) * r if count else width,
        crossings=0,
        bends=2 if count else 0,
        angle=pi if count else 0,
        min_radius=r if count else None,
    )
    c.tracks = [dict(ports=["w", "e"], **metrics), dict(ports=["e", "w"], **metrics)]
    c.metadata = dict(width=width, lane=lane, up=up)
    return c


def return_turn(lib, radius, left=False):
    radius = snap(radius)
    name = f"RETURN_{'L' if left else 'R'}_{radius:.3f}"
    if name in lib.cells:
        return lib.cells[name]
    c = lib.cell(name, "turn")
    start, end = -pi / 2, -3 * pi / 2 if left else pi / 2
    lib.poly(
        c,
        "WG",
        arc_polygon(
            0, radius, radius, start, end, lib.cfg.wg_width, lib.cfg.chord_error
        ),
    )
    c.ports = {
        "w": [0, 0, 0 if left else 180],
        "e": [0, snap(2 * radius), 0 if left else 180],
    }
    c.metadata["arc"] = dict(center=[0, radius], radius=radius, start=start, end=end)
    c.tracks = [
        dict(
            ports=["w", "e"],
            length=pi * radius,
            crossings=0,
            bends=1,
            angle=pi,
            min_radius=radius,
        )
    ]
    return c
