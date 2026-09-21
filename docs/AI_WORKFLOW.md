# Human + Codex development workflow

This project was developed collaboratively: the human designer set requirements,
reviewed generated layouts, and selected tradeoffs; Codex assisted with research,
planning, Python implementation, GDS generation, testing, and documentation.
AI assistance was substantial and included production and verification code.
The repository should not be presented as entirely handwritten code.

## Human design direction

The human supplied the 100 × 100 switching requirement, 20 µm minimum bend
radius, TFLN MZI/GSG direction, two-metal routing allowance, and pad constraints.
They prioritized footprint over uniformity and iteratively inspected layouts.
Their feedback included reducing pad rows, preserving minimum pad pitch,
simplifying electrode leads, sharing ground contacts, and making pad placement
serve orderly wiring. Architecture choices and their tradeoffs were discussed
and accepted through this process.

## Codex assistance

Codex translated requirements into OpenSpec proposals and implementation tasks;
implemented recursive network construction, state solving, hierarchical cells,
optical and electrical routing, and CLI workflows; generated layouts and
comparisons; and added tests, fault injection, and readback checks. It also
assisted with investigating public reference designs and documenting limits.

The process repeatedly followed:

1. State a requirement and an explicit constraint or acceptance check.
2. Implement a bounded change and generate actual layout geometry.
3. Inspect the layout and measured area, routing, and connectivity results.
4. Correct the identified issue and add or retain relevant regression checks.
5. Compare results and record both improvements and tradeoffs.

## Concrete examples in the retained history

| Commits | Decision and evidence |
|---|---|
| `f963765` → `d83e84a` | Waksman requirements preceded the first working generator and verification framework. |
| `9ff8699` → `16f3843` | Centralized four-row pads exposed fanout overhead; stage-distributed pads reduced whole-layout area. |
| `c78f11f` → `570b0c6` | Interstage and folding experiments recorded that reducing width could increase area substantially. |
| `7c7c7ee` → `723347d` | Inspection of the GSG MZI led to symmetric electrode end margins and clearance tests. |
| `723347d` → `7b3db6f` | Questions about repeated metal transitions led to direct M2 exits and physical-disconnect tests. |
| `9156c94` → `d663272` | The exact-100 core was refined with ordered fanout and adaptive pads while preserving optical placement. |

These commits preserve an evolving design, including superseded approaches.
They are not a reconstructed sequence intended to suggest first-pass success.
The repository does not include a complete prompt transcript or a line-by-line
record of AI authorship; no percentage of AI-generated code is asserted.

## Verification and its limits

The solver is checked through separate explicit-port path tracing. Exported GDS
is read back and compared with the geometric model; actual metal regions and
vias are used to check electrical connectivity. Fault tests deliberately alter
geometry or connectivity to check that defects are rejected. These checks add
evidence beyond visual inspection or a generated success message.

Both implementation and verification code received AI assistance. "Independent"
describes separate checking paths and GDS readback, not an independent author,
external audit, or foundry signoff. Shared assumptions can still be wrong.
All-pairs single-connection testing and sampled full permutations are not an
exhaustive test of 100! switch configurations.

The review cleanup replaced an ignored-output test dependency with a committed
legacy fixture and fixed digest, then ran all 428 tests in a fresh checkout.
It also regenerated the final layout and independently reverified its bundle.
See [reproduction instructions](REPRODUCING.md) for the exact commands and
environment boundaries.

The result demonstrates parameterization, hierarchy, routing, scalability, and
verification of layout geometry. Coupler/crossing optical performance, electrode
RF behavior, fabrication rules, and measured chip performance remain future
work. Public literature inspires the device shapes; it does not validate this
particular geometry or replace a real PDK.
