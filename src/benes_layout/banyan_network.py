"""Matched-port recursive Banyan: sparse graph, unique paths and blocking.

Parent lane addresses stay stable after pruning. Unused switch pins terminate;
there is deliberately no completion of partial requests to a permutation.
"""

from collections import Counter
from copy import deepcopy


def parent_permutations(p):
    return [
        [
            base + i // 2 + (i % 2) * (size // 2)
            for base in range(0, p, size)
            for i in range(size)
        ]
        for size in (p >> s for s in range(p.bit_length() - 2))
    ]


def bar_outputs(p):
    lanes = list(range(p))
    for perm in parent_permutations(p):
        lanes = [perm[lane] for lane in lanes]
    return lanes


def matched_outputs(n, p):
    return tuple(sorted(bar_outputs(p)[:n]))


def switch_id(stage, row):
    return f"b_s{stage:02d}_r{row:04d}"


class BlockingError(ValueError):
    def __init__(self, first, second, stage, switch, edge=None):
        self.diagnostic = dict(
            status="blocked",
            requests=[list(first), list(second)],
            stage=stage,
            switch=switch,
            edge=edge,
        )
        super().__init__(
            f"blocked requests {first} and {second} at stage {stage}, "
            f"switch {switch}" + (f", edge {edge}" if edge else "")
        )


class BanyanNetwork:
    def __init__(self, cfg):
        self.cfg, self.p = cfg, cfg.internal_ports
        self.depth = self.p.bit_length() - 1
        perms = parent_permutations(self.p)
        forward = [set(cfg.input_map)]
        for perm in perms:
            forward.append(
                {perm[(a // 2) * 2 + pin] for a in forward[-1] for pin in (0, 1)}
            )
        backward = [set() for _ in range(self.depth)]
        backward[-1] = set(cfg.output_map)
        for s in range(self.depth - 2, -1, -1):
            targets = {a // 2 for a in backward[s + 1]}
            backward[s] = {a for a, b in enumerate(perms[s]) if b // 2 in targets}
        self.switches, self.slots = {}, [{} for _ in range(self.depth)]
        for s in range(self.depth):
            rows = sorted({a // 2 for a in forward[s]} & {a // 2 for a in backward[s]})
            for physical, q in enumerate(rows):
                sid = switch_id(s, 2 * q)
                self.switches[sid] = dict(stage=s, row=2 * q, physical_row=physical)
                for pin in (0, 1):
                    self.slots[s][2 * q + pin] = (sid, pin)
        self.boundaries = []
        for s, perm in enumerate(perms):
            edges = [
                [a, b]
                for a, b in enumerate(perm)
                if a in self.slots[s] and b in self.slots[s + 1]
            ]
            size = self.p >> s
            blocks = []
            for base in range(0, self.p, size):
                active = [a - base for a, b in edges if base <= a < base + size]
                if active:
                    blocks.append(
                        dict(base=base, size=size, inverse=False, active=active)
                    )
            dests = [b for a, b in edges]
            crossings = sum(a > b for i, a in enumerate(dests) for b in dests[i + 1 :])
            self.boundaries.append(
                dict(stage=s, edges=edges, blocks=blocks, graph_crossings=crossings)
            )
        self.bypasses = []
        self.terminations = []
        for sid, sw in self.switches.items():
            s, row = sw["stage"], sw["row"]
            ins = (
                set(cfg.input_map)
                if s == 0
                else {b for a, b in self.boundaries[s - 1]["edges"]}
            )
            outs = (
                set(cfg.output_map)
                if s == self.depth - 1
                else {a for a, b in self.boundaries[s]["edges"]}
            )
            for direction, live in (("i", ins), ("o", outs)):
                for pin in (0, 1):
                    if row + pin not in live:
                        self.terminations.append(
                            dict(
                                id=f"term_{sid}_{direction}{pin}",
                                switch=sid,
                                pin=f"{direction}{pin}",
                                stage=s,
                                row=row + pin,
                            )
                        )
        bars = bar_outputs(self.p)
        self.reference = [
            [a, cfg.output_map.index(bars[lane])]
            for a, lane in enumerate(cfg.input_map)
        ]
        # Destination reachability is used only by the solver; verification
        # below walks the explicit graph without consulting these masks.
        self._edges = [dict(b["edges"]) for b in self.boundaries]
        self._reachable = [{} for _ in range(self.depth)]
        for lane in self.slots[-1]:
            row = lane // 2 * 2
            self._reachable[-1][lane] = {
                v for v in (row, row + 1) if v in cfg.output_map
            }
        for s in range(self.depth - 2, -1, -1):
            for lane in self.slots[s]:
                row = lane // 2 * 2
                self._reachable[s][lane] = set().union(
                    *(
                        self._reachable[s + 1][self._edges[s][out]]
                        for out in (row, row + 1)
                        if out in self._edges[s]
                    )
                )

    def _pairs(self, requests):
        try:
            pairs = [tuple(v) for v in requests]
        except TypeError as exc:
            raise ValueError("requests must be input/output pairs") from exc
        n = self.cfg.active_ports
        if any(
            len(v) != 2 or any(type(i) is not int or not 0 <= i < n for i in v)
            for v in pairs
        ):
            raise ValueError("requests must name valid active input/output indices")
        if len({a for a, b in pairs}) != len(pairs) or len(
            {b for a, b in pairs}
        ) != len(pairs):
            raise ValueError(
                "requests must be one-to-one, with no duplicate input or output"
            )
        return sorted(pairs)

    def path(self, a, b):
        self._pairs([(a, b)])
        lane, dest, path = self.cfg.input_map[a], self.cfg.output_map[b], []
        for s in range(self.depth):
            sid, pin = self.slots[s][lane]
            row = self.switches[sid]["row"]
            outputs = [
                out
                for out in (0, 1)
                if (
                    row + out == dest
                    if s == self.depth - 1
                    else row + out in self._edges[s]
                    and dest in self._reachable[s + 1][self._edges[s][row + out]]
                )
            ]
            if len(outputs) != 1:
                raise ValueError(f"non-unique Banyan path {a}->{b} at {sid}")
            out = outputs[0]
            path.append(dict(switch=sid, stage=s, row=lane, input=pin, output=out))
            if s < self.depth - 1:
                lane = self._edges[s][row + out]
        return path

    def solve(self, requests):
        pairs = self._pairs(requests)
        constraints, occupied, paths = {}, {}, []
        for pair in pairs:
            path = self.path(*pair)
            for item in path:
                sid, s = item["switch"], item["stage"]
                state = item["input"] ^ item["output"]
                if sid in constraints and constraints[sid][0] != state:
                    raise BlockingError(constraints[sid][1], pair, s, sid)
                constraints[sid] = (state, pair)
                if s < self.depth - 1:
                    row = self.switches[sid]["row"] + item["output"]
                    key = (s, row, self._edges[s][row])
                    if key in occupied:
                        raise BlockingError(occupied[key], pair, s, sid, list(key))
                    occupied[key] = pair
            paths.append(dict(input=pair[0], output=pair[1], switches=path))
        return dict(
            active=[list(v) for v in pairs],
            states={
                sid: constraints.get(sid, (0,))[0] for sid in sorted(self.switches)
            },
            paths=paths,
            dark_active_inputs=sorted(
                set(range(self.cfg.active_ports)) - {a for a, b in pairs}
            ),
            blocking=True,
            rearrangeable=False,
        )

    def trace(self, internal_input, states):
        if internal_input not in self.cfg.input_map:
            raise ValueError("invalid selected internal input")
        lane, path = internal_input, []
        for s in range(self.depth):
            if lane not in self.slots[s]:
                raise ValueError(f"missing switch at stage {s}, lane {lane}")
            sid, pin = self.slots[s][lane]
            out = pin ^ states[sid]
            path.append(dict(switch=sid, stage=s, row=lane, input=pin, output=out))
            lane = self.switches[sid]["row"] + out
            if s < self.depth - 1:
                edges = dict(self.boundaries[s]["edges"])
                if lane not in edges:
                    return None, path
                lane = edges[lane]
        return (lane if lane in self.cfg.output_map else None), path

    def verify(self, settings):
        states = settings.get("states", {})
        if set(states) != set(self.switches) or any(
            type(v) is not int or v not in (0, 1) for v in states.values()
        ):
            raise ValueError("settings must cover every switch with bar/cross states")
        pairs = self._pairs(settings.get("active", []))
        if (
            settings.get("blocking") is not True
            or settings.get("rearrangeable") is not False
            or settings.get("dark_active_inputs")
            != sorted(set(range(self.cfg.active_ports)) - {a for a, b in pairs})
        ):
            raise ValueError("settings operating assumptions differ from request")
        occupied, paths, depths = set(), [], []
        for a, b in pairs:
            dest, path = self.trace(self.cfg.input_map[a], states)
            if dest != self.cfg.output_map[b]:
                raise ValueError(
                    f"input {a}: expected output {b}, got parent {dest} (None means termination)"
                )
            for item in path:
                key = (item["stage"], item["row"])
                if key in occupied:
                    raise ValueError(f"duplicate occupied internal port {key}")
                occupied.add(key)
            paths.append(dict(input=a, output=b, switches=path))
            depths.append(len(path))
        if settings.get("paths") != paths:
            raise ValueError("reported paths differ from independently traced paths")
        return dict(
            connections=len(pairs),
            switch_depth=self.depth,
            blocking=True,
            rearrangeable=False,
            actual_mzi_counts=dict(sorted(Counter(depths).items())),
        )

    def export(self):
        return deepcopy(
            dict(
                topology="pruned-banyan",
                active_ports=self.cfg.active_ports,
                parent_ports=self.p,
                internal_ports=self.p,
                depth=self.depth,
                input_map=list(self.cfg.input_map),
                output_map=list(self.cfg.output_map),
                reference=self.reference,
                switches=self.switches,
                boundaries=self.boundaries,
                terminations=self.terminations,
                stage_switch_counts=[len(v) // 2 for v in self.slots],
                boundary_lane_counts=[len(b["edges"]) for b in self.boundaries],
                graph_crossings=sum(b["graph_crossings"] for b in self.boundaries),
            )
        )
