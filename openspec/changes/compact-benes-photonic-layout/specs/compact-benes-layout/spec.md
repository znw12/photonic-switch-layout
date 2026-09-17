## Purpose

Define parameterized hierarchical Beneš layouts that minimize complete-chip area before optimizing physical path uniformity.

## ADDED Requirements

### Requirement: Independent additive implementation

The system SHALL provide a separate Beneš generation interface, topology, solver, and placement/routing flow. It SHALL preserve existing Waksman commands and examples and SHALL NOT implement Beneš by relabeling the Waksman topology or invoking its router unchanged.

#### Scenario: Both implementations installed
- **WHEN** the new version is installed in the existing environment
- **THEN** users SHALL be able to generate each architecture independently into separate output locations

### Requirement: Parameterized replaceable components

The system SHALL expose active/internal port counts and mappings, device footprint/ports, optical routing rules, pad geometry, metal/via rules, termination geometry, die margins, database unit, and bounded search settings in a serializable configuration. Optical minimum bend radius SHALL default to 20 um and SHALL NOT be configured below 20 um for this design. TFLN MZIs, crossings, and terminations SHALL have replaceable geometry and declared port contracts.

#### Scenario: Device geometry changes
- **WHEN** a valid larger MZI footprint or pad pitch is selected
- **THEN** placement, routing, die bounds, and verification SHALL use the new values without editing topology-specific source constants

#### Scenario: Invalid physical configuration
- **WHEN** dimensions, port positions, or clearances cannot satisfy the declared rules
- **THEN** the generator SHALL reject the configuration or report no feasible candidate without exporting a successful layout

### Requirement: Preserved layout hierarchy

The GDS SHALL contain reusable component references and explicit fabric, stage, interstage routing, IO/termination, and pad-bank structure. All stages SHALL use the same configured MZI primitive. Default export SHALL preserve hierarchy.

#### Scenario: Full-size GDS readback
- **WHEN** the 100-active-port output is reopened independently
- **THEN** its hierarchy SHALL resolve to 13 full stages and 832 MZI instances using shared primitive cells, with reported cell/reference counts

### Requirement: Complete-chip area has strict priority

The system SHALL first reject candidates violating topology or physical constraints. It SHALL compare feasible candidates under the same device/package rules by exact database-grid die area, including pads, fanout, active adapters, spare terminations, and margins. It SHALL use active-path length spread, crossing-count spread, and bend-count spread, in that order, only as lexicographic secondary objectives. Remaining ties SHALL use total routed waveguide length and a stable identifier. It SHALL NOT use a weighted objective or area tolerance that selects a larger die for improved uniformity.

#### Scenario: Smaller candidate has worse path spread
- **WHEN** two valid candidates have different areas and the larger has better uniformity
- **THEN** the smaller-area candidate SHALL rank first

#### Scenario: Equal-area candidates
- **WHEN** two valid candidates have exactly equal die area on the export grid
- **THEN** path-length spread SHALL decide first, followed by crossing and bend spreads when preceding metrics tie

### Requirement: Bounded search and honest comparison

The system SHALL retain a fully verified conservative Beneš baseline, evaluate a reproducible bounded candidate set, and report feasibility, final footprints, objective values, and rejection reasons. It SHALL select the best verified candidate including the baseline and SHALL state search limits rather than claim global optimality. It SHALL report pad-span constraints and core/fanout/termination/die extents separately.

#### Scenario: No improved candidate
- **WHEN** all alternative candidates are invalid or rank below the baseline
- **THEN** the baseline SHALL be selected and the report SHALL state that no improvement was found

#### Scenario: Packaging span
- **WHEN** 832 pads occupy each single-row bank with 60 um pad width and 100 um pitch
- **THEN** the report SHALL identify a minimum bank span of 83,160 um before margins

### Requirement: Footprint-preserving optional equalization

Length-matching meanders SHALL be disabled by default. Optional equalization SHALL preserve the selected die bounds and all physical rules; unattainable matching SHALL be reported as residual nonuniformity without expanding the chip solely to equalize paths.

#### Scenario: Insufficient matching space
- **WHEN** optional equalization requires more than the available interior area
- **THEN** the result SHALL retain the die bounds and report unmatched paths and residual spread
