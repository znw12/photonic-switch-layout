## Purpose

Provide compact hierarchical photonic switch layouts with reduced optical pitch, local shared grounds, and verified independent signal connections.

## ADDED Requirements

### Requirement: Compact optical fabric
The compact reference SHALL have 100 active inputs and outputs, 128 internal lanes, 25 um MZI optical port spacing, 1000 um MZI length, bend radii >=20 um and reusable fixed 20x20 um cosine crossing cells. Continuous diagonal mesh spacing SHALL be 25*sqrt(2) um, with explicit radius-compliant end transitions.

#### Scenario: Generate compact optical network
- **WHEN** the compact reference is generated
- **THEN** all optical routes have connected paired ports, valid clearance and 13 MZI stages, with inputs west and outputs east.

### Requirement: Local shared grounding
The reference SHALL retain 832 independent S pads and use four G pads on each of the north and south sides. Ground aggregation SHALL occur in the array, not through one long external G route per MZI. Pad banks SHALL use three rows and same-row spacing >=120 um.

#### Scenario: Read back electrical conductors
- **WHEN** the generated GDS is independently extracted
- **THEN** all 1664 G electrodes and eight G pads are on one ground net, each S is connected only to its own pad, and there are 833 electrical nets without unassigned metal islands.

### Requirement: Simplified leads and accountable verification
The compact MZI SHALL use a straight signal export without the previous small electrical doglegs. Reports SHALL include real die dimensions, pad count, measured turn counts and verification results. Existing reference configurations SHALL remain supported.

#### Scenario: Compare reference outputs
- **WHEN** the compact matrix completes validation
- **THEN** separate GDS and previews are exported and compared with the previous reference without claiming unverified optical or RF performance.

#### Scenario: Detect defective geometry
- **WHEN** a ground connection is severed, a signal is shorted, or an optical transition violates clearance
- **THEN** the corresponding geometric or GDS extraction check fails.
