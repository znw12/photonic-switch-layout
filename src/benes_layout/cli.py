"""Beneš command interface (physical workflows are implemented separately)."""

import argparse
import json
from pathlib import Path
import sys

from .config import Config
from .network import Network


def request_pairs(value, n):
    if value == "identity":
        return list(enumerate(range(n)))
    if value == "reverse":
        return list(enumerate(reversed(range(n))))
    if value == "none":
        return []
    if Path(value).is_file():
        return json.loads(Path(value).read_text())
    return [tuple(map(int, v.split(":"))) for v in value.split(",")]


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Complete Beneš photonic layout; area first"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "solve"):
        p = sub.add_parser(command)
        p.add_argument("--config")
        p.add_argument("--n", type=int, help="number of active ports")
        p.add_argument("--internal", type=int)
        p.add_argument("--connections", default="identity")
        p.add_argument(
            "--out", default="output/benes/n100" if command == "generate" else None
        )
        if command == "generate":
            p.add_argument("--candidates", type=int)
            p.add_argument("--pad-rows", type=int)
            p.add_argument("--pad-row-stagger", type=float)
            p.add_argument("--fold-bands", type=int)
    sub.add_parser("verify").add_argument("directory")
    comparison = sub.add_parser("compare")
    comparison.add_argument("directories", nargs="+")
    comparison.add_argument("--out", default="output/benes/reshape/comparison")
    comparison.add_argument("--baseline")
    b = sub.add_parser("benchmark")
    b.add_argument("--sizes", default="16,128,256,1024")
    b.add_argument("--out", default="output/benes/scaling.json")
    b.add_argument("--seed", type=int, default=17)
    args = parser.parse_args(argv)
    try:
        if args.command in ("solve", "generate"):
            cfg = Config.load(
                args.config,
                active_ports=args.n,
                internal_ports=args.internal,
                max_candidates=getattr(args, "candidates", None),
                pad_rows=getattr(args, "pad_rows", None),
                pad_row_stagger=getattr(args, "pad_row_stagger", None),
                fold_bands=getattr(args, "fold_bands", None),
            )
            pairs = request_pairs(args.connections, cfg.active_ports)
            if args.command == "solve":
                net = Network(cfg)
                settings = net.solve(pairs)
                net.verify(settings)
                if args.out:
                    save(args.out, settings)
                else:
                    print(json.dumps(settings, indent=2))
            else:
                from .workflow import generate

                result = generate(cfg, args.out, pairs)
                print(json.dumps(result["summary"], indent=2))
        elif args.command == "verify":
            from .workflow import verify_bundle

            print(json.dumps(verify_bundle(args.directory), indent=2))
        elif args.command == "compare":
            from .comparison import compare_bundles

            result = compare_bundles(args.directories, args.out, args.baseline)
            print(
                json.dumps(
                    {k: v for k, v in result.items() if k.startswith("smallest_")},
                    indent=2,
                )
            )
        else:
            from .workflow import benchmark

            result = benchmark([int(s) for s in args.sizes.split(",")], args.seed)
            save(args.out, result)
            print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
