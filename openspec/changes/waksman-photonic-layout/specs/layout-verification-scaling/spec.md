## Purpose

Provide independent evidence that exported photonic layouts preserve intended connectivity and geometry, and quantify behavior as network size grows.

## ADDED Requirements

### Requirement: Independent functional verification
Switch-state verification SHALL traverse a network model independently of the solver. Acceptance SHALL include all permutations for N=1 through 7; all 10000 single-pair requests at N=100; identity, reversal, every cyclic shift, and at least 100 seeded random full permutations at N=100. Odd-size topology/solver regression SHALL include N=25 and 101. Passing samples SHALL not be described as exhaustive verification of all 100! permutations.

#### Scenario: Incorrect synthesized state
- **WHEN** a deliberately altered switch state breaks a requested connection
- **THEN** independent verification identifies the mismatched input/output path

### Requirement: Geometry and netlist reconciliation
The system SHALL reconcile routed geometry and transformed component ports with the intended logical graph and SHALL check curvature, continuity, unintended intersections, spacing, via rules, die containment, and terminal-to-pad connectivity. Electrical extraction SHALL compare physical conductor partitions with expected nets. Optical extraction SHALL honor local MZI/crossing transfer contracts rather than treating every polygon overlap as a connection.

#### Scenario: Missing electrical via
- **WHEN** the only via between a terminal route and its pad route is removed
- **THEN** the verifier reports an open circuit despite the route manifest claiming completion

#### Scenario: Invalid optical connection
- **WHEN** a waveguide is severed or a crossing's through-port mapping is swapped
- **THEN** geometry/netlist reconciliation reports the affected edge or path

### Requirement: Export readback and defect detection
The system SHALL reopen the delivered GDS and check hierarchy, component counts, transformed interfaces, connectivity, and configured geometry constraints on readback data. Acceptance SHALL include injected waveguide gaps, unintended intersections, undersized bends, metal shorts, missing vias, and insufficient via enclosures. Reports SHALL separate logical and geometric outcomes from unassessed physical performance.

#### Scenario: Export introduces a gap
- **WHEN** grid snapping or export creates an optical endpoint gap
- **THEN** readback verification fails even if the pre-export route was marked complete

### Requirement: Reproducible scalability evidence
The system SHALL deliver fully routed, verified geometries for N=4, 16, and 100 and topology/solver measurements for N=16, 100, 256, and 1024. Reports SHALL record configuration/seed, stage timings, measurable peak memory, switch/cell counts, GDS size, core/die dimensions, path lengths/crossings, pad/via totals, and unresolved routes. Larger geometry experiments SHALL distinguish completed, infeasible, and budget-exhausted outcomes.

#### Scenario: Hundred-port acceptance
- **WHEN** the N=100 example is accepted
- **THEN** its exported layout has zero unrouted optical/electrical nets, passes logical/geometric/readback checks, and includes all required reports

#### Scenario: Larger topology-only benchmark
- **WHEN** N=1024 topology and state synthesis complete without geometric routing
- **THEN** the result is labeled topology/solver-only and makes no claim of a routed or manufacturable 1024-port chip
