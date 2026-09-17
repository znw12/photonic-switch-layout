## Purpose

Generate and compare narrower large Beneš photonic layouts with multirow electrical pads and folded optical bands while preserving independent physical and logical verification.

## ADDED Requirements

### Requirement: Multirow electrical pads
The generator SHALL support two or three rows on each north/south bank with dedicated terminals, M1/M2 routing and explicit vias, while preserving the single-row baseline. It MUST include fanout and pads in reported extents.

#### Scenario: Two and three rows
- **WHEN** a 100-active-port design is generated with either row count
- **THEN** all 1664 pads are connected to distinct terminal nets and row pitch and same-layer spacing pass verification.

### Requirement: Folded optical fabric
The generator SHALL support odd horizontal band counts, preserve complete Beneš topology and west/east active interfaces, and use hierarchical crossings and bends with centerline radius at least 20 µm.

#### Scenario: Folded routing
- **WHEN** a supported multi-band layout is generated
- **THEN** all canonical graph edges have continuous physical routes and every stage retains all its MZIs, including spare-lane stages.

### Requirement: Reproducible physical comparison
The system SHALL compare straight two/three-row and folded candidates using actual routed width, height, area and path metrics. Successful candidates MUST pass independent manifest and GDS readback checks. The 20 mm width target SHALL be advisory and pad-count bounds SHALL be reported.

#### Scenario: Target cannot be met
- **WHEN** fixed pad geometry requires more than 20 mm
- **THEN** the report states the bound and actual dimensions without changing pad count or reporting false success against the width target.

#### Scenario: Invalid geometry
- **WHEN** routing contains a short, disconnected optical edge, bad radius or unintended intersection
- **THEN** verification rejects it and the candidate is not presented as a verified design.
