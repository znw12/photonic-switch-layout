## Why

Create a reproducible large-scale photonic layout generator that demonstrates parameterization, hierarchy, routing strategy, scalability, and verification. The first target is an exact 100-input/100-output TFLN switching matrix; no device library, layout implementation, or main specifications currently exist in this project.

## What Changes

- Generate an arbitrary-size Waksman network, with exactly 573 replaceable 2x2 MZI instances at N=100, without padding the network to 128 ports.
- Support single-connection operation initially and retain routing of any simultaneous one-to-one permutation. Reconfiguration may rearrange existing paths; uninterrupted reconfiguration is not promised.
- Build a hierarchical gdsfactory layout with west optical inputs, east outputs, and north/south electrical pads.
- Enforce a 20 um minimum optical centerline bend radius, explicit optical crossing cells, and two metal routing layers connected only by explicit vias.
- Parameterize device footprints, optical/electrical ports, routing clearances, pads, layers, and N. Mark all technology-dependent defaults as illustrative placeholders.
- Optimize the complete die footprint, including electrical fanout and pads, using a bounded, deterministic search over legal floorplans.
- Export GDS, a preview, connectivity and pad maps, switch settings, resolved configuration, and verification/scaling reports.

## Capabilities

### New Capabilities

- `waksman-network`: Exact arbitrary-size topology, stable identifiers, and single/parallel connection state synthesis.
- `parametric-hierarchical-layout`: Configurable placeholder technology, replaceable MZIs, and reusable GDS hierarchy.
- `photonic-electrical-routing`: Curvature-constrained optical interconnects, explicit crossings, and north/south two-metal pad fanout.
- `layout-verification-scaling`: Independent connectivity/geometry checks, export validation, footprint comparison, and reproducible scaling measurements.

### Modified Capabilities

None. This is a greenfield project.

## Impact

The implementation will add a Python package/CLI, example configuration, tests, and documentation. It will use gdsfactory and a pinned compatible Python environment, with KLayout or equivalent geometry support for independent GDS readback checks. Conda is permitted but not required. This planning change creates only OpenSpec artifacts; implementation and dependency installation follow separately.

No foundry PDK, fabrication-ready mask qualification, optical performance simulation, RF design, multicast, or hitless reconfiguration is included. A smaller dual-tree architecture is a conceptual comparison only, not an additional implementation target.
