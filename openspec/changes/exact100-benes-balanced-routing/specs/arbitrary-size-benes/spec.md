## Purpose

Define an exact-port arbitrary-size Beneš switching network with independently verifiable routing. The capability supports single connections and simultaneous one-to-one permutations without padding the network to a power of two, and exposes actual path differences for layout assessment.

## ADDED Requirements

### Requirement: Exact size symmetric AS-Beneš topology

系统 SHALL 提供显式选择的 AS-Beneš 模式，使用相等的有效及内部端口数；对 `n>2` 采用两侧各 `floor(n/2)` 个开关及 `floor(n/2)`、`ceil(n/2)` 两个递归子网络，`n=1` 为直通、`n=2` 为一个 2×2 开关。系统 SHALL 拒绝非正整数规模及精确模式下不相等的内外端口数。

#### Scenario: Exact one hundred port reference

- **WHEN** 生成 100 路 AS-Beneš 网络
- **THEN** 网络具有恰好 100 个输入、100 个输出和 596 个 2×2 MZI，最大逻辑列数为 13，不含补齐到 128 路的额外光学通道或终端

#### Scenario: Non power of two recursion

- **WHEN** 生成含 25、13 或其他奇数规模递归节点的网络
- **THEN** 每个奇数节点两端的未配对通道连接较大子网络，所有逻辑端口均有唯一且可追踪的接续关系

#### Scenario: Invalid exact size request

- **WHEN** 精确模式请求 100 个有效端口与 128 个内部端口，或请求零、负数、非整数规模
- **THEN** 系统报告参数错误，不静默补齐或改变拓扑

### Requirement: Single and simultaneous permutation routing

系统 SHALL 为合法单连接、部分一对一连接和完整一对一置换生成确定性的 bar/cross 状态及完整置换。重复输入、重复输出、越界端口 SHALL 被拒绝。部分连接的补全及暗输入 SHALL 显式报告。能力 SHALL 标注为可重排无阻塞，不承诺重配置过程中既有连接不中断。

#### Scenario: Simultaneous one hundred connections

- **WHEN** 请求合法的 100 路一对一置换
- **THEN** 返回覆盖全部 596 个 MZI 的状态，100 个输入同时到达指定的互不重复输出，且无矛盾的开关状态或同一内部端口占用

#### Scenario: Single connection with unused inputs

- **WHEN** 仅请求输入 i 到输出 j
- **THEN** 系统实现该连接，确定性补全内部置换并列出其余暗输入，不将单连接结果描述为其他输入均可任意点亮

#### Scenario: Repeated destination

- **WHEN** 两个有效输入同时请求同一个输出
- **THEN** 系统明确拒绝请求，不生成看似成功的状态文件

### Requirement: Independent path verification

系统 SHALL 依据显式端口连接及给定开关状态独立验证实际路径，覆盖奇数旁路及较浅子网络的直通段，不使用求解器的期望路径代替走图结果。验证 SHALL 检查开关状态完整性、输出映射及同时连接的一致性。

#### Scenario: Odd and even scale routing validation

- **WHEN** 对 N=2 至 8 的全部置换以及 N=100 的全部单连接、恒等、反序、100 个循环移位和固定种子的 100 个随机全置换进行验收
- **THEN** 独立路径验证均通过，每条请求实际到达其指定输出

#### Scenario: Corrupted routing information

- **WHEN** 状态缺失、状态值非法，或被测实例的一条旁路边被改接以使实际输出偏离目标
- **THEN** 验证失败并指出缺失状态或路径不一致，不因原始求解成功而接受损坏结果

### Requirement: Explicit path and bypass reporting

系统 SHALL 导出稳定的开关标识、连接端口、旁路身份及每条受检路径的实际 MZI 数，并区分逻辑列数与经过的器件数。给定置换的实际路径统计 SHALL 与拓扑范围统计分别标注；物理布局存在时 SHALL 包括实际波导长度及 crossing 数。

#### Scenario: Unequal path depths

- **WHEN** 100 路 AS-Beneš 中某路径绕过一个逻辑列
- **THEN** 路径报告保留该旁路及其物理长度，不把旁路计为 MZI，也不将所有路径统一报告为 13 个器件

### Requirement: Standard Beneš compatibility

系统 SHALL 保留现有标准 Beneš 默认模式、端口补齐行为、配置序列化规则和参考输出；精确 AS-Beneš SHALL 使用独立配置与输出目录，不覆盖原 128 路参考。

#### Scenario: Existing compact reference

- **WHEN** 运行原有 100 有效端口的 compact-gsg 示例且未选择 AS-Beneš
- **THEN** 仍采用 128 内部端口和 832 个 MZI，原配置校验及既有结果比较继续有效
