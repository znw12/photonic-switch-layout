## Purpose

为单带连续斜线 Beneš 光子开关矩阵提供两排固定中心距 pad、协调的南北电学布局和可验证的跨置换区布线，在保持完整光电连接与器件约束的同时衡量芯片整体尺寸收益。

## ADDED Requirements

### Requirement: Two-row reference and compatibility
新模式 SHALL 保持 100 活动/128 内部端口、13 级、832 MZI、1664 独立 pad、M1/M2 两层金属、单带连续斜线和至少 20 μm 弯曲半径。南北 MUST 各两排 pad，参考同排中心距固定 100 μm，pad 尺寸 60 μm，排间错位 25 μm。旧配置与旧产物回读 SHALL 保持兼容。

#### Scenario: Generate reference layout
- **WHEN** 选择新的两排电学模式
- **THEN** 生成全部独立端子和 pad，记录实际 via 数量，西入东出，不自动缩小 pad 同排中心距。

### Requirement: Coordinated centered electrical layout
新布局 SHALL 以 y=0 为光学束中心，并采用协调的南北 pad 行和布线规则。MUST 保持正确端子连接；不要求每条网严格镜像。所有金属转弯、间距和换层 MUST 满足已声明的几何规则。

#### Scenario: North and south escape
- **WHEN** 生成南北电学引出和 pad 扇出
- **THEN** 两侧 pad 行与外框关于 y=0 对齐，局部不对称不改变网络连接，报告完整高度。

### Requirement: Explicit passive optical overpasses
共享置换区模式 SHALL 只在显式绝缘占位合约下允许 M2 跨越被动光学结构，并记录实际跨越窗口。M1/via 和未授权器件 MUST 继续执行光学避让。窗口 MUST 绑定实际光学实例，不能豁免整片置换区。

#### Scenario: Valid or corrupted overlap
- **WHEN** 金属跨越被动置换区，或窗口、层、via 位置被破坏
- **THEN** 合法跨越保留可核对记录；缺失窗口、未授权重叠、光学 keepout 或金属间距违规导致验证失败。

### Requirement: Complete verification and measured comparison
系统 SHALL 检查规范光学图、半径、crossing 对穿、金属开短路、同层间距、via 包围和 pad 排布。SHALL 输出共享与独立引出的完整候选比较，区分核心尺寸与成品尺寸，以实际面积优先推荐；最佳结果 MUST 重复生成一致并独立回读。

#### Scenario: Reproducible delivery
- **WHEN** 完成参考布局生成
- **THEN** 交付 GDS、预览、配置、端口及 pad 表、验证和比较报告，报告相对旧四排连续版的真实收益或代价及未达到的尺寸目标。
