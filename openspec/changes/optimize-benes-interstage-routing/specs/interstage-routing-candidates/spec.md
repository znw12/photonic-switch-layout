## Purpose

为当前单条带 Beneš 光子交换矩阵提供可复现的级间波导置换候选，在保留器件、电学和逻辑连接约束的条件下，通过完整几何与 GDS 验证比较实际芯片尺寸。

## ADDED Requirements

### Requirement: Explicit routing mode and compatibility

系统 SHALL 支持选择现有逐列交换、连续斜线和局部压缩三种级间布线模式，保持旧模式为默认。局部置换间距 MUST 与 MZI 端口行距独立，并在输出配置和报告中明确记录。非法参数与不支持的模式组合 MUST 明确拒绝。

#### Scenario: Existing configuration
- **WHEN** 使用未指定新模式的旧配置，或回读此前生成的 bundle
- **THEN** 原布局行为及验证能力保持兼容，不强制重新生成旧产物。

#### Scenario: Local pitch and unsupported combinations
- **WHEN** 请求局部压缩、非法间距或新模式不支持的折叠/pad 组合
- **THEN** 合法请求保留配置的器件接口行距并记录实际局部间距，非法请求报错，不能静默忽略参数或修改约束。

### Requirement: Canonical connectivity and fixed reference constraints

A、B 的 100/128 参考布局 SHALL 保持完整规范 Beneš 连接、13 级、832 个 1000 × 100 μm MZI、100 活动输入/输出及 56 个备用端口终止。布局 MUST 保持单条带、60 μm 器件端口行距、至少 20 μm 弯曲半径、1664 个独立 pad、4992 个 via、M1/M2 两层金属及南北四排按级分组的 25 μm 错位 pad。配置的金属和光学间距约束 MUST 继续执行。

#### Scenario: Full reference candidate
- **WHEN** 生成任一 A 或 B 的完整 100/128 端口参考版图
- **THEN** 独立验证确认所有光路具有 13 个开关级、规范图不变、电学端子没有合并，且全部接口和备用终止齐全。

### Requirement: Continuous routing with explicit crossing hierarchy

连续斜线模式 SHALL 消除同向连续交换间重复恢复水平的弯曲，保留正反置换的完整端口传输关系。每个实际 crossing MUST 是具有明确对穿端口、允许方向和独立实例身份的层级单元。重复模块 SHALL 复用单元，不能以扁平化或免检整块替代可验证的内部结构。

#### Scenario: Forward and inverse modules
- **WHEN** 生成 4、8、16、32、64、128 通道正向及逆向置换模块
- **THEN** 每个输入连接到规范置换指定的输出，逆向映射可独立核对，crossing 不能被当作任意四通节点。

#### Scenario: Unsupported component direction
- **WHEN** 置换布局需要某 crossing 器件未声明允许的朝向
- **THEN** 系统拒绝该放置，不将几何旋转视为真实 TFLN 器件性能等效。

### Requirement: Full transition cost for compressed candidates

局部压缩模式 SHALL 实际生成入口收束、压缩交叉区和出口展开，并将三者全部计入面积、路径长度、弯曲和间距验证。报告 MUST 区分压缩边界、未压缩边界及无压缩对照，不得把全回退结果称为压缩收益。

#### Scenario: Physical compressed comparison
- **WHEN** 比较 q=40、45、50、55、60 μm 的参考候选
- **THEN** 输出实际尝试和失败原因，并对至少一个 q<60 的真实压缩完整布局进行物理验证；q=60 单独标注为无压缩对照，不能替代压缩功能验收。

#### Scenario: Fan-in overhead exceeds savings
- **WHEN** 某边界的收束和展开开销抵消交叉区的缩小
- **THEN** 报告反映真实开销，允许显式选择未压缩边界，整体结论由最终 die 面积决定。

### Requirement: Independent route and geometry validation

验证 SHALL 从基本段、端口和 crossing 对穿关系独立重建光路，检查端点及切向连续性、最小曲率半径、波导间距和未声明相交，并重算路径统计。crossing 交叉窗口 MUST 仅豁免所属两条波导的合法重叠。完整产物 MUST 通过 GDS 多边形/层级回读及真实金属连通、宽度、间距、via enclosure 和光电窗口检查。

#### Scenario: Corrupted route or statistics
- **WHEN** 存在错误置换、断点、切向折角、未声明交叉、过小半径、错误 crossing 对穿关系或汇总统计篡改
- **THEN** 独立验证失败，即使 manifest 的声明数量或路由器成功标志没有变化。

#### Scenario: Unintended overlap in a crossing neighborhood
- **WHEN** 第三条波导进入交叉窗口或相邻 crossing、过渡波导违反间距
- **THEN** 系统拒绝该布局，不因附近存在合法 crossing 而豁免错误。

### Requirement: Measured comparison and reproducible delivery

系统 SHALL 为旧基线、A 和 B 保存可再生配置、成功产物或失败记录，以及覆盖全芯片的尺寸与路径比较。推荐排序 MUST 优先实际完整 die 面积，随后保持现有均匀性决胜规则。所有候选、预算和实际边界策略 MUST 可追溯；仅完整验证通过的布局可以被推荐，且旧基线可保留为最优结果。

#### Scenario: Complete 100-port evaluation
- **WHEN** 执行参考比较
- **THEN** A 提供完整验证的 100/128 bundle，B 提供真实压缩候选的完整生成和验证证据；若无法得到合法压缩布局，应明确报告阻塞原因，不将估算或全未压缩回退视作完成。

#### Scenario: Repeat selected candidate
- **WHEN** 最佳已验证配置重复生成
- **THEN** 规范化几何 hash、开关设置、端口/pad 映射、尺寸和路径统计一致；报告明确 20 mm 目标是否达到，不将解析估算或硅光文献数值当作本芯片实测。
