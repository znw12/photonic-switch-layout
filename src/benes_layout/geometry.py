"""Technology-neutral primitives plus analytic Beneš shuffle blocks.

Only the existing explicit polygon/cell exporter and elementary primitives are
shared. No Waksman network, placement, permutation scheduler, or router is used.
"""

from math import pi, sqrt, degrees

from waksman_layout.geometry import (
    Library as PrimitiveLibrary,
    snap,
    rectangle,
    arc_polygon,
    line_polygon,
    validate_mzi,
)


class Library(PrimitiveLibrary):
    def mzi(self):
        c = super().mzi()
        if not c.tracks:
            for a in range(2):
                for b in range(2):
                    c.tracks.append(
                        dict(
                            ports=[f"i{a}", f"o{b}"],
                            length=self.cfg.mzi_length,
                            bends=0,
                            angle=0,
                            crossings=0,
                            min_radius=None,
                        )
                    )
            c.metadata["length_model"] = (
                "Ideal black-box propagation length; coupler/phase/state delay unmodeled"
            )
        return c

    def straight(self, length):
        c = super().straight(length)
        c.tracks[0].update(bends=0, angle=0, crossings=0)
        return c

    def crossing(self):
        c = super().crossing()
        for t in c.tracks:
            t.update(bends=0, angle=0, crossings=1)
        c.metadata.setdefault("allowed_transforms", [0, 45, 90, 135, 180, 225, 270, 315])
        return c

    def bend(self, name, cx, cy, start, end):
        if name in self.cells:
            return self.cells[name]
        from math import cos, sin

        cfg = self.cfg
        c = self.cell(name, "bend")
        self.poly(
            c,
            "WG",
            arc_polygon(cx, cy, cfg.radius, start, end, cfg.wg_width, cfg.chord_error),
        )
        sign = 1 if end > start else -1
        c.ports = {
            "w": [
                snap(cx + cfg.radius * cos(start)),
                snap(cy + cfg.radius * sin(start)),
                (degrees(start + sign * pi / 2) + 180) % 360,
            ],
            "e": [
                snap(cx + cfg.radius * cos(end)),
                snap(cy + cfg.radius * sin(end)),
                degrees(end + sign * pi / 2) % 360,
            ],
        }
        c.metadata["arc"] = dict(
            center=[cx, cy], radius=cfg.radius, start=start, end=end
        )
        c.tracks = [
            dict(
                ports=["w", "e"],
                length=cfg.radius * abs(end - start),
                bends=1,
                angle=abs(end - start),
                crossings=0,
                min_radius=cfg.radius,
            )
        ]
        return c

    def exchange(self):
        if "EXCHANGE" in self.cells:
            return self.cells["EXCHANGE"]
        cfg = self.cfg
        r, p = cfg.radius, cfg.lane_pitch
        ax, ay = r / sqrt(2), r * (1 - 1 / sqrt(2))
        width = snap(2 * ax + p - 2 * ay)
        mid = (width / 2, p / 2)
        h = cfg.crossing_half_length / sqrt(2)
        if (p / 2 - ay) * sqrt(2) <= cfg.crossing_half_length + cfg.wg_clearance:
            raise ValueError("lane pitch cannot fit crossing approaches")
        c = self.cell("EXCHANGE", "exchange")
        if 45 not in self.crossing().metadata["allowed_transforms"]:
            raise ValueError("crossing transform 45 is not permitted")
        self.ref(c, self.crossing(), *mid, angle=45)
        for name, cx, cy, a, b in (
            ("BEND_NE", 0, r, -pi / 2, -pi / 4),
            ("BEND_SE", 0, p - r, pi / 2, pi / 4),
            ("BEND_EN", width, p - r, 3 * pi / 4, pi / 2),
            ("BEND_ES", width, r, -3 * pi / 4, -pi / 2),
        ):
            self.ref(c, self.bend(name, cx, cy, a, b))
        for a, b in (
            ((ax, ay), (mid[0] - h, mid[1] - h)),
            ((mid[0] + h, mid[1] + h), (width - ax, p - ay)),
        ):
            poly = line_polygon(a, b, cfg.wg_width)
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
            dict(
                ports=[f"w{i}", f"e{1-i}"],
                length=length,
                bends=2,
                angle=pi / 2,
                crossings=1,
                min_radius=r,
            )
            for i in range(2)
        ]
        c.metadata = {"width": width, "crossing_center": mid, "placeholder": True}
        return c

    def shuffle_block(self, size, inverse=False):
        """Closed-form triangular perfect shuffle; no generic sorting router.

        Deinterleaving 2m lanes has m-1 parallel crossing columns. At column c,
        exchange pairs start at rows c+1,c+3,...,2m-c-3. Reversing the column
        sequence realizes the inverse. Repeated subnetwork groups share cells.
        """
        if self.cfg.interstage_routing != "legacy":
            from .interstage import shuffle_block

            return shuffle_block(self, size, inverse)
        name = f"{'MERGE' if inverse else 'SPLIT'}_{size}"
        if name in self.cells:
            return self.cells[name]
        c = self.cell(name, "shuffle")
        exchange = self.exchange()
        width = exchange.metadata["width"]
        current = list(range(size))
        parts = [[] for _ in current]
        columns = list(range(size // 2 - 1))
        if inverse:
            columns.reverse()
        for column, pattern in enumerate(columns):
            x = snap(column * width)
            used = set()
            for row in range(pattern + 1, size - pattern - 2, 2):
                self.ref(
                    c, exchange, x, row * self.cfg.lane_pitch, id=f"c{column}_r{row}"
                )
                for pin in range(2):
                    parts[current[row + pin]].append(
                        dict(
                            cell=exchange.name,
                            x=x,
                            y=row * self.cfg.lane_pitch,
                            entry=f"w{pin}",
                            exit=f"e{1-pin}",
                        )
                    )
                current[row], current[row + 1] = current[row + 1], current[row]
                used.update((row, row + 1))
            for row, wire in enumerate(current):
                if row not in used:
                    straight = self.straight(width)
                    self.ref(
                        c,
                        straight,
                        x,
                        row * self.cfg.lane_pitch,
                        id=f"c{column}_r{row}",
                    )
                    parts[wire].append(
                        dict(
                            cell=straight.name,
                            x=x,
                            y=row * self.cfg.lane_pitch,
                            entry="w",
                            exit="e",
                        )
                    )
        span = snap(len(columns) * width)
        c.metadata = {
            "width": span,
            "size": size,
            "inverse": inverse,
            "permutation": [current.index(i) for i in range(size)],
        }
        for row in range(size):
            c.ports[f"w{row}"] = [0, row * self.cfg.lane_pitch, 180]
            c.ports[f"e{row}"] = [span, row * self.cfg.lane_pitch, 0]
            totals = dict(length=0.0, bends=0, angle=0.0, crossings=0)
            for part in parts[row]:
                t = next(
                    t
                    for t in self.cells[part["cell"]].tracks
                    if t["ports"] == [part["entry"], part["exit"]]
                )
                for key in totals:
                    totals[key] += t[key]
            c.tracks.append(
                dict(
                    ports=[f"w{row}", f"e{current.index(row)}"],
                    pieces=parts[row],
                    **totals,
                )
            )
        return c

    def termination(self, side):
        name = "TERMINATION_" + side.upper()
        if name in self.cells:
            return self.cells[name]
        c = self.cell(name, "termination")
        l = self.cfg.termination_length
        a, b = (-l, 0) if side == "west" else (0, l)
        self.poly(
            c, "WG", rectangle(a, -self.cfg.wg_width / 2, b, self.cfg.wg_width / 2)
        )
        c.ports = {"opt": [0, 0, 0 if side == "west" else 180]}
        c.metadata = {"placeholder": True, "reflectionless": False, "length": l}
        return c


def validate_components(lib):
    validate_mzi(lib.mzi(), lib.cfg)
    c = lib.crossing()
    if c.metadata.get("through") != [["w", "e"], ["s", "n"]] or set(c.ports) != {
        "w",
        "e",
        "s",
        "n",
    }:
        raise ValueError("crossing contract must define paired opposing ports")
    for side in ("west", "east"):
        c = lib.termination(side)
        if set(c.ports) != {"opt"} or c.ports["opt"] != [
            0,
            0,
            0 if side == "west" else 180,
        ]:
            raise ValueError("termination contract requires an oriented optical port")


def point(x, y, angle, at):
    """Exact orthogonal transform without accumulating trigonometric drift."""
    a, b = at[:2]
    if angle % 90 == 0:
        a, b = {0: (a, b), 90: (-b, a), 180: (-a, -b), 270: (b, -a)}[angle % 360]
    else:
        from math import cos, sin, radians

        t = radians(angle)
        a, b = a * cos(t) - b * sin(t), a * sin(t) + b * cos(t)
    return [snap(x + a), snap(y + b)]
