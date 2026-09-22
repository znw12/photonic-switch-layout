# Spec Delta

## Purpose

Define a compact hierarchical physical layout for a pruned Banyan switch, retaining the project's optical devices, metal stack, shared grounds and pad spacing while explicitly implementing sparse internal connectivity and unused device-port terminations.

## ADDED Requirements

### Requirement: Preserved optical and electrical device constraints

100路布局 SHALL 保持单条横向光学带、西入东出、1000 µm MZI总长、680 µm有源电极、GSG、至少20 µm波导弯曲半径、20×20 µm cosine crossing footprint、M1/M2两层金属与via以及现有局部净距规则。每个 MZI SHALL 独立控制，不以缩小器件、追加光学层或削减端口能力实现数量降低。

#### Scenario: Reference device geometry

- **WHEN** 检查100路参考GDS及器件元数据
- **THEN** 恰好400个独立 MZI，全部器件满足规定的长度、半径、层及crossing尺寸，所有光学连接连续且连接处切向一致

### Requirement: Sparse internal lanes and exact external interfaces

布局 SHALL 只布置裁剪图需要的开关、有效波导和显式终端，保留逻辑端口到物理坐标的可追踪映射。内部允许局部占用母网128轨道范围；外部 SHALL 恰好100个西侧输入及100个东侧输出，按公开编号顺序排布，不将已裁去支路延伸为额外外部接口。

#### Scenario: Output compression without hidden relabeling

- **WHEN** 母网输出选择包含不连续轨道
- **THEN** 保留相对顺序连接到100个外部输出，适配区域的波导、弯曲、长度和任何额外交叉均纳入验证与统计

### Requirement: Explicit on-chip unused-port treatment

100路参考 SHALL 为28个未用输入端和28个未用输出端各提供唯一、定向、可验证的片内终端连接，不允许悬空光学端口、跨支路连接或将占位器件直接描述为无反射终端。终端及引线 SHALL 遵守半径、光学/金属净距和全片包络规则。

#### Scenario: Internal termination inventory

- **WHEN** 读回100路参考的器件端口与终端图
- **THEN** 每个保留 MZI 的物理端口恰好接入一条有效边、外部接口或一个终端；终端恰好56个且无额外外部光口，活动连接不进入终端

#### Scenario: Missing or displaced termination

- **WHEN** 一处终端丢失、重复、朝向错误或与器件断开
- **THEN** 连接或几何检查失败；不能通过将该端口标为未用而豁免物理检查

### Requirement: Continuous routing and honest crossing reduction

系统 SHALL 优先采用可复用的连续斜线/分组置换布线，保留明确的两条crossing贯通路径，避免把全部级间布线替换为冗长相邻交换链。报告 SHALL 区分保持母网相对顺序时的2,433个级间图交叉与实际全片crossing实例；最终100路交付的全片crossing SHALL 少于4,522，包含I/O、终端避让和所有补充路由。

#### Scenario: Topology crossing baseline

- **WHEN** 对参考图按原相对轨道顺序计数
- **THEN** 六个级间计数为1,225、600、312、168、96、32，总计2,433，明确注明它是图级基线

#### Scenario: Physical routing adds crossings

- **WHEN** 终端或端口适配需要额外交叉
- **THEN** 报告分别列出来源并以GDS中的实际总数验收；总数不低于4,522时不得宣告减少crossing的任务完成

### Requirement: Independent signals and shared ground ownership

布局 SHALL 复用左右电学引出及共享G方案，每个可共享连续G轨仅有一个接触落点与一组via；光学波导或终端阻挡的G区域 SHALL 分段，所有G电极仍接入同一公共网络。100路参考 SHALL 提取出400个独立S网络及1个共地网络。

#### Scenario: Sparse column changes ground sharing

- **WHEN** 裁剪后的相邻开关之间存在光学连接或终端禁布区
- **THEN** 不以M1填合跨越该障碍，分段地轨经合法电学布线接入公共G；全部S/G探针、via和金属仍通过连接及间距检查

### Requirement: Two pad rows per side with direct stems

100路参考 SHALL 包含400个S pad与8个共地pad，南北各200个S及4个G、每侧两排各102个pad。pad SHALL 为60 µm方形、同排中心距至少100 µm、行距至少70 µm，并采用按引线顺序的两排排布及直接M2末端连接，验证外排引线避开内排pad。不得为压缩尺寸降低间距或增加金属层。

#### Scenario: Pad and metal readback

- **WHEN** 从100路参考读回pad和电学布线
- **THEN** 恰好408个pad，分配与独立信号一一对应，8个G pad共地，两排间距和全部引线净距满足要求，无无功能必要的统一pad换层结构

### Requirement: Bounded physical candidate selection

系统 SHALL 比较34/35 µm间距并联合选择逐列引出方向及pad位置；完整候选数量 SHALL 有明确上限且结果确定。只有通过光电连接、几何和crossing减少检查的候选能参与选择，优先最小实际全片面积，再比较宽度、crossing、信号转折和线长。20 mm宽度 SHALL 保持软目标，不把图级计数或pad跨度当成已实现芯片尺寸。

#### Scenario: Best valid candidate misses the width goal

- **WHEN** 所有通过检查的候选宽度均超过20 mm
- **THEN** 报告实际最优候选、尺寸及未达软目标，不违反硬约束或声称全局最优；若没有任何通过硬约束的候选，则返回明确失败
