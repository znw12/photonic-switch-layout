"""Render the generated GDS-model polygons at physical aspect ratio."""

from math import sin, cos, pi


def render(m, path, detail=False):
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.collections import PolyCollection

    colors = {
        "DEVICE": "#244a59",
        "M2": "#849cf7",
        "M1": "#f5ad58",
        "WG": "#52dfd4",
        "VIA": "#fff2c9",
    }
    polys = {k: [] for k in colors}

    def visit(name, x=0, y=0, angle=0):
        c = m["cells"][name]
        ca, sa = cos(angle * pi / 180), sin(angle * pi / 180)
        for p in c["polygons"]:
            if p["layer"] in polys:
                polys[p["layer"]].append(
                    [
                        (x + px * ca - py * sa, y + px * sa + py * ca)
                        for px, py in p["points"]
                    ]
                )
        for r in c["refs"]:
            visit(
                r["cell"],
                x + r["x"] * ca - r["y"] * sa,
                y + r["x"] * sa + r["y"] * ca,
                angle + r["angle"],
            )

    visit(m["top"])
    size = (
        (12, min(16, max(4, 12 * m["height"] / m["width"])))
        if m.get("bands") and not detail
        else (18, 5)
    )
    fig, ax = plt.subplots(figsize=size, layout="constrained")
    fig.patch.set_facecolor("#101923")
    ax.set_facecolor("#101923")
    for layer, color in colors.items():
        ax.add_collection(
            PolyCollection(
                polys[layer],
                facecolors=color,
                edgecolors="none",
                alpha=0.8 if layer in ("M1", "M2") else 1,
            )
        )
    a, b, c, d = m["die_bbox"]
    if detail:
        s = m["stages"][0]
        a = s["x"] - 50
        c = min(s["end"], s["escape_end"] + 4 * m["config"]["lane_pitch"])
        b = -50
        d = min(d, 6 * m["config"]["lane_pitch"])
    ax.set(xlim=(a, c), ylim=(b, d), aspect="equal", xlabel="x (um)", ylabel="y (um)")
    ax.tick_params(colors="#afc2d3")
    ax.xaxis.label.set_color("#afc2d3")
    ax.yaxis.label.set_color("#afc2d3")
    for spine in ax.spines.values():
        spine.set_color("#456")
    cfg = m["config"]
    ax.set_title(
        f"Beneš {cfg['active_ports']} active / {cfg['internal_ports']} internal | {len(m['stages'])} stages | {len(m['instances'])} MZIs | R >= {cfg['radius']:g} um"
        + (" | detail" if detail else ""),
        color="white",
        loc="left",
        pad=15,
    )
    fig.supxlabel(
        "WG: teal    M1: amber    M2/pads: blue    VIA: cream    PLACEHOLDER TECHNOLOGY",
        color="#afc2d3",
        fontsize=9,
    )
    fig.savefig(path, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)
