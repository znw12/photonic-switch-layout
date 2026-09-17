"""Illustrative technology rules, in micrometres; not a foundry PDK."""

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Config:
    schema_version: int = 1
    n: int = 100
    grid: float = 0.001
    radius: float = 20.0
    chord_error: float = 0.002
    wg_width: float = 1.0
    wg_clearance: float = 5.0
    lane_pitch: float = 80.0
    mzi_length: float = 1000.0
    mzi_height: float = 100.0
    metal_width: float = 5.0
    metal_spacing: float = 5.0
    via_size: float = 5.0
    via_enclosure: float = 2.0
    optical_metal_clearance: float = 10.0
    pad_size: float = 60.0
    pad_pitch: float = 100.0
    margin: float = 100.0
    crossing_half_length: float = 10.0
    terminal_names: tuple[str, ...] = ("return", "control")
    terminal_offsets: tuple[float, ...] = (20.0, 40.0)
    pad_assignment: str = "nearest"
    insulated_m2_overpasses: bool = True
    max_swap_columns: int = 100000
    max_candidates: int = 2
    pitch_factors: tuple[float, ...] = (1.2, 1.0)
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
        if type(self.n) is not int or self.n < 1:
            raise ValueError("n must be a positive integer")
        if self.schema_version != 1:
            raise ValueError("unsupported schema_version")
        for key in (
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
        ):
            value = getattr(self, key)
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{key} must be finite and positive")
        if self.radius < 20:
            raise ValueError("radius must be at least 20 um")
        if self.grid != 0.001:
            raise ValueError("this GDS profile requires grid=0.001 um")
        if self.chord_error < self.grid or self.chord_error > self.wg_width / 10:
            raise ValueError("chord_error must lie between grid and wg_width/10")
        if self.lane_pitch < max(2 * self.radius, self.wg_width + self.wg_clearance):
            raise ValueError("lane_pitch cannot fit the bends or waveguide clearance")
        if not self.lane_pitch < self.mzi_height < 2 * self.lane_pitch:
            raise ValueError("mzi_height must be between one and two lane pitches")
        if self.mzi_length < 8 * self.radius:
            raise ValueError(
                "mzi_length cannot fit placeholder couplers and electrodes"
            )
        if self.pad_pitch < self.pad_size + self.metal_spacing:
            raise ValueError("pad_pitch violates pad spacing")
        if self.pad_pitch < self.via_size + 2 * self.via_enclosure + self.metal_spacing:
            raise ValueError("pad_pitch violates via spacing")
        if self.pad_size < self.metal_width:
            raise ValueError("pad_size must enclose metal_width")
        if self.margin < self.pad_size / 2 + self.optical_metal_clearance:
            raise ValueError("margin too small for pad and optical clearance")
        if (
            len(self.terminal_names) != len(self.terminal_offsets)
            or not self.terminal_names
        ):
            raise ValueError(
                "terminal names/offsets must have matching nonzero lengths"
            )
        if len(set(self.terminal_names)) != len(self.terminal_names):
            raise ValueError(
                "terminal names must be unique; net sharing must be explicit"
            )
        clearance = (
            self.via_size / 2
            + self.via_enclosure
            + self.optical_metal_clearance
            + self.wg_width / 2
        )
        if any(
            not clearance <= y <= self.lane_pitch - clearance
            for y in self.terminal_offsets
        ):
            raise ValueError("electrical terminals violate optical/via clearance")
        offsets = sorted(self.terminal_offsets)
        if any(
            b - a < self.via_size + 2 * self.via_enclosure + self.metal_spacing
            for a, b in zip(offsets, offsets[1:])
        ):
            raise ValueError("electrical terminal spacing is insufficient")
        if self.pad_assignment not in ("nearest", "split"):
            raise ValueError("pad_assignment must be nearest or split")
        if self.pad_assignment == "split" and len(offsets) != 2:
            raise ValueError("split assignment requires exactly two terminals")
        if type(self.insulated_m2_overpasses) is not bool:
            raise ValueError("insulated_m2_overpasses must be boolean")
        for key in ("max_swap_columns", "max_candidates"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError(f"{key} must be a positive integer")
        if not self.pitch_factors or any(
            not math.isfinite(f) or f < 1 for f in self.pitch_factors
        ):
            raise ValueError("pitch_factors must be finite and >=1")
        needed = {"WG", "M1", "M2", "VIA", "OUTLINE", "LABEL", "DEVICE", "WINDOW"}
        if set(self.layers) != needed:
            raise ValueError(f"layers must define {sorted(needed)}")
        pairs = []
        for key, pair in self.layers.items():
            if len(pair) != 2 or any(
                type(x) is not int or not 0 <= x < 65536 for x in pair
            ):
                raise ValueError(f"invalid GDS layer/datatype for {key}")
            pairs.append(tuple(pair))
        if len(set(pairs)) != len(pairs):
            raise ValueError(
                "layer/datatype assignments must be distinct, including M1/M2/VIA"
            )

    def to_dict(self):
        return asdict(self)

    @property
    def digest(self):
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True).encode()
        ).hexdigest()

    @classmethod
    def load(cls, path: str | Path | None = None, **overrides):
        data = json.loads(Path(path).read_text()) if path else {}
        data.update({k: v for k, v in overrides.items() if v is not None})
        for key in ("terminal_names", "terminal_offsets", "pitch_factors"):
            if key in data:
                data[key] = tuple(data[key])
        return cls(**data)
