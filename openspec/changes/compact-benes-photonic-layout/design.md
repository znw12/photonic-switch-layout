## Context

The repository contains a working gdsfactory Waksman generator, a pinned Python environment, independent connectivity/geometry checks, and N=4/16/100 examples. Its 100-port fabric has 573 MZIs and possible single-connection depths from 4 to 13. The new version addresses switch-depth uniformity with a complete standard Beneš topology and a separately developed placement/routing engine.

The accepted priority is **physical feasibility and complete Beneš topology as hard constraints, then minimum complete-chip area, then physical path uniformity**. Equal switch depth is mandatory; equal geometric length, crossing count, or optical loss is not. The decisions below define the implementation; measured acceptance evidence is recorded at the end of this document.

## Goals / Non-Goals

**Goals:**

- Expose 100 west optical inputs and 100 east optical outputs through a full 128-port fabric: 13 stages, 64 MZIs per stage, 832 MZIs total.
- Support arbitrary simultaneous one-to-one mappings as well as single-illuminated-input operation, with deterministic switch settings.
- Demonstrate parameterization, hierarchy, routing strategy, scalability, and verification as separately testable capabilities.
- Use replaceable TFLN MZI placeholders, optical bend radius at least 20 um, and two metal layers plus vias connecting every switch to north/south pads.
- Minimize the measured complete die area within a documented, bounded candidate search; quantify uniformity without sacrificing this objective.
- Preserve the Waksman package, CLI, examples, and regression tests.

**Non-Goals:**

- Foundry-qualified TFLN devices, calibrated voltages, measured insertion loss, group-delay matching, or fabrication signoff.
- Pruned/padded Waksman disguised as Beneš, bypassing switch stages, or removing switches reachable only through currently unused ports.
- Hitless reconfiguration, a global mathematical area optimum, or a guarantee of being smaller than the 573-switch Waksman version.
- Redesigning the package around multiplexed controls or shared return pads in this change.

## Decisions

### 1. Separate implementation and explicit configuration

Add a `benes_layout` package and `benes-layout` CLI alongside the existing package. Reuse the pinned gdsfactory/KLayout environment. Only reviewed technology-neutral geometry/export utilities may be shared; the topology, solver, placement, routing, and metric definitions belong to the new implementation. Outputs go into separate Beneš directories.

Configuration distinguishes active port count A from internal count P. Default P is the smallest power of two at least max(2, A); explicit P must be a power of two and at least A. Thus A=1 has a well-defined P=2 fabric. Separate injective input/output maps default to internal indices 0 through A-1. Invalid maps, unsupported dimensions, and impossible geometric constraints fail before export.

All geometric lengths use um with an explicit GDS database unit. Parameters cover MZI footprint and optical/electrical ports, waveguide width/clearance, bend radius, crossing and termination cells, lane pitch, metal widths/spacings, via size/enclosure, pad dimensions/pitch, die margins, and bounded search settings. The initial technology profile derives from the existing placeholders (including 60 um pads on 100 um pitch), but derived geometry must be recomputed for every valid profile.

### 2. Full standard Beneš topology and deterministic synthesis

For P=2^k, create 2k-1 stages of P/2 identical 2x2 switches, with (P/2)(2k-1) switches overall. Use the standard recursive construction with P/2 switches on each boundary and two P/2-port subnetworks, ending at one 2x2 switch. Stable stage/switch identifiers make logical and physical records traceable.

Develop a recursive permutation solver using alternating coloring of the input/output pairing graph. Complete a partial active mapping to a full internal permutation deterministically before synthesis. Unrequested active inputs and spare inputs are assumed dark during single-connection operation; bar/cross MZIs are not shutters. Independent graph traversal must recover the requested mapping from emitted switch states. Reconfiguration can change switches used by other paths.

All 28 spare input interfaces and 28 spare output interfaces in the initial design have explicit on-chip, replaceable placeholder terminations and appear in the manifest. These are physical interface placeholders, not validated reflectionless absorbers. No internal switch or link is removed. Active interface remapping changes adapters and solver translation together, never the external port identity silently.

Alternative rejected: a generalized non-power-of-two or pruned 100-port network would reduce component count but give up the complete standard topology selected for regularity.

### 3. Hierarchy and regular placement

Preserve explicit hierarchy for the chip, fabric, stages, interstage routing blocks, reusable MZI/crossing/bend primitives, active IO adapters, spare terminations, and pad banks. Repeated components are cell references; export must not flatten the full design by default. Stage cells may differ in surrounding routing while sharing the same MZI primitive and orientation.

Use a left-to-right sequence of complete stages with a regular row array. Allow stage gaps, legal row-order symmetries, lane pitch, and optical/electrical corridor widths to vary within the search profile. Every physical row-order transformation must be represented in the logical-to-physical map and checked for graph equivalence. Retain a conservative feasible Beneš baseline under the same device and pad constraints for paired comparison.

### 4. Beneš-specific optical routing

Derive each interstage permutation from the new graph. Route its repeated shuffle/unshuffle groups as reusable blocks, then compact legal corridors and stage gaps. Use explicit four-port crossing primitives at intended intersections and analytic straight/arc access geometry with minimum 20 um centerline radius. A crossing transmits each logical channel through its designated opposing port pair; it is not a branching graph junction.

Build a conservative channel allocation first, then evaluate bounded candidates using repeated permutation groups and legal physical row orders to reduce span and crossing cost. This is a new structured router, not the existing Waksman adjacent-swap router with renamed cells. A candidate may expand a congested local corridor to become feasible; its actual final area determines its rank. Unintended intersections, touching waveguides, invalid crossing approaches, and below-radius bends reject a candidate.

Route active adapters and spare terminations before measuring the complete footprint. Equalization meanders default to off. If optional matching is enabled, it may use available interior space only while retaining the selected die bounds and all clearances; otherwise report the unmatched residual instead of enlarging the chip solely for uniformity.

### 5. Two-metal fanout and package-aware area

Keep the established placeholder interface of two independently routed electrical terminals per MZI (control and return), without shorting returns together. The 832-switch default therefore requires 1,664 pads, balanced as 832 north and 832 south. Place single-row global pad banks and allocate pads deterministically according to physical source order; local stage routing corridors must fit the global allocation instead of imposing avoidable repeated pad-bank margins.

Use M1 for local escape/distribution and M2 for separated trunks, with explicit vias for layer transitions. Same-layer conductors from different nets must remain separated, and every terminal must have exactly its designated pad connection. Declare the placeholder assumption that insulated M2 may pass above straight waveguide windows; vias, bends, MZIs, and optical crossings retain the configured keepouts. Validate the actual polygons against this policy rather than treating a second metal layer as permission for arbitrary overlap.

For 832 pads in one bank with 60 um width and 100 um pitch, pad span alone is (832-1)*100+60 = 83,160 um before margins. Report this packaging lower bound and the actual core, fanout, termination, and die extents. This explains why a more regular optical fabric need not produce a smaller complete chip than Waksman.

### 6. Area-first candidate selection

Compare candidates under identical device, pad, layer, clearance, margin, and active-interface requirements. Reject every candidate that fails functional or physical verification. Quantize the enclosing die rectangle to the GDS grid, including pads, optical adapters, terminations, routing, and margins. The primary score is its exact integer-grid width times height.

Rank feasible candidates lexicographically by:

1. Complete die area.
2. Active-path geometric length spread.
3. Active-path crossing-count spread.
4. Active-path bend-count spread.
5. Total routed waveguide length and a stable candidate identifier.

Secondary metrics apply only when preceding values tie; there is no weighted score or area tolerance that trades a larger footprint for improved uniformity. Report the selected candidate, search bounds, rejected candidates/reasons, and the valid baseline. If no compact candidate improves on the baseline, retain the baseline and report that outcome honestly. The result is best among evaluated feasible candidates, not a proven global optimum.

### 7. Explicit uniformity metrics and independent verification

Verify minimum and maximum switch depth over the complete fabric, including spare interfaces; both must equal 2log2(P)-1. Separately compute length, crossing, and bend extrema over all possible single-connection paths between active input/output interfaces. Use dynamic programming on the stage DAG, not enumeration of all simultaneous permutations. Distinct extrema may come from different paths and must carry their own witness paths.

For a requested simultaneous mapping, traverse its actual switch settings and report per-path values plus min/max, spread, mean, and standard deviation. Define geometric length as the sum of explicit component centerline lengths and routed links, including active IO adapters, with no double counting. Define bend count as the number of curved primitives and also report total absolute bend angle. Report the configuration's selected placeholder MZI state-dependent geometric contributions where represented, and explicitly identify unmodeled physical delay/loss.

Export a geometry/port/net manifest and reopen GDS independently. Verify cell references/transforms, geometry extents, optical endpoint continuity and crossing semantics, minimum radius and clearance, metal connectivity/shorts, vias/enclosures, and pad/termination coverage. Readback must corroborate generated geometry rather than merely trusting the planner's declared counts. These checks validate a placeholder layout, not a foundry design-rule deck or optical performance model.

### 8. Scalability and acceptance evidence

Deliver parameterized complete layouts for A/P = 4/4, 16/16, and 100/128, plus a padded small case such as 5/8. Functional tests cover exhaustive permutations at P=2/4/8; every one of the 10,000 active single pairs at A=100; identity, reversal, cyclic shifts, and at least 100 seeded random full active permutations; and explicit spare-interface behavior. Independently verify the complete internal fabric's depth and permutation capability.

Report topology/solver scaling for P=16, 128, 256, and 1024, with stage/switch counts, runtime, and memory measurement method. Large topology checks do not imply full large-layout routing completion. Full-layout reports include GDS size, cell/reference counts, generation/verification time, die/core extents, crossing counts, and path statistics.

## Risks / Trade-offs

- **Pad count dominates width:** 1,664 dedicated pads constrain packing. Keep this constraint visible and optimize full-chip area, rather than hiding pads in a core-only comparison.
- **Full Beneš has more MZIs:** regular depth costs 832 switches versus the existing 573. Compare footprints and depth metrics with their different internal sizes stated explicitly.
- **Structured routing may remain wide:** repeated shuffle blocks still contain many crossings. Start from a valid baseline, measure candidate feasibility, and report search limits without promising an untested improvement.
- **Equal depth is not equal loss:** crossing count, state response, bends, and real component variation remain relevant. Publish geometric spreads without claiming equal optical performance.
- **Placeholder overpass/termination assumptions:** the first real process/device data may change keepouts, required lengths, and feasible packing. Isolate these assumptions in replaceable interfaces and technology parameters.
- **Uniformity evaluation cost:** all-path metrics use DAG extrema; distributions are computed only for explicitly selected settings. Reports must not label sampled statistics as global guarantees.

## Migration Plan

Introduce the new package and CLI additively, establish topology/solver correctness, produce and verify a conservative full layout, then optimize with reproducible candidate comparisons. Keep existing Waksman commands and outputs intact and run their regression suite before accepting the new version. Save representative Beneš reports/configurations alongside instructions for regenerating ignored large output artifacts.

## Open Questions

Real MZI geometry, electrical drive structure, passive crossing loss, termination performance, metal stack, and foundry rules remain unavailable. They are deferred technology inputs with explicit placeholders, not blockers to this demonstrator. Replacing them requires regeneration and verification; the current plan does not promise that placeholder dimensions or performance assumptions will survive that replacement.

## Implementation Evidence

The independent `benes-layout` implementation is complete. Its repeated shuffle blocks use a closed-form triangular exchange schedule; no Waksman topology or router is called. Compact M2 escape trunks expand through M1 tracks outside the optical array and then M2 pad stems, using three vias per terminal-pad net. This realizes the two-metal plan without making the full optical corridor use pad pitch.

Default 100/128 output has 13 complete stages, 832 MZIs, 1,664 pads, 4,992 vias, 56 spare terminations, and 7,680 passive crossings. The selected die is 87.560030 by 12.644252 mm, 17.15% less area than the conservative Beneš baseline under identical device/package constraints. The search does not prove global optimality. Exact active-path length extrema are 87.280030 to 94.819743 mm; fixed depth does not establish equal length or loss.

Complete 4/4, 5/8, 16/16, and 100/128 examples pass geometry and independent GDS/conductor readback. Two full 100/128 generation runs reproduce normalized geometry, settings, interface maps, selection, and path metrics. The final suite has 111 passing tests, including retained Waksman regressions. Reproducible configurations and reports are in `examples/benes/`; operating instructions and limitations are in `docs/BENES.md`.

Optional equalization acts on the requested switch configuration's output adapters while preserving die bounds. It reports remaining mismatch when the available interior is insufficient and does not claim equalization of every possible reconfiguration.
