## Why

The verified 100-port Beneš layout is 87.56 × 12.64 mm. Its single-row pad banks and straight optical fabric constrain its horizontal dimension. The user requests two sequential experiments: multirow pads with tighter stage spacing, then horizontal serpentine bands.

## What Changes

- Preserve the existing single-row baseline; add exactly two- and three-row north/south pad banks.
- Decouple pad pitch from stage spacing using dedicated M1 stems, M2 escape trunks and explicit vias.
- Add odd-count horizontal optical bands with hierarchical radius-qualified turns and west/east interfaces.
- Keep CROSSING as the existing reusable unit cell and retain all 832 switches and 1664 dedicated pads for 100 active / 128 internal ports.
- Test complete routed geometry and GDS readback, compare actual dimensions, area, connectivity and uniformity.
- Treat 20 mm horizontal span as a soft target. At fixed pad dimensions, two/three rows alone require at least 41.56/27.76 mm before margins; do not change pad count or introduce additional rows to meet the target.

## Capabilities

### New Capabilities
- `reshaped-benes-layout`: Parameterized multirow electrical routing and folded optical floorplans with reproducible verification and comparison.

### Modified Capabilities

None; existing implementations remain available.

## Impact

Beneš configuration, geometry, floorplanning, verification, command line, reports, tests and documentation. Waksman topology and routing are unaffected. Two-metal insulation and routing beneath pads remain placeholder process assumptions, not packaging qualification.
