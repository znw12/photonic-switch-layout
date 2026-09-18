"""AS optical blocks and electrical variants; no padded optical lanes."""

from copy import deepcopy
from .geometry import snap, rectangle
from .interstage import continuous, reverse_block, finish, segment, attach


def shuffle(lib, size, inverse=False):
    """Odd split is an even split of n-1 lanes plus the unpaired last lane.

    Reverse only the even block: rotating the whole odd block would reverse
    its bypass position and implement a different permutation.
    """
    name = f'AS_{"MERGE" if inverse else "SPLIT"}_{size}'
    if name in lib.cells:
        return lib.cells[name]
    pitch = lib.cfg.lane_pitch
    even = size - size % 2
    base = continuous(lib, even, pitch)
    if inverse:
        base = reverse_block(lib, base, pitch)
    width = base.metadata["width"]
    c = lib.cell(name, "shuffle")
    lib.ref(c, base)
    paths = [deepcopy(t["pieces"]) for t in base.tracks]
    perm = list(base.metadata["permutation"])
    if size % 2:
        path = []
        attach(
            lib,
            c,
            path,
            segment(lib, [0, (size - 1) * pitch], [width, (size - 1) * pitch]),
        )
        paths.append(path)
        perm.append(size - 1)
    return finish(
        lib,
        c,
        paths,
        perm,
        pitch,
        width,
        mode="as-continuous",
        inverse=inverse,
        actual_pitch=pitch,
        extra_bypass_bends=0,
        fanin_width=0,
        fanout_width=0,
    )


def variants(lib):
    """Share the optical body; shared ground rails belong to the column."""
    from .gsg_verify import verify_device

    base = lib.mzi()
    # The fully assembled source device is checked before separating ownership.
    verify_device(lib.export(), lib.cfg)
    cfg = lib.cfg
    optical = lib.cell("AS_MZI_OPTICAL", "device_optical")
    optical.refs = deepcopy([r for r in base.refs if r["cell"] != "VIA"])
    optical.polygons = deepcopy([p for p in base.polygons if p["layer"] == "DEVICE"])
    optical.ports = {
        k: deepcopy(v) for k, v in base.ports.items() if k.startswith(("i", "o"))
    }
    optical.metadata = {"optical_paths": deepcopy(base.metadata["optical_paths"])}
    out = {}
    for side in ("R", "L"):
        c = lib.cell("AS_MZI_" + side, "mzi")
        lib.ref(c, optical)
        a, b = base.metadata["active_x"]
        mid = cfg.lane_pitch / 2
        sx = b - 20 if side == "R" else a + 20
        gx = b - 60 if side == "R" else a + 60
        ex = cfg.mzi_length if side == "R" else 0
        lib.poly(
            c,
            "M1",
            rectangle(
                a, mid - cfg.gsg_signal_width / 2, b, mid + cfg.gsg_signal_width / 2
            ),
        )
        half = cfg.metal_width / 2
        lib.poly(c, "M2", rectangle(min(sx, ex), mid - half, max(sx, ex), mid + half))
        lib.ref(c, lib.via(), sx, mid)
        c.ports = {
            **deepcopy(optical.ports),
            "G": [gx, mid, 90],
            "S": [ex, mid, 0 if side == "R" else 180],
        }
        c.tracks = deepcopy(base.tracks)
        c.metadata = {
            **deepcopy(base.metadata),
            "exit_side": side,
            "internal_vias": [[sx, mid]],
            "ground_owner": "column",
            "electrical_probes": {
                "G": [[gx, base.metadata["electrode_centers"][j]] for j in (0, 2)],
                "S": [[sx, mid]],
            },
        }
        out[side] = c
    return out


def ground_runs(rows):
    result = []
    for row in sorted(rows):
        if not result or row != result[-1][-1] + 2:
            result.append([])
        result[-1].append(row)
    return result


def ground_column(lib, side, rows):
    cfg = lib.cfg
    p = cfg.lane_pitch
    name = f"AS_G_{side}_" + "_".join(map(str, rows))
    if name in lib.cells:
        return lib.cells[name]
    c = lib.cell(name, "ground_column")
    gx = 780 if side == "R" else 220
    halfs = cfg.gsg_signal_width / 2
    rails = []
    for run in ground_runs(rows):
        centers = [(r + 0.5) * p for r in run]
        bounds = [
            (
                centers[0] - halfs - cfg.gsg_gap - cfg.gsg_ground_width,
                centers[0] - halfs - cfg.gsg_gap,
            )
        ]
        bounds += [
            (a + halfs + cfg.gsg_gap, b - halfs - cfg.gsg_gap)
            for a, b in zip(centers, centers[1:])
        ]
        bounds.append(
            (
                centers[-1] + halfs + cfg.gsg_gap,
                centers[-1] + halfs + cfg.gsg_gap + cfg.gsg_ground_width,
            )
        )
        for low, high in bounds:
            y = snap((low + high) / 2)
            lib.poly(c, "M1", rectangle(160, low, 840, high))
            lib.ref(c, lib.via(), gx, y)
            rails.append(
                dict(bounds=[160, low, 840, high], contact=[gx, y], run=list(run))
            )
    c.metadata = dict(rails=rails, runs=ground_runs(rows), exit_side=side)
    return c
