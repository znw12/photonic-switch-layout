## Why

The 60 um optical lane pitch and one ground pad per MZI consume unnecessary area. The user approved 25 um ports, local ground aggregation with four G pads per bank, and simpler electrical leads, while retaining 1 mm MZIs and radius >=20 um.

## What Changes

- Add an opt-in compact GSG profile with 25 um lane pitch and reusable, fixed-footprint cosine crossings.
- Add radius-compliant entry/exit offsets around the continuous diagonal permutation mesh.
- Aggregate device grounds inside each stage; retain every independent S and only four distributed G pads on each side.
- Remove local signal doglegs and replan stage trunks/pads at three rows per bank, keeping 120 um minimum same-row pad pitch.
- Export separate GDS, previews, connection tables and independent geometry/electrical verification; preserve the existing reference profile.

## Capabilities

### New Capabilities
- `compact-gsg-matrix`: Compact optical pitch, locally shared grounds and simplified electrical routing with extraction checks.

### Modified Capabilities
None. This is an additional profile; existing reference configurations remain supported.

## Impact

Beneš configuration, physical MZI, interstage templates, electrical placement/routing, validation, reports, tests and reference artifacts. Uses the existing gdsfactory/KLayout stack; no new dependencies or calibrated optical/RF claims.
