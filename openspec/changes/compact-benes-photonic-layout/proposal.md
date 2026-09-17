## Why

The existing Waksman demonstrator provides verified connectivity but its possible single-connection paths traverse 4 to 13 MZIs. Add a separately developed, regular Beneš implementation with equal switch depth, while making complete-chip area the primary optimization objective and physical path uniformity a secondary objective.

## What Changes

- Build a complete standard power-of-two Beneš fabric. The first target has 128 internal inputs/outputs, 13 stages, 64 identical 2x2 MZI cells per stage, and 832 MZIs; expose 100 west inputs and 100 east outputs.
- Keep all internal switches and interconnects. Explicitly map and terminate the remaining 28 input and 28 output interfaces with replaceable placeholder terminations; never prune stages or bypass MZIs to save area.
- Preserve arbitrary simultaneous one-to-one active-port mappings and single-illuminated-input operation, with documented rearrangeable reconfiguration behavior.
- Develop a new topology generator, state solver, regular placement, and Beneš-specific optical/electrical routing flow. Retain the Waksman implementation and examples for comparison.
- Retain parameterization, hierarchy, routing strategy, scalability, and verification as design requirements, with 20 um minimum optical bend radius, replaceable TFLN MZIs, gdsfactory, and two metal layers plus vias routed to north/south pads.
- Rank fully verified candidates first by complete die area, including pads, termination regions, fanout, and margins. Use path-length, crossing-count, and bend-count spreads only as secondary tie-breakers; do not expand the footprint solely to equalize paths by default.
- Deliver hierarchical GDS, previews, active/spare port and pad maps, switch settings, reproducible configuration, and independent geometry/connectivity/size/uniformity reports.

## Capabilities

### New Capabilities

- `benes-permutation-network`: Complete regular fabric, active/spare interfaces, state synthesis, and equal switch-depth invariants.
- `compact-benes-layout`: Parametric hierarchical components, regular placement, and area-first candidate selection.
- `benes-optical-electrical-routing`: Beneš-specific interconnects, spare terminations, and two-metal north/south fanout.
- `benes-verification-metrics`: Independent functional/readback validation, explicit uniformity statistics, reproducibility, and scaling evidence.

### Modified Capabilities

None. The main specification directory is empty; the completed Waksman change and its implementation remain intact.

## Impact

Implementation will add a separate Python package/CLI and Beneš-specific configurations, tests, and examples within this repository. Existing pinned gdsfactory/KLayout dependencies can be reused; only reviewed, technology-neutral utility code may be shared. The new engine must not invoke the Waksman topology or router under a different name. New outputs use separate directories.

This change captures planning only. Implementation follows separately. Foundry qualification, equal measured loss, equal group delay, calibrated voltages, hitless reconfiguration, shared-ground/package redesign, and a guaranteed global area optimum are outside scope. Smaller die area than the lower-switch-count Waksman example is not an acceptance requirement.
