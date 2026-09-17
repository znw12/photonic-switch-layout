## Context

See proposal.md for motivation and scope. The repository has OpenSpec scaffolding but no layout code, environment, device geometry, or foundry rules. This design is cross-cutting: topology, state synthesis, geometric placement, optical/electrical routing, and independent validation must share stable interfaces.

Confirmed decisions are an exact 100-port Waksman fabric, replaceable 2x2 TFLN MZIs, 20 um minimum optical bend radius, west/east optical interfaces, and north/south electrical pads using two metal layers plus vias. The initial operating example uses one illuminated input; the fabric retains full simultaneous permutation capability. It is rearrangeably nonblocking, not a guarantee of uninterrupted live reconfiguration.

## Goals / Non-Goals

**Goals:** Implement the five design pillars as separate, testable stages; generate a fully routed 100-port example; retain meaningful hierarchy; expose routability and footprint trade-offs; demonstrate scaling without claiming a globally optimal layout.

**Non-Goals:** Foundry qualification, electro-optic/RF performance, calibrated drive voltages, loss/crosstalk prediction without device models, and an implemented alternative switch architecture. A logical bar/cross state is not a calibrated voltage.

## Decisions

### 1. Parameterization and component contracts

Use Python with gdsfactory for ports, reusable cells, geometry, and GDS export. Keep network construction and switch-state solving independent of gdsfactory. Compared with a polygon-only gdspy implementation, this reduces custom component/port infrastructure; it does not remove the need for a custom routing strategy.

Use a versioned configuration, validated before generation, with N, database grid, waveguide geometry, minimum curvature radius, port pitch, MZI/crossing footprints, electrode port definitions, optical/metal clearances, M1/M2/VIA/pad layers, via enclosure, pad size/pitch, margins, search limits, and random seed. Record the complete resolved configuration and dependency versions with each result. Pin a compatible environment during implementation rather than choosing unverified package versions now.

The initial placeholder technology uses circular bends with R=20 um and a 0.001 um database grid. Illustrative starting dimensions are waveguide width 1 um, waveguide edge clearance 5 um, MZI envelope 1000 x 100 um, metal width/spacing 5/5 um, via cut 5 x 5 um with 2 um enclosure, and pads 60 x 60 um at 100 um pitch. Assume an insulating cladding under M2 and explicitly permit M2 overpasses at reserved straight-waveguide crossing windows; forbid vias at these windows and forbid unapproved metal overlap with bends/couplers/crossing cells. Other optical/metal regions use 10 um clearance except approved device electrode zones. Without insulated overpasses, west/east optical tracks can block north/south electrical escape regardless of available metal layers. This placeholder stack assumption is configurable and must be requalified for a real process. These numbers are layout exercises, not validated TFLN design rules. Curved polygonization has an explicit chord-error tolerance distinct from physical bend radius.

Each MZI has two input and two output optical ports with orientation/width, declared bar/cross transfer pairs, electrical terminals and net identities, and keepouts. Begin with one control and one return terminal per MZI, each routed to its own pad, to avoid assuming shared-ground connectivity. Thus the initial pad budget is 1146, not 573; adding terminals changes pad count automatically. Shared returns require an explicit configured net grouping and are not inferred from port names. More realistic differential/GSG/bias terminal definitions can replace this profile without changing topology.

Crossings have four optical ports with opposite-port through mappings. Their waveguide polygons intersect physically, but the optical verification model must not treat the crossing as an arbitrary four-way junction. Placeholders are replaceable through the same interface; incompatible replacements fail with a useful contract error.

### 2. Exact arbitrary-size network and hierarchy

Use the arbitrary-size Waksman recursive construction, including its bypasses and reduced boundary switch columns. Split subnetwork size n into floor(n/2) and ceil(n/2); do not pad to a power of two. With S(1)=0, use S(n)=n-1+S(floor(n/2))+S(ceil(n/2)). Equivalently, for k=ceil(log2 n), S(n)=n*k-2^k+1. N=100 gives 573 switches in at most 13 logical columns. Treat n=1 as a direct link and n=2 as one switch.

Construct immutable connectivity and stable IDs from recursive subnetwork paths. Route requested permutations using recursive constraints/bipartite coloring, with special cases for odd subnetworks and bypasses. Validate requests before solving. Complete a partial injective mapping deterministically to a full permutation and label filler assignments as inactive. An MZI fabric is not an optical shutter: single-connection operation assumes other external inputs are dark; filler paths still physically exist.

Retain CHIP, recursive NETWORK/subnetwork cells, reusable MZI and crossing/bend cells, pad banks, and routing groups. Avoid flattening the delivered GDS. A geometry checker can flatten temporary regions for verification. Cell caching keys include geometry/configuration, so only identical cells are reused. Keep logical IDs stable when only physical dimensions change.

References for implementation, not copied code: arbitrary-size network construction [research paper](https://www.sciencedirect.com/science/article/abs/pii/S0304397523002529); routing model and references in [SCIPR Lab's AS-Waksman interface](https://github.com/scipr-lab/libsnark/blob/master/libsnark/common/routing_algorithms/as_waksman_routing_algorithm.hpp).

### 3. Routing strategy and footprint optimization

Pipeline: validated configuration -> logical graph -> recursive stage placement -> reserved routing corridors/pad budget -> optical routing -> electrical routing -> validation -> scored candidate -> export. Retain a deterministic route manifest linking every physical route to logical endpoints.

Place recursive subnetworks in contiguous bands with west-facing input and east-facing output ports. Keep MZI electrode orientation consistent; mirrored/rotated replacements must declare legal transforms. Reserve interstage optical channels and electrical escape corridors before routing. Set the initial horizontal span from both core and pad-bank lower bounds, not optical core width alone.

For each stage boundary, decompose the required port permutation into adjacent transpositions (for example, an odd-even schedule). Place an explicit crossing cell for each necessary transposition, reuse parallel crossing columns, and connect with bend-compliant lanes. Straight-through bypasses remain explicit edges. This gives a constructive routing baseline for arbitrary permutations; later compaction can reduce area but cannot omit required crossings. Built-in bundle routing is only used where port ordering and obstacle assumptions hold; it must not silently sort away the intended permutation.

Circular bends use centerline R >= 20 um; S-bends are built from verified arcs/straights. Any future Euler option must check its true minimum curvature radius rather than its effective footprint radius. Snap ports and routes to the database grid and check continuity after snapping.

Place each electrical terminal in a reserved escape channel. Assign pad banks using terminal location and capacity, preserve monotone pad order where possible, and route with an obstacle-aware two-layer grid/channel router. Prefer local horizontal escapes on M1 and vertical trunks on M2, but permit direction changes when needed. Different-net overlap on one metal layer is forbidden. M1/M2 overlap is insulated unless an explicit via joins them. Enforce via cuts/enclosures, optical keepouts, pad escape spacing, and component-specific allowed electrode zones.

Single-row pad banks are the baseline. For P pads, the larger balanced bank requires at least (ceil(P/2)-1)*pad_pitch+pad_width before margins. With 1146 pads, 100 um pitch, and 60 um pad width, that bound is 57.26 mm. Report this illustrative packaging cost rather than hiding it. It is a strong reason to keep electrical terminal definitions and pad pitch configurable.

Search a bounded deterministic set of stage/channel pitches and north/south assignments. Begin with a conservative baseline; when congestion occurs, expand the affected channel or reject that candidate. Among verified candidates minimize full die area, then worst-path crossing count, then total optical length. Never shrink below a hard rule to improve the score. Export baseline/selected metrics, candidate failures, and the search budget. If all candidates fail, return a nonzero result with route IDs and congestion diagnostics; an optional debug preview must be clearly marked incomplete.

### 4. Scalability and deliverables

Topology is O(N log N) in switch count and O(log N) in logical depth. Physical crossing schedules, long interconnects, pads, and clearance can grow faster; do not promise linear area or runtime. Use spatial indexing for geometry conflict queries and hierarchical reuse for GDS size. Cache topology/device cells separately from placement so parameter changes invalidate the appropriate work only.

Provide a CLI for generation, connection-state solving, verification, and scaling reports. Output GDS, SVG/PNG preview, logical connectivity and route manifest JSON, switch settings JSON, pad map CSV, resolved configuration, and a verification/metrics report. Stable IDs join these artifacts. Repeated runs must have equal normalized geometry/connectivity and configuration hashes; timestamps and timings can differ.

Mandatory geometric demonstration sizes are N=4, 16, and 100. Topology/solver scaling covers N=16, 100, 256, and 1024, whose switch counts are 49, 573, 1793, and 9217. Larger full-layout attempts are bounded experiments and must report timeouts/failures honestly. Record stage timings, peak memory where measurable, hierarchy/cell counts, GDS bytes, core/die dimensions, pad totals, optical lengths/crossings, via count, and unrouted-net counts. N=100 must finish fully routed and verified; topology-only success is insufficient.

### 5. Verification independent of drawing

Use a graph traversal verifier that consumes generated switch states but does not call the state solver. Exhaustively test all permutations for N=1..7, then identity, reversal, cyclic shifts, and at least 100 seeded random full permutations at N=100. Separately verify all 10,000 single input/output requests. Reject duplicated inputs/outputs, out-of-range ports, and multicast requests. Include odd sizes such as 3, 5, 25, and 101 in regression checks.

Geometry checks reconcile placed/transformed ports and routed centerlines with expected logical edges. Validate bend curvature analytically before polygonization, then read back GDS to check snapped connectivity, gaps, unauthorized intersections, conductor spacing, via enclosure, pad sides, and die containment. Component interiors have explicit local rule scopes; crossing/coupler/MZI semantics do not excuse defects outside their registered footprints. Check every instance transform so rotated crossings retain the correct through pairs.

Extract electrical connected regions per layer and join them only at valid vias; compare the resulting terminal/pad net partition with the intended netlist. Optical extraction recognizes component through mappings and excludes intended internal coupling from generic short checks. Validate every physical edge once, then use the reconciled graph for connection/permutation checks.

Include negative fixtures: severed waveguide, unintended optical intersection, swapped crossing port mapping, M1 same-net/other-net distinctions, missing via, insufficient enclosure, electrical short, and undersized bend. A checker must detect these rather than only agreeing with the generator's own success flags. Reports distinguish logical success, geometric success, placeholder assumptions, and unassessed physical performance. No report may claim foundry DRC or measured TFLN performance.

## Risks / Trade-offs

- Unknown phase-shifter footprint and crystal orientation -> replaceable contracts, explicit legal transforms, and parameter sweeps; no fabrication claim.
- Dense optical permutations require many crossings -> report worst-path crossing counts; use replaceable crossing cells and retain channel expansion.
- Electrical escape conflicts with optical keepouts -> reserve corridors early, use two layers and explicit vias, and fail visibly if a configuration cannot route.
- Pads dominate die width -> include them in optimization and report the pad bound; do not assume shared returns or multiplexed drivers.
- Logical connectivity mistaken for real optical isolation -> label inactive filler routes and defer losses/extinction/crosstalk to real models.
- Large layouts exceed resources -> bounded routing/search budgets and topology-versus-geometry benchmark separation, while retaining N=100 full-layout acceptance.

## Migration Plan

There is no existing implementation to migrate. Implement and validate the contracts/topology first, then cells and small routed examples, then N=100 electrical integration, independent readback, and scaling. Pin dependencies only after a compatible installation is tested. Keep generated results in a dedicated output directory and preserve resolved configuration for reproduction. Git commits separate implementation phases; reverting a phase restores the prior code/configuration without modifying external services.

## Open Questions

Real TFLN cross-section, wavelength, phase-shifter length/voltage, crystal cut, electrode topology, pad packaging rules, and crossing performance await a PDK or real cells. They do not block a placeholder demonstrator: the initial assumptions above are explicit and replaceable. Any fabrication target will require a separate technology qualification step.
