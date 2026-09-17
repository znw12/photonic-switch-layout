## ADDED Requirements

### Requirement: Explicit continuous three-band profile
系统 SHALL 支持三条带的连续斜线布局，保持西侧输入、东侧输出及完整 Beneš 网络。参考布局 MUST 保留 100/128 端口、13 级、832 MZI、1664 pad、4992 via、7680 crossing 和 R≥20 μm；南北各四排 pad，排错位 25 μm。

#### Scenario: Generate folded reference
- **WHEN** 使用 continuous、三带和四排中央 pad 配置生成参考版图
- **THEN** 产生完整层级光电布局，未请求的光路与备用终止保持齐全。

### Requirement: Configurable complete stage partition
系统 SHALL 支持显式逐带级数，非法分配必须拒绝。既有默认分配和旧 bundle MUST 保持兼容。

#### Scenario: Invalid partition
- **WHEN** 级数不是正整数、带数不符或总级数不符
- **THEN** 配置明确报错，不截断或重复放置逻辑 stage。

### Requirement: Direction-aware physical validation
系统 MUST 按实际源/目标器件朝向验证每条路由的切向，并验证回弯、真实几何及 GDS 金属连通。

#### Scenario: Defective reversed band or turn
- **WHEN** 中间带切向、回弯半径、连接、pad 或跨带金属窗口损坏
- **THEN** 独立验证失败，不因折叠模式而跳过原有间距或连通检查。

### Requirement: Measured trade-off and reproducibility
系统 SHALL 比较约定的完整三带候选，保留候选失败原因并按实际面积优先排序。结果 MUST 包含相对 continuous 单带的宽高/面积、路径统计和最佳候选重复生成证据。

#### Scenario: Folded layout has larger area
- **WHEN** 三带缩短左右尺寸但增大完整面积
- **THEN** 如实报告二者，不宣称面积优化或 20 mm 达标。
