"""Two-layer channel levels with vertical-trunk precedence constraints.

A source trunk terminates before any foreign destination stem at a nearby x
begins. M1 intervals on one level remain disjoint, including via landing
clearance. This avoids reserving the entire pad-stem projection in the core.
"""

import heapq


def channel_levels(sources, targets, clear=14.002):
    if len(sources) != len(targets):
        raise ValueError("channel source/target count mismatch")
    children = [set() for _ in sources]
    before = [set() for _ in sources]
    for i, x in enumerate(sources):
        for j, y in enumerate(targets):
            if i != j and abs(x - y) < clear:
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
