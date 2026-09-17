"""Compare measured, successfully verified bundles; never estimate routed extents."""

import csv
import json
from pathlib import Path
from .cli import save


def compare_bundles(directories, out, baseline=None):
    records = []
    for directory in directories:
        path = Path(directory)
        report = json.loads((path / "report.json").read_text())
        if not report.get("success"):
            records.append(
                dict(
                    bundle=str(path), status="rejected", candidates=report["candidates"]
                )
            )
            continue
        checks = report["checks"]
        if not all(
            checks.get(k)
            for k in (
                "manifest_geometry_passed",
                "gds_readback_passed",
                "electrical_extraction_passed",
            )
        ):
            raise ValueError(f"{path}: missing verification evidence")
        cfg = json.loads((path / "config.json").read_text())
        summary = report["summary"]
        uniformity = report["uniformity"]["metrics"]
        records.append(
            dict(
                bundle=str(path),
                status="verified",
                pad_rows=cfg["pad_rows"],
                pad_distribution=cfg.get("pad_distribution", "central"),
                lane_pitch_um=cfg["lane_pitch"],
                interstage_routing=cfg.get("interstage_routing", "legacy"),
                shuffle_pitch_um=cfg.get("shuffle_pitch"),
                objective=next(c["objective"] for c in report["candidates"] if c["id"]==summary["selected_candidate"]),
                pad_row_stagger_um=cfg.get("pad_row_stagger", 0),
                pad_bank_width_mm=report["metrics"]
                .get("pad_banks", {})
                .get("north", {})
                .get(
                    "width_um",
                    report["metrics"]["extents_um"]["pads"][2]
                    - report["metrics"]["extents_um"]["pads"][0],
                )
                / 1000,
                fanout_bbox_um=report["metrics"]["extents_um"]["fanout"],
                fold_bands=cfg["fold_bands"],
                active_ports=summary["active_ports"],
                internal_ports=summary["internal_ports"],
                width_mm=summary["width_mm"],
                height_mm=summary["height_mm"],
                area_mm2=summary["area_mm2"],
                maximum_dimension_mm=max(summary["width_mm"], summary["height_mm"]),
                pad_width_lower_bound_mm=report["metrics"][
                    "pad_bank_width_lower_bound_um"
                ]
                / 1000,
                width_target_met=report["metrics"]["width_target_met"],
                crossings=report["metrics"]["crossings"],
                length_min_mm=uniformity["length"]["min"] / 1000,
                length_max_mm=uniformity["length"]["max"] / 1000,
                bend_min=uniformity["bends"]["min"],
                bend_max=uniformity["bends"]["max"],
                crossing_min=uniformity["crossings"]["min"],
                crossing_max=uniformity["crossings"]["max"],
                normalized_hash=report["normalized_hash"],
            )
        )
    valid = [r for r in records if r["status"] == "verified"]
    if not valid:
        raise ValueError("no verified comparison candidates")
    for r in valid:
        r["pareto_width_area"] = not any(
            all(v[k] <= r[k] for k in ("width_mm", "area_mm2"))
            and any(v[k] < r[k] for k in ("width_mm", "area_mm2"))
            for v in valid
        )
    result = dict(
        scope="Measured generation reports; rerun benes-layout verify on a bundle for fresh physical readback.",
        target_width_mm=20,
        global_optimum_proven=False,
        results=records,
        smallest_area=min(valid, key=lambda r: tuple(r["objective"])+ (r["bundle"],))["bundle"],
        smallest_width=min(valid, key=lambda r: r["width_mm"])["bundle"],
        smallest_maximum_dimension=min(valid, key=lambda r: r["maximum_dimension_mm"])[
            "bundle"
        ],
    )
    if baseline:
        result["legacy_baseline"] = json.loads(Path(baseline).read_text())["summary"]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    save(out / "comparison.json", result)
    with (out / "comparison.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(valid[0]))
        writer.writeheader()
        writer.writerows(valid)
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6), layout="constrained")
    label_counts = {}
    for r in valid:
        location = (r["width_mm"], r["height_mm"])
        label_index = label_counts.get(location, 0)
        label_counts[location] = label_index + 1
        ax.scatter(r["width_mm"], r["height_mm"], s=70)
        ax.annotate(
            f"{r['interstage_routing']} / q={r['shuffle_pitch_um']}\n"
            f"{r['pad_rows']} rows / {r['fold_bands']} bands / {r['pad_row_stagger_um']:g} um stagger",
            (r["width_mm"], r["height_mm"]),
            xytext=(5, 5 + 14 * label_index),
            textcoords="offset points",
            fontsize=8,
        )
    if baseline:
        b = result["legacy_baseline"]
        ax.scatter(
            b["width_mm"],
            b["height_mm"],
            marker="x",
            color="black",
            s=70,
            label="Legacy single row",
        )
        ax.legend()
    ax.axvline(20, color="gray", linestyle="--", label="Soft width target")
    ax.set(
        xlabel="Full die width (mm)",
        ylabel="Full die height (mm)",
        title="Verified physical floorplans",
        xlim=(
            0,
            max(
                25,
                max(r["width_mm"] for r in valid) * 1.25,
                result.get("legacy_baseline", {}).get("width_mm", 0) * 1.1,
            ),
        ),
        ylim=(0, max(r["height_mm"] for r in valid) * 1.2),
    )
    ax.grid(alpha=0.2)
    fig.savefig(out / "comparison.png", dpi=160)
    plt.close(fig)
    return result
