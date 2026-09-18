## Purpose

提供参考公开余弦渐变交叉设计的参数化光学单元，在已有大规模 Beneš 版图中替换十字占位轮廓，同时维持原有四端口、占用范围、直通配对和复用层级，并明确其几何设计与尚未验证的光学性能边界。

## ADDED Requirements

### Requirement: Cosine crossing with fixed interface
系统 SHALL 提供四臂余弦渐变 crossing，并保持原有端口位置、宽度、方向、直通配对及 0°/45° 旋转后的 footprint。

#### Scenario: Default standalone geometry
- **WHEN** 生成默认 cosine crossing
- **THEN** 端口位于 (±10,0)、(0,±10) μm，宽 1 μm；中心宽 3 μm、臂最大宽 4 μm，轮廓连续且四重对称，输出单元 GDS、图和实际尺寸报告。

### Requirement: Integration and geometry validation
系统 SHALL 检查渐变轮廓、四端口连续和邻近净距；新形状 MUST NOT 改变当前矩阵尺寸、路由中心线或电学布局。

#### Scenario: Full matrix and defects
- **WHEN** 生成完整 100/128 矩阵，或篡改 crossing 轮廓、端口及中心连接
- **THEN** 合法设计的 7680 个 crossing 复用同一单元，保持 8460 个 via、1 个 GND 和 832 个独立 S；非法几何被检测，完整 GDS 回读通过。

### Requirement: Provenance and compatibility
系统 SHALL 将新模型标记为几何参考、光学性能未标定，保留旧 placeholder 模型和产物回读。

#### Scenario: Reference interpretation
- **WHEN** 查看新单元报告或回读旧版矩阵
- **THEN** 报告包含参考页面、项目所选尺寸和未标定状态；旧矩阵按其原有配置和几何合约验证。
