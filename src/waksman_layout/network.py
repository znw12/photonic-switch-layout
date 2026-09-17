"""Exact arbitrary-size Waksman construction and recursive two-colouring solver.

Port numbering is zero-based. State 0 is bar; state 1 is cross.
The independently exported edge graph is used for validation, not the solver.
"""

from dataclasses import dataclass, field
from collections import deque
from typing import Iterable


def switch_count(n: int) -> int:
    if type(n) is not int or n < 1:
        raise ValueError("N must be a positive integer")
    k = (n - 1).bit_length()
    return n * k - (1 << k) + 1


@dataclass
class Node:
    n: int
    id: str
    depth: int
    row: int
    left: list[str] = field(default_factory=list)
    right: list[str] = field(default_factory=list)
    children: list["Node"] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


class Network:
    def __init__(self, n: int):
        switch_count(n)
        self.n = n
        self.columns = max(1, 2 * (n - 1).bit_length() - 1)
        self.switches: dict[str, dict] = {}
        self.edges: list[tuple[str, str]] = []
        self.root = self._build(n, "net", 0, 0)
        for i in range(n):
            self.edges.extend(
                [(f"in:{i}", self.root.inputs[i]), (self.root.outputs[i], f"out:{i}")]
            )
        self.successor = dict(self.edges)
        if len(self.switches) != switch_count(n):
            raise AssertionError("construction switch count mismatch")

    def _switch(self, sid: str, stage: int, row: int, parent: str):
        self.switches[sid] = dict(stage=stage, row=row, parent=parent)
        return [f"{sid}:i{k}" for k in range(2)], [f"{sid}:o{k}" for k in range(2)]

    def _build(self, n: int, name: str, depth: int, row: int) -> Node:
        node = Node(n, name, depth, row)
        if n == 1:
            node.inputs, node.outputs = [name + ":pass_in"], [name + ":pass_out"]
            self.edges.append((node.inputs[0], node.outputs[0]))
            return node
        if n == 2:
            sid = name + "/S"
            node.left = [sid]
            node.inputs, node.outputs = self._switch(sid, depth, row, name)
            return node
        a = n // 2
        upper = self._build(a, name + "/U", depth + 1, row)
        lower = self._build(n - a, name + "/D", depth + 1, row + a)
        node.children = [upper, lower]
        for j in range(a):
            sid = name + f"/L{j}"
            ins, outs = self._switch(sid, depth, row + 2 * j, name)
            node.left.append(sid)
            node.inputs.extend(ins)
            self.edges.extend([(outs[0], upper.inputs[j]), (outs[1], lower.inputs[j])])
        if n % 2:
            node.inputs.append(lower.inputs[-1])
        for j in range((n - 1) // 2):
            sid = name + f"/R{j}"
            ins, outs = self._switch(sid, self.columns - 1 - depth, row + 2 * j, name)
            node.right.append(sid)
            node.outputs.extend(outs)
            self.edges.extend([(upper.outputs[j], ins[0]), (lower.outputs[j], ins[1])])
        if n % 2:
            node.outputs.append(lower.outputs[-1])
        else:
            node.outputs.extend([upper.outputs[-1], lower.outputs[-1]])
        return node

    def solve(self, requests: Iterable[tuple[int, int]]) -> dict:
        requests = [tuple(pair) for pair in requests]
        used_i, used_o = set(), set()
        for pair in requests:
            if len(pair) != 2 or any(
                type(v) is not int or not 0 <= v < self.n for v in pair
            ):
                raise ValueError(
                    f"invalid input/output pair {pair}; expected 0..{self.n-1}"
                )
            i, o = pair
            if i in used_i or o in used_o:
                raise ValueError(
                    f"duplicate input {i} or output {o}; mappings must be one-to-one"
                )
            used_i.add(i)
            used_o.add(o)
        pairs = sorted(requests) + list(
            zip(
                sorted(set(range(self.n)) - used_i), sorted(set(range(self.n)) - used_o)
            )
        )
        perm = dict(pairs)
        settings: dict[str, int] = {}
        self._solve_node(self.root, [perm[i] for i in range(self.n)], settings)
        return {
            "n": self.n,
            "active": sorted(requests),
            "inactive": sorted([p for p in pairs if p[0] not in used_i]),
            "permutation": [perm[i] for i in range(self.n)],
            "states": dict(sorted(settings.items())),
        }

    def _solve_node(self, node: Node, p: list[int], states: dict[str, int]):
        n = node.n
        if n == 1:
            return
        if n == 2:
            states[node.left[0]] = p[0]
            return
        inv = [0] * n
        for i, j in enumerate(p):
            inv[j] = i
        adj = [[] for _ in range(n)]
        for a, b in [(2 * j, 2 * j + 1) for j in range(n // 2)] + [
            (inv[2 * j], inv[2 * j + 1]) for j in range((n - 1) // 2)
        ]:
            adj[a].append(b)
            adj[b].append(a)
        colors = [-1] * n
        forced = (
            [(n - 1, 1), (inv[n - 1], 1)]
            if n % 2
            else [(inv[n - 2], 0), (inv[n - 1], 1)]
        )
        for seed, color in forced + [(i, 0) for i in range(n)]:
            if colors[seed] >= 0:
                if (seed, color) in forced and colors[seed] != color:
                    raise AssertionError("inconsistent bypass constraint")
                continue
            colors[seed] = color
            queue = deque([seed])
            while queue:
                v = queue.popleft()
                for w in adj[v]:
                    want = 1 - colors[v]
                    if colors[w] == -1:
                        colors[w] = want
                        queue.append(w)
                    elif colors[w] != want:
                        raise AssertionError("Waksman constraints not bipartite")
        for j, sid in enumerate(node.left):
            states[sid] = colors[2 * j]
        for j, sid in enumerate(node.right):
            states[sid] = colors[inv[2 * j]]
        sub = [[0] * child.n for child in node.children]
        for i, j in enumerate(p):
            sub[colors[i]][i // 2] = j // 2
        for child, perm in zip(node.children, sub):
            self._solve_node(child, perm, states)

    def trace(self, states: dict[str, int], i: int) -> tuple[int, list[str]]:
        """Independent edge traversal; has no knowledge of recursive coloring."""
        port, path = f"in:{i}", []
        seen = set()
        while not port.startswith("out:"):
            if port in seen:
                raise ValueError(f"cycle at {port}")
            seen.add(port)
            if port in self.successor:
                port = self.successor[port]
            else:
                sid, pin = port.rsplit(":", 1)
                if sid not in self.switches or pin not in ("i0", "i1"):
                    raise ValueError(f"unconnected port {port}")
                state = states.get(sid)
                if type(state) is not int or state not in (0, 1):
                    raise ValueError(f"missing/invalid state for {sid}")
                path.append(sid)
                port = f"{sid}:o{int(pin[-1]) ^ state}"
        return int(port.split(":")[1]), path

    def verify(self, solution: dict) -> None:
        if solution.get("n") != self.n or sorted(
            solution.get("permutation", [])
        ) != list(range(self.n)):
            raise ValueError("solution must contain a complete permutation for this N")
        active = solution.get("active", [])
        inactive = solution.get("inactive", [])
        pairs = active + inactive
        if len(pairs) != self.n or sorted(pairs) != sorted(
            enumerate(solution["permutation"])
        ):
            # JSON readback uses lists instead of tuples.
            if len(pairs) != self.n or sorted(map(tuple, pairs)) != sorted(
                enumerate(solution["permutation"])
            ):
                raise ValueError(
                    "active/inactive mappings disagree with the permutation"
                )
        if set(solution["states"]) != set(self.switches):
            raise ValueError("switch-state identifiers do not match network")
        for i, expected in enumerate(solution["permutation"]):
            reached, _ = self.trace(solution["states"], i)
            if reached != expected:
                raise ValueError(
                    f"input {i}: expected output {expected}, reached {reached}"
                )

    def export(self) -> dict:
        return {
            "n": self.n,
            "columns": self.columns,
            "switches": self.switches,
            "edges": self.edges,
            "inputs": [f"in:{i}" for i in range(self.n)],
            "outputs": [f"out:{i}" for i in range(self.n)],
            "transfer": {
                "0": [["i0", "o0"], ["i1", "o1"]],
                "1": [["i0", "o1"], ["i1", "o0"]],
            },
        }
