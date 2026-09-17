## Purpose

Define physically checked Beneš optical interconnects and two-metal fanout to north and south pad banks, including all spare interfaces.

## ADDED Requirements

### Requirement: Structured interstage routing

The router SHALL derive connections from the full Beneš graph, use repeated shuffle/unshuffle groups and reusable routing blocks, and preserve every stage-to-stage connection under physical row reordering. Every declared edge SHALL correspond to a continuous routed optical path with compatible endpoints.

#### Scenario: Physical row reordering
- **WHEN** a candidate changes the physical order of logical lanes
- **THEN** its mapping and interstage routes SHALL preserve the original graph connectivity and independent traversal results

### Requirement: Optical geometry rules

All curved optical centerlines, including those within placeholder components and IO/termination adapters, SHALL have radius at least 20 um and satisfy the configured larger minimum if applicable. Waveguide clearances SHALL hold except inside explicitly declared component connection or crossing regions. Intended waveguide intersections SHALL use identified crossing cells with paired through-port semantics; accidental intersections SHALL fail verification.

#### Scenario: Intended crossing
- **WHEN** two paths cross at a declared crossing primitive
- **THEN** both through connections SHALL remain distinct logical channels and SHALL be counted in the paths that traverse them

#### Scenario: Invalid geometry
- **WHEN** readback finds an undeclared optical intersection, insufficient clearance, a discontinuity, or a below-radius bend
- **THEN** the candidate SHALL fail physical verification

### Requirement: Active adapters and spare terminations

All active ports SHALL have continuous adapters to their mapped internal interfaces. Every spare interface SHALL have a replaceable termination cell with a connected optical port, an identifier, and a reported footprint inside the die. Documentation SHALL identify terminations as unqualified placeholders.

#### Scenario: Missing spare termination
- **WHEN** one of the 28 spare inputs or 28 spare outputs in the default fabric lacks a connected termination
- **THEN** the layout SHALL fail verification even if all active connections remain routable

### Requirement: Complete two-terminal electrical fanout

Every MZI SHALL have two independently routed placeholder terminals, each connected to its own designated pad using only M1, M2, and explicit vias. Default pad placement SHALL use balanced single-row north and south banks. Different terminal nets SHALL NOT be merged, including return nets. The port/pad map SHALL identify every switch, terminal, net, layer transition, and pad.

#### Scenario: Full-size electrical connectivity
- **WHEN** the default 832-MZI layout is generated
- **THEN** it SHALL contain 1,664 distinct terminal-to-pad connections, with 832 pads in each bank

#### Scenario: Electrical fault
- **WHEN** a required via is absent, a net is open, or two independent nets are shorted through actual conductor polygons or vias
- **THEN** verification SHALL reject the candidate regardless of the intended net labels

### Requirement: Electrical clearances and optical overpasses

Routing SHALL satisfy configured same-layer spacing, conductor width, via enclosure, and optical-device keepouts. Insulated M2-over-straight-waveguide windows MAY be used only under an explicitly reported placeholder stack assumption. Vias SHALL NOT occupy those windows; MZIs, optical bends, and crossings SHALL retain their declared keepouts.

#### Scenario: Permitted overpass
- **WHEN** an M2 trunk crosses a straight waveguide within a declared permitted window
- **THEN** the geometry MAY pass validation only if the stack assumption and remaining keepouts are satisfied

#### Scenario: Via over optical route
- **WHEN** a via lies in an optical overpass window or violates an optical component keepout
- **THEN** the candidate SHALL fail verification
