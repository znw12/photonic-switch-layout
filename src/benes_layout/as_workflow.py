"""Deterministic bounded AS candidate generation, reports and artifact bundles."""

import csv
import json
import time
import shutil
from pathlib import Path
from itertools import product
from dataclasses import replace
from collections import Counter
from .config import Config
from .network import Network
from .as_layout import build, placement, assign_banks, profile
from .as_verify import verify_manifest, verify_gds, track
from .geometry import Library
from .as_geometry import shuffle
from .verify import normalized_hash
from .cli import save
from .as_channel import channel_levels


def direction_patterns(depth, budget=8192):
    """Exhaust the 13-column reference, cap exploration for larger networks."""
    if depth <= 13:
        return ["".join(v) for v in product("LR", repeat=depth)]
    patterns = {"L" * depth, "R" * depth}
    for i in range(depth + 1):
        patterns.update(("L" * i + "R" * (depth - i), "R" * i + "L" * (depth - i)))
    import random

    rng = random.Random(17)
    while len(patterns) < budget:
        patterns.add("".join(rng.choice("LR") for _ in range(depth)))
    return sorted(patterns)[:budget]


def candidates(cfg):
    net = Network(cfg)
    bankmap = assign_banks(net)
    results = []
    for pitch in (34, 35):
        c = replace(
            cfg,
            lane_pitch=pitch,
            mzi_height=2 * pitch,
            terminal_offsets=(pitch / 2,) * 2,
        )
        lib = Library(c)
        widths = [
            max(
                (
                    shuffle(lib, b["size"], b["inverse"]).metadata["width"]
                    for b in bd["blocks"]
                ),
                default=0,
            )
            for bd in net.boundaries
        ]
        counts = [
            max(
                sum(
                    v["stage"] == s and bankmap[sid] == bank
                    for sid, v in net.switches.items()
                )
                for bank in ("north", "south")
            )
            for s in range(net.depth)
        ]
        keep = (
            2
            * (
                cfg.optical_metal_clearance
                + cfg.via_size / 2
                + cfg.via_enclosure
                + cfg.wg_width / 2
            )
            + 0.004
        )
        # Estimate stem keepout occupancy; only the shortlist receives geometry.
        step = (
            (cfg.via_size + 2 * cfg.via_enclosure + cfg.metal_width) / 2
            + cfg.metal_spacing
            + 2 * cfg.grid
        )
        channel_step = (
            cfg.via_size + 2 * cfg.via_enclosure + cfg.metal_spacing + 2 * cfg.grid
        )
        ranked = []
        for dirs in direction_patterns(net.depth):
            edge = (counts[0] * step if dirs[0] == "L" else 0) + (
                counts[-1] * step if dirs[-1] == "R" else 0
            )
            span = net.depth * 1000 + edge + 2 * cfg.margin
            for s, w in enumerate(widths):
                tracks = (counts[s] if dirs[s] == "R" else 0) + (
                    counts[s + 1] if dirs[s + 1] == "L" else 0
                )
                span += max(w, tracks * step + keep)
            ranked.append((span, "".join(dirs)))
        ranked.sort()
        shortlist = []
        for _, dirs in ranked[:8]:
            scored = []
            for phase in (-25, -12.5, 0, 12.5, 25):
                stages, width, grids, _ = placement(
                    c, net, widths, dirs, bankmap, phase
                )
                # Coarse pad channel height based on actual source ordering.
                scores = []
                for bank in ("north", "south"):
                    sources = []
                    for stage in stages:
                        n = sum(
                            v["stage"] == stage["stage"] and bankmap[sid] == bank
                            for sid, v in net.switches.items()
                        )
                        sources += stage["trunk_xs"][:n]
                    from .local_ground import tap_stages

                    sources += [
                        stages[s]["x"] + (780 if dirs[s] == "R" else 220)
                        for s in tap_stages(
                            net.depth, min(c.ground_pads_per_side, net.depth)
                        )
                    ]
                    levels = channel_levels(
                        sorted(sources), [v["px"] for v in grids[bank]], channel_step
                    )
                    scores.append(max(levels))
                pad_keep = (
                    cfg.via_size / 2
                    + cfg.via_enclosure
                    + cfg.metal_spacing
                    + 2 * cfg.grid
                )
                height = net.p * pitch + 2 * (
                    1.5 * cfg.margin
                    + cfg.pad_size
                    + cfg.pad_row_pitch
                    + pad_keep
                    + (max(scores) + 2) * channel_step
                )
                scored.append((width * height, width, abs(phase), phase))
            _, _, _, phase = min(scored)
            shortlist.append(dict(exits=dirs, pad_phase=phase, lane_pitch=pitch))
        right = "R" * net.depth
        if not any(v["exits"] == right for v in shortlist):
            shortlist.append(dict(exits=right, pad_phase=0, lane_pitch=pitch))
        for i, v in enumerate(shortlist):
            results.append(
                dict(id=f"as-p{pitch}-{i:02d}", **v, control=v["exits"] == right)
            )
    return results[: cfg.max_candidates]


def metrics(m, settings):
    cfg = Config(**m["config"])
    net = Network(cfg)
    cells = m["cells"]
    routes = {(r["stage"], r["row"]): r for r in m["routes"]}
    route_metrics = {}
    for key, r in routes.items():
        ts = [track(cells[p["cell"]], p["entry"], p["exit"]) for p in r["pieces"]]
        route_metrics[key] = {
            k: sum(t[k] for t in ts) for k in ("length", "bends", "crossings")
        }
    instances = {i["id"]: i for i in m["instances"]}
    io = sum(
        cells[v["cell"]]["tracks"][0]["length"]
        for v in m["interfaces"]
        if v["internal"] == 0
    )
    actual = []
    for a in range(net.p):
        out, path = net.trace(a, settings["states"])
        tot = dict(length=io, bends=0, crossings=0, mzis=0)
        for node in path:
            s = node["stage"]
            if "switch" in node:
                c = cells[instances[node["switch"]]["cell"]]
                t = track(c, f"i{node['input']}", f"o{node['output']}")
                for k in ("length", "bends", "crossings"):
                    tot[k] += t[k]
                tot["mzis"] += 1
                row = net.switches[node["switch"]]["row"] + node["output"]
            else:
                tot["length"] += 1000
                row = node["row"]
            if s < net.depth - 1:
                for k, v in route_metrics[s, row].items():
                    tot[k] += v
        actual.append(dict(input=a, output=out, **tot))
    # Dynamic min/max over all reachable paths, separate from selected states.
    topology = []
    for a in range(net.p):
        values = {a: (0, 0, io, io, 0, 0)}
        for s in range(net.depth):
            nxt = {}
            for row, v in values.items():
                sw = net.slots[s].get(row)
                outputs = (
                    [(net.switches[sw[0]]["row"] + j, j) for j in (0, 1)]
                    if sw
                    else [(row, 0)]
                )
                for output, j in outputs:
                    t = (
                        track(cells[instances[sw[0]]["cell"]], f"i{sw[1]}", f"o{j}")
                        if sw
                        else dict(length=1000, crossings=0)
                    )
                    count = int(sw is not None)
                    length = t["length"]
                    cross = t["crossings"]
                    dest = output
                    if s < net.depth - 1:
                        length += route_metrics[s, output]["length"]
                        cross += route_metrics[s, output]["crossings"]
                        dest = net.boundaries[s]["permutation"][output]
                    nv = (
                        v[0] + count,
                        v[1] + count,
                        v[2] + length,
                        v[3] + length,
                        v[4] + cross,
                        v[5] + cross,
                    )
                    if dest in nxt:
                        old = nxt[dest]
                        nv = tuple(
                            min(old[k], nv[k]) if k % 2 == 0 else max(old[k], nv[k])
                            for k in range(6)
                        )
                    nxt[dest] = nv
            values = nxt
        topology += [
            dict(
                input=a,
                output=b,
                mzi_min=v[0],
                mzi_max=v[1],
                length_min=v[2],
                length_max=v[3],
                crossing_min=v[4],
                crossing_max=v[5],
            )
            for b, v in sorted(values.items())
        ]
    turns = 0
    wirelength = 0
    for e in m["electrical"]:
        previous = None
        end = [e["x"], e["y"]]
        for s in e["segments"]:
            a, b = s["start"], s["end"]
            if a != end:
                continue
            end = b
            direction = 0 if a[1] == b[1] else 1
            if previous is not None and direction != previous:
                turns += e["terminal"] == "S"
            previous = direction
            wirelength += abs(a[0] - b[0]) + abs(a[1] - b[1])
    return dict(
        realized_paths=actual,
        topology_paths=topology,
        realized_mzi_counts=dict(sorted(Counter(v["mzis"] for v in actual).items())),
        path_length_min_um=min(v["length"] for v in actual),
        path_length_max_um=max(v["length"] for v in actual),
        topology_mzi_min=min(v["mzi_min"] for v in topology),
        topology_mzi_max=max(v["mzi_max"] for v in topology),
        signal_turns=turns,
        external_wire_length_um=wirelength,
        ground_contact_count=len(m["ground_rails"]),
        removed_ground_contacts=2 * len(m["instances"]) - len(m["ground_rails"]),
        width_target_um=20000,
        width_target_met=m["width"] <= 20000,
        extents_um=physical_extents(m),
        pad_only_width_um=(
            15110 if net.p == 100 else m["extents"]["pads"][2] - m["extents"]["pads"][0]
        ),
        signal_turns_per_net=turns / len(m["instances"]),
        routing_metrics_scope="External S terminal to pad turns; external S and G fanout wire length. Device interiors and common G bus excluded.",
    )


def physical_extents(m):
    """Layer bounds from hierarchical polygons; no floorplan estimates."""
    from functools import lru_cache
    from .geometry import point

    @lru_cache(None)
    def bounds(name, layer):
        c = m["cells"][name]
        points = [
            p
            for poly in c["polygons"]
            if poly["layer"] == layer
            for p in poly["points"]
        ]
        for ref in c["refs"]:
            b = bounds(ref["cell"], layer)
            if b:
                points.extend(
                    point(ref["x"], ref["y"], ref["angle"], p)
                    for p in ((b[0], b[1]), (b[0], b[3]), (b[2], b[1]), (b[2], b[3]))
                )
        if not points:
            return None
        return [
            min(p[0] for p in points),
            min(p[1] for p in points),
            max(p[0] for p in points),
            max(p[1] for p in points),
        ]

    return {
        **{layer: bounds(m["top"], layer) for layer in ("WG", "M1", "M2", "VIA")},
        "pads": m["extents"]["pads"],
        "die": m["die_bbox"],
    }


def generate(cfg, out, requests, choices=None):
    profile(cfg)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    net = Network(cfg)
    settings = net.solve(requests)
    logical = net.verify(settings)
    save(
        out / "report.json",
        dict(success=False, state="generating", config=cfg.to_dict()),
    )
    save(out / "search.json", [])
    started = time.perf_counter()
    records = []
    best = None
    selected_choices = candidates(cfg) if choices is None else choices
    for choice in selected_choices:
        pitch = choice.get("lane_pitch", cfg.lane_pitch)
        cc = replace(
            cfg,
            lane_pitch=pitch,
            mzi_height=2 * pitch,
            terminal_offsets=(pitch / 2,) * 2,
        )
        scratch = out / ("." + choice["id"])
        scratch.mkdir(exist_ok=True)
        t = time.perf_counter()
        try:
            lib, m = build(cc, choice)
            checks = verify_manifest(m)
            names = lib.write_gds(m["top"], scratch / "layout.gds")
            checks.update(
                verify_gds(
                    scratch / "layout.gds",
                    m,
                    names,
                    windows_path=scratch / "overpass_windows.json",
                )
            )
            measured = metrics(m, settings)
            score = (
                round(m["width"] / cc.grid) * round(m["height"] / cc.grid),
                m["width"],
                measured["signal_turns"],
                measured["external_wire_length_um"],
                measured["path_length_max_um"] - measured["path_length_min_um"],
                0 if pitch == 35 else 1,
                choice["id"],
            )
            rec = dict(
                **choice,
                status="verified",
                width_um=m["width"],
                height_um=m["height"],
                area_um2=m["width"] * m["height"],
                signal_turns=measured["signal_turns"],
                objective=list(score),
                time_s=time.perf_counter() - t,
            )
            if best is None or score < best[0]:
                best = (score, m, names, checks, measured, rec)
                shutil.copyfile(scratch / "layout.gds", out / "layout.gds")
                shutil.copyfile(
                    scratch / "overpass_windows.json", out / "overpass_windows.json"
                )
            print(
                f"{choice['id']}: verified {m['width']/1000:.3f} x {m['height']/1000:.3f} mm",
                flush=True,
            )
        except ValueError as e:
            rec = dict(
                **choice,
                status="rejected",
                reason=str(e),
                time_s=time.perf_counter() - t,
            )
            print(f"{choice['id']}: rejected: {e}", flush=True)
        finally:
            shutil.rmtree(scratch)
        records.append(rec)
        save(out / "search.json", records)
    if best is None:
        (out / "layout.gds").unlink(missing_ok=True)
        save(out / "report.json", dict(success=False, candidates=records))
        raise ValueError("no AS candidate passed geometry and readback checks")
    _, m, names, checks, measured, selected = best
    for filename, value in (
        ("config.json", m["config"]),
        ("manifest.json", m),
        ("network.json", net.export()),
        ("settings.json", settings),
        ("cell_names.json", names),
    ):
        save(out / filename, value)
    with (out / "pads.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["net", "terminal", "side", "row", "column", "x_um", "y_um"])
        for e in m["electrical"]:
            w.writerow(
                [
                    e["net"],
                    e["terminal"],
                    e["side"],
                    e["pad_row"],
                    e["pad_column"],
                    *e["pad"],
                ]
            )
    with (out / "ports.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["side", "internal", "active", "x_um", "y_um"])
        for p in m["interfaces"]:
            w.writerow([p["side"], p["internal"], p["active"], *p["position"]])
    from .as_preview import render

    render(out / "layout.gds", m, out)
    area = m["width"] * m["height"] / 1e6
    import importlib.metadata

    report = dict(
        success=True,
        summary=dict(
            topology="as-benes",
            active_ports=net.p,
            internal_ports=net.p,
            stages=net.depth,
            mzis=len(net.switches),
            pads=len(m["electrical"]),
            pad_rows_per_side=2,
            pad_pitch_um=100,
            pad_row_stagger_um=50,
            lane_pitch_um=m["config"]["lane_pitch"],
            width_mm=m["width"] / 1000,
            height_mm=m["height"] / 1000,
            area_mm2=area,
            selected_candidate=selected["id"],
            column_exits=selected["exits"],
        ),
        checks={**logical, **checks},
        metrics=measured,
        candidates=records,
        normalized_hash=normalized_hash(m),
        comparison=dict(
            baseline="output/benes/compact-gsg/n100",
            baseline_width_mm=22.462870,
            baseline_height_mm=4.484092,
            baseline_area_mm2=22.462870 * 4.484092,
            width_reduction_percent=100 * (1 - m["width"] / 22462.870),
            area_reduction_percent=100 * (1 - area / (22.462870 * 4.484092)),
        ),
        search=dict(
            max_full_candidates=18,
            actual_candidates=len(records),
            global_optimum_proven=False,
            objective_order=[
                "die_area",
                "width",
                "signal_turns",
                "wire_length",
                "path_length_spread",
                "pitch_margin",
                "stable_id",
            ],
        ),
        assumptions=[
            "Geometrical TFLN GSG model; coupling, loss, RF impedance and foundry signoff remain uncalibrated.",
            "M2 passive overpasses assume insulation; vias obey explicit optical keepouts.",
            "AS paths have unequal switch counts; rearrangement is not hitless.",
            "Unrequested inputs must remain dark in single-connection operation.",
        ],
        total_time_s=time.perf_counter() - started,
    )
    report["versions"] = {
        package: importlib.metadata.version(package)
        for package in ("gdsfactory", "kfactory", "klayout", "shapely")
    }
    report["gds_bytes"] = (out / "layout.gds").stat().st_size
    save(out / "report.json", report)
    return report


def verify_bundle(directory):
    directory = Path(directory)

    def read(name):
        return json.loads((directory / name).read_text())

    m = read("manifest.json")
    cfg = Config(**read("config.json"))
    report = read("report.json")
    settings = read("settings.json")
    if not report["success"] or cfg.digest != Config(**m["config"]).digest:
        raise ValueError("bundle config/status mismatch")
    net = Network(cfg)
    if read("network.json") != net.export():
        raise ValueError("network bundle mismatch")
    net.verify(settings)
    result = verify_manifest(m)
    result.update(verify_gds(directory / "layout.gds", m, read("cell_names.json")))
    import hashlib

    window_hash = hashlib.sha256(
        json.dumps(read("overpass_windows.json"), sort_keys=True).encode()
    ).hexdigest()
    if window_hash != result["passive_m2_overpass_digest"]:
        raise ValueError("passive overpass windows differ from GDS")
    if any(report["checks"].get(k) != v for k, v in result.items()):
        raise ValueError("verification report differs from readback")
    if normalized_hash(m) != report["normalized_hash"]:
        raise ValueError("bundle hash mismatch")
    if json.loads(json.dumps(metrics(m, settings))) != report["metrics"]:
        raise ValueError("bundle metrics mismatch")
    return result
