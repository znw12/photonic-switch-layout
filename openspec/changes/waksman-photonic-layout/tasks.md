## 1. Parameterization and environment

- [ ] 1.1 Create the Python package/CLI and a pinned compatible gdsfactory environment; verify installation, imports, CLI help, and a minimal GDS write/read cycle in a clean environment.
- [ ] 1.2 Implement versioned configuration validation and the illustrative technology profile from design.md, including explicit M2 insulated-overpass windows; verify invalid N, dimensions, layers, and inconsistent clearance rules produce actionable errors.
- [ ] 1.3 Define MZI/crossing port, transfer, terminal-net, keepout, and transform contracts; verify incompatible replacements fail and a compatible larger MZI preserves logical IDs.

## 2. Waksman topology and state synthesis

- [ ] 2.1 Implement exact arbitrary-size recursive topology with stable IDs and bypasses; verify counts for N=1, 2, 3, 16, 25, 100, 101, 256, and 1024 and confirm 573 switches at N=100.
- [ ] 2.2 Implement full-permutation synthesis and deterministic partial-mapping completion; verify duplicate/out-of-range/multicast requests are rejected and filler assignments are labeled inactive.
- [ ] 2.3 Implement an independent state traversal checker; verify all permutations for N=1..7, all 10000 single-pair N=100 requests, identity/reversal/all cyclic shifts, at least 100 seeded N=100 permutations, and odd-size regressions including N=25/101.
- [ ] 2.4 Export logical connectivity and settings with shared IDs; verify repeated requests produce equal normalized exports and deliberately corrupted states fail the independent checker.

## 3. Reusable cells and hierarchy

- [ ] 3.1 Build placeholder MZI, crossing, circular bend, straight, pad, and via cells with declared interfaces; verify dimensions, optical transfer metadata, true bend radius, grid alignment, and via enclosure.
- [ ] 3.2 Build recursive subnetwork and chip-level hierarchy without flattening the delivered design; verify reopened GDS identifies every MZI instance and reuses identical primitive cells.
- [ ] 3.3 Implement recursive placement with explicit optical channels, electrical escape corridors, and a pad-span width budget; verify west/east interfaces and legal component spacing for N=4 and 16.

## 4. Optical routing

- [ ] 4.1 Implement stage permutation routing using explicit crossing schedules and bypass connections; verify requested port ordering and transformed crossing through-pairs on odd/even small networks.
- [ ] 4.2 Route interstage links with circular-bend/S-bend geometry and snap-aware endpoints; verify every link has continuous endpoints, radius >=20 um, and no unauthorized waveguide intersections.
- [ ] 4.3 Add corridor expansion, route manifests, and finite routing budgets; verify a congested case either finds a legal route or fails with affected net IDs rather than exporting a successful incomplete design.

## 5. Two-metal electrical routing and pads

- [ ] 5.1 Derive electrical nets and north/south pad assignments from declared terminals and explicit sharing; verify the separate-control/return N=100 profile yields 1146 pads and a complete pad map.
- [ ] 5.2 Implement obstacle-aware M1/M2 escape and trunk routing with explicit vias and reserved insulated optical-overpass windows; verify clearances, layer transitions, pad escape, and absence of vias in optical-overpass windows on small layouts.
- [ ] 5.3 Implement per-layer conductor extraction and valid-via joining; verify every terminal reaches its intended pad, insulated overlaps remain separate, and missing-via/short/enclosure defects are detected.
- [ ] 5.4 Integrate north/south fanout for N=100; verify zero unrouted electrical nets, no unintentional shared returns, and all pads within the declared die banks.

## 6. Footprint selection and geometric verification

- [ ] 6.1 Implement bounded deterministic candidate search over legal pitches/corridors/pad assignments; verify selected full-die area is no worse than a legal included baseline and tie-breaking follows the documented objective.
- [ ] 6.2 Reconcile placed optical ports and routed geometry with the intended graph, including local component interaction scopes; verify defects involving gaps, unintended intersections, undersized bends, and swapped crossing mappings fail.
- [ ] 6.3 Reopen final GDS and independently check hierarchy, counts, snapped connectivity, geometry rules, vias, and die containment; verify export-induced defects are detected rather than trusting route-success flags.
- [ ] 6.4 Add explicit success/failure reports with normalized hashes and assumption labels; verify incomplete debug artifacts cannot be confused with verified outputs and no report asserts foundry qualification.

## 7. Complete demonstrator and scaling evidence

- [ ] 7.1 Expose generation, state synthesis, verification, and benchmark CLI commands with documented example configurations; verify commands reproduce GDS, preview, manifests, pad map, settings, resolved configuration, and reports.
- [ ] 7.2 Deliver fully routed N=4, 16, and 100 examples; verify logical, geometry, and GDS-readback acceptance, zero unresolved nets, and deterministic normalized geometry on repeated runs.
- [ ] 7.3 Benchmark topology/solver for N=16, 100, 256, and 1024 and record required geometry metrics for completed layouts; verify reports include timings, measurable memory, switch/cell counts, GDS size, core/die bounds, pad/via totals, and optical path/crossing metrics.
- [ ] 7.4 Document component replacement, illustrative pad/overpass assumptions, single-input darkness, rearrangement behavior, and scale limits; verify the documented N=100 example runs from the pinned environment and any larger bounded experiments are honestly labeled.
