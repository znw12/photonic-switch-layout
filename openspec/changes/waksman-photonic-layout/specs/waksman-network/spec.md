## Purpose

Define the exact arbitrary-size photonic Waksman topology and the externally observable behavior of its connection-state solver.

## ADDED Requirements

### Requirement: Exact arbitrary-size topology
The system SHALL accept integer N >= 1 and construct exactly N inputs and N outputs without power-of-two padding. The switch count SHALL satisfy S(1)=0 and S(n)=n-1+S(floor(n/2))+S(ceil(n/2)) for n>1. Logical IDs SHALL remain stable when only geometry parameters change.

#### Scenario: Exact hundred-port fabric
- **WHEN** N=100 is requested
- **THEN** the topology has 100 external inputs, 100 external outputs, 573 two-input/two-output MZI instances, and at most 13 logical switch columns

#### Scenario: Odd and minimal sizes
- **WHEN** N is 1, 2, 3, 25, or 101
- **THEN** the topology preserves that exact port count and the stated switch-count recurrence, including a direct link with no MZI at N=1

### Requirement: Single and simultaneous one-to-one routing
The system SHALL produce bar/cross states realizing any injective partial input/output mapping and any full permutation. It SHALL identify active requests separately from inactive assignments that complete a partial mapping. Documentation SHALL state that existing internal paths can change during reconfiguration and that inactive inputs must be dark for single-illuminated-input operation.

#### Scenario: One selected connection
- **WHEN** only input 0 to output 73 is requested at N=100
- **THEN** an independent traversal of the returned states reaches output 73 from input 0 and the report distinguishes this request from filler assignments

#### Scenario: One hundred simultaneous connections
- **WHEN** a permutation of all 100 outputs is assigned to the 100 inputs
- **THEN** one common switch-state assignment realizes all 100 connections simultaneously, without two requested signals sharing an interconnect edge or output

### Requirement: Invalid requests are rejected
The system SHALL reject nonpositive or noninteger N, out-of-range ports, duplicate requested inputs, duplicate requested outputs, and multicast mappings with explicit diagnostics before state synthesis or layout generation.

#### Scenario: Competing outputs
- **WHEN** two inputs request the same output
- **THEN** the request fails and identifies the conflicting output and inputs

### Requirement: Reproducible connectivity export
The system SHALL export port IDs, switch IDs, edges, bar/cross transfer definitions, requested mappings, and complete switch settings in a machine-readable form. Identical valid inputs SHALL give identical logical results.

#### Scenario: Stable solver output
- **WHEN** the same topology and connection request are solved twice
- **THEN** their logical identifiers, connectivity, active mappings, and switch states are identical
