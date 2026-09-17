"""Ordered two-metal escape and multirow pads with M1 stems below M2 pads."""

from math import ceil
import heapq
from .geometry import snap, rectangle


def pad_slots(cfg, total, center, pad_pitch):
    """Actual pad centers, centered by the occupied bank (including partial columns)."""
    raw = [
        dict(
            column=i // cfg.pad_rows,
            row=i % cfg.pad_rows,
            offset=snap((i % cfg.pad_rows) * cfg.pad_row_stagger),
            px=(i // cfg.pad_rows) * pad_pitch
            + (i % cfg.pad_rows) * cfg.pad_row_stagger,
        )
        for i in range(total)
    ]
    midpoint = (min(s["px"] for s in raw) + max(s["px"] for s in raw)) / 2
    slots = [{**s, "px": snap(center + s["px"] - midpoint)} for s in raw]
    bounds = [
        snap(min(s["px"] for s in slots) - cfg.pad_size / 2),
        snap(max(s["px"] for s in slots) + cfg.pad_size / 2),
    ]
    return slots, bounds


def fanout_levels(sources, destinations, clearance, stem_clearance=None):
    """Schedule horizontal M1 runs below every foreign M1 stem they cross.

    Both x sequences are ordered. The dependency DAG is checked explicitly;
    disconnected horizontal spans may share a level.
    """
    stem_clearance = clearance if stem_clearance is None else stem_clearance
    spans = [(min(a, b), max(a, b)) for a, b in zip(sources, destinations)]
    successors = [[] for _ in spans]
    degree = [0] * len(spans)
    for i, (a, b) in enumerate(spans):
        for j, x in enumerate(destinations):
            if i != j and a - stem_clearance < x < b + stem_clearance:
                successors[i].append(j)
                degree[j] += 1
    ready = [i for i, d in enumerate(degree) if d == 0]
    heapq.heapify(ready)
    levels, minimum, occupied = [-1] * len(spans), [0] * len(spans), []
    while ready:
        i = heapq.heappop(ready)
        level = minimum[i]
        a, b = spans[i]
        while level < len(occupied) and any(
            not (b + clearance <= c or d + clearance <= a) for c, d in occupied[level]
        ):
            level += 1
        while len(occupied) <= level:
            occupied.append([])
        occupied[level].append((a, b))
        levels[i] = level
        for j in successors[i]:
            minimum[j] = max(minimum[j], level + 1)
            degree[j] -= 1
            if degree[j] == 0:
                heapq.heappush(ready, j)
    if -1 in levels:
        raise ValueError("multirow fanout ordering cannot satisfy metal spacing")
    return levels


def route_pads(lib, m, groups, terminals, optical_bounds, step):
    cfg = lib.cfg
    left, bottom, right, top = optical_bounds
    total = len(terminals) // 2
    columns = ceil(total / cfg.pad_rows)
    pad_pitch = snap(cfg.pad_pitch * m["candidate"]["pad"])
    pad_span = (columns - 1) * pad_pitch + cfg.pad_size
    center = (left + right) / 2
    slots, pad_bounds = pad_slots(cfg, total, center, pad_pitch)
    for slot in slots:
        dx = (
            0
            if cfg.pad_row_stagger
            else snap((slot["row"] - (cfg.pad_rows - 1) / 2) * step)
        )
        if abs(dx) + (cfg.via_size + 2 * cfg.via_enclosure) / 2 > cfg.pad_size / 2:
            raise ValueError("pad cannot fit multirow stem offsets")
        slot["sx"] = snap(slot["px"] + dx)
    slots.sort(key=lambda s: s["sx"])
    if any(b["sx"] - a["sx"] < step - cfg.grid / 10 for a, b in zip(slots, slots[1:])):
        raise ValueError("pad stems cannot satisfy metal spacing at requested stagger")
    outer = []
    for side, sign in (("south", -1), ("north", 1)):
        bank = sorted(
            (t for t in terminals if t["side"] == side), key=lambda t: t["tx"]
        )
        levels = fanout_levels(
            [t["tx"] for t in bank],
            [s["sx"] for s in slots],
            step - cfg.grid / 10,
            (cfg.via_size + 2 * cfg.via_enclosure + cfg.metal_width) / 2
            + cfg.metal_spacing
            + cfg.grid,
        )
        edge = top if sign == 1 else bottom
        pad_base = snap(
            edge + sign * (2 * cfg.margin + max(levels) * step + cfg.pad_size / 2)
        )
        for i, (t, slot, level) in enumerate(zip(bank, slots, levels)):
            fy = snap(edge + sign * (cfg.margin + level * step))
            py = snap(pad_base + sign * slot["row"] * cfg.pad_row_pitch)
            tx, sx, px = t["tx"], slot["sx"], slot["px"]
            cell = lib.cell(f"NET_{side}_{i}", "electrical_route")
            w = cfg.metal_width

            def metal(layer, a, b):
                if a == b:
                    return
                if a[0] == b[0]:
                    poly = rectangle(
                        a[0] - w / 2,
                        min(a[1], b[1]) - w / 2,
                        a[0] + w / 2,
                        max(a[1], b[1]) + w / 2,
                    )
                else:
                    poly = rectangle(
                        min(a[0], b[0]) - w / 2,
                        a[1] - w / 2,
                        max(a[0], b[0]) + w / 2,
                        a[1] + w / 2,
                    )
                lib.poly(cell, layer, poly)

            metal("M1", (t["x"], t["y"]), (tx, t["y"]))
            metal("M2", (tx, t["y"]), (tx, fy))
            metal("M1", (tx, fy), (sx, fy))
            metal("M1", (sx, fy), (sx, py))
            vias = [[tx, t["y"]], [tx, fy], [sx, py]]
            for at in vias:
                lib.ref(cell, lib.via(), *at)
            lib.ref(groups["ELECTRICAL_FANOUT"], cell, id=t["net"])
            lib.ref(groups[side.upper() + "_PADS"], lib.pad(), px, py, id=t["net"])
            m["electrical"].append(
                {
                    **t,
                    "cell": cell.name,
                    "pad": [px, py],
                    "pad_row": slot["row"],
                    "pad_column": slot["column"],
                    **({"pad_row_offset": slot["offset"]} if cfg.pad_rows == 4 else {}),
                    "vias": vias,
                    "fanout_y": fy,
                }
            )
            for band in m["bands"]:
                for lane in range(cfg.internal_ports):
                    y = snap(band["y"] + lane * cfg.lane_pitch)
                    if min(t["y"], fy) < y < max(t["y"], fy):
                        m["overpasses"].append(dict(net=t["net"], x=tx, y=y))
            outer.append(py)
    return [
        pad_bounds[0] if cfg.pad_rows == 4 else snap(center - pad_span / 2),
        snap(min(outer) - cfg.pad_size / 2),
        pad_bounds[1] if cfg.pad_rows == 4 else snap(center + pad_span / 2),
        snap(max(outer) + cfg.pad_size / 2),
    ]
