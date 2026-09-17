## 1. Separate package and parameter contract

- [ ] 1.1 Add the independent Beneš package and CLI alongside Waksman using the pinned environment; verify both command interfaces load and use separate output paths.
- [ ] 1.2 Define serializable active/internal port counts, input/output maps, technology geometry, margins, and search settings; verify default 100/128, boundary cases 1/2 and 2/2, non-default maps, round trips, and invalid inputs.
- [ ] 1.3 Define replaceable optical/electrical component port contracts and manifest identifiers; verify malformed component ports fail before layout generation.

## 2. Complete Beneš topology and switch synthesis

- [ ] 2.1 Implement the full recursive topology with stable stage/switch identifiers; verify stage counts, switch counts, absence of bypasses, and constant complete-fabric depth for P=2, 4, 8, 128, and 1024.
- [ ] 2.2 Implement deterministic permutation synthesis and partial active-request completion; verify all permutations for P=2/4/8 using an independent graph traversal.
- [ ] 2.3 Implement active/spare translation and request validation; verify a padded 5/8 case, non-default maps, single dark-input operation, and duplicate/out-of-range/spare-ID rejection.
- [ ] 2.4 Validate 100/128 connectivity across all 10,000 active single pairs, identity/reversal/cyclic full active mappings, at least 100 seeded random full active permutations, and complete 128-interface mappings; retain a reproducible functional report.

## 3. Hierarchical physical baseline

- [ ] 3.1 Build gdsfactory MZI, crossing, analytic bend, pad, via, and spare-termination placeholders with declared port and centerline metadata; verify dimensions, radius constraints, layer assignments, and reusable cell references.
- [ ] 3.2 Build the regular stage array and explicit logical-to-physical maps; verify each logical switch appears exactly once and legal row transformations preserve graph connectivity.
- [ ] 3.3 Implement the new structured interstage router using repeated shuffle/unshuffle groups and explicit crossings; verify small fabrics have continuous intended paths, minimum-radius bends, and no undeclared optical intersections.
- [ ] 3.4 Route west/east active adapters and all spare terminations; verify 100 active interfaces plus 28 connected spare terminations per side for the initial design.
- [ ] 3.5 Export a conservative hierarchical Beneš baseline including component, stage, routing, IO/termination, and bank structure; verify readback cell/reference counts and complete logical edge coverage.

## 4. Electrical fanout and complete die bounds

- [ ] 4.1 Allocate deterministic global north/south pad banks and terminal maps; verify 1,664 distinct pads and nets, balanced 832 per bank, and the 83,160 um bank-span lower bound under default pad geometry.
- [ ] 4.2 Route M1 escapes and M2 trunks with explicit vias and configured optical overpass windows; verify every terminal reaches only its assigned pad and no return nets are merged.
- [ ] 4.3 Enforce metal spacing, widths, via enclosures, and optical keepouts from actual geometry; verify missing-via, same-layer short, and prohibited optical-overpass fixtures fail.
- [ ] 4.4 Derive grid-quantized die bounds after optical/electrical/termination routing and margins; verify all geometry lies inside the bounds and report core, fanout, termination, bank, and complete-die extents.

## 5. Verification and uniformity metrics

- [ ] 5.1 Implement exact stage-DAG extrema and witness paths for full-fabric switch depth and active-interface length/crossing/bend metrics; cross-check small cases by exhaustive path enumeration and reject a deleted or bypassed switch.
- [ ] 5.2 Implement per-configuration path traces and statistics, including IO/component lengths, curved-primitive counts, and absolute bend angles; verify hand-computable fixtures and explicit separation from global extrema and unmodeled optical performance.
- [ ] 5.3 Implement independent GDS hierarchy, geometry, optical-continuity, radius, crossing, and clearance checks; verify corrupted references, missing routes, too-tight bends, and missing terminations are detected.
- [ ] 5.4 Implement conductor/via readback connectivity and spacing checks independent of intended net labels; verify open and short fixtures fail and a complete valid baseline passes.

## 6. Area-first optimization

- [ ] 6.1 Define a bounded deterministic candidate search over legal stage gaps, row orders, pitches, and routing corridors under fixed technology/package constraints; verify candidate provenance and rejection reasons are reproducible.
- [ ] 6.2 Rank fully verified candidates by exact die area, then length/crossing/bend spread, routed length, and stable identifier; verify a larger more uniform candidate loses and equal-area candidates follow each tie-breaker.
- [ ] 6.3 Compare compact candidates against the verified conservative baseline and retain the best feasible result; verify fallback when no improvement exists and report paired full-chip metrics without claiming global optimality.
- [ ] 6.4 Add optional footprint-preserving equalization with default off; verify enabled matching never expands the selected die and reports residual spread when interior space is insufficient.

## 7. Deliverables, scalability, and compatibility

- [ ] 7.1 Deliver generation, solve, verify, and benchmark workflows with resolved configuration, GDS, preview, interface/pad maps, settings/geometry manifest, and machine-readable reports; verify end-to-end artifact completeness on a small design.
- [ ] 7.2 Generate and independently readback-verify complete 4/4, 5/8, 16/16, and 100/128 examples; retain representative reports and reproducible configurations, including 13-stage/832-switch/1,664-pad evidence for the initial target.
- [ ] 7.3 Measure topology/solver scaling at P=16, 128, 256, and 1024 and full-layout runtime, memory methodology, hierarchy counts, and GDS size where generated; verify reports distinguish topology-only results from physical-layout completion.
- [ ] 7.4 Document regeneration, architecture comparison, priority ordering, operating assumptions, and replacement of placeholders; verify a repeated seeded run reproduces normalized geometry, settings, selection, and metrics.
- [ ] 7.5 Run the complete Beneš acceptance suite and existing Waksman regressions; verify all pass and that prior Waksman commands/examples remain usable before marking implementation complete.
