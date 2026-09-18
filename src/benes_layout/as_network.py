"""Symmetric arbitrary-size Beneš, including explicit odd bypasses.

Pair edges alternate input/output along cycles or the one open odd path.
The latter has an even number of edges, so both unpaired endpoints can be
assigned to the larger child. Every paired port contributes one member to
each child. The remaining permutation therefore splits into bijections of
floor(n/2) and ceil(n/2); induction supplies a rearrangeability argument.
Verification walks the exported stage graph, independently of this coloring.
"""

from collections import Counter


def split_permutation(n):
    k = n // 2
    return [i // 2 + (k if i % 2 else 0) for i in range(2 * k)] + (
        [n - 1] if n % 2 else []
    )


class ASNetwork:
    def __init__(self, cfg):
        self.cfg, self.p = cfg, cfg.internal_ports
        self.depth = max(0, 2 * (self.p - 1).bit_length() - 1)
        self.switches = {}
        self.slots = [{} for _ in range(self.depth)]
        self.boundaries = [
            dict(stage=s, permutation=list(range(self.p)), blocks=[])
            for s in range(max(0, self.depth - 1))
        ]

        def switch(address, stage, lane):
            sid = f"a{address}_s{stage:02d}_r{lane:04d}"
            self.switches[sid] = dict(stage=stage, row=lane, address=address)
            for pin in (0, 1):
                if lane + pin in self.slots[stage]:
                    raise ValueError("overlapping AS switch slots")
                self.slots[stage][lane + pin] = (sid, pin)
            return sid

        def build(n, lo, hi, base, address):
            node = dict(size=n, base=base, address=address, first=lo, last=hi)
            if n == 1:
                return node
            if n == 2:
                node["switch"] = switch(address, (lo + hi) // 2, base)
                return node
            k = n // 2
            node["left"] = [switch(address + "i", lo, base + 2 * i) for i in range(k)]
            node["right"] = [switch(address + "o", hi, base + 2 * i) for i in range(k)]
            perm = split_permutation(n)
            inverse = [perm.index(i) for i in range(n)]
            for s, ps, inv in ((lo, perm, False), (hi - 1, inverse, True)):
                boundary = self.boundaries[s]
                boundary["permutation"][base : base + n] = [base + i for i in ps]
                boundary["blocks"].append(
                    dict(base=base, size=n, inverse=inv, permutation=ps)
                )
            node["children"] = [
                build(k, lo + 1, hi - 1, base, address + "0"),
                build(n - k, lo + 1, hi - 1, base + k, address + "1"),
            ]
            return node

        self.root = build(self.p, 0, self.depth - 1, 0, "r")
        for b in self.boundaries:
            b["blocks"].sort(key=lambda v: v["base"])
        self.bypasses = [
            dict(stage=s, row=r)
            for s in range(self.depth)
            for r in range(self.p)
            if r not in self.slots[s]
        ]

    def solve(self, requests):
        pairs = [tuple(v) for v in requests]
        n = self.p
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
        pi = [-1] * n
        for a, b in pairs:
            pi[self.cfg.input_map[a]] = self.cfg.output_map[b]
        unused = iter(sorted(set(range(n)) - set(pi)))
        for a in range(n):
            if pi[a] < 0:
                pi[a] = next(unused)
        states = {}

        def recurse(node, perm):
            size = len(perm)
            if size == 1:
                return
            if size == 2:
                states[node["switch"]] = perm[0]
                return
            inv = [0] * size
            for a, b in enumerate(perm):
                inv[b] = a
            colors = [-1] * size
            seeds = [(size - 1, 1), (inv[size - 1], 1)] if size % 2 else []
            seeds += [(i, 0) for i in range(size)]
            for start, color in seeds:
                if colors[start] >= 0:
                    if (
                        size % 2
                        and start in (size - 1, inv[size - 1])
                        and colors[start] != 1
                    ):
                        raise ValueError("unpaired endpoint color conflict")
                    continue
                colors[start] = color
                stack = [start]
                while stack:
                    a = stack.pop()
                    others = []
                    if a ^ 1 < size:
                        others.append(a ^ 1)
                    if perm[a] ^ 1 < size:
                        others.append(inv[perm[a] ^ 1])
                    for other in others:
                        if colors[other] < 0:
                            colors[other] = 1 - colors[a]
                            stack.append(other)
                        elif colors[other] == colors[a]:
                            raise ValueError("AS pairing graph is not bipartite")
            k = size // 2
            for i in range(k):
                states[node["left"][i]] = colors[2 * i]
                states[node["right"][i]] = colors[inv[2 * i]]
            sub = [[-1] * k, [-1] * (size - k)]
            for a, b in enumerate(perm):
                sub[colors[a]][a // 2] = b // 2
            for child, ps in zip(node["children"], sub):
                if sorted(ps) != list(range(len(ps))):
                    raise ValueError("invalid AS recursive permutation")
                recurse(child, ps)

        recurse(self.root, pi)
        return dict(
            active=pairs,
            internal_permutation=pi,
            states=dict(sorted(states.items())),
            dark_active_inputs=sorted(set(range(n)) - {a for a, b in pairs}),
            rearrangeable=True,
        )

    def trace(self, internal_input, states):
        if type(internal_input) is not int or not 0 <= internal_input < self.p:
            raise ValueError("invalid internal input")
        lane, path = internal_input, []
        for s in range(self.depth):
            pair = self.slots[s].get(lane)
            if pair:
                sid, pin = pair
                out = pin ^ states[sid]
                path.append(dict(switch=sid, input=pin, output=out, stage=s, row=lane))
                lane = self.switches[sid]["row"] + out
            else:
                path.append(dict(bypass=True, stage=s, row=lane))
            if s < self.depth - 1:
                lane = self.boundaries[s]["permutation"][lane]
        return lane, path

    def verify(self, settings):
        states = settings.get("states", {})
        if set(states) != set(self.switches) or any(
            type(v) is not int or v not in (0, 1) for v in states.values()
        ):
            raise ValueError("settings must cover every switch with bar/cross states")
        pi = settings.get("internal_permutation", [])
        if (
            len(pi) != self.p
            or any(type(v) is not int for v in pi)
            or sorted(pi) != list(range(self.p))
        ):
            raise ValueError("invalid complete internal permutation")
        occupied, depths = set(), []
        for a, expected in enumerate(pi):
            actual, path = self.trace(a, states)
            if actual != expected:
                raise ValueError(f"input {a}: expected output {expected}, got {actual}")
            for item in path:
                key = (item["stage"], item["row"])
                if key in occupied:
                    raise ValueError("duplicate occupied internal port")
                occupied.add(key)
            depths.append(sum("switch" in item for item in path))
        pairs = settings.get("active", [])
        if any(
            len(v) != 2 or any(type(i) is not int or not 0 <= i < self.p for i in v)
            for v in pairs
        ):
            raise ValueError("invalid active requests")
        if len({a for a, b in pairs}) != len(pairs) or len(
            {b for a, b in pairs}
        ) != len(pairs):
            raise ValueError("duplicate active ports")
        if any(pi[self.cfg.input_map[a]] != self.cfg.output_map[b] for a, b in pairs):
            raise ValueError("completed permutation disagrees with active request")
        if (
            settings.get("dark_active_inputs")
            != sorted(set(range(self.p)) - {a for a, b in pairs})
            or settings.get("rearrangeable") is not True
        ):
            raise ValueError("settings operating assumptions differ from request")
        return dict(
            connections=len(pairs),
            internal_paths=self.p,
            switch_depth=self.depth,
            actual_mzi_counts=dict(sorted(Counter(depths).items())),
        )

    def export(self):
        return dict(
            topology="as-benes",
            internal_ports=self.p,
            depth=self.depth,
            switches=self.switches,
            boundaries=self.boundaries,
            bypasses=self.bypasses,
        )
