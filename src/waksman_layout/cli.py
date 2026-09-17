"""Command line entry points; every successful GDS is independently verified."""

import argparse
import csv
import importlib.metadata
import json
import math
import resource
import shutil
import sys
import time
from functools import lru_cache
from pathlib import Path

from .config import Config
from .network import Network


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def request_pairs(value, n):
    if value == "identity":
        return list(enumerate(range(n)))
    if value == "reverse":
        return list(enumerate(reversed(range(n))))
    if value == "none":
        return []
    p = Path(value)
    if p.is_file():
        return json.loads(p.read_text())
    try:
        return [tuple(map(int, pair.split(":"))) for pair in value.split(",")]
    except ValueError as error:
        raise ValueError(
            "connections must be identity, reverse, none, JSON pairs, or 0:73,1:4"
        ) from error


def path_metrics(m):
    routes = {r["source"]: r for r in m["routes"]}

    @lru_cache(None)
    def visit(source):
        r = routes[source]
        length = r["length"]
        cross = r["crossings"]
        if r["target"].startswith("out:"):
            return length, cross, 0
        sid = r["target"].rsplit(":", 1)[0]
        a = visit(sid + ":o0")
        b = visit(sid + ":o1")
        return (
            length + m["config"]["mzi_length"] + max(a[0], b[0]),
            cross + max(a[1], b[1]),
            1 + max(a[2], b[2]),
        )

    values = [visit(f"in:{i}") for i in range(m["config"]["n"])]
    return {
        "worst_path_length_um": max(v[0] for v in values),
        "worst_path_crossings": max(v[1] for v in values),
        "worst_path_mzis": max(v[2] for v in values),
        "total_interconnect_length_um": sum(r["length"] for r in routes.values()),
    }


def generate(cfg, out, requests):
    from .layout import build_layout
    from .verify import verify_manifest, verify_gds, normalized_hash
    from .preview import render

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # Never leave an old success report beside a failed new generation.
    for name in ("report.json", "layout.gds", "preview.png", "detail.png"):
        (out / name).unlink(missing_ok=True)
    net = Network(cfg.n)
    solution = net.solve(requests)
    net.verify(solution)
    candidates = []
    best = None
    start = time.perf_counter()
    modes = [cfg.pad_assignment]
    if len(cfg.terminal_names) == 2:
        modes.append("split" if cfg.pad_assignment == "nearest" else "nearest")
    # The initial conservative baseline comes first. Pair the compact candidate
    # with the alternate legal pad assignment, then explore remaining pairs.
    choices = []
    for i, factor in enumerate(cfg.pitch_factors):
        choices.append((factor, modes[i % len(modes)]))
    choices.extend(
        (factor, mode)
        for factor in cfg.pitch_factors
        for mode in modes
        if (factor, mode) not in choices
    )
    for index, (factor, mode) in enumerate(choices[: cfg.max_candidates]):
        step = time.perf_counter()
        candidate_dir = out / f".candidate-{index}"
        candidate_dir.mkdir(exist_ok=True)
        try:
            lib, m = build_layout(cfg, factor, mode)
            built = time.perf_counter()
            checks = verify_manifest(m)
            geometry_checked = time.perf_counter()
            names = lib.write_gds("CHIP", candidate_dir / "layout.gds")
            written = time.perf_counter()
            checks.update(verify_gds(candidate_dir / "layout.gds", m, names))
            verified = time.perf_counter()
            metrics = path_metrics(m)
            area = m["width"] * m["height"]
            score = (
                area,
                metrics["worst_path_crossings"],
                metrics["total_interconnect_length_um"],
            )
            item = dict(
                index=index,
                status="verified",
                factor=factor,
                pad_assignment=mode,
                die_width_um=m["width"],
                die_height_um=m["height"],
                die_area_um2=area,
                **metrics,
                timings_s={
                    "build": built - step,
                    "geometry": geometry_checked - built,
                    "export": written - geometry_checked,
                    "readback": verified - written,
                    "total": verified - step,
                },
            )
            candidates.append(item)
            print(
                f"candidate {index}: verified, {m['width']/1000:.3f} x {m['height']/1000:.3f} mm",
                flush=True,
            )
            if best is None or score < best[0]:
                best = (score, m, checks, names, item)
                shutil.copy2(candidate_dir / "layout.gds", out / "layout.gds")
        except (ValueError, RuntimeError) as error:
            candidates.append(
                dict(
                    index=index,
                    status="failed",
                    factor=factor,
                    pad_assignment=mode,
                    error=str(error),
                )
            )
            print(f"candidate {index}: failed: {error}", file=sys.stderr, flush=True)
        finally:
            shutil.rmtree(candidate_dir)
    if best is None:
        (out / "layout.gds").unlink(missing_ok=True)
        save(
            out / "report.json",
            {"success": False, "candidates": candidates, "config": cfg.to_dict()},
        )
        raise ValueError("no fully routed verified candidate; see report.json")
    _, m, checks, names, selected = best
    versions = {
        name: importlib.metadata.version(name)
        for name in ("gdsfactory", "kfactory", "klayout", "shapely")
    }
    save(out / "config.json", cfg.to_dict())
    save(out / "network.json", net.export())
    save(out / "manifest.json", m)
    save(out / "cell_names.json", names)
    save(out / "settings.json", solution)
    with (out / "pads.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["net", "mzi", "terminal", "side", "x_um", "y_um"])
        for e in m["electrical"]:
            writer.writerow(
                [e["net"], e["instance"], e["terminal"], e["side"], *e["pad"]]
            )
    render(m, out / "preview.png")
    render(m, out / "detail.png", detail=True)
    pad_total = len(m["electrical"])
    pad_bound = max(0, math.ceil(pad_total / 2) - 1) * cfg.pad_pitch + (
        cfg.pad_size if pad_total else 0
    )
    report = {
        "success": True,
        "n": cfg.n,
        "selected_candidate": selected["index"],
        "candidates": candidates,
        "checks": checks,
        "metrics": {
            **path_metrics(m),
            "die_bbox_um": m["die_bbox"],
            "core_bbox_um": m["core_bbox"],
            "pad_count": pad_total,
            "pad_bank_width_lower_bound_um": pad_bound,
            "crossing_count": m["crossing_count"],
            "swap_columns": m["swap_columns"],
            "gds_bytes": (out / "layout.gds").stat().st_size,
            "unrouted_optical": 0,
            "unrouted_electrical": 0,
        },
        "normalized_hash": normalized_hash(m),
        "versions": versions,
        "python": sys.version,
        "total_time_s": time.perf_counter() - start,
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "assumptions": [
            "Illustrative TFLN cells and technology; no foundry/optical/RF qualification.",
            "M2 is insulated over straight waveguides in registered windows; no vias there.",
            "Single-connection operation assumes other inputs are dark.",
            "Waksman reconfiguration may rearrange and interrupt existing connections.",
            "Dedicated terminal pads; no implicit shared return.",
        ],
        "physical_performance_assessed": False,
        "global_area_optimum_proven": False,
    }
    save(out / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Hierarchical Waksman photonic layout (placeholder technology)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="Generate and independently verify GDS")
    gen.add_argument("--config")
    gen.add_argument("--n", type=int)
    gen.add_argument("--out", default="output/n100")
    gen.add_argument("--connections", default="0:0")
    gen.add_argument("--candidates", type=int)
    solve = sub.add_parser(
        "solve", help="Solve a single/partial/full one-to-one mapping"
    )
    solve.add_argument("--n", type=int, default=100)
    solve.add_argument("--connections", default="identity")
    solve.add_argument("--out")
    check = sub.add_parser("verify", help="Recheck an exported artifact bundle")
    check.add_argument("directory")
    bench = sub.add_parser(
        "benchmark", help="Topology and solver scaling, without geometry"
    )
    bench.add_argument("--sizes", default="16,100,256,1024")
    bench.add_argument("--seed", type=int, default=17)
    bench.add_argument("--out", default="output/scaling.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            cfg = Config.load(args.config, n=args.n, max_candidates=args.candidates)
            result = generate(cfg, args.out, request_pairs(args.connections, cfg.n))
            print(
                json.dumps(
                    {
                        "success": result["success"],
                        "directory": str(Path(args.out).resolve()),
                        "metrics": result["metrics"],
                    },
                    indent=2,
                )
            )
        elif args.command == "solve":
            net = Network(args.n)
            s = net.solve(request_pairs(args.connections, args.n))
            net.verify(s)
            if args.out:
                save(args.out, s)
            else:
                print(json.dumps(s, indent=2))
        elif args.command == "verify":
            from .verify import verify_manifest, verify_gds, normalized_hash

            directory = Path(args.directory)
            m = json.loads((directory / "manifest.json").read_text())
            names = json.loads((directory / "cell_names.json").read_text())
            s = json.loads((directory / "settings.json").read_text())
            Network(m["config"]["n"]).verify(s)
            result = verify_manifest(m)
            result.update(verify_gds(directory / "layout.gds", m, names))
            original = json.loads((directory / "report.json").read_text())
            if normalized_hash(m) != original["normalized_hash"]:
                raise ValueError("manifest hash differs from generation report")
            print(json.dumps(result, indent=2))
        elif args.command == "benchmark":
            import random

            rng = random.Random(args.seed)
            results = []
            for n in map(int, args.sizes.split(",")):
                t = time.perf_counter()
                net = Network(n)
                built = time.perf_counter()
                p = list(range(n))
                rng.shuffle(p)
                s = net.solve(enumerate(p))
                solved = time.perf_counter()
                net.verify(s)
                results.append(
                    dict(
                        n=n,
                        switches=len(net.switches),
                        columns=net.columns,
                        build_s=built - t,
                        solve_s=solved - built,
                        verify_s=time.perf_counter() - solved,
                        process_peak_rss_kib=resource.getrusage(
                            resource.RUSAGE_SELF
                        ).ru_maxrss,
                    )
                )
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            save(
                args.out,
                {
                    "scope": "topology/solver only; no geometry claim",
                    "seed": args.seed,
                    "results": results,
                },
            )
            print(json.dumps(results, indent=2))
        return 0
    except (ValueError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
