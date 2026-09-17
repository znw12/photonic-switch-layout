## Purpose

Define a complete regular Beneš fabric with explicit active and spare ports, deterministic state synthesis, and invariant switch depth.

## ADDED Requirements

### Requirement: Complete power-of-two fabric

The system SHALL construct a complete standard Beneš network for internal port count P=2^k, P>=2, with 2k-1 stages and P/2 two-by-two switches per stage. It SHALL retain every internal switch and link regardless of active port count A. Every internal input-to-output path SHALL traverse exactly 2k-1 switches.

#### Scenario: Initial 100-port design
- **WHEN** the user generates the default A=100 design
- **THEN** P SHALL be 128, with 13 stages, 64 switches per stage, 832 switches total, and 13 switches on every path

#### Scenario: Supported parameter range
- **WHEN** A is a positive integer and P is omitted
- **THEN** P SHALL be the smallest power of two at least max(2, A), including a single-stage P=2 fabric for A=1 or A=2

#### Scenario: Invalid internal size
- **WHEN** an explicit P is not a power of two, is below 2, or is smaller than A
- **THEN** generation SHALL fail with an actionable configuration error

### Requirement: Explicit active and spare interfaces

The system SHALL expose A numbered west inputs and A numbered east outputs through separate configurable injective maps into the P internal interfaces. Default maps SHALL select indices 0 through A-1. All spare input and output interfaces SHALL remain in the topology and SHALL have identified placeholder terminations in the physical design and manifest.

#### Scenario: Padded initial fabric
- **WHEN** the A=100, P=128 design is generated
- **THEN** its manifest SHALL identify 100 active interfaces and 28 spare terminations on each optical side without deleting or bypassing internal switches

#### Scenario: Invalid or remapped interfaces
- **WHEN** a map contains duplicates or out-of-range indices
- **THEN** it SHALL be rejected; valid non-default maps SHALL preserve the external port identities in synthesis and physical adapters

### Requirement: One-to-one routing and reproducible settings

The system SHALL synthesize bar/cross settings for arbitrary partial injective active-port mappings and full active permutations. It SHALL complete unused internal assignments deterministically and emit settings using stable stage/switch identifiers. Independent traversal of those settings SHALL reproduce every requested connection.

#### Scenario: Concurrent permutation
- **WHEN** 100 distinct inputs are assigned to 100 distinct outputs
- **THEN** one switch configuration SHALL realize all 100 connections simultaneously through the complete 128-port fabric

#### Scenario: Single active connection
- **WHEN** one active input is requested at one active output
- **THEN** the settings SHALL route that pair, and the operating description SHALL require unrequested inputs to be dark rather than claiming that unused MZIs block light

#### Scenario: Conflicting or spare-port request
- **WHEN** a request repeats an input or output, or names a spare interface as an external active port
- **THEN** the solver SHALL reject it with a diagnostic and SHALL NOT emit success settings

### Requirement: Rearrangeable operating semantics

The interface and documentation SHALL describe the network as rearrangeably nonblocking and SHALL NOT promise that adding a connection preserves existing switch states or is hitless.

#### Scenario: Reconfiguration
- **WHEN** a new complete requested mapping differs from the current mapping
- **THEN** the solver MAY change any switch state and SHALL validate the resulting complete requested mapping
