"""Small explicit geometry model, then emitted as gdsfactory cell references.

The manifest keeps component contracts, centerlines, and cell polygons for GDS
readback reconciliation. Layout connectivity is checked separately from pixels.
"""

from dataclasses import dataclass, field, asdict
from math import sin, cos, pi, ceil, acos, hypot, sqrt
import hashlib
import json

from .config import Config


def snap(x: float, grid=0.001) -> float:
    return round(round(x / grid) * grid, 6)


def rectangle(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def line_polygon(a, b, width):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = hypot(dx, dy)
    if length <= 0:
        raise ValueError("zero-length segment")
    # Tiny internal overlap absorbs independent polygon grid rounding at
    # tangent arc/crossing joints, without changing external cell interfaces.
    overlap = 0.005
    a = (a[0] - dx / length * overlap, a[1] - dy / length * overlap)
    b = (b[0] + dx / length * overlap, b[1] + dy / length * overlap)
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    return [
        [a[0] + nx, a[1] + ny],
        [b[0] + nx, b[1] + ny],
        [b[0] - nx, b[1] - ny],
        [a[0] - nx, a[1] - ny],
    ]


def arc_polygon(cx, cy, r, start, end, width, tolerance):
    steps = max(4, ceil(abs(end - start) / (2 * acos(1 - tolerance / (r + width / 2)))))
    angles = [start + (end - start) * i / steps for i in range(steps + 1)]
    return [
        [cx + (r + width / 2) * cos(t), cy + (r + width / 2) * sin(t)] for t in angles
    ] + [
        [cx + (r - width / 2) * cos(t), cy + (r - width / 2) * sin(t)]
        for t in reversed(angles)
    ]


@dataclass
class Cell:
    name: str
    kind: str
    polygons: list = field(default_factory=list)
    refs: list = field(default_factory=list)
    ports: dict = field(default_factory=dict)
    tracks: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class Library:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cells: dict[str, Cell] = {}

    def cell(self, name, kind):
        if name not in self.cells:
            self.cells[name] = Cell(name, kind)
        return self.cells[name]

    def poly(self, cell, layer, points):
        cell.polygons.append(
            {
                "layer": layer,
                "points": [
                    [snap(x, self.cfg.grid), snap(y, self.cfg.grid)] for x, y in points
                ],
            }
        )

    def ref(self, parent, child, x=0, y=0, angle=0, id=None):
        parent.refs.append(
            dict(
                cell=child.name, x=snap(x), y=snap(y), angle=angle, id=id or child.name
            )
        )

    def straight(self, length):
        length = snap(length)
        name = f"WG_{length:.3f}".replace(".", "p")
        if name in self.cells:
            return self.cells[name]
        c = self.cell(name, "straight")
        self.poly(
            c, "WG", rectangle(0, -self.cfg.wg_width / 2, length, self.cfg.wg_width / 2)
        )
        c.ports = {"w": [0, 0, 180], "e": [length, 0, 0]}
        c.tracks = [dict(ports=["w", "e"], length=length, min_radius=None)]
        return c

    def pad(self):
        if "PAD" in self.cells:
            return self.cells["PAD"]
        c = self.cell("PAD", "pad")
        a = self.cfg.pad_size / 2
        self.poly(c, "M2", rectangle(-a, -a, a, a))
        c.ports = {"e": [0, 0, 90]}
        return c

    def via(self):
        if "VIA" in self.cells:
            return self.cells["VIA"]
        c = self.cell("VIA", "via")
        r = self.cfg.via_size / 2
        self.poly(c, "VIA", rectangle(-r, -r, r, r))
        for layer in ("M1", "M2"):
            e = r + self.cfg.via_enclosure
            self.poly(c, layer, rectangle(-e, -e, e, e))
        return c

    def mzi(self):
        if "MZI" in self.cells:
            return self.cells["MZI"]
        c = self.cell("MZI", "mzi")
        cfg = self.cfg
        L = cfg.mzi_length
        p = cfg.lane_pitch
        for y in (0, p):
            self.ref(c, self.straight(L), y=y)
        # Explicit interaction blocks are black-box 2x2 coupler placeholders.
        for x in (L * 0.1, L * 0.9):
            self.poly(
                c,
                "WG",
                rectangle(x - 5, -cfg.wg_width / 2, x + 5, p + cfg.wg_width / 2),
            )
        edge = (cfg.mzi_height - p) / 2
        self.poly(c, "DEVICE", rectangle(0, -edge, L, p + edge))
        c.ports = {
            "i0": [0, 0, 180],
            "i1": [0, p, 180],
            "o0": [L, 0, 0],
            "o1": [L, p, 0],
        }
        for name, y in zip(cfg.terminal_names, cfg.terminal_offsets):
            self.poly(
                c,
                "M1",
                rectangle(L * 0.2, y - cfg.metal_width / 2, L, y + cfg.metal_width / 2),
            )
            c.ports[name] = [L, y, 0]
        c.metadata = {
            "placeholder": True,
            "terminal_names": list(cfg.terminal_names),
            "allowed_transforms": [0],
            "interaction_bbox": [0, -edge, L, p + edge],
            "bar": [["i0", "o0"], ["i1", "o1"]],
            "cross": [["i0", "o1"], ["i1", "o0"]],
        }
        return c

    def crossing(self):
        if "CROSSING" in self.cells:
            return self.cells["CROSSING"]
        c = self.cell("CROSSING", "crossing")
        a = self.cfg.crossing_half_length
        w = self.cfg.wg_width
        self.poly(c, "WG", rectangle(-a, -w / 2, a, w / 2))
        self.poly(c, "WG", rectangle(-w / 2, -a, w / 2, a))
        c.ports = {
            "w": [-a, 0, 180],
            "e": [a, 0, 0],
            "s": [0, -a, 270],
            "n": [0, a, 90],
        }
        c.tracks = [
            dict(ports=["w", "e"], length=2 * a, min_radius=None),
            dict(ports=["s", "n"], length=2 * a, min_radius=None),
        ]
        c.metadata = {"placeholder": True, "through": [["w", "e"], ["s", "n"]]}
        return c

    def swap(self):
        if "SWAP" in self.cells:
            return self.cells["SWAP"]
        c = self.cell("SWAP", "swap")
        cfg = self.cfg
        r = cfg.radius
        p = cfg.lane_pitch
        # 45-degree approach arcs; the central explicit crossing is orthogonal.
        ax = r / sqrt(2)
        ay = r * (1 - 1 / sqrt(2))
        width = snap(2 * ax + p - 2 * ay)
        mid = (width / 2, p / 2)
        h = cfg.crossing_half_length / sqrt(2)
        if (p / 2 - ay) * sqrt(2) <= cfg.crossing_half_length + cfg.wg_clearance:
            raise ValueError("lane pitch cannot fit crossing approaches")
        self.ref(c, self.crossing(), *mid, angle=45, id="cross")
        # Four tangent arcs and straight approaches, mirrored about p/2.
        path_polys = [
            arc_polygon(0, r, r, -pi / 2, -pi / 4, cfg.wg_width, cfg.chord_error),
            line_polygon((ax, ay), (mid[0] - h, mid[1] - h), cfg.wg_width),
            line_polygon((mid[0] + h, mid[1] + h), (width - ax, p - ay), cfg.wg_width),
            arc_polygon(
                width, p - r, r, 3 * pi / 4, pi / 2, cfg.wg_width, cfg.chord_error
            ),
        ]
        for poly in path_polys:
            self.poly(c, "WG", poly)
            self.poly(c, "WG", [[x, p - y] for x, y in poly])
        c.ports = {
            "w0": [0, 0, 180],
            "w1": [0, p, 180],
            "e0": [width, 0, 0],
            "e1": [width, p, 0],
        }
        length = pi * r / 2 + (p - 2 * ay) * sqrt(2)
        c.tracks = [
            dict(ports=["w0", "e1"], length=length, min_radius=r),
            dict(ports=["w1", "e0"], length=length, min_radius=r),
        ]
        c.metadata = {"crossing_center": list(mid), "width": width, "placeholder": True}
        return c

    def export(self):
        return {name: asdict(cell) for name, cell in self.cells.items()}

    def write_gds(self, top, path):
        import gdsfactory as gf
        from gdsfactory.gpdk import PDK

        PDK.activate()
        made = {}
        prefix = self.cfg.digest[:8]
        # Separate layout database per export; deterministic GDS cell names do
        # not depend on process-global caches or earlier candidate generation.
        import uuid

        kcl = type(gf.kcl)(name="waksman_" + uuid.uuid4().hex)
        for pair in self.cfg.layers.values():
            index = gf.get_layer(tuple(pair))
            kcl.layout.insert_layer_at(int(index), gf.kdb.LayerInfo(*pair))

        def create(name):
            if name in made:
                return made[name]
            model = self.cells[name]
            digest = hashlib.sha256(
                json.dumps(asdict(model), sort_keys=True).encode()
            ).hexdigest()[:10]
            full_name = f"{name[:35]}_{prefix}_{digest}"
            c = gf.Component(full_name, kcl=kcl)
            made[name] = c
            for poly in model.polygons:
                c.add_polygon(
                    poly["points"], layer=tuple(self.cfg.layers[poly["layer"]])
                )
            for ref in model.refs:
                instance = c.add_ref(create(ref["cell"]))
                if ref["angle"]:
                    instance.drotate(ref["angle"])
                instance.dmove((ref["x"], ref["y"]))
            for pname, (x, y, orientation) in model.ports.items():
                optical = (
                    model.kind not in ("pad", "via")
                    and pname not in self.cfg.terminal_names
                )
                c.add_port(
                    name=pname,
                    center=(x, y),
                    orientation=orientation,
                    width=self.cfg.wg_width if optical else self.cfg.metal_width,
                    layer=tuple(self.cfg.layers["WG" if optical else "M1"]),
                    port_type="optical" if optical else "electrical",
                )
            return c

        create(top).write_gds(path)
        return {name: c.name for name, c in made.items()}


def transform_point(x, y, ref):
    t = ref.get("angle", 0) * pi / 180
    return (
        snap(ref["x"] + x * cos(t) - y * sin(t)),
        snap(ref["y"] + x * sin(t) + y * cos(t)),
    )


def validate_mzi(cell: Cell, cfg: Config):
    """Replacement contract: geometry may change, interface follows config."""
    expected = {
        "i0": [0, 0, 180],
        "i1": [0, cfg.lane_pitch, 180],
        "o0": [cfg.mzi_length, 0, 0],
        "o1": [cfg.mzi_length, cfg.lane_pitch, 0],
    }
    for name, y in zip(cfg.terminal_names, cfg.terminal_offsets):
        expected[name] = [cfg.mzi_length, y, 0]
    if set(cell.ports) != set(expected):
        raise ValueError(
            "MZI replacement must expose the configured four optical ports and electrical terminals"
        )
    for name, port in expected.items():
        if any(abs(a - b) > cfg.grid for a, b in zip(cell.ports[name], port)):
            raise ValueError(
                f"MZI replacement port {name} differs from configured interface"
            )
    if cell.metadata.get("bar") != [["i0", "o0"], ["i1", "o1"]] or cell.metadata.get(
        "cross"
    ) != [["i0", "o1"], ["i1", "o0"]]:
        raise ValueError("MZI replacement must declare bar/cross transfer pairs")
    if 0 not in cell.metadata.get("allowed_transforms", []):
        raise ValueError("MZI replacement must permit its unrotated orientation")
