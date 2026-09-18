"""Independent Beneš configuration; lengths are in micrometres."""

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Config:
    topology: str = "benes"
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
    interstage_routing: str = "legacy"
    shuffle_pitch: float | None = None
    mzi_length: float = 1000.0
    mzi_height: float = 100.0
    mzi_model: str = 'placeholder'
    mzi_wg_width: float = 0.8
    coupler_gap: float = 0.3
    coupler_length: float = 30.0
    gsg_signal_width: float = 20.0
    gsg_gap: float = 5.0
    gsg_ground_width: float = 10.0
    ground_pads_per_side: int = 0
    terminal_names: tuple[str, str] = ("return", "control")
    terminal_offsets: tuple[float, float] = (20.0, 40.0)
    metal_width: float = 5.0
    metal_spacing: float = 5.0
    via_size: float = 5.0
    via_enclosure: float = 2.0
    optical_metal_clearance: float = 10.0
    pad_size: float = 60.0
    pad_pitch: float = 100.0
    pad_rows: int = 1
    pad_distribution: str = "central"
    pad_row_stagger: float = 0.0
    pad_row_pitch: float = 100.0
    fold_bands: int = 1
    band_stage_counts: tuple[int, ...] | None = None
    fold_gap: float = 200.0
    bundle_pitch: float = 6.01
    margin: float = 100.0
    crossing_half_length: float = 10.0
    crossing_model: str = 'placeholder'
    crossing_center_width: float = 3.0
    crossing_max_width: float = 4.0
    crossing_port_straight: float = 0.5
    termination_length: float = 40.0
    insulated_m2_overpasses: bool = True
    electrical_routing: str = "legacy"
    electrical_fanout: str = "channel"
    share_interstage: bool = False
    electrical_stage_bias: float = 0.0
    electrical_width_extra: float = 0.0
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
        if self.topology not in ('benes', 'as-benes'):
            raise ValueError('unknown topology')
        exact = self.topology == 'as-benes'
        if p is None:
            p = self.active_ports if exact else 1 << max(1, (self.active_ports - 1).bit_length())
        if exact and (type(p) is not int or p != self.active_ports):
            raise ValueError('as-benes requires equal positive active/internal ports')
        if not exact and (type(p) is not int or p < max(2, self.active_ports) or p & (p - 1)):
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
            "mzi_wg_width", "coupler_gap", "coupler_length",
            "gsg_signal_width", "gsg_gap", "gsg_ground_width",
            "metal_width",
            "metal_spacing",
            "via_size",
            "via_enclosure",
            "optical_metal_clearance",
            "pad_size",
            "pad_pitch",
            "pad_row_pitch",
            "fold_gap",
            "bundle_pitch",
            "margin",
            "crossing_half_length",
            "crossing_center_width", "crossing_max_width", "crossing_port_straight",
            "termination_length",
        )
        for name in positive:
            v = getattr(self, name)
            if type(v) not in (float, int) or not math.isfinite(v) or v <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.grid != 0.001:
            raise ValueError("export profile requires grid=0.001 um")
        if self.crossing_model not in ('placeholder','cosine'):
            raise ValueError('unknown crossing_model')
        if self.crossing_model=='cosine' and not (
            self.wg_width < self.crossing_center_width < self.crossing_max_width
            and self.crossing_max_width < self.crossing_half_length
            and self.crossing_port_straight >= 5*self.grid
            and self.crossing_half_length-self.crossing_port_straight-self.crossing_center_width/2 > self.wg_width):
            raise ValueError('cosine crossing dimensions cannot fit the fixed footprint')
        if self.radius < 20 or self.radius <= self.wg_width / 2:
            raise ValueError("radius must be >=20 um and exceed waveguide half width")
        if not self.grid <= self.chord_error <= self.wg_width / 10:
            raise ValueError("chord_error must be between grid and wg_width/10")
        if type(self.ground_pads_per_side) is not int or self.ground_pads_per_side < 0:
            raise ValueError('ground_pads_per_side must be a nonnegative integer')
        compact = self.ground_pads_per_side > 0 or exact
        if compact and not exact and not (self.mzi_model == 'paper-gsg' and self.electrical_fanout == 'aligned'
                            and self.share_interstage and p >= 4
                            and self.ground_pads_per_side <= 2*(p.bit_length()-1)-1):
            raise ValueError('local ground pads require aligned shared-interstage GSG routing and at most one tap per stage per side')
        if self.lane_pitch < max(0 if compact else 2 * self.radius, self.wg_width + self.wg_clearance):
            raise ValueError("lane_pitch cannot fit bends/clearance")
        if not (self.lane_pitch < self.mzi_height <= 2 * self.lane_pitch if compact
                else self.lane_pitch < self.mzi_height < 2 * self.lane_pitch):
            raise ValueError("mzi_height must lie between one and two lane pitches")
        if self.mzi_length < 8 * self.radius:
            raise ValueError("mzi_length cannot fit the placeholder")
        if self.mzi_model not in ('placeholder', 'paper-gsg'):
            raise ValueError('unknown mzi_model')
        if self.mzi_model == 'paper-gsg':
            dimensions = ((self.lane_pitch == 25 and self.mzi_height == 50
                           and tuple(self.terminal_offsets) == (12.5,12.5) and self.metal_width <= 4)
                          if compact else (self.lane_pitch == 60 and self.mzi_height == 100
                                           and tuple(self.terminal_offsets) == (20,40)))
            if exact:
                dimensions = (self.lane_pitch in (34,35) and self.mzi_height == 2*self.lane_pitch
                              and tuple(self.terminal_offsets) == (self.lane_pitch/2,)*2
                              and self.metal_width <= 4)
            if not (self.mzi_length == 1000 and dimensions
                    and tuple(self.terminal_names) == ('G','S')
                    and self.electrical_routing == ('two-row' if exact else 'three-row') and self.fold_bands == 1):
                raise ValueError('paper-gsg requires a supported interface (standard 60/25 um or AS 34/35 um), 1000 um length and matching single-band pad routing')
            landing = self.via_size + 2*self.via_enclosure
            if not (self.gsg_gap >= self.metal_spacing and self.gsg_gap > self.mzi_wg_width
                    and self.gsg_signal_width >= landing and self.gsg_ground_width >= landing
                    and self.gsg_signal_width + 2*(self.gsg_gap+self.gsg_ground_width) <= (self.mzi_height if compact else self.lane_pitch)
                    and self.coupler_gap+self.mzi_wg_width < self.gsg_signal_width+self.gsg_gap):
                raise ValueError('GSG electrode or coupler dimensions cannot fit')
        if self.pad_pitch < self.pad_size + self.metal_spacing or self.pad_size < max(
            self.metal_width, self.via_size + 2 * self.via_enclosure
        ):
            raise ValueError("pad geometry violates metal spacing/enclosure")
        if type(self.pad_rows) is not int or self.pad_rows not in (1, 2, 3, 4):
            raise ValueError("pad_rows must be 1, 2, 3 or 4")
        if self.pad_distribution not in ("central", "stage"):
            raise ValueError("pad_distribution must be central or stage")
        if self.electrical_routing not in ("legacy", "two-row", "three-row"):
            raise ValueError("invalid electrical_routing")
        two_row = self.layered_electrical
        if self.electrical_fanout not in ('channel', 'aligned'):
            raise ValueError('invalid electrical_fanout')
        if self.electrical_fanout == 'aligned' and self.electrical_routing != 'three-row' and not exact:
            raise ValueError('aligned fanout requires three-row electrical routing')
        if type(self.share_interstage) is not bool or (self.share_interstage and not two_row):
            raise ValueError("share_interstage requires layered electrical routing")
        bias = self.electrical_stage_bias
        if (type(bias) not in (int, float) or not math.isfinite(bias)
            or abs(bias/self.grid-round(bias/self.grid)) > 1e-7
            or (bias != 0 and not two_row)):
            raise ValueError("electrical_stage_bias must be finite, on grid and used with layered routing")
        extra = self.electrical_width_extra
        if (type(extra) not in (int,float) or not math.isfinite(extra) or extra < 0
            or abs(extra/self.grid-round(extra/self.grid)) > 1e-7
            or (extra != 0 and not two_row)):
            raise ValueError("electrical_width_extra must be finite, nonnegative, on grid and used with layered routing")
        if two_row and not (
            self.pad_rows == (2 if self.electrical_routing == 'two-row' else 3) and self.fold_bands == 1
            and self.pad_distribution == "central" and self.interstage_routing == "continuous"
            and self.insulated_m2_overpasses and not self.equalize
            and (self.pad_pitch >= 100 if self.electrical_fanout == 'aligned' else self.pad_pitch == 100)
            and tuple(self.pad_factors) == (1.0,)
        ):
            raise ValueError("layered electrical routing requires matching pad rows, continuous single band, central pads, insulated M2 and 100 um pad pitch (minimum for aligned fanout)")
        if self.pad_distribution == "stage" and (
            self.pad_rows != 4 or self.fold_bands != 1
        ):
            raise ValueError("stage pad distribution requires four rows and one band")
        if self.interstage_routing not in ("legacy", "continuous", "compressed"):
            raise ValueError("invalid interstage_routing")
        folded_continuous = (
            self.interstage_routing == "continuous"
            and self.fold_bands == 3
            and self.pad_rows == 4
            and self.pad_distribution == "central"
        )
        if self.interstage_routing != "legacy" and not folded_continuous and not two_row and (
            self.pad_distribution != "stage" or self.pad_rows != 4 or self.fold_bands != 1
        ):
            raise ValueError(
                "new interstage routing requires single-band stage pads or "
                "three-band continuous routing with central four-row pads"
            )
        if self.interstage_routing == "compressed":
            q = self.shuffle_pitch
            if (type(q) not in (int, float) or not math.isfinite(q)
                or not self.wg_width + self.wg_clearance < q <= self.lane_pitch
                or abs(q / self.grid - round(q / self.grid)) > 1e-7):
                raise ValueError("shuffle_pitch must be finite, on grid and within clearance/lane pitch")
        elif self.shuffle_pitch is not None:
            raise ValueError("shuffle_pitch only applies to compressed routing")
        if (
            type(self.pad_row_stagger) not in (int, float)
            or not math.isfinite(self.pad_row_stagger)
            or self.pad_row_stagger < 0
        ):
            raise ValueError("pad_row_stagger must be finite and nonnegative")
        if (
            abs(
                self.pad_row_stagger / self.grid
                - round(self.pad_row_stagger / self.grid)
            )
            > 1e-7
        ):
            raise ValueError("pad_row_stagger must lie on the database grid")
        if self.pad_rows == 4 and self.fold_bands != 1 and not folded_continuous:
            raise ValueError("four pad rows require a single band or three-band continuous routing")
        if self.pad_row_stagger and not two_row and (
            self.pad_rows != 4 or (self.fold_bands != 1 and not folded_continuous)
        ):
            raise ValueError("pad row staggering requires four rows and a supported band profile")
        if (self.pad_rows - 1) * self.pad_row_stagger >= self.pad_pitch:
            raise ValueError("pad row stagger spans a full column pitch")
        depth = max(1, 2*(p-1).bit_length()-1) if exact else 2 * (p.bit_length() - 1) - 1
        if (
            type(self.fold_bands) is not int
            or not 1 <= self.fold_bands <= depth
            or self.fold_bands % 2 != 1
        ):
            raise ValueError("fold_bands must be odd and no greater than stage depth")
        if self.band_stage_counts is not None:
            counts = self.band_stage_counts
            if (
                not isinstance(counts, (tuple, list))
                or len(counts) != self.fold_bands
                or any(type(v) is not int or v < 1 for v in counts)
                or sum(counts) != depth
            ):
                raise ValueError(
                    "band_stage_counts must be positive integers, one per band, "
                    "summing to stage depth"
                )
            object.__setattr__(self, "band_stage_counts", tuple(counts))
        if self.fold_bands > 1 and self.pad_rows == 1:
            raise ValueError("folded layouts require multiple pad rows")
        if self.pad_row_pitch < self.pad_size + self.metal_spacing:
            raise ValueError("pad row pitch violates spacing")
        if self.fold_bands > 1 and (
            self.fold_gap
            < max(
                2 * self.radius,
                self.mzi_height - self.lane_pitch + 2 * self.optical_metal_clearance,
            )
            or not self.wg_width + self.wg_clearance + 2 * self.grid
            <= self.bundle_pitch
            <= self.lane_pitch - 2 * self.radius
        ):
            raise ValueError("fold gap or bundle pitch cannot fit radius/clearance")
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
        if not compact and (len(self.terminal_offsets) != 2 or any(
            not math.isfinite(y) or not c <= y <= self.lane_pitch - c
            for y in self.terminal_offsets
        )):
            raise ValueError("terminal_offsets violate optical/via clearance")
        if (
            not compact and
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
        data = asdict(self)
        if self.topology == 'benes':
            data.pop('topology')
        # Preserve serialized legacy profiles and their reproducibility hashes.
        if not self.ground_pads_per_side:
            data.pop('ground_pads_per_side')
        return data

    @property
    def layered_electrical(self):
        return self.electrical_routing in ('two-row', 'three-row')

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
