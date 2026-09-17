"""Independent Beneš configuration; lengths are in micrometres."""

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Config:
    active_ports: int = 100
    internal_ports: int | None = None
    input_map: tuple[int, ...] | None = None
    output_map: tuple[int, ...] | None = None
    grid: float = 0.001
    radius: float = 20.0
    chord_error: float = 0.002
    wg_width: float = 1.0
    wg_clearance: float = 5.0
    lane_pitch: float = 80.0
    mzi_length: float = 1000.0
    mzi_height: float = 100.0
    terminal_names: tuple[str, str] = ("return", "control")
    terminal_offsets: tuple[float, float] = (20.0, 40.0)
    metal_width: float = 5.0
    metal_spacing: float = 5.0
    via_size: float = 5.0
    via_enclosure: float = 2.0
    optical_metal_clearance: float = 10.0
    pad_size: float = 60.0
    pad_pitch: float = 100.0
    margin: float = 100.0
    crossing_half_length: float = 10.0
    termination_length: float = 40.0
    insulated_m2_overpasses: bool = True
    equalize: bool = False
    max_candidates: int = 3
    gap_factors: tuple[float, ...] = (1.2, 1.0)
    row_orders: tuple[str, ...] = ("normal", "reverse")
    pad_factors: tuple[float, ...] = (1.0,)
    corridor_factors: tuple[float, ...] = (1.0, 1.2)
    seed: int = 17
    layers: dict = field(
        default_factory=lambda: {
            "WG": (1, 0),
            "M1": (10, 0),
            "M2": (11, 0),
            "VIA": (12, 0),
            "OUTLINE": (90, 0),
            "LABEL": (91, 0),
            "DEVICE": (92, 0),
            "WINDOW": (93, 0),
        }
    )

    def __post_init__(self):
        if type(self.active_ports) is not int or self.active_ports < 1:
            raise ValueError("active_ports must be a positive integer")
        p = self.internal_ports
        if p is None:
            p = 1 << max(1, (self.active_ports - 1).bit_length())
        if type(p) is not int or p < max(2, self.active_ports) or p & (p - 1):
            raise ValueError(
                "internal_ports must be a power of two >= max(2, active_ports)"
            )
        object.__setattr__(self, "internal_ports", p)
        for name in ("input_map", "output_map"):
            v = getattr(self, name)
            v = tuple(range(self.active_ports)) if v is None else tuple(v)
            if (
                len(v) != self.active_ports
                or len(set(v)) != len(v)
                or any(type(i) is not int or not 0 <= i < p for i in v)
            ):
                raise ValueError(
                    f"{name} must contain distinct valid internal port indices"
                )
            object.__setattr__(self, name, v)
        positive = (
            "grid",
            "radius",
            "chord_error",
            "wg_width",
            "wg_clearance",
            "lane_pitch",
            "mzi_length",
            "mzi_height",
            "metal_width",
            "metal_spacing",
            "via_size",
            "via_enclosure",
            "optical_metal_clearance",
            "pad_size",
            "pad_pitch",
            "margin",
            "crossing_half_length",
            "termination_length",
        )
        for name in positive:
            v = getattr(self, name)
            if type(v) not in (float, int) or not math.isfinite(v) or v <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.grid != 0.001:
            raise ValueError("export profile requires grid=0.001 um")
        if self.radius < 20 or self.radius <= self.wg_width / 2:
            raise ValueError("radius must be >=20 um and exceed waveguide half width")
        if not self.grid <= self.chord_error <= self.wg_width / 10:
            raise ValueError("chord_error must be between grid and wg_width/10")
        if self.lane_pitch < max(2 * self.radius, self.wg_width + self.wg_clearance):
            raise ValueError("lane_pitch cannot fit bends/clearance")
        if not self.lane_pitch < self.mzi_height < 2 * self.lane_pitch:
            raise ValueError("mzi_height must lie between one and two lane pitches")
        if self.mzi_length < 8 * self.radius:
            raise ValueError("mzi_length cannot fit the placeholder")
        if self.pad_pitch < self.pad_size + self.metal_spacing or self.pad_size < max(
            self.metal_width, self.via_size + 2 * self.via_enclosure
        ):
            raise ValueError("pad geometry violates metal spacing/enclosure")
        if self.margin < self.pad_size / 2 + self.optical_metal_clearance:
            raise ValueError("margin cannot fit pad/optical clearance")
        object.__setattr__(self, "terminal_names", tuple(self.terminal_names))
        object.__setattr__(self, "terminal_offsets", tuple(self.terminal_offsets))
        if (
            len(self.terminal_names) != 2
            or len(set(self.terminal_names)) != 2
            or any(
                not isinstance(v, str) or not v or v in {"i0", "i1", "o0", "o1"}
                for v in self.terminal_names
            )
        ):
            raise ValueError("two distinct electrical terminal names are required")
        c = (
            self.via_size / 2
            + self.via_enclosure
            + self.optical_metal_clearance
            + self.wg_width / 2
        )
        if len(self.terminal_offsets) != 2 or any(
            not math.isfinite(y) or not c <= y <= self.lane_pitch - c
            for y in self.terminal_offsets
        ):
            raise ValueError("terminal_offsets violate optical/via clearance")
        if (
            abs(self.terminal_offsets[1] - self.terminal_offsets[0])
            < self.via_size + 2 * self.via_enclosure + self.metal_spacing
        ):
            raise ValueError("terminal offsets violate metal spacing")
        if type(self.max_candidates) is not int or self.max_candidates < 1:
            raise ValueError("max_candidates must be positive")
        for name in ("gap_factors", "pad_factors", "corridor_factors"):
            values = tuple(getattr(self, name))
            if not values or any(not math.isfinite(v) or v < 1 for v in values):
                raise ValueError(f"{name} must contain finite factors >=1")
            object.__setattr__(self, name, values)
        if not self.row_orders or any(
            v not in ("normal", "reverse") for v in self.row_orders
        ):
            raise ValueError("row_orders must be normal or reverse")
        object.__setattr__(self, "row_orders", tuple(self.row_orders))
        if type(self.seed) is not int or any(
            type(v) is not bool for v in (self.equalize, self.insulated_m2_overpasses)
        ):
            raise ValueError("invalid seed or boolean option")
        if set(self.layers) != {
            "WG",
            "M1",
            "M2",
            "VIA",
            "OUTLINE",
            "LABEL",
            "DEVICE",
            "WINDOW",
        }:
            raise ValueError("incomplete layer assignments")
        pairs = list(self.layers.values())
        if any(
            len(v) != 2 or any(type(i) is not int or not 0 <= i < 65536 for i in v)
            for v in pairs
        ) or len(set(map(tuple, pairs))) != len(pairs):
            raise ValueError("layer/datatype pairs must be valid and distinct")

    def to_dict(self):
        return asdict(self)

    @property
    def digest(self):
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True).encode()
        ).hexdigest()

    @classmethod
    def load(cls, path=None, **overrides):
        data = json.loads(Path(path).read_text()) if path else {}
        data.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**data)
