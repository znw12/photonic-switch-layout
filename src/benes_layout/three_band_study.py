"""Measured comparison of four complete 100/128 continuous three-band layouts."""
from dataclasses import replace
import json
from pathlib import Path

from .cli import save
from .config import Config
from .workflow import generate, verify_bundle
from .comparison import compare_bundles

PARTITIONS = ((4, 5, 4), (6, 5, 2), (5, 5, 3), (5, 4, 4))


def run_three_band(cfg, out):
    if cfg.active_ports != 100 or cfg.internal_ports != 128:
        raise ValueError("this reference study requires 100 active / 128 internal ports")
    out = Path(out)
    bundles = []
    for counts in PARTITIONS:
        profile = replace(
            cfg, interstage_routing="continuous", shuffle_pitch=None,
            fold_bands=3, band_stage_counts=counts,
            pad_rows=4, pad_distribution="central", pad_row_stagger=25,
            pad_factors=(1.0, 1.4), max_candidates=2,
            gap_factors=(1.0,), corridor_factors=(1.0,), row_orders=("normal",),
        )
        target = out / "-".join(map(str, counts))
        bundles.append(target)
        try:
            generate(profile, target, list(enumerate(range(100))))
        except ValueError:
            if not (target / "report.json").exists():
                raise
    result = compare_bundles(bundles, out / "comparison")
    chosen = Path(result["smallest_area"])
    original = json.loads((chosen / "report.json").read_text())
    repeat = out / "repeat-best"
    repeated = generate(
        Config.load(chosen / "config.json"), repeat, list(enumerate(range(100))),
    )
    for field in ("normalized_hash", "summary", "uniformity", "realized"):
        if repeated[field] != original[field]:
            raise ValueError(f"three-band repeat differs: {field}")
    for filename in ("settings.json", "ports.csv", "pads.csv"):
        if (chosen / filename).read_bytes() != (repeat / filename).read_bytes():
            raise ValueError(f"three-band repeat differs: {filename}")
    result["repeat"] = dict(
        bundle=str(repeat), matches=str(chosen), passed=True,
        normalized_hash=repeated["normalized_hash"],
        independent_readback=verify_bundle(repeat),
    )
    result["all_partitions_verified"] = all(r["status"] == "verified" for r in result["results"])
    save(out / "study.json", result)
    return result
