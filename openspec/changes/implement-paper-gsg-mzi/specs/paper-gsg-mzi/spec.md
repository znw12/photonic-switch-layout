## Purpose

将单带 Beneš 矩阵中的占位器件替换为参考所附 TFLN 论文的实体四端口 MZI，保持一毫米全长并定义 GSG 和公共地，提供独立几何、连接及重复生成证据，明确物理设计与未标定光学性能的边界。

## ADDED Requirements

### Requirement: Four-port physical MZI
系统 SHALL 提供总长 1000 μm、四光端口的 2×2 MZI，含两端方向耦合器、两臂和半径不小于 20 μm 的圆弧 S 弯，并保留参数及器件层级。

#### Scenario: Standalone device
- **WHEN** 生成 paper-gsg 单元
- **THEN** 两入两出接口正确、各波导分支连续、耦合间隙存在、弯曲半径通过检查，输出有效电极长度和器件 GDS/预览。

### Requirement: GSG and shared ground
两臂 SHALL 分别位于 G–S 与 S–G 间隙。两个 G SHALL 在单元内连通，并接入矩阵公共地；每个 S SHALL 独立。共地网络 MUST 显式声明，不得将任意短路视为合法。

#### Scenario: Full electrical extraction
- **WHEN** 回读完整 832 MZI 矩阵
- **THEN** 提取出一个公共 G 和 832 个独立 S，所有器件电极及 pad 到达对应网络，内部、外部和公共地 via 均被统计。

### Requirement: Evidence and limitations
系统 SHALL 区分论文尺寸与自行选定参数，SHALL 明示 2×2 耦合比例、Vπ 及射频性能未标定，并保留旧模型可用。

#### Scenario: Verification and repeat
- **WHEN** 破坏内部弯曲、间隙、地连接或信号隔离，或重复生成合法布局
- **THEN** 缺陷被检测，合法重复生成的规范化几何、端口和设置一致，完整 GDS 独立回读通过。
