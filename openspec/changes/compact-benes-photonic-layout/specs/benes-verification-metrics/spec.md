## Purpose

Define reproducible, independent evidence for Beneš functionality, physical geometry, area priority, path uniformity, and scaling.

## ADDED Requirements

### Requirement: Independent functional validation

Verification SHALL traverse the generated graph using emitted switch states independently of the synthesis algorithm. Acceptance SHALL include exhaustive full permutations for P=2, 4, and 8; padded active-port mappings; all 10,000 active single pairs for A=100/P=128; identity, reversal, cyclic shifts, and at least 100 seeded random full active permutations; and complete internal-fabric checks including spare interfaces. Invalid, conflicting, and out-of-range requests SHALL have negative tests.

#### Scenario: Incorrect state assignment
- **WHEN** settings do not reproduce a requested active mapping under independent traversal
- **THEN** the verification result SHALL fail and identify the affected connection

### Requirement: Invariant depth and explicit metric scope

Verification SHALL prove equal switch depth over every full-fabric path, including spare interfaces. Reports SHALL distinguish all-possible-single-path extrema between active interfaces from statistics of paths realized by one specified switch configuration. Global extrema SHALL use exact graph computation with witness paths, not sampled permutations presented as exhaustive evidence.

#### Scenario: Initial depth report
- **WHEN** A=100/P=128 is verified
- **THEN** both minimum and maximum full-fabric switch depth SHALL be 13, and an omitted or bypassed switch SHALL cause failure

#### Scenario: Uniformity report
- **WHEN** a layout report is emitted
- **THEN** it SHALL include active-path geometric length, crossing-count, and bend-count extrema and spreads, and per-configuration path values with mean and standard deviation for each evaluated mapping

### Requirement: Consistent geometry metrics

Reports SHALL define geometric length using explicit component centerline and link lengths including active IO adapters without double counting. They SHALL define bend count as curved-primitive count and additionally report absolute accumulated bend angle. Reports SHALL identify placeholder and state-dependent component contributions and SHALL NOT equate constant switch count or geometric matching with measured loss or group-delay equality.

#### Scenario: Unmodeled physical performance
- **WHEN** placeholder MZI, crossing, or termination geometry is used
- **THEN** performance fields SHALL state their modeling limits instead of reporting unvalidated optical performance as verified

### Requirement: Independent GDS and conductor readback

The verification flow SHALL reopen exported GDS and compare hierarchical geometry and connectivity against the manifest. It SHALL check references/transforms, extents, optical continuity/crossings/radii/clearances, terminal-to-pad connectivity, same-layer shorts/spacing, via enclosure, overpass policy, and termination coverage. Negative fixtures SHALL demonstrate detection of corrupted geometry and electrical connections. The report SHALL distinguish these checks from foundry DRC signoff.

#### Scenario: Export differs from planned geometry
- **WHEN** readback finds a misplaced reference, missing path or via, short, or missing termination despite a valid planning manifest
- **THEN** verification SHALL fail with a concrete discrepancy

### Requirement: Reproducible artifacts and comparisons

Each delivered layout SHALL include hierarchical GDS, a preview, resolved configuration, active/spare interface maps, pad map, topology/settings manifest, and machine-readable verification/area/uniformity reports. Reports SHALL record environment versions, seeds, search settings, and candidate results. Baseline and compact comparisons SHALL use identical constraints. Waksman comparisons SHALL explicitly identify their different internal port and switch counts.

#### Scenario: Repeated generation
- **WHEN** the same resolved configuration, seed, and tool versions are used
- **THEN** topology, switch settings, candidate selection, and normalized geometry/metrics SHALL be reproducible, without requiring identical timestamp metadata bytes

### Requirement: Scaling and regression evidence

Acceptance SHALL include complete generated and readback-verified A/P=4/4, 16/16, 100/128 layouts and a padded small case such as 5/8. It SHALL include topology/solver measurements at P=16, 128, 256, and 1024 and continued success of the Waksman regression suite. Measurements SHALL report their scope, runtime, memory methodology, switch/stage counts, and, for full layouts, cell/reference counts and GDS size.

#### Scenario: Large topology-only benchmark
- **WHEN** P=1024 is evaluated without physical routing
- **THEN** the report SHALL identify 19 stages and 9,728 switches and SHALL label the result topology/solver-only rather than claim a verified 1024-port physical layout

#### Scenario: Objective regression
- **WHEN** candidate-selection tests compare a smaller feasible layout against a larger more uniform layout, and compare equal-area layouts
- **THEN** they SHALL demonstrate strict area priority and the documented secondary tie-breakers
