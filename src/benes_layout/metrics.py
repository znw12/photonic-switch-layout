"""Exact DAG extrema and separately scoped realized-configuration statistics."""

from functools import lru_cache
from statistics import mean, pstdev

from .config import Config
from .network import Network

KEYS = ("length", "crossings", "bends", "angle")


def mzi_track(m, sid, incoming, outgoing):
    i = next(i for i in m["instances"] if i["id"] == sid)
    flip = i["pin_flip"]
    pair = [f"i{incoming ^ flip}", f"o{outgoing ^ flip}"]
    return next(t for t in m["cells"][i["cell"]]["tracks"] if t["ports"] == pair)


def uniformity(m):
    cfg = Config(**m["config"])
    routes = {r["source"]: r for r in m["routes"]}
    devices = {i["id"]: i for i in m["instances"]}
    active_out = set(cfg.output_map)
    results = {}
    for key in KEYS:

        @lru_cache(None)
        def visit(source, maximize):
            r = routes[source]
            target = r["target"]
            if target.startswith("out:"):
                if int(target.split(":")[1]) not in active_out:
                    return None
                return r[key], (source,)
            sid, pin = target.rsplit(":", 1)
            inst = devices[sid]
            possibilities = []
            for out in range(2):
                child = visit(f"{sid}:o{out}", maximize)
                if child is None:
                    continue
                pair = [
                    f"i{int(pin[1]) ^ inst['pin_flip']}",
                    f"o{out ^ inst['pin_flip']}",
                ]
                t = next(
                    t for t in m["cells"][inst["cell"]]["tracks"] if t["ports"] == pair
                )
                possibilities.append((r[key] + t[key] + child[0], (source,) + child[1]))
            if not possibilities:
                return None
            return (max if maximize else min)(possibilities, key=lambda v: (v[0], v[1]))

        extrema = []
        for maximize in (False, True):
            paths = [visit(f"in:{i}", maximize) for i in cfg.input_map]
            paths = [v for v in paths if v is not None]
            value, witness = (max if maximize else min)(
                paths, key=lambda v: (v[0], v[1])
            )
            extrema.append({"value": value, "witness": list(witness)})
        results[key] = {
            "min": extrema[0]["value"],
            "max": extrema[1]["value"],
            "spread": extrema[1]["value"] - extrema[0]["value"],
            "min_witness": extrema[0]["witness"],
            "max_witness": extrema[1]["witness"],
        }
    return {
        "scope": "exact extrema over all possible single paths between active interfaces",
        "metrics": results,
    }


def realized(m, settings):
    cfg = Config(**m["config"])
    net = Network(cfg)
    net.verify(settings)
    routes = {r["source"]: r for r in m["routes"]}
    paths = []
    for a, b in settings["active"]:
        internal = cfg.input_map[a]
        _, trace = net.trace(internal, settings["states"])
        first = routes[f"in:{internal}"]
        values = {k: first[k] for k in KEYS}
        witness = [first["source"]]
        for hop in trace:
            t = mzi_track(m, hop["switch"], hop["input"], hop["output"])
            r = routes[f"{hop['switch']}:o{hop['output']}"]
            witness.append(r["source"])
            for k in KEYS:
                values[k] += t[k] + r[k]
        paths.append(
            {
                "input": a,
                "output": b,
                "switches": len(trace),
                "witness": witness,
                **values,
            }
        )
    summary = {}
    for k in KEYS:
        values = [p[k] for p in paths]
        summary[k] = (
            dict(
                min=min(values),
                max=max(values),
                spread=max(values) - min(values),
                mean=mean(values),
                stddev=pstdev(values),
            )
            if values
            else None
        )
    return {
        "scope": "paths realized by the specified switch settings only",
        "paths": paths,
        "statistics": summary,
    }


def objective(m, metrics, candidate_id):
    grid = m["config"]["grid"]
    area = round(m["width"] / grid) * round(m["height"] / grid)
    values = metrics["metrics"]
    return (
        area,
        values["length"]["spread"],
        values["crossings"]["spread"],
        values["bends"]["spread"],
        sum(r["length"] for r in m["routes"]),
        candidate_id,
    )
