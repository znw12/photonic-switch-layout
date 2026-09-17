## Purpose

为单带连续斜线 Beneš 交换网络增加南北各三排固定中心距 pad 的电学布局，结合开关级放置和分层扇出优化完整尺寸，并提供兼容旧两排结果的参数、层级产物与独立几何验证。

## ADDED Requirements

### Requirement: Three-row reference constraints
系统 SHALL 支持独立 three-row 模式，保留单带 continuous、100/128 端口、13 级、832 MZI、1664 独立 pad、8320 via、两层金属和至少 20 μm 弯曲半径。南北 SHALL 各三排，100 μm 同排中心距、25 μm 逐排错位、60 μm pad；末列 MUST 保持完整端子覆盖而不添加虚假 pad。

#### Scenario: Full and partial columns
- **WHEN** 生成 100/128 参考布局
- **THEN** 每侧行计数为 278/277/277，末列与真实外框一致，西入东出，南北行和外框以 y=0 对齐。

### Requirement: Bounded placement optimization and compatibility
系统 SHALL 允许显式 stage 对齐偏置，保持 pad 中心距与合法器件间距；非法参数 MUST 被拒绝。旧 two-row 配置与产物 SHALL 保持可用。优化 MUST 以完整面积而非仅 pad 宽度为准。

#### Scenario: Compare placement candidates
- **WHEN** 有限扫描三排候选
- **THEN** 记录规划筛选和完整物理验证的区别，比较无偏置共享基线、选定改进候选和独立引出对照，只推荐通过完整验证的结果。

### Requirement: Physical and reproducibility verification
系统 SHALL 检查规范光路、crossing 对穿、半径、金属开短路、间距、via 包围、M2 跨越窗口及三排 pad 合约。交付 MUST 包括 GDS、预览、参数、报告和最佳重复生成证据。

#### Scenario: Corrupted or repeated layout
- **WHEN** pad 槽位、错位、窗口或 via 被破坏，或重复生成最佳布局
- **THEN** 违规布局验证失败；合法重复布局具有一致几何摘要、端口/pad 表、开关设置及尺寸统计，并通过独立 GDS 回读。
