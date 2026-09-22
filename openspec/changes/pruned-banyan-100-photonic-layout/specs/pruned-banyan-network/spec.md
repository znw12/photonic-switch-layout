# Spec Delta

## Purpose

Provide a parameterized pruned Banyan optical switching network with exactly the requested external ports, unique single-connection paths, explicit blocking diagnostics, and a demonstrated full-load reference configuration. Distinguish external ports from the parent network's lane address space and retained internal links.

## ADDED Requirements

### Requirement: Explicit matched-port pruned topology

系统 SHALL 提供独立的 `pruned-banyan` 模式，以相互匹配的输入/输出集合裁剪标准二进制递归 Banyan，保留所有选定输入到选定输出的路径。系统 SHALL 分别导出外部端口数、母网规模、各级保留开关及有效通道数，不能将母网规模报告为外部光口数或虚构已删除的通道。

#### Scenario: One hundred port reference inventory

- **WHEN** 构造默认100路裁剪 Banyan参考
- **THEN** 外部恰好100输入/100输出，母网为128路，7列分别具有50、50、52、56、64、64、64个 MZI，共400个；6个级间分别保留100、100、104、112、128、128条有效通道
- **AND** 未用器件端口为28个输入端和28个输出端，作为片内终端端口导出

#### Scenario: Parameterized scale and invalid input

- **WHEN** 请求整数规模 N≥2，未显式声明母网规模
- **THEN** 选择不小于N的最小2的幂作为母网，按相同匹配选择规则构造网络，开关/终端数量从裁剪图得到
- **AND** 零、负数、布尔值、非整数N，以及显式声明非默认母网规模的配置均被明确拒绝，不静默改变规模

### Requirement: Stable public port numbering and selection

系统 SHALL 将公开输入/输出编号分别定义为0至N−1，并导出它们与母网端口的双射。默认输入选择母网前N口；默认输出选择这些输入在母网全bar状态下实际到达的集合，按母网轨道升序分配公开输出编号。系统 SHALL 导出该全bar满载配置对应的公开置换，不将其默认假设为恒等置换。

#### Scenario: Matched full-load reference

- **WHEN** 路由100路参考的公开全bar置换
- **THEN** 全部100个输入同时到达各自不同的公开输出，无内部链路或开关状态冲突，且不会到达片内终端

#### Scenario: Unsupported selection override

- **WHEN** 本模式配置提供不同于默认匹配选择规则的输入或输出映射
- **THEN** 明确报告不支持该端口选择，不将两端直接截取前100口的其他裁剪图冒充400-MZI参考

### Requirement: Unique single-connection reachability

系统 SHALL 对每个有效输入—输出对保留恰好一条有向光学路径。100路参考的全部10,000对路径 SHALL 均经过7个 MZI；内部端口与每个开关标识 SHALL 稳定、可追踪，物理行号调整不能改变逻辑连接。

#### Scenario: All single connections at one hundred ports

- **WHEN** 分别请求100路参考的每一对单连接
- **THEN** 每次成功，独立走图实际到达对应公开输出，路径唯一且包含7个 MZI，未请求输入被列为必须保持暗态

### Requirement: Deterministic routing with explicit blocking

系统 SHALL 只对实际请求求解，不先任意补全置换。重复输入、重复输出、越界或格式错误 SHALL 被拒绝；无冲突请求 SHALL 得到完整400开关状态（100路参考），未约束开关按稳定规则设定。内部链路争用或bar/cross要求矛盾 SHALL 导致整个请求失败，包含冲突请求对及内部位置的诊断；不得静默丢弃请求、改变目标或通过分时声称同时完成。

#### Scenario: Compatible partial request

- **WHEN** 从全bar满载参考中选择部分输入—输出对请求连接
- **THEN** 全部请求同时成功，返回确定性状态、实际路径和其余公开暗输入列表，而不要求未请求输入形成指定的完整置换

#### Scenario: Blocked one-to-one request

- **WHEN** 外部输入/输出均不重复，但唯一路径争用内部链路或同一开关需要相反状态
- **THEN** 返回显式阻塞错误及冲突位置，进程以失败状态退出，不发布可被误认为此次成功结果的状态文件或成功生成包

#### Scenario: Request ordering and empty request

- **WHEN** 同一组合法请求以不同顺序提交，或提交空请求
- **THEN** 前者得到相同规范化状态/诊断；后者将全部公开输入列为暗输入，完整开关状态按默认规则给出，不声称有活动连接

### Requirement: Independent state and graph verification

系统 SHALL 按导出的实际端口连接及bar/cross状态独立追踪请求，不以求解器报告的期望路径替代走图。验证 SHALL 检查状态覆盖、状态值、映射双射、活动请求、暗输入、链路占用及终端去向，并明确标注网络为阻塞网络。

#### Scenario: Modified state or edge

- **WHEN** 设置缺失或包含非法状态，活动路径的一条边被改接，或活动请求被引向片内终端
- **THEN** 验证失败，定位状态或连接问题，即使原求解结果曾成功也不能接受

### Requirement: Compatible command-line operation

系统 SHALL 在生成、求解、验证中识别新拓扑；新拓扑未指定连接时采用已知可达的满载参考置换。显式请求 `identity`、`reverse` 或自定义置换 SHALL 被正常求解并在阻塞时失败，不被替换成参考置换。原 Beneš/AS-Beneš 的默认恒等请求、序列化和行为 SHALL 保持兼容。

#### Scenario: Default generation and explicit blocked pattern

- **WHEN** 不带连接参数生成新参考，随后显式提交一个阻塞的完整置换
- **THEN** 默认生成使用并导出满载参考映射；第二次明确失败，不能沿用上一包成功报告代表此次请求
