"""Views of exported GDS polygons, including shared grounds and odd bypasses."""

from pathlib import Path
import numpy as np


def render(gds, m, out):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    import klayout.db as kdb

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ly = kdb.Layout()
    ly.read(str(gds))
    top = ly.top_cell()
    cfg = m["config"]
    colors = {"WG": "#44d8cc", "M1": "#efae60", "M2": "#728dea", "VIA": "#f7efd2"}
    poly = {k: [] for k in colors}
    for key in colors:
        it = top.begin_shapes_rec(ly.layer(*cfg["layers"][key]))
        while not it.at_end():
            shape = it.shape()
            if shape.is_polygon() or shape.is_box() or shape.is_path():
                p = shape.polygon.transformed(it.trans())
                poly[key].append(
                    np.array(
                        [[v.x * ly.dbu, v.y * ly.dbu] for v in p.each_point_hull()]
                    )
                )
            it.next()

    def view(path, bounds, title, size=(16, 6)):
        fig, ax = plt.subplots(figsize=size, layout="constrained")
        fig.patch.set_facecolor("#101923")
        ax.set_facecolor("#101923")
        a, b, c, d = bounds
        for layer, ps in poly.items():
            selected = [
                p
                for p in ps
                if p[:, 0].max() >= a
                and p[:, 0].min() <= c
                and p[:, 1].max() >= b
                and p[:, 1].min() <= d
            ]
            ax.add_collection(
                PolyCollection(
                    selected, facecolors=colors[layer], edgecolors="none", alpha=0.85
                )
            )
        ax.set(
            xlim=(a, c), ylim=(b, d), aspect="equal", xlabel="x (um)", ylabel="y (um)"
        )
        ax.set_title(title, color="white")
        ax.tick_params(colors="#b8c9dc")
        ax.xaxis.label.set_color("#b8c9dc")
        ax.yaxis.label.set_color("#b8c9dc")
        for spine in ax.spines.values():
            spine.set_color("#516176")
        fig.savefig(out / path, dpi=200)
        plt.close(fig)

    view(
        "preview.png",
        m["die_bbox"],
        f"Exact {cfg['active_ports']} x {cfg['active_ports']} AS-Benes | {m['width']/1000:.3f} x {m['height']/1000:.3f} mm | WG teal / M1 amber / M2 blue",
    )
    for side in ("L", "R"):
        inst = next((i for i in m["instances"] if i["cell"] == "AS_MZI_" + side), None)
        if inst:
            x, y = inst["x"], inst["y"]
            p = cfg["lane_pitch"]
            view(
                "mzi_" + side.lower() + ".png",
                [x - 10, y - p / 2 - 10, x + 1010, y + 1.5 * p + 10],
                f"1 mm GSG MZI | {side} electrical exit | shared G contacts owned by column",
                (16, 4),
            )
    rail = next(
        (
            r
            for r in m["ground_rails"]
            if len(r["run"]) > 1
            and r["bounds"][3] - r["bounds"][1] > cfg["gsg_ground_width"]
        ),
        m["ground_rails"][0],
    )
    x, y = rail["contact"]
    view(
        "ground_detail.png",
        [x - 90, y - 80, x + 90, y + 80],
        "Shared G rail: one landing and via; independent S electrodes",
        (9, 7),
    )
    if m["bypasses"]:
        b = m["bypasses"][0]
        view(
            "bypass_detail.png",
            [
                b["x"] - 90,
                b["y"] - 2 * cfg["lane_pitch"],
                b["x"] + 1090,
                b["y"] + 2 * cfg["lane_pitch"],
            ],
            "Odd subnet bypass and adjacent electrodes",
            (16, 5),
        )
    if m["routes"]:
        x = m["stages"][0]["x"] + cfg["mzi_length"]
        y = m["stages"][0]["y"]
        pitch = cfg["lane_pitch"]
        view(
            "interstage_detail.png",
            [x - 90, y - pitch, x + 350, y + min(8, cfg["active_ports"]) * pitch],
            "Direct 45 degree shuffle entries | no offset compensation S bends",
            (10, 7),
        )
    pads = [e for e in m["electrical"] if e["side"] == "north"]
    p = pads[len(pads) // 2]["pad"]
    base = m["electrical_plan"]["pad_base_y"]
    view(
        "pads_detail.png",
        [p[0] - 350, base - 200, p[0] + 350, base + cfg["pad_row_pitch"] + 60],
        (
            "North pads: M2 direct stems / minimum 100 um pitch"
            if cfg["pad_distribution"] == "routing"
            else "North pads: 100 um same-row pitch / 50 um stagger"
        ),
        (13, 6),
    )
    for label, selected_stages in (
        ("left", m["stages"][:2]),
        ("right", m["stages"][-2:]),
    ):
        routes = [
            e for e in pads if e["stage"] in {s["stage"] for s in selected_stages}
        ]
        xs = [x for e in routes for x in (e["tx"], e["pad"][0])]
        view(
            f"electrical_{label}.png",
            [
                min(xs) - 100,
                m["electrical_plan"]["ground_y"] - 180,
                max(xs) + 100,
                base + cfg["pad_row_pitch"] + 60,
            ],
            f"{label.title()} electrical fanout | M1 amber / M2 blue / vias white",
            (16, 6),
        )
