"""Reproducible candidate selection, artifact bundles and benchmarks."""

from itertools import product
import csv
from math import ceil
import importlib.metadata
import json
from pathlib import Path
import random
import resource
import shutil
import sys
import time
import tracemalloc

from .config import Config
from .network import Network
from .cli import save


def candidates(cfg):
    choices = [
        (
            max(cfg.gap_factors),
            cfg.row_orders[0],
            max(cfg.pad_factors),
            max(cfg.corridor_factors),
        )
    ]
    for gap, pad, corridor, row in product(
        sorted(cfg.gap_factors),
        sorted(cfg.pad_factors),
        sorted(cfg.corridor_factors),
        cfg.row_orders,
    ):
        if (gap, row, pad, corridor) not in choices:
            choices.append((gap, row, pad, corridor))
    return [
        dict(
            id=f"candidate-{i:03d}",
            gap=v[0],
            row_order=v[1],
            pad=v[2],
            corridor=v[3],
            baseline=i == 0,
        )
        for i, v in enumerate(choices[: cfg.max_candidates])
    ]


def generate(cfg, out, requests):
    from .layout import build_layout
    from .verify import verify_manifest, verify_gds, normalized_hash
    from .metrics import uniformity, realized, objective
    from .equalize import apply_equalization
    from .preview import render

    net = Network(cfg)
    settings = net.solve(requests)
    net.verify(settings)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in (
        "report.json",
        "layout.gds",
        "preview.png",
        "detail.png",
        "manifest.json",
        "settings.json",
        "cell_names.json",
        "pads.csv",
        "ports.csv",
        "config.json",
        "network.json",
    ):
        (out / name).unlink(missing_ok=True)
    started = time.perf_counter()
    best = None
    records = []
    for choice in candidates(cfg):
        start = time.perf_counter()
        scratch = out / ("." + choice["id"])
        scratch.mkdir(exist_ok=True)
        try:
            lib, m = build_layout(cfg, choice)
            matching = (
                apply_equalization(lib, m, settings)
                if cfg.equalize
                else {"enabled": False}
            )
            built = time.perf_counter()
            checks = verify_manifest(m)
            checked = time.perf_counter()
            names = lib.write_gds(m["top"], scratch / "layout.gds")
            written = time.perf_counter()
            checks.update(verify_gds(scratch / "layout.gds", m, names))
            verified = time.perf_counter()
            metrics = uniformity(m)
            score = objective(m, metrics, choice["id"])
            item = {
                **choice,
                "status": "verified",
                "width_um": m["width"],
                "height_um": m["height"],
                "area_um2": score[0] * cfg.grid**2,
                "objective": list(score),
                "uniformity": metrics,
                "equalization": matching,
                "timings_s": {
                    "build": built - start,
                    "geometry": checked - built,
                    "export": written - checked,
                    "readback": verified - written,
                    "total": time.perf_counter() - start,
                },
            }
            records.append(item)
            print(
                f"{choice['id']}: verified {m['width']/1000:.3f} x {m['height']/1000:.3f} mm",
                flush=True,
            )
            if best is None or score < best[0]:
                best = (score, m, names, checks, item)
                shutil.copyfile(scratch / "layout.gds", out / "layout.gds")
        except (ValueError, RuntimeError) as error:
            records.append({**choice, "status": "rejected", "reason": str(error)})
            print(f"{choice['id']}: rejected: {error}", file=sys.stderr, flush=True)
        finally:
            shutil.rmtree(scratch)
    if best is None or records[0]["status"] != "verified":
        (out / "layout.gds").unlink(missing_ok=True)
        save(
            out / "report.json",
            {"success": False, "candidates": records, "config": cfg.to_dict()},
        )
        raise ValueError(
            "a verified conservative baseline is required; see report.json"
        )
    score, m, names, checks, selected = best
    versions = {
        name: importlib.metadata.version(name)
        for name in ("gdsfactory", "kfactory", "klayout", "shapely")
    }
    report = {
        "success": True,
        "summary": {
            "active_ports": cfg.active_ports,
            "internal_ports": net.p,
            "stages": net.depth,
            "mzis": len(net.switches),
            "pads": len(m["electrical"]),
            "pad_rows_per_side": cfg.pad_rows,
            "fold_bands": cfg.fold_bands,
            "vias": checks["via_count"],
            "width_mm": m["width"] / 1000,
            "height_mm": m["height"] / 1000,
            "area_mm2": score[0] * cfg.grid**2 / 1e6,
            "selected_candidate": selected["id"],
        },
        "checks": checks,
        "candidates": records,
        "search": {
            "bounds": {
                "max_candidates": cfg.max_candidates,
                "gap_factors": cfg.gap_factors,
                "row_orders": cfg.row_orders,
                "pad_factors": cfg.pad_factors,
                "corridor_factors": cfg.corridor_factors,
            },
            "objective_order": [
                "integer_grid_die_area",
                "active_length_spread",
                "active_crossing_spread",
                "active_bend_spread",
                "total_interconnect_length",
                "stable_id",
            ],
            "global_optimum_proven": False,
        },
        "baseline_comparison": {
            "baseline": records[0]["id"],
            "selected": selected["id"],
            "baseline_area_um2": records[0]["area_um2"],
            "selected_area_um2": selected["area_um2"],
            "area_reduction_percent": 100
            * (1 - selected["area_um2"] / records[0]["area_um2"]),
            "improvement_found": score < tuple(records[0]["objective"]),
        },
        "uniformity": selected["uniformity"],
        "realized": realized(m, settings),
        "equalization": selected["equalization"],
        "metrics": {
            "die_bbox_um": m["die_bbox"],
            "extents_um": m["extents"],
            "pad_bank_width_lower_bound_um": (
                ceil(len(net.switches) / cfg.pad_rows) - 1
            )
            * cfg.pad_pitch
            + cfg.pad_size,
            "width_target_um": 20000,
            "width_target_met": m["width"] <= 20000,
            "crossings": m["crossing_count"],
            "gds_bytes": (out / "layout.gds").stat().st_size,
            "unrouted_optical": 0,
            "unrouted_electrical": 0,
        },
        "normalized_hash": normalized_hash(m),
        "versions": versions,
        "python": sys.version,
        "total_time_s": time.perf_counter() - started,
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "memory_method": "Linux ru_maxrss; process lifetime high-water resident memory, includes prior candidates and native libraries",
        "assumptions": [
            "Placeholder TFLN, crossing, termination and stack; no foundry or optical performance signoff.",
            "Constant MZI count does not imply equal optical loss, state response, or group delay.",
            "MZI geometric propagation length is an ideal black-box model; phase/coupler delay is unmodeled.",
            "Insulated M2 over straight waveguides only in declared windows; no vias in these windows.",
            "Single-connection operation requires unrequested inputs to be dark.",
            "Rearrangeable operation may interrupt existing connections; no hitless guarantee.",
            "Two dedicated pads per MZI; returns remain separate.",
            "Multirow pads use insulated M1 stems beneath M2 pads; packaging access is not qualified.",
        ],
    }
    for filename, value in (
        ("config.json", cfg.to_dict()),
        ("manifest.json", m),
        ("network.json", net.export()),
        ("settings.json", settings),
        ("cell_names.json", names),
    ):
        save(out / filename, value)
    with (out / "pads.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["net", "mzi", "terminal", "side", "x_um", "y_um", "via_positions_um"]
        )
        for e in m["electrical"]:
            w.writerow(
                [
                    e["net"],
                    e["instance"],
                    e["terminal"],
                    e["side"],
                    *e["pad"],
                    json.dumps(e["vias"]),
                ]
            )
    with (out / "ports.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["side", "internal_index", "active_index", "kind", "x_um", "y_um"])
        for p in m["interfaces"]:
            w.writerow(
                [
                    p["side"],
                    p["internal"],
                    p["active"],
                    "active" if p["active"] is not None else "spare_termination",
                    *p["position"],
                ]
            )
    render(m, out / "preview.png")
    render(m, out / "detail.png", detail=True)
    report["total_time_s"] = time.perf_counter() - started
    report["process_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    save(out / "report.json", report)
    return report


def verify_bundle(directory):
    from .verify import verify_manifest, verify_gds, normalized_hash, require
    from .metrics import uniformity, realized

    directory = Path(directory)

    def read(name):
        return json.loads((directory / name).read_text())

    m, names, settings, report = map(
        read, ("manifest.json", "cell_names.json", "settings.json", "report.json")
    )
    require(report["success"], "bundle was not successfully generated")
    cfg = Config(**m["config"])
    require(
        Config(**read("config.json")).digest == cfg.digest,
        "resolved config differs from manifest",
    )
    require(
        read("network.json") == Network(cfg).export(),
        "topology export differs from configuration",
    )
    Network(cfg).verify(settings)
    result = verify_manifest(m)
    result.update(verify_gds(directory / "layout.gds", m, names))
    require(
        normalized_hash(m) == report["normalized_hash"],
        "manifest hash differs from report",
    )
    require(
        uniformity(m) == report["uniformity"],
        "uniformity report differs from exact recomputation",
    )
    require(
        realized(m, settings) == report["realized"],
        "realized path report differs from settings",
    )
    return result


def benchmark(sizes, seed=17):
    results = []
    rng = random.Random(seed)
    for p in sizes:
        if p < 2 or p & (p - 1):
            raise ValueError("benchmark internal sizes must be powers of two")
        tracemalloc.start()
        start = time.perf_counter()
        net = Network(Config(active_ports=p, internal_ports=p))
        built = time.perf_counter()
        permutation = list(range(p))
        rng.shuffle(permutation)
        settings = net.solve(enumerate(permutation))
        solved = time.perf_counter()
        net.verify(settings)
        done = time.perf_counter()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results.append(
            dict(
                internal_ports=p,
                stages=net.depth,
                switches=len(net.switches),
                build_s=built - start,
                solve_s=solved - built,
                verify_s=done - solved,
                python_peak_bytes=peak,
                process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            )
        )
    return {
        "scope": "topology/solver only; not physical routing",
        "seed": seed,
        "memory_method": "tracemalloc per size for Python allocations; Linux ru_maxrss for process lifetime peak including native memory",
        "results": results,
    }
