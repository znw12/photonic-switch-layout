"""Optional output-adapter matching inside the already allocated die.

This matches the requested configuration, subject to finite tail capacity. It
does not claim to make every path of a rearrangeable network the same length.
"""

from math import acos, pi, sin, cos
from .geometry import snap, rectangle
from .metrics import realized


def apply_equalization(lib, m, settings):
    before = realized(m, settings)
    cfg = lib.cfg
    target = max((p["length"] for p in before["paths"]), default=0)
    routes = {r["source"]: r for r in m["routes"]}
    changes = []
    original_bounds = list(m["die_bbox"])
    for path in before["paths"]:
        requested = target - path["length"]
        if requested < cfg.grid:
            continue
        route = routes[path["witness"][-1]]
        part = route["pieces"][-1]
        old = lib.cells[part["cell"]]
        if old.kind != "straight":
            raise ValueError("equalization needs a straight output tail")
        length = old.tracks[0]["length"]
        amplitude = min(
            1.8 * cfg.radius, (cfg.lane_pitch - cfg.wg_width - cfg.wg_clearance) / 2
        )
        theta_max = acos(1 - amplitude / (2 * cfg.radius))
        width_max = 4 * cfg.radius * sin(theta_max)
        # Leave straight joins at both ends. Integer pitch includes snap error.
        pitch = snap(width_max + 2 * cfg.grid)
        count = max(0, int((length - 2 * cfg.radius) / pitch))
        capacity = count * 4 * cfg.radius * (theta_max - sin(theta_max))
        added = min(requested, capacity)
        if added < cfg.grid or not count:
            changes.append(
                dict(
                    output=path["output"],
                    requested_um=requested,
                    added_um=0.0,
                    capacity_um=capacity,
                )
            )
            continue
        low, high = 0.0, theta_max
        for _ in range(60):
            theta = (low + high) / 2
            if count * 4 * cfg.radius * (theta - sin(theta)) < added:
                low = theta
            else:
                high = theta
        theta = (low + high) / 2
        r = cfg.radius
        step = snap(4 * r * sin(theta))
        name = f"MATCH_{path['output']}"
        cell = lib.cell(name, "meander")
        bends = []
        for suffix, cx, cy, a, b in (
            ("A", 0, r, -pi / 2, -pi / 2 + theta),
            (
                "B",
                2 * r * sin(theta),
                r * (1 - 2 * cos(theta)),
                pi / 2 + theta,
                pi / 2 - theta,
            ),
            ("C", 4 * r * sin(theta), r, -pi / 2 - theta, -pi / 2),
        ):
            bends.append(lib.bend(name + suffix, cx, cy, a, b))
        x = cfg.radius
        lib.ref(cell, lib.straight(x))
        for j in range(count):
            # Internal horizontal seam overlap absorbs floating-point transform
            # roundoff before export; it is two database units, not a route gap.
            lib.poly(
                cell,
                "WG",
                rectangle(
                    x - 2 * cfg.grid,
                    -cfg.wg_width / 2,
                    x + 2 * cfg.grid,
                    cfg.wg_width / 2,
                ),
            )
            for bend in bends:
                lib.ref(cell, bend, x)
            x = snap(x + step)
            lib.poly(
                cell,
                "WG",
                rectangle(
                    x - 2 * cfg.grid,
                    -cfg.wg_width / 2,
                    x + 2 * cfg.grid,
                    cfg.wg_width / 2,
                ),
            )
            if j < count - 1:
                spacing = snap(pitch - step)
                lib.ref(cell, lib.straight(spacing), x)
                x = snap(x + spacing)
        if length - x > 0:
            lib.ref(cell, lib.straight(snap(length - x)), x)
        actual_added = count * (4 * r * theta - step)
        cell.ports = {"w": [0, 0, 180], "e": [length, 0, 0]}
        cell.tracks = [
            dict(
                ports=["w", "e"],
                length=length + actual_added,
                crossings=0,
                bends=3 * count,
                angle=4 * theta * count,
                min_radius=r,
            )
        ]
        cell.metadata = {
            "capacity_um": capacity,
            "placeholder": False,
            "matched_configuration_only": True,
        }
        # Replace the actual hierarchical reference and its edge record together.
        found = 0
        for parent in lib.cells.values():
            if parent.kind != "interstage":
                continue
            for ref in parent.refs:
                if (
                    ref["cell"] == part["cell"]
                    and ref["x"] == part["x"]
                    and ref["y"] == part["y"]
                ):
                    ref["cell"] = name
                    found += 1
        if found != 1:
            raise ValueError("output-tail reference is not unique")
        part["cell"] = name
        route["length"] += actual_added
        route["bends"] += 3 * count
        route["angle"] += 4 * theta * count
        changes.append(
            dict(
                output=path["output"],
                requested_um=requested,
                added_um=actual_added,
                capacity_um=capacity,
            )
        )
    reachable = set()

    def visit(name):
        if name in reachable:
            return
        reachable.add(name)
        for ref in lib.cells[name].refs:
            visit(ref["cell"])

    visit(m["top"])
    lib.cells = {k: v for k, v in lib.cells.items() if k in reachable}
    m["cells"] = lib.export()
    after = realized(m, settings)
    if original_bounds != m["die_bbox"]:
        raise ValueError("equalization expanded die bounds")
    return {
        "enabled": True,
        "scope": "requested switch configuration; not all possible network paths",
        "die_bounds_preserved": True,
        "changes": changes,
        "before_spread_um": (
            before["statistics"]["length"]["spread"] if before["paths"] else None
        ),
        "residual_spread_um": (
            after["statistics"]["length"]["spread"] if after["paths"] else None
        ),
    }
