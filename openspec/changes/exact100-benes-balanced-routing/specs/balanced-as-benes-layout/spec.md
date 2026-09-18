## Purpose

Define a compact physical layout for the exact-port AS-Beneš network using reusable optical and electrical cells. The capability combines direct diagonal permutations, selectable electrode exits, staggered pad rows and deduplicated shared-ground contacts with geometry-based acceptance and reproducible reporting.

## ADDED Requirements

### Requirement: Preserved physical device constraints

新参考布局 SHALL 保持单条横向光学带、西侧输入、东侧输出、1000 µm MZI 光学总长、680 µm 有源电极、GSG、M1/M2 两层金属与 via，以及 20×20 µm cosine crossing 单元 footprint。所有波导弯曲 SHALL 满足至少 20 µm 半径，光学连接 SHALL 连续且在连接处保持切向一致。

#### Scenario: Exact one hundred physical ports

- **WHEN** 导出新的 100 路参考 GDS
- **THEN** 仅有 100 个西侧输入及 100 个东侧输出，所放置的 MZI、crossing 与波导满足上述长度、层和半径约束

### Requirement: Direct diagonal permutations with measured pitch selection

系统 SHALL 比较 34 和 35 µm 光学端口间距的完整布局。规则偶数置换区 SHALL 采用直接转入及转出连续 45° 波导的连接，消除旧 25 µm 方案为入口偏移增加的补偿 S 弯。奇数旁路所需的额外转弯 SHALL 单独标注原因和数量。候选 SHALL 保持 crossing footprint，并检查量化后真实的半径、端点、切线及净距。

#### Scenario: Direct entry at both candidate pitches

- **WHEN** 生成 34/35 µm 的偶数置换块并连接相邻 MZI
- **THEN** 光学端点对齐、连接连续，入口不含旧模板的额外反向补偿 S 弯；不满足几何约束的候选被拒绝并记录原因

#### Scenario: Necessary odd bypass turns

- **WHEN** 奇数递归块的旁路需要额外避让
- **THEN** 旁路按真实端口图接续并满足半径及净距，报告其额外转弯，不以全网相邻交换链或静默恢复旧补偿模板替代该设计

### Requirement: Left and right electrical exits

系统 SHALL 提供左出和右出两种电学变体，并按物理列联合选择。两种变体 SHALL 保持相同的光学端口位置、器件长度、S/G 身份及开关状态含义。系统 SHALL 优先使用可直接连接的线段，避免无功能必要的局部折返和反复换层。

#### Scenario: Change a column exit side

- **WHEN** 某列从右出改为左出
- **THEN** 所有光学连接和控制状态含义保持一致，S 与 G 电学连接仍完整且隔离；该列共地汇流线与选定引出侧匹配

#### Scenario: Opposing exits into one gap

- **WHEN** 相邻两列同时向中间空隙引线
- **THEN** 两组独立信号均占有满足间距的布线空间；空间不足时拒绝或扩大该候选空隙，不能形成同层短接

### Requirement: Two precisely staggered pad rows

100 路参考 SHALL 在南北各放两排 pad，默认同排中心距固定为 100 µm，两排横向错开 50 µm；新增 `routing` 分布允许 pad 服务于布线，同排中心距不小于 100 µm，局部错位量不再固定；pad 尺寸为 60 µm 方形。每侧 SHALL 包含 298 个独立 S pad 和 4 个分布式 G pad，两排各 151 个，合计 604 个 pad。行距 SHALL 不小于 70 µm且通过实际几何检查；G pad SHALL 占用相同固定格点并连接公共 G 网络。

#### Scenario: Pad grid and counts

- **WHEN** 读取 100 路参考的南北 pad 表及 GDS
- **THEN** 每侧两排各 151 个 pad，默认分布相邻同排中心差为 100 µm，两排格点偏移为 50 µm，`routing` 分布检查同排至少 100 µm 和实际引线净距；全片恰好有 596 个 S pad 与 8 个 G pad

#### Scenario: Pad width estimate is not die width

- **WHEN** 报告该固定格点的横向包络
- **THEN** 151 个位置/排、两排及 60 µm pad 的 15.110 mm 包络仅标注为 pad 区尺寸，整片宽度另由全部实际几何求出

### Requirement: Direct pad stems and bounded channel regularization

两排错位 pad 的末端 SHALL 采用连续 M2 引线直接接入 M2 pad，并通过实际金属间距及连接检查；不再统一插入无避让作用的 M1 竖线和两次换层。系统 SHALL 支持按源干线顺序自适应布置 pad，在现有芯片宽度内保持两排及同排至少 100 µm 中心距，并让外排 M2 引线避开内排 pad。电学通道 SHALL 在已选光学布局和原通道高度预算内，确定性地减少不同网络的横纵跨层穿插和同列阶梯顺序跳变，同时保留同层间距与干线先后约束。

#### Scenario: Outer row lead passes between inner pads

- **WHEN** 采用至少 100 µm 同排中心距、相邻交替排 pad 至少 50 µm 横向间隔和 60 µm pad 的两排布局
- **THEN** 外排 M2 引线从内排 pad 之间的空隙通过，所有 pad 和电极仍属于正确网络，报告减少的 via 数量

#### Scenario: Regularization cannot increase channel height

- **WHEN** 对已选择的 100 路布局规整横向转接轨道
- **THEN** 优化后轨道数不超过原分配，报告明确统计范围的穿插数量及列内阶梯反向次数，交付左右端局部预览和完整读回结果

### Requirement: One contact per shareable ground rail

可共享的相邻 G 电极 SHALL 构成连续金属轨，每轨仅有一个接触落点和一组 via，接入公共 G 网络。一个无光学障碍的连续段若含 m 个 MZI，SHALL 有 m+1 条 G 轨及对应接点。系统 SHALL 保留每个 G 电极的连接归属，不能通过删除一侧电极探针掩盖断路。独立 S 接点 SHALL 保持独立。

#### Scenario: Two adjacent MZIs share ground

- **WHEN** 两个 MZI 的相邻 G 电极之间允许连续共地
- **THEN** 两者之间只有一条共享 G 轨和一个接触落点及一组 via，两侧外 G 各自保留接点，总计三个 G 接点而非四个

#### Scenario: Optical bypass prevents sharing

- **WHEN** 两个 MZI 间的光学旁路占据拟填合的 G 区域
- **THEN** 共地连续段在此断开，不用 M1 金属跨越旁路；两段分别接入公共 G 汇流线并保持光学净距

### Requirement: Electrical and optical geometry isolation

系统 SHALL 验证全部独立 S 网络与公共 G 网络，100 路参考应提取出 597 个电学网络。金属跨越 crossing 区 SHALL 遵守层间绝缘假设和明确的 via/光学禁布区；器件内部专用净距规则 SHALL 局部限定，不能成为整列的检查豁免。Crossing 的光学连接 SHALL 按两条贯通路径处理，而非四端口短接。

#### Scenario: Complete ground connectivity

- **WHEN** 从参考 GDS 提取电学连接
- **THEN** 所有 MZI G 电极探针及 8 个 G pad 属于同一网络，596 个 S pad 各自只连接对应 S 电极，彼此及与 G 隔离

#### Scenario: Ground or signal defect

- **WHEN** 测试版图出现共享 G 开路、S-G 桥接、漏掉或重复的共享接点
- **THEN** 连接或几何验证失败并定位问题，不因共有 G 网络名称相同而忽略实际断开

### Requirement: Verified bounded layout optimization

系统 SHALL 用确定性有限搜索联合比较光学间距、按列引出方向及 pad 格点整体位置，保留各间距全右出控制组。只有通过几何与连接检查的候选 SHALL 参与面积择优，依次比较实际面积、宽度、S 引线转折数、线长及路径差异。系统 SHALL 记录搜索预算、候选指标和淘汰原因，不宣称全局最优。20 mm 左右尺寸 SHALL 作为软目标报告，均匀性不得优先于尺寸最小化。

#### Scenario: Larger pitch has smoother but larger routing

- **WHEN** 一个候选减少了补偿曲线但实际芯片面积更大
- **THEN** 系统依据完整几何与规定顺序比较，不仅凭曲线更少就将其标记为尺寸改善

#### Scenario: No valid result below twenty millimetres

- **WHEN** 所有通过验证的候选宽度均超过 20 mm
- **THEN** 交付搜索范围内排序最优的合理布局，报告实际尺寸、约束及目标未达到，不压缩 pad 间距或违反弯曲半径

### Requirement: Hierarchical and scalable layout delivery

系统 SHALL 使用可复用的 MZI 光学单元、左右电学变体、crossing 单元和置换子块，显式导出旁路及共享 G 连续段的对应关系。新物理布局 SHALL 支持 N≥2 的奇数和偶数规模；小规模共地 pad 数 SHALL 随可用分布位置调整，不能硬编码 100 路的列占用。

#### Scenario: Smaller odd and even layouts

- **WHEN** 生成 5、7、12、13 路配置用于验收
- **THEN** 网络与物理端口数量一致，旁路可追踪，共享 G 及 pad 分配通过检查，单元复用不混淆不同端口排列

### Requirement: Reproducible comparison and independent readback

交付 SHALL 包括配置、GDS、端口与状态/连接数据、总览和局部预览、独立读回验证及相对旧 128 路参考的报告。报告 SHALL 包含拓扑、器件/pad/crossing/via 数、G 接点去重数、宽高面积、分区包络、S 引线转折/长度、真实路径 MZI 数与光学长度分布及候选选择依据。相同配置重复生成 SHALL 在规范化时间戳后得到相同几何、连接与指标。

#### Scenario: Full reference acceptance

- **WHEN** 两次生成 100 路参考并独立读回 GDS
- **THEN** 验证 100 输入/输出、596 个 MZI、604 个 pad、597 个电学网络及所有光学接续，规范化结果一致，并提供左右引线、共享 G、奇数旁路和错位 pad 的放大图

#### Scenario: Geometric validation is not performance certification

- **WHEN** 发布尺寸与验证报告
- **THEN** 区分版图连接/几何检查与未执行的电磁、损耗、阻抗和代工工艺认证，不把几何通过等同于已实现等损耗或射频指标
