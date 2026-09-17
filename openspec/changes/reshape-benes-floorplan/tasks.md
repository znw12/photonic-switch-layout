## 1. Parameterization and routing

- [x] 1.1 Add validated pad-row and band parameters and CLI options; verify invalid configurations are rejected and defaults preserve old behavior.
- [x] 1.2 Implement compact multirow routing; verify small two/three-row layouts through GDS extraction.
- [x] 1.3 Implement hierarchical compressed turns and folded stage placement; verify small odd-band layouts and minimum radii.

## 2. Verification and comparison

- [x] 2.1 Extend transform, row and physical verification; add negative tests for rotated endpoints, routing defects and row violations.
- [x] 2.2 Generate phase-one 100-port two/three-row bundles and phase-two three/five-band candidates with two/three rows; retain verification reports and actual extent comparisons.
- [x] 2.3 Verify reproducibility and run the complete regression suite; save results.

## 3. Delivery

- [x] 3.1 Document commands, measured trade-offs, reusable crossing hierarchy and the 20 mm pad bound; include previews and comparison artifacts.
- [x] 3.2 Validate OpenSpec artifacts and commit the completed code, tests, examples and documentation to Git.
