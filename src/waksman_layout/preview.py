"""Render the actual hierarchy polygons with physical aspect ratio."""

from math import cos, sin, pi


def render(manifest, path, detail=False):
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.collections import PolyCollection

    cells = manifest["cells"]
    polygons = {k: [] for k in ("WG", "M1", "M2", "VIA", "DEVICE")}

    def visit(name, dx=0, dy=0, angle=0):
        c = cells[name]
        ca, sa = cos(angle * pi / 180), sin(angle * pi / 180)
        for p in c["polygons"]:
            if p["layer"] in polygons:
                polygons[p["layer"]].append(
                    [
                        (dx + x * ca - y * sa, dy + x * sa + y * ca)
                        for x, y in p["points"]
                    ]
                )
        for r in c["refs"]:
            visit(
                r["cell"],
                dx + r["x"] * ca - r["y"] * sa,
                dy + r["x"] * sa + r["y"] * ca,
                angle + r["angle"],
            )

    visit(manifest["top"])
    fig, ax = plt.subplots(figsize=(18, 5), layout="constrained")
    fig.patch.set_facecolor("#101923")
    ax.set_facecolor("#101923")
    colors = {
        "DEVICE": "#224355",
        "WG": "#52dfd4",
        "M1": "#f5ad58",
        "M2": "#849cf7",
        "VIA": "#fff2c9",
    }
    for layer in ("DEVICE", "M2", "M1", "WG", "VIA"):
        ax.add_collection(
            PolyCollection(
                polygons[layer],
                facecolors=colors[layer],
                edgecolors="none",
                alpha=0.8 if layer in ("M1", "M2") else 1,
            )
        )
    a, b, c, d = manifest["die_bbox"]
    if detail:
        first = manifest["stages"][0]
        c = min(c, first["escape_end"] + 200)
        d = min(d, manifest["config"]["lane_pitch"] * 8)
    ax.set_xlim(a, c)
    ax.set_ylim(b, d)
    ax.set_aspect("equal")
    ax.tick_params(colors="#afc2d3")
    ax.set_xlabel("x (um)", color="#afc2d3")
    ax.set_ylabel("y (um)", color="#afc2d3")
    for spine in ax.spines.values():
        spine.set_color("#456")
    n = manifest["config"]["n"]
    title = f"{n} x {n} Waksman | {len(manifest['instances'])} MZI placeholders | R >= 20 um"
    ax.set_title(
        title + (" | detail" if detail else ""), color="white", loc="left", pad=15
    )
    fig.text(
        0.99,
        0.01,
        "WG: teal    M1: amber    M2/pads: blue    VIA: cream    PLACEHOLDER TECHNOLOGY",
        ha="right",
        color="#afc2d3",
        fontsize=9,
    )
    fig.savefig(path, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)
