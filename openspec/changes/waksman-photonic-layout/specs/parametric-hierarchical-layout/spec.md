## Purpose

Define configurable component and technology interfaces and preserve reusable hierarchy in exported large-scale photonic layouts.

## ADDED Requirements

### Requirement: Validated parameterization
The system SHALL accept a versioned configuration covering N, database grid, component dimensions and ports, optical geometry and clearances, electrical layers and rules, pads, margins, and bounded routing/search settings. It SHALL record resolved values, units, placeholder assumptions, and dependency versions. Invalid dimensions, overlapping layer assignments for M1/M2/VIA, or contradictory rules SHALL fail before geometry generation.

#### Scenario: New device dimensions
- **WHEN** a legal MZI length or pad pitch changes
- **THEN** the layout is regenerated using that value without editing network code, and the resolved configuration reports it

#### Scenario: Invalid metal-layer definition
- **WHEN** M1 and M2 are assigned the same GDS layer/datatype
- **THEN** configuration validation rejects the assignment with a specific error

### Requirement: Replaceable component contracts
The system SHALL support replaceable MZI cells with four optical ports, bar/cross transfer pairs, declared electrical terminals/net identities, keepouts, and allowed transforms. Crossing cells SHALL declare through-port pairs. Electrical pad count SHALL follow the declared terminal nets and explicit sharing policy rather than a fixed switch-count multiplier.

#### Scenario: Placeholder replacement
- **WHEN** an MZI replacement satisfies the same logical port contract but has changed dimensions or terminal positions
- **THEN** logical connectivity remains unchanged while placement and routing are recalculated

#### Scenario: Explicit electrical terminal budget
- **WHEN** the N=100 profile assigns separate pads to one control and one return terminal on each MZI
- **THEN** the pad manifest contains 1146 distinct pad assignments with no implicit common-ground merge

### Requirement: Hierarchical deliverable
The exported GDS SHALL preserve a chip-level cell, recognizable recursive network/subnetwork hierarchy, reusable component references, and north/south pad groups. Every physical instance SHALL be traceable to its logical identifier. Repeated identical primitives SHALL use cell references rather than duplicated flattened geometry.

#### Scenario: Inspect delivered hierarchy
- **WHEN** the exported N=100 GDS is reopened
- **THEN** the hierarchy and instance mapping identify all 573 MZIs and preserve references to reusable cells

### Requirement: Deterministic artifact bundle
Successful generation SHALL produce GDS, a preview, resolved configuration, connectivity and physical-route manifests, a pad map, switch states for supplied requests, and verification/metrics reports. Repeated runs SHALL reproduce normalized geometry and connectivity; timestamps and measured timing values are exempt.

#### Scenario: Repeated generation
- **WHEN** the same configuration, connection request, dependency versions, and seed are used twice
- **THEN** normalized geometry/connectivity hashes match and all exported mappings reference consistent IDs
