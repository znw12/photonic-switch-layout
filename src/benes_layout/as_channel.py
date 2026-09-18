"""Two-layer channel levels with vertical-trunk precedence constraints.

A source trunk terminates before any foreign destination stem at a nearby x
begins. M1 intervals on one level remain disjoint, including via landing
clearance. This avoids reserving the entire pad-stem projection in the core.
"""

import heapq


def channel_levels(sources, targets, clear=14.002, *, ordered=False):
    if len(sources) != len(targets):
        raise ValueError("channel source/target count mismatch")
    children = [set() for _ in sources]
    before = [set() for _ in sources]
    for i, x in enumerate(sources):
        for j, y in enumerate(targets):
            if i != j and abs(x - y) < clear:
                children[i].add(j)
                before[j].add(i)
    if ordered:
        if sources != sorted(sources) or targets != sorted(targets):
            raise ValueError("ordered channel requires monotone source/pad assignment")
        # Left-going bundles rise in source order; right-going bundles rise in
        # reverse order. This keeps the horizontal leg outside foreign vertical
        # legs. Include landing clearance when two horizontal intervals meet.
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                if min(sources[j], targets[j]) >= max(sources[i], targets[i]) + clear:
                    continue
                if targets[i] > sources[i] and targets[j] > sources[j]:
                    children[j].add(i)
                    before[i].add(j)
                elif targets[i] < sources[i] and targets[j] < sources[j]:
                    children[i].add(j)
                    before[j].add(i)
    indegree = list(map(len, before))
    ready = [i for i, degree in enumerate(indegree) if not degree]
    heapq.heapify(ready)
    levels = [-1] * len(sources)
    rows = []
    visited = 0
    while ready:
        i = heapq.heappop(ready)
        visited += 1
        level = max((levels[j] + 1 for j in before[i]), default=0)
        lo, hi = sorted((sources[i], targets[i]))
        while level < len(rows) and any(
            not (b + clear <= lo or hi + clear <= a) for a, b in rows[level]
        ):
            level += 1
        while len(rows) <= level:
            rows.append([])
        rows[level].append((lo, hi))
        levels[i] = level
        for j in sorted(children[i]):
            indegree[j] -= 1
            if indegree[j] == 0:
                heapq.heappush(ready, j)
    if visited < len(sources):
        raise ValueError("vertical channel dependency cycle")
    return levels


def aligned_slots(sources, width, cfg):
    """Fit pads to trunks with a monotone, minimum-pitch least-squares fit.

    Pool adjacent violating means of source[i] - i*pitch. Alternating rows
    then have at least pad_pitch spacing; half-pitch separation also preserves
    a clear M2 stem corridor through the opposite row. No new chip width.
    """
    from .geometry import snap

    if sources != sorted(sources):
        raise ValueError("pad sources must be sorted")
    if not sources:
        return []
    pitch = cfg.pad_pitch / 2
    low = cfg.margin + cfg.pad_size / 2
    high = width - low - (len(sources) - 1) * pitch
    if high < low:
        raise ValueError("aligned pads do not fit within the existing width")
    blocks = []
    for i, x in enumerate(sources):
        blocks.append([x - i * pitch, 1])
        while (
            len(blocks) > 1
            and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]
        ):
            total, count = blocks.pop()
            blocks[-1][0] += total
            blocks[-1][1] += count
    offsets = [
        min(high, max(low, total / count))
        for total, count in blocks
        for _ in range(count)
    ]
    return [
        dict(row=i % 2, column=i // 2, offset=None, px=snap(x + i * pitch))
        for i, x in enumerate(offsets)
    ]


def plan_channels(banks, grids, width, cfg):
    """Try ordered local pad bundles within the original uniform-grid height."""
    clear = cfg.via_size + 2 * cfg.via_enclosure + cfg.metal_spacing + 2 * cfg.grid
    sources = {b: [t["tx"] for t in ts] for b, ts in banks.items()}
    baseline = {
        b: channel_levels(sources[b], [v["px"] for v in grid], clear)
        for b, grid in grids.items()
    }
    budget = max(max(v, default=0) for v in baseline.values()) + 1
    if cfg.pad_distribution != "routing":
        return grids, baseline, dict(strategy="packed", level_budget=budget)
    grids = {b: aligned_slots(xs, width, cfg) for b, xs in sources.items()}
    for ordered in (True, False):
        try:
            levels = {
                b: channel_levels(
                    sources[b], [v["px"] for v in grid], clear, ordered=ordered
                )
                for b, grid in grids.items()
            }
        except ValueError:
            continue
        if max(max(v, default=0) for v in levels.values()) < budget:
            choices = dict(
                strategy="ordered" if ordered else "packed", level_budget=budget
            )
            return grids, levels, choices
    raise ValueError("routing-aligned pads exceed the original channel height budget")


def fanout_metrics(m):
    """Count centerline crossings in the pad redistribution channel only.

    Device fanout, the common ground bus, optical crossings, and same-net
    intersections are excluded. These projected M1/M2 crossings are insulated,
    not electrical junctions. Derive levels from geometry, not planner labels.
    """
    horizontal, vertical, bundles = [], [], {}
    ground_y = m["electrical_plan"]["ground_y"]
    for e in m["electrical"]:
        for s in e["segments"]:
            a, b = s["start"], s["end"]
            if s["layer"] == "M1" and a[1] == b[1] and abs(a[1]) > ground_y:
                horizontal.append(
                    (e["electrical_net"], min(a[0], b[0]), max(a[0], b[0]), a[1])
                )
                if e["terminal"] == "S":
                    direction = 1 if e["pad"][0] > e["tx"] else -1
                    bundles.setdefault((e["side"], e["stage"]), []).append(
                        (e["tx"], abs(a[1]), direction)
                    )
            if s["layer"] == "M2" and a[0] == b[0]:
                vertical.append(
                    (e["electrical_net"], a[0], min(a[1], b[1]), max(a[1], b[1]))
                )
    crossings = sum(
        net != other and lo < x < hi and bottom < y < top
        for net, lo, hi, y in horizontal
        for other, x, bottom, top in vertical
    )
    reversals = 0
    for routes in bundles.values():
        routes.sort()
        for a, b, c in zip(routes, routes[1:], routes[2:]):
            if a[2] == b[2] == c[2] and (b[1] - a[1]) * (c[1] - b[1]) < 0:
                reversals += 1
    return dict(
        projected_m1_m2_crossings=crossings,
        same_direction_staircase_reversals=reversals,
        horizontal_length_um=sum(hi - lo for _, lo, hi, _ in horizontal),
        scope="Pad redistribution channel; different electrical nets; centerline intersections; excludes device fanout and common ground bus.",
    )
