## Context

See proposal.md. Existing reference uses 832 one-mm MZIs, 7680 20x20 um cosine crossings, 60 um optical lanes, 832 S and 832 G pads. All G are connected only after individual fanout. Drive remains quasi-static, without RF matching. Size has priority over geometric path uniformity.

## Goals / Non-Goals

Goals: parameterized pitch and grounding; reusable hierarchy; compact routing; scalability to power-of-two internal fabrics; independent optical and conductor verification. Preserve 100 active west inputs/east outputs and three pad rows per side at >=120 um same-row pitch.

Non-goals: fabrication signoff, calibrated splitting/loss/Vpi, RF ground impedance certification, fewer independent signal controls.

## Decisions

- Opt in with `ground_pads_per_side=4`; preserve the previous profile by default. The compact reference uses lane_pitch=25 and mzi_height=50. Adjacent equal-potential G rails can touch deliberately. Keep the 20/5/10 um S/gap/G dimensions and R>=20 um.
- G exports at its local bridge, S exports horizontally at the electrode center. Set external signal trace width to 4 um so the straight lead between 25 um optical lanes meets the 10 um optical clearance. Internal electrodes and via landings retain their widths.
- Shift nontrivial input lanes alternately inward by a small offset and shift output half-bundles outward before returning to the normal grid. Circular S bends surround a continuous 45-degree mesh. This increases end crossing clearance without changing the 20x20 um crossing cell or the bulk 25*sqrt(2) spacing. Outer straight bypasses stay on their original lanes.
- Connect each stage's M2 G bridges vertically, then join stages by M1 rails above/below the optical array. Four distributed stage taps per side feed G pads. Every S retains one dedicated pad. The existing aligned pad router handles S and the selected G taps; stage planning counts only S fanout trunks.
- Ground connectivity is defined independently of pad coverage. Readback must prove both G electrodes of every MZI belong to the same ground conductor and every S is distinct. Approved local insulated ground-spine geometry is explicit and bounded; no blanket metal/optical waiver.

## Risks / Trade-offs

- Tight bends near mesh ends → verify primitive clearance, tangency and continuity across all block sizes, including reverse blocks.
- Common G rail contacts → extract real GDS conductors and inject opens/shorts in tests.
- Smaller pitch makes electrical routing more constrained → preserve independent signal routing, inspect preview and measure actual turns; do not promise all routes have one turn.
- Electrical performance depends on stack and packaging → retain quasi-static scope. Ground aggregation precedents: [Luceda](https://academy.lucedaphotonics.com/designs/opa_shuksan/opa_shuksan) and [Cornell 512-channel OPA report, page 12](https://www.cnf.cornell.edu/sites/default/files/2019-RA/2018cnfRA_6OPTS.pdf); these are architectural references, not TFLN RF validation.

## Migration Plan

Add a separate compact example/output bundle, preserve existing examples, run focused and regression tests, generate and independently read back the full matrix, and document measured changes. User explicitly authorized implementation after exploration; supporting artifacts are created as part of the apply work.
