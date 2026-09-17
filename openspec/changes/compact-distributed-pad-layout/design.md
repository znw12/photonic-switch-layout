## Context

See proposal.md. Each stage has 64 north and 64 south electrical escape trunks in the 128-lane reference network. Existing routing schedules M1 horizontal segments around M1 pad stems, reusing levels when spans are disjoint. Central pad placement prevents effective reuse.

## Goals / Non-Goals

Keep the existing optical topology and component hierarchy; reuse the verified two-metal routing strategy. The 80 µm profile isolates pad placement effects, and the 60 µm profile additionally compacts optics. Do not fold the network, redesign shuffle routing, reduce bend radius, shorten MZIs or merge terminal nets.

## Decisions

- Add `pad_distribution=central|stage`, default central. Stage distribution requires four rows and one optical band.
- Center each stage's local pad group around its escape trunks, clamping it inside the optical core's horizontal bounds. Reject groups that cannot meet inter-group spacing. Allocate four rows with local column numbers; all groups share north/south row heights.
- Pair trunks and pads in increasing x order with explicit stage membership. Schedule the existing global fanout dependency graph; disjoint groups can reuse fanout levels without losing electrical isolation.
- Preserve 100 µm within-group pad pitch, 100 µm row pitch, 60 µm square pads and 25 µm stagger in both reference profiles. Inter-group gaps are determined by stage placement, with at least metal-spacing clearance between group extents.
- Record group identity in electrical manifests/CSV and group extents in reports. Validate slots and group membership against the canonical network, then perform existing independent GDS readback, optical extraction, metal connectivity/spacing and via checks.
- Keep the legacy central report shape compatible; add group metrics only for stage mode. Pad-detail preview selects one stage so individual rows remain readable.

## Risks / Trade-offs

- Physical TFLN devices and foundry rules are still placeholders → clearly report geometric verification limits; keep MZI length/height unchanged.
- Parameter combinations may not fit separated groups or may produce unschedulable fanout → reject the candidate with a diagnostic, never relax spacing.
- Tighter lanes may expose optical or electrical clearance violations → verify both small networks and full 100-port GDS before recommending the profile.

## Migration Plan

Opt-in profiles preserve existing defaults. Keep old output bundles, generate separate new bundles and compare measured dimensions. Repeat the selected profile and compare normalized GDS hashes. Rollback consists of selecting central distribution or the previous profile.
