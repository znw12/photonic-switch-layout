## Purpose

Provide four staggered rows of independently connected north/south electrical pads for a single-band Beneš photonic layout, with auditable geometry, complete die dimensions and reproducible physical verification.

## ADDED Requirements

### Requirement: Four-row single-band profile

The generator SHALL provide a profile with one horizontal optical band and four pad rows on each north/south side. For 100 active ports and 128 internal ports it MUST retain 13 complete stages, 832 MZIs, 1664 dedicated pads, all spare interfaces and reusable crossing cells. Every optical bend centerline radius MUST remain at least 20 μm.

#### Scenario: Full-size profile
- **WHEN** the four-row 100-port profile is generated successfully
- **THEN** each side contains 832 pads, with 208 pads in each of four rows, and the complete canonical Beneš network is physically connected within one band.

#### Scenario: Partially filled final column
- **WHEN** a smaller supported network has a per-side pad count not divisible by four
- **THEN** each actual electrical terminal still has exactly one pad, no dummy nets or pads are introduced, row populations differ by at most one and empty rows are allowed when fewer than four pads are needed.

### Requirement: Physical row staggering

The generator SHALL accept a finite nonnegative row-stagger parameter with default zero. The new profile SHALL use 25 μm per adjacent row, 60 × 60 μm pads and 100 μm row/column center pitches. Both banks MUST number rows from the optical network outward and shift row centers by 0, 25, 50 and 75 μm in the same global +x direction before any common bank-centering translation. The exported pad polygons MUST realize the requested offsets.

#### Scenario: Four staggered rows
- **WHEN** the new default profile is generated
- **THEN** corresponding pad columns in consecutive rows differ by 25 μm in x, while row separation is 100 μm toward the appropriate chip edge and within-row column pitch is 100 μm.

#### Scenario: Zero-stagger control
- **WHEN** four rows and zero stagger are requested for a single band
- **THEN** corresponding pad columns align physically while their terminal nets remain distinct and connected.

#### Scenario: Unsupported parameters
- **WHEN** staggering is negative, nonfinite, off the database grid, spans a full column pitch across the four rows, or is requested outside the supported four-row single-band profile
- **THEN** generation rejects the configuration with a specific reason; existing zero-stagger one-to-three-row modes remain supported.

### Requirement: Independent two-metal electrical routing

Each MZI terminal MUST reach exactly one assigned pad through M1/M2 and three explicit vias, with no shared returns or unintended connections. M1 stems underneath other M2 pads SHALL remain insulated except at their assigned pad connection. Wire spacing, minimum width, via enclosure and approved straight-waveguide overpass constraints MUST pass physical checks.

#### Scenario: Complete extraction
- **WHEN** the generated 100-port GDS is independently read back
- **THEN** extraction finds 1664 distinct terminal-to-pad nets, 4992 vias, no electrical opens or shorts and no unassigned conductor islands.

#### Scenario: Added via underneath a foreign pad
- **WHEN** a via accidentally joins a stem to another net's pad
- **THEN** verification rejects the design even if the altered polygons agree with its manifest.

### Requirement: Accurate dimensions and pad exports

The report SHALL distinguish actual pad-bank bounds, full routed die dimensions and any pad-only width bound. Full die bounds MUST include the optical network, fanout, staggered pads, terminations and margins. Pad records SHALL expose side, row, column, requested row offset, actual center and via coordinates; previews SHALL include a readable pad-bank detail.

#### Scenario: Default bank extent
- **WHEN** a bank has four rows of 208 pads at the default geometry
- **THEN** its reported physical extent is 20.835 mm wide and 0.360 mm high, and the report does not present this as the full chip size or as evidence of meeting a 20 mm chip-width target.

#### Scenario: Outermost pad omitted from bounds
- **WHEN** declared bounds omit any staggered pad polygon
- **THEN** independent verification rejects the bundle.

### Requirement: Compatibility and repeatability

Existing zero-stagger one-to-three-row configurations and folded profiles SHALL retain their physical behavior. Successful new bundles MUST pass graph, optical geometry, electrical extraction and GDS hierarchy/polygon readback checks. Repeating a new profile with the same configuration and connections SHALL reproduce normalized geometry and path metrics.

#### Scenario: Regression and repeated generation
- **WHEN** existing regression cases and two independent generations of the new full-size profile are evaluated
- **THEN** existing cases pass, and the new generations have identical normalized geometry hashes, pad mappings, dimensions and path statistics.

#### Scenario: Optical geometry retained
- **WHEN** the new four-row profile is compared with a single-band reference having the same optical routing parameters
- **THEN** the complete topology, MZI placements and interstage optical geometry are retained, with any required external IO extension accounted for explicitly.
