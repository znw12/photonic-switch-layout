# Spec Delta

## Purpose

Make pruned Banyan results independently reviewable through exhaustive single-connection coverage, explicit blocking tests, physical GDS readback, fault injection and reproducible metric bundles, while preserving all existing topology modes and reference outputs.

## ADDED Requirements

### Requirement: Reachability and blocking acceptance

验收 SHALL 覆盖100路全部10,000个单连接、已知满载参考及其部分请求、合法但阻塞的请求，并检查请求顺序不改变结果。小规模 N=2至8 SHALL 枚举全部一对一完整置换，用独立路径/状态枚举判定可路由或阻塞，而非要求所有置换成功。

#### Scenario: One hundred port logical acceptance

- **WHEN** 对默认100路参考执行逻辑验收
- **THEN** 全部10,000对唯一可达且各7个MZI；满载参考及其抽样子集成功；固定种子的随机完整请求各自得到经独立检查的成功映射或真实阻塞诊断，不把失败率当作普遍阻塞概率

#### Scenario: Small network oracle

- **WHEN** 对N=2至8的全部置换与独立判定结果比较
- **THEN** 求解器的成功/阻塞分类一致，成功状态经独立走图验证，并拒绝重复端口、越界和非法状态

### Requirement: Geometry and independent GDS readback

系统 SHALL 验证层级、实际多边形、器件/终端/波导端点、两路贯通crossing、半径、切向、净距、包络以及M1/M2/via连接。报告 SHALL 验证每个保留器件端口和全部S/G探针，不能把元数据中的同名网络等同于真实连通。

#### Scenario: Reference physical acceptance

- **WHEN** 独立读回100路参考GDS
- **THEN** 验证100输入、100输出、400个MZI、56个片内终端、408个pad、401个电学网络以及少于4,522个全片crossing，所有光学和电学几何检查通过

### Requirement: Defect detection

验证 SHALL 能拒绝会改变有效连接、器件约束或电学隔离的故障，包括漏终端、错接边、错误crossing传输、非法小半径、共享地开路、S-G短接、丢失/重复via及pad间距破坏。

#### Scenario: Injected optical and electrical defects

- **WHEN** 向已通过的小规模裁剪布局逐项注入上述故障
- **THEN** 对应验证明确失败并给出可定位问题，不能因正常参考包曾通过而接受损坏产物

### Requirement: Explicit delivered metrics and assumptions

交付 SHALL 包含配置、网络/端口映射、完整控制状态、实际请求路径、暗输入、终端与pad归属、GDS、规范化摘要、验证报告、总览及局部预览。指标 SHALL 区分外部/母网/各级有效通道、MZI、图交叉/全片crossing、终端、pad、via、G接点、实际宽高面积及路径长度/crossing分布。

#### Scenario: Comparison with existing AS-Benes reference

- **WHEN** 发布100路裁剪结果
- **THEN** 与596-MZI、4,522-crossing、20.252711×4.555112 mm的现有AS-Beneš参考比较，注明源配置；如实说明新模式有阻塞、局部内部128通道和未校准的终端/光学性能，不将几何检查等同于损耗、反射或工艺认证

### Requirement: Reproducible and isolated generation

新参考 SHALL 使用独立示例与输出目录，相同配置、候选和请求两次生成的规范化几何、网络、控制及指标 SHALL 一致。失败生成 SHALL 不发布成功包，也不能用目录内上一次成功产物掩盖本次失败。

#### Scenario: Repeated generation and stale outputs

- **WHEN** 重复生成一个选定候选，随后对同一目标路径提交阻塞请求
- **THEN** 前两次规范化结果一致；第三次返回失败，并明确保留的旧包并非此次结果，或在隔离临时位置留下明确失败记录

### Requirement: Existing topology compatibility

现有Waksman、标准Beneš、AS-Beneš的配置、默认行为、控制语义、序列化哈希、示例及验证 SHALL 保持可用。新模式的部分端口/终端数据 SHALL 不被旧验证器误当成完整无阻塞网络。

#### Scenario: Historical reference regression

- **WHEN** 运行项目现有回归与原AS-Beneš参考生成/验证入口
- **THEN** 保持既有契约，包括AS-Beneš内部精确100路和任意一对一置换能力；新模式不会改变历史配置或覆盖其输出
