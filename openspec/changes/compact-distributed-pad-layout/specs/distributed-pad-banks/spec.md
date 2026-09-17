## Purpose

Reduce single-band Beneš layout area by distributing electrical pads by optical stage and supporting verified tighter optical lane spacing while preserving independent terminal connections.

## ADDED Requirements

### Requirement: Explicit stage-distributed pad placement
The generator SHALL support an opt-in stage distribution for four north and four south pad rows in a single optical band, preserving centralized placement as the default. Each stage SHALL connect only to its own pad group on each side, with one independent pad per terminal. Configured staggering and within-group pitches MUST be preserved; separated groups MUST satisfy metal spacing.

#### Scenario: Full 100-port layout
- **WHEN** the 128-lane 100-port profile uses stage distribution and 25 µm stagger
- **THEN** each side has 13 groups of 64 pads, with 16 pads in each of four rows per group, and all terminal nets remain separate.

#### Scenario: Small or invalid configurations
- **WHEN** a smaller network or unsupported distribution is requested
- **THEN** partial local columns are supported, and incompatible row/band settings or unrouteable spacing are rejected rather than silently changed.

### Requirement: Verified lane-pitch compaction
The system SHALL provide separate 80 µm and 60 µm lane-pitch reference profiles, preserving the 20 µm minimum bend radius, 1000 µm MZI length, Beneš logical network and switch/crossing hierarchy. Dimensions SHALL be measured from generated layouts rather than estimates.

#### Scenario: Sequential optimization comparison
- **WHEN** both reference profiles are generated
- **THEN** reports distinguish pad distribution and lane pitch, compare actual dimensions against the central four-row baseline, and identify which output bundles passed verification.

### Requirement: Independent pad-group verification and reproducibility
Artifacts SHALL expose group identity and actual occupied extents. Verification MUST detect wrong stage assignment, missing or duplicate slots, incorrect stagger, pad shape/bounds errors, disconnected nets, shorts and spacing violations using the manifest and independent GDS readback. Repeated identical generation SHALL produce the same normalized geometry hash.

#### Scenario: Tampered group or geometry
- **WHEN** group membership or physical pad/routing geometry is corrupted
- **THEN** verification fails even when the recorded net counts are unchanged.

#### Scenario: Repeated full-size build
- **WHEN** the selected full-size profile is generated twice
- **THEN** both bundles pass verification and their normalized geometry hashes agree.
