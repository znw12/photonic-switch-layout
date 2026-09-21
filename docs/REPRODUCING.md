# Reproduce the reviewed 100 × 100 layout

Run commands in Bash on Linux, from the repository root unless stated otherwise.
The final design descends from `d663272`; review cleanup commits preserve that
history. The private repository requires access granted by its owner.

## 1. Obtain the final branch

```bash
git clone --branch codex/exact100-benes-balanced-routing --single-branch \
  https://github.com/znw12/photonic-switch-layout.git
cd photonic-switch-layout
```

For an existing clone, select `codex/exact100-benes-balanced-routing`.
The old local `master` ends before the final exact-100 design.

## 2. Install the recorded environment

The development environment uses Python **3.13.5**, gdsfactory **9.51.0**,
KLayout **0.30.12**, kfactory **3.0.4**, and Shapely **2.1.2**.
All recorded Python package versions are in `requirements.lock`.

With Python 3.13.5 available as `python3.13`:

```bash
python3.13 --version
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
export MPLCONFIGDIR="$PWD/.venv/matplotlib-cache"
```

Alternatively, the existing Conda recipe selects the Python version:

```bash
conda env create --prefix "$PWD/.venv" --file environment.yml
export MPLCONFIGDIR="$PWD/.venv/matplotlib-cache"
```

The explicit Conda prefix keeps the executable paths below identical for both
installation routes. Choose one installation route for an empty `.venv`. Installation
requires the pinned packages to be available from the package index; the review
validation reused the existing pinned environment rather than downloading a
second independent environment.

## 3. Run the regression suite before generating anything

```bash
.venv/bin/python -m pytest -q
```

Review result: **428 passed** in a fresh local clone containing no pre-existing
`output/`, using the recorded environment and that clone's source tree. The
legacy compatibility test uses `tests/fixtures/compact_gsg_legacy_config.json`
and a fixed expected hash; it also runs from an empty temporary directory.

Tests cover all 10,000 single input/output pairs for the exact-100 network,
identity/reverse/cyclic and seeded random full permutations, exhaustive small
networks, geometry checks, and electrical/optical fault injection. The small
integration tests are separate from the full-size build below.

## 4. Generate and independently verify the final physical layout

```bash
.venv/bin/benes-layout generate \
  --config examples/benes/exact100-balanced/regular.json \
  --layout-choice examples/benes/exact100-balanced/regular-choice.json \
  --out output/review-final

.venv/bin/benes-layout verify output/review-final
```

The fixed choice uses 34 µm lanes and column exits `RRLLLLRRRRRLL`. Supplying
`--layout-choice` reproduces the selected floorplan; omitting it starts candidate
exploration and is not the same experiment. The default connection pattern is
identity, which routes all 100 inputs simultaneously.

Expected dimensions: **20.252711 × 4.555112 mm**, area **92.253367 mm²**;
596 MZIs, 4,522 crossings, 604 pads, 2,528 vias, and 597 extracted electrical
nets (596 signals and one shared ground).

Expected normalized geometry hash:

```text
d51610f7da8b76c6e45de433dfe7814be745ac9ccb3571cdcfe0598f47a48562
```

`verify` rechecks the exported GDS, connectivity, metrics, and bundle consistency.
This is project-specific geometry verification, not foundry DRC or optical/RF
simulation. GDS file bytes and elapsed times can vary; the normalized geometry
hash is the useful geometry comparison.

## 5. Inspect outputs and solve a single connection

Open `output/review-final/layout.gds` in KLayout, or inspect its `preview.png`
and the device/pad/interstage detail images. Layers are WG 1/0, M1 10/0,
M2 11/0, and VIA 12/0. The bundle also contains `report.json`, `manifest.json`,
`config.json`, `settings.json`, `pads.csv`, and `ports.csv`.

```bash
.venv/bin/benes-layout solve \
  --config examples/benes/exact100-balanced/regular.json \
  --connections 0:99 \
  --out output/review-final-single-settings.json
```

Ports are numbered 0–99. This writes a separate state file and does not alter
the verified identity-layout bundle. Partial requests are completed to a
permutation; unrequested physical inputs must remain dark for single-connection
operation. Reconfiguration is not guaranteed to be hitless.

## 6. Recreate the curated repository preview and result snapshot

After generation and successful verification, run:

```bash
.venv/bin/python - <<'PY'
import json
import shutil
from pathlib import Path

bundle = Path("output/review-final")
assets = Path("docs/assets")
assets.mkdir(parents=True, exist_ok=True)
report = json.loads((bundle / "report.json").read_text())
assert report["success"]
shutil.copyfile(bundle / "preview.png", assets / "final-layout.png")
snapshot = {
    "design_commit": "d66327202f7fe88802ddddff57568f53491c3df6",
    "config": "examples/benes/exact100-balanced/regular.json",
    "layout_choice": "examples/benes/exact100-balanced/regular-choice.json",
    **{key: report[key] for key in (
        "summary", "checks", "normalized_hash", "versions", "assumptions"
    )},
}
(assets / "final-layout-summary.json").write_text(
    json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
)
PY
```

This copies the actual GDS rendering without redrawing or retouching geometry.
Only one final preview and a compact report excerpt are curated into the
repository; full generated bundles remain ignored under `output/`.
