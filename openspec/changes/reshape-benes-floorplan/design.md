## Context

See proposal.md. Geometry uses gdsfactory export of reusable manifest cells; graph and readback verification are independent of generation. Preserve that separation and the legacy baseline.

## Goals / Non-Goals

Goals: verified shorter layouts, auditable two-phase comparison and parameterized scaling. Non-goals: process signoff, shared return pads, four or more pad rows, bypassing Beneš stages, exact loss matching or a proof of global optimality.

## Decisions

1. Keep the default one-row straight layout; use a separate reshaping engine for two/three rows. Global pad allocation removes the per-stage pad-width floor.
2. Use M2 trunks through aligned straight-waveguide corridors. Use M1 pad stems beneath inner-row M2 pads; vias only join their assigned pad. Sort trunks and destination stems and schedule fanout levels with spacing constraints to avoid same-layer shorts. The extra vertical fanout extent is included in the die.
3. Fold contiguous stages into odd horizontal bands, alternating 0/180-degree placement. Odd band counts preserve west input/east output. Align electrode escape corridors across bands so trunks reach north/south without crossing curved waveguides or MZIs.
4. Compress the optical bundle before each semicircular return and expand afterwards. All arc centerlines retain radius >=20 µm; compressed spacing preserves waveguide clearance. This limits return-wing width compared with full-pitch nested turns.
5. Preserve CROSSING/EXCHANGE and shuffle hierarchy. Extend transform-aware endpoint and spatial checks, retaining canonical graph coverage and exact GDS polygon/reference checks.
6. Test phase one at two/three rows; phase two at two/three rows with three/five bands where stage count permits. Compare width, height, area and path metrics, exposing rejected candidates. The 20 mm target is advisory; keep dimensions and dedicated terminals fixed.

## Risks / Trade-offs

- More bands increase height and electrode escape demand → report full die area and do not assume folding improves area.
- Bundle compression or pad fanout can violate clearance → test actual polygons and reject failing layouts.
- Under-pad metal and waveguide overpasses require process support → explicitly retain placeholder-stack assumptions.
- Equal MZI depth is not equal optical delay → report lengths, bends and crossing spread, with size taking priority.

## Migration Plan

Add opt-in parameters and examples, retain old examples/reports, run regressions, then commit the verified change. No existing output is overwritten by the comparison runs.
