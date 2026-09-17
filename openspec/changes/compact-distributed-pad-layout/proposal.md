## Why

The single-band 100-port layout is 50.286 × 24.018 mm because all electrical terminals converge onto a central four-row pad bank. Distributing the pads by optical stage can reuse fanout heights; reducing optical lane pitch can then reduce both dimensions without shortening placeholder MZIs or changing the Beneš network.

## What Changes

- Add opt-in stage-distributed north/south four-row pad banks, retaining 25 µm row staggering in reference profiles.
- Preserve the centralized default and introduce verified 80 µm and 60 µm lane-pitch profiles.
- Export group identity and independently verify stage assignment, placement, spacing, connectivity and GDS geometry.
- Record reproducible full-size comparisons and commit implementation, tests and documentation.

## Capabilities

### New Capabilities

- `distributed-pad-banks`: Stage-local electrical fanout and parameterized lane-pitch compaction with independently verified artifacts.

### Modified Capabilities

None.

## Impact

Beneš configuration, pad routing, floorplan, verification, previews, reports, CLI, tests and documentation. No new dependencies or Waksman changes. Keep single-band optics, 20 µm minimum bends, two metals/vias, separate terminal pads and existing switch/crossing hierarchy.
