"""Full regular Beneš graph and recursive alternating-cycle solver.

The solver recurses through subproblems; verification instead walks the
explicit interstage permutations. Neither imports the Waksman engine.
"""

from .config import Config


def switch_id(stage, index):
    return f"s{stage:02d}_m{index:04d}"


def shuffle(size):
    return [i // 2 + (i % 2) * (size // 2) for i in range(size)]


class Network:
    def __init__(self, config: Config | int = 100):
        self.cfg = Config(active_ports=config) if isinstance(config, int) else config
        self.p = self.cfg.internal_ports
        self.depth = 2 * (self.p.bit_length() - 1) - 1
        self.switches = {
            switch_id(s, i): {"stage": s, "index": i}
            for s in range(self.depth)
            for i in range(self.p // 2)
        }
        self.boundaries = []
        for s in range(self.depth - 1):
            level = min(s, self.depth - 2 - s)
            size = self.p >> level
            perm = shuffle(size)
            inverse = s >= self.depth // 2
            if inverse:
                perm = [perm.index(i) for i in range(size)]
            self.boundaries.append(
                {
                    "size": size,
                    "inverse": inverse,
                    "permutation": [
                        b + perm[i] for b in range(0, self.p, size) for i in range(size)
                    ],
                }
            )

    def solve(self, requests):
        pairs = [tuple(v) for v in requests]
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
        pi = [-1] * self.p
        for a, b in pairs:
            pi[self.cfg.input_map[a]] = self.cfg.output_map[b]
        unused = iter(sorted(set(range(self.p)) - set(pi)))
        for a in range(self.p):
            if pi[a] < 0:
                pi[a] = next(unused)
        states = {}

        def recurse(perm, stage, offset):
            size = len(perm)
            if size == 2:
                states[switch_id(stage, offset)] = perm[0]
                return
            inv = [0] * size
            for a, b in enumerate(perm):
                inv[b] = a
            color = [-1] * size
            for start in range(size):
                if color[start] >= 0:
                    continue
                color[start] = 0
                stack = [start]
                while stack:
                    a = stack.pop()
                    for other in (a ^ 1, inv[perm[a] ^ 1]):
                        if color[other] < 0:
                            color[other] = color[a] ^ 1
                            stack.append(other)
                        elif color[other] == color[a]:
                            raise ValueError("pairing graph is not bipartite")
            last = stage + 2 * (size.bit_length() - 1) - 2
            for i in range(size // 2):
                states[switch_id(stage, offset + i)] = color[2 * i]
                states[switch_id(last, offset + i)] = color[inv[2 * i]]
            sub = [[0] * (size // 2) for _ in range(2)]
            for a, b in enumerate(perm):
                sub[color[a]][a // 2] = b // 2
            recurse(sub[0], stage + 1, offset)
            recurse(sub[1], stage + 1, offset + size // 4)

        recurse(pi, 0, 0)
        return {
            "active": pairs,
            "internal_permutation": pi,
            "states": dict(sorted(states.items())),
            "dark_active_inputs": sorted(set(range(n)) - {a for a, _ in pairs}),
            "rearrangeable": True,
        }

    def trace(self, internal_input, states):
        lane = internal_input
        path = []
        for stage in range(self.depth):
            sid = switch_id(stage, lane // 2)
            out = (lane % 2) ^ states[sid]
            path.append({"switch": sid, "input": lane % 2, "output": out})
            lane = lane - lane % 2 + out
            if stage < self.depth - 1:
                lane = self.boundaries[stage]["permutation"][lane]
        return lane, path

    def verify(self, settings):
        states = settings["states"]
        if set(states) != set(self.switches) or any(
            type(v) is not int or v not in (0, 1) for v in states.values()
        ):
            raise ValueError("settings must cover every switch with bar/cross states")
        pi = settings["internal_permutation"]
        if (
            len(pi) != self.p
            or any(type(v) is not int for v in pi)
            or sorted(pi) != list(range(self.p))
        ):
            raise ValueError("settings must contain a complete internal permutation")
        for a, expected in enumerate(pi):
            actual, path = self.trace(a, states)
            if actual != expected or len(path) != self.depth:
                raise ValueError(f"input {a}: expected output {expected}, got {actual}")
        pairs = settings["active"]
        # Validate requests independently of their completed permutation.
        if (
            any(
                len(v) != 2
                or any(
                    type(i) is not int or not 0 <= i < self.cfg.active_ports for i in v
                )
                for v in pairs
            )
            or len(set(a for a, b in pairs)) != len(pairs)
            or len(set(b for a, b in pairs)) != len(pairs)
        ):
            raise ValueError("invalid active mapping in settings")
        for a, b in pairs:
            if pi[self.cfg.input_map[a]] != self.cfg.output_map[b]:
                raise ValueError("completed permutation disagrees with active request")
        if (
            settings.get("dark_active_inputs")
            != sorted(set(range(self.cfg.active_ports)) - {a for a, b in pairs})
            or settings.get("rearrangeable") is not True
        ):
            raise ValueError("settings operating assumptions differ from request")
        return {
            "connections": len(pairs),
            "internal_paths": self.p,
            "switch_depth": self.depth,
        }

    def export(self):
        return {
            "internal_ports": self.p,
            "depth": self.depth,
            "switches": self.switches,
            "boundaries": self.boundaries,
        }
