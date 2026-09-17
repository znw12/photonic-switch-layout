## Purpose

Define legal optical and electrical routing, external port placement, and the footprint objective for a complete photonic switching die.

## ADDED Requirements

### Requirement: Curvature-constrained optical interconnects
The system SHALL place inputs on the west and outputs on the east, connect every intended optical edge, and enforce at least 20 um minimum centerline curvature radius for the initial profile, including component bends and S-bends. It SHALL verify endpoint continuity after database-grid snapping and distinguish curve radius from polygonization tolerance. Ports SHALL keep their intended mapping rather than being silently reordered by a router.

#### Scenario: Tight interstage space
- **WHEN** an optical route cannot satisfy the bend radius or clearance in its allocated corridor
- **THEN** the system expands/replans within its search budget or reports the route as infeasible without violating the radius

### Requirement: Explicit optical crossings
Every intentional interconnect intersection SHALL use an identified crossing cell with declared through-port pairs. Unintended waveguide intersections outside declared component interaction regions SHALL fail verification. Crossing instances SHALL appear in route and path metrics.

#### Scenario: Permuted channel order
- **WHEN** a stage boundary requires two channels to exchange order
- **THEN** routing preserves their logical destinations using declared crossing geometry, and verification follows the transformed through-port pairs

### Requirement: Two-metal north and south electrical fanout
The system SHALL route all declared MZI electrical nets to pads exclusively on the north/south edges using two metal layers and explicit vias. It SHALL enforce metal spacing, via enclosure, pad escape rules, and configured optical/electrode keepouts. Layer overlap SHALL connect nets only where a valid via exists. Intended sharing SHALL be explicit in the netlist.

#### Scenario: Cross-layer insulated overlap
- **WHEN** distinct M1 and M2 nets overlap without a via
- **THEN** electrical extraction keeps them separate

#### Scenario: Complete terminal fanout
- **WHEN** N=100 generation succeeds
- **THEN** every declared terminal has its intended pad connection, all pads are in north/south banks, and no electrical nets remain unrouted or unintentionally shorted

### Requirement: Full-die footprint objective
The system SHALL optimize the complete die bounding-box area including pads, fanout, component keepouts, and margins over a finite reproducible candidate set. It SHALL report the conservative baseline, selected verified candidate, pad-bank width bound, candidate failures, and search budget. Ties SHALL prefer fewer worst-path optical crossings, then shorter total optical route length. It SHALL not claim a global minimum.

#### Scenario: Pads dominate width
- **WHEN** the required pad-bank span exceeds the optical core width
- **THEN** the die width accommodates the bank and the report separates core and complete-die dimensions

### Requirement: Infeasibility is observable
The system SHALL return failure with affected net IDs and constraint diagnostics when no fully routed verified candidate exists within its budget. An incomplete debug artifact SHALL be clearly labeled and SHALL NOT be reported as a successful layout.

#### Scenario: Exhausted routing budget
- **WHEN** a configuration cannot be routed before its candidate or routing budget is exhausted
- **THEN** generation exits unsuccessfully and reports unresolved connections and the exhausted budget
