"""Bounded Banyan physical search and transactional artifact publication."""

import csv
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from dataclasses import replace
from collections import Counter
from .config import Config
from .network import Network
from .banyan_network import BlockingError
from .banyan_layout import build, placement, profile, port_keeps
from .banyan_verify import verify_manifest, verify_gds
from .as_verify import track
from .as_workflow import candidates as as_candidates, physical_extents
from .as_channel import fanout_metrics
from .verify import normalized_hash
from .cli import save


def candidates(cfg):
    def adjust(c, net, widths, dirs, bankmap):
        ins, outs = port_keeps(c, net, dirs, bankmap)
        return [w + outs[s] + ins[s + 1] for s, w in enumerate(widths)]

    return as_candidates(
        cfg, placement_fn=placement, width_adjust=adjust, prefix="banyan"
    )


def record_failure(out, requests, error):
    target = Path(out)
    record = dict(
        success=False,
        request=requests,
        reason=str(error),
        target=str(target),
        previous_output_preserved=target.exists(),
    )
    if isinstance(error, BlockingError):
        record["blocking"] = error.diagnostic
    path = target.with_name(target.name + ".failure.json")
    save(path, record)
    return path


def save_settings(out, settings):
    """Publish a complete state file, retaining the previous result on failure."""
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + target.name, dir=target.parent)
    scratch = Path(name)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps(settings, indent=2, sort_keys=True) + "\n")
        os.replace(scratch, target)
    finally:
        scratch.unlink(missing_ok=True)


def generate(cfg, out, requests, choices=None):
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(
        tempfile.mkdtemp(prefix="." + target.name + "-pending-", dir=target.parent)
    )
    backup = None
    try:
        report = _generate(cfg, scratch, requests, choices)
        verify_bundle(scratch)
        if target.exists():
            backup = Path(
                tempfile.mkdtemp(
                    prefix="." + target.name + "-previous-", dir=target.parent
                )
            )
            backup.rmdir()
            os.replace(target, backup)
        try:
            os.replace(scratch, target)
        except OSError:
            if backup:
                os.replace(backup, target)
                backup = None
            raise
        if backup:
            shutil.rmtree(backup)
        return report
    except (ValueError, KeyError, TypeError, OSError) as error:
        failure = record_failure(target, requests, error)
        if (scratch / "search.json").exists():
            save(
                target.with_name(target.name + ".failed-search.json"),
                json.loads((scratch / "search.json").read_text()),
            )
        raise ValueError(
            f"{error}; previous output preserved={target.exists()}; this attempt failed, see {failure}"
        ) from error
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def metrics(m, settings):
    cfg = Config(**m["config"])
    net = Network(cfg)
    cells = m["cells"]
    rm = {}
    for r in m["routes"]:
        ts = [track(cells[p["cell"]], p["entry"], p["exit"]) for p in r["pieces"]]
        rm[r["stage"], r["row"]] = {
            k: sum(t[k] for t in ts) for k in ("length", "bends", "crossings")
        }
    instances = {i["id"]: i for i in m["instances"]}
    io = {
        (v["side"], v["active"]): track(cells[v["cell"]], "w", "e")
        for v in m["interfaces"]
    }

    def measure(a, b, path):
        totals = {
            k: io["west", a][k] + io["east", b][k]
            for k in ("length", "bends", "crossings")
        }
        for node in path:
            c = cells[instances[node["switch"]]["cell"]]
            t = track(c, f"i{node['input']}", f"o{node['output']}")
            for k in totals:
                totals[k] += t[k]
            if node["stage"] < net.depth - 1:
                row = net.switches[node["switch"]]["row"] + node["output"]
                for k, v in rm[node["stage"], row].items():
                    totals[k] += v
        return dict(input=a, output=b, mzis=len(path), **totals)

    actual = [
        measure(a, b, net.trace(cfg.input_map[a], settings["states"])[1])
        for a, b in settings["active"]
    ]
    topology = [
        measure(a, b, net.path(a, b))
        for a in range(cfg.active_ports)
        for b in range(cfg.active_ports)
    ]
    turns = 0
    length = 0
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
            length += abs(a[0] - b[0]) + abs(a[1] - b[1])
    return dict(
        realized_paths=actual,
        topology_paths=topology,
        realized_mzi_counts=dict(sorted(Counter(v["mzis"] for v in actual).items())),
        path_length_min_um=min((v["length"] for v in actual), default=0),
        path_length_max_um=max((v["length"] for v in actual), default=0),
        topology_mzi_min=net.depth,
        topology_mzi_max=net.depth,
        topology_length_min_um=min(v["length"] for v in topology),
        topology_length_max_um=max(v["length"] for v in topology),
        topology_crossing_min=min(v["crossings"] for v in topology),
        topology_crossing_max=max(v["crossings"] for v in topology),
        graph_crossings=net.export()["graph_crossings"],
        physical_crossings=m["crossing_count"],
        crossing_sources=dict(
            interstage=sum(v["crossings"] for v in rm.values()) // 2,
            io=sum(v["crossings"] for v in io.values()) // 2,
            termination=sum(
                track(cells[p["cell"]], p["entry"], p["exit"])["crossings"]
                for t in m["terminations"]
                for p in t["pieces"]
            )
            // 2,
        ),
        signal_turns=turns,
        external_wire_length_um=length,
        ground_contact_count=len(m["ground_rails"]),
        termination_count=len(m["terminations"]),
        width_target_um=20000,
        width_target_met=m["width"] <= 20000,
        extents_um=physical_extents(m),
        pad_only_width_um=m["extents"]["pads"][2] - m["extents"]["pads"][0],
        signal_turns_per_net=turns / len(m["instances"]),
        fanout=fanout_metrics(m),
        routing_metrics_scope="External S terminal to pad turns; S and G fanout wire length. Common G bus and device interiors excluded.",
    )


def _generate(cfg, out, requests, choices=None):
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
    if not selected_choices or len(selected_choices) > 18:
        raise ValueError("Banyan requires 1 to 18 full candidates")
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
            if cfg.active_ports == 100 and m["crossing_count"] >= 4522:
                raise ValueError(
                    "actual whole-chip crossing count does not improve AS-Benes"
                )
            measured = metrics(m, settings)
            score = (
                round(m["width"] / cc.grid) * round(m["height"] / cc.grid),
                m["width"],
                m["crossing_count"],
                measured["signal_turns"],
                measured["external_wire_length_um"],
                measured["path_length_max_um"] - measured["path_length_min_um"],
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
        raise ValueError(
            "no pruned Banyan candidate passed geometry and readback checks"
        )
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
    save(out / "terminations.json", m["terminations"])
    save(out / "selected-choice.json", m["candidate"])
    from .as_preview import render

    render(out / "layout.gds", m, out)
    area = m["width"] * m["height"] / 1e6
    import importlib.metadata

    report = dict(
        success=True,
        summary=dict(
            topology="pruned-banyan",
            active_ports=cfg.active_ports,
            parent_ports=net.p,
            blocking=True,
            terminations=len(m["terminations"]),
            crossings=m["crossing_count"],
            graph_crossings=net.export()["graph_crossings"],
            boundary_lane_counts=net.export()["boundary_lane_counts"],
            internal_ports=net.p,
            stages=net.depth,
            mzis=len(net.switches),
            pads=len(m["electrical"]),
            pad_rows_per_side=2,
            pad_pitch_um=100,
            pad_placement=cfg.pad_distribution,
            pad_pitch_rule="minimum" if cfg.pad_distribution == "routing" else "fixed",
            pad_row_stagger_um=None if cfg.pad_distribution == "routing" else 50,
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
            baseline="examples/benes/exact100-balanced/regular.json",
            baseline_mzis=596,
            baseline_crossings=4522,
            baseline_width_mm=20.252711,
            baseline_height_mm=4.555112,
            baseline_area_mm2=92.253366908632,
            mzi_reduction_percent=100 * (1 - len(net.switches) / 596),
            crossing_reduction_percent=100 * (1 - m["crossing_count"] / 4522),
            width_reduction_percent=100 * (1 - m["width"] / 20252.711),
            area_reduction_percent=100 * (1 - area / 92.253366908632),
        ),
        search=dict(
            max_full_candidates=18,
            actual_candidates=len(records),
            global_optimum_proven=False,
            objective_order=[
                "die_area",
                "width",
                "crossings",
                "signal_turns",
                "wire_length",
                "path_length_spread",
                "stable_id",
            ],
        ),
        assumptions=[
            "Geometrical TFLN GSG model; coupling, loss, RF impedance and foundry signoff remain uncalibrated.",
            "M2 passive overpasses assume insulation; vias obey explicit optical keepouts.",
            "Single-plane blocking network; every selected pair has one path through log2(parent_ports) switches.",
            "Terminations are geometric placeholders, reflectionless=False; reflection and loss are uncalibrated.",
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
