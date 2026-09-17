## Purpose

以有界、可复核的小规模物理实验评估 Beneš 各级器件和子网络的排列，区分连接图不变、全网络交叉减少和实际芯片面积改善，为后续大规模布局决策提供证据。

## ADDED Requirements

### Requirement: Bounded experimental scope and explicit mapping

排列实验 SHALL 仅面向本轮 8、16 活动/内部端口参考网络，不自动启用到 100 端口生产候选。系统 MUST 保持规范 Beneš 图、逻辑开关标识、求解状态和外部接口编号，导出逐级逻辑开关到物理位置及端口的完整双射。

#### Scenario: Rearranged stage
- **WHEN** 某级 MZI 或递归子组的上下顺序变化
- **THEN** 导出的映射能够还原每条规范逻辑边，外部输入输出及每路径开关深度不变，器件朝向满足原组件约束。

#### Scenario: Invalid placement map
- **WHEN** 映射遗漏、重复放置、错误 pin 对应或 pad 被绑定到其他逻辑 stage
- **THEN** 独立验证拒绝该候选，而不是仅依据连接求解器的成功标志接受。

### Requirement: Deterministic search and fair physical comparison

实验 SHALL 包含恒等对照和非恒等的递归子组交换、反序或索引重排候选，使用明确的有限搜索预算、确定性顺序及 tie-break。恒等与重排候选 MUST 使用相同物理路由后端进行主比较；逻辑代理指标与完整物理结果 MUST 分开报告。

#### Scenario: Finite candidate search
- **WHEN** 在 8 或 16 端口运行排列实验
- **THEN** 输出预算、已尝试映射、全网络逆序数/位移代理、筛选结果和失败原因，重复运行产生相同候选顺序。

#### Scenario: Fewer crossings but larger die
- **WHEN** 某候选减少了逻辑代理交叉数但增加完整布线后的面积
- **THEN** 报告展示两种指标，并继续按实际面积优先评估，不宣称该候选实现尺寸优化。

### Requirement: Complete small-network validation and honest conclusions

两个实验规模 SHALL 分别提供恒等布局和非恒等候选的完整生成/验证结果或具体拒绝证据。成功候选 MUST 包含 IO、电学逃逸、四排分组 pad 和整体边界，并通过规范图映射、几何及 GDS 回读。报告 MUST 统计所有级间连接和 IO，不得将局部交叉移动当成全局减少。

#### Scenario: No improvement within budget
- **WHEN** 约定范围内的物理比较未发现更小的合法布局
- **THEN** 输出“本预算内未发现收益”的结论、已测范围和可复核记录，不外推为全局最优，也不自动扩展到 100 端口。

#### Scenario: Successful rearrangement
- **WHEN** 非恒等候选通过独立检查并具有更小完整面积
- **THEN** 保存其可再生映射、物理结果及相对同后端恒等对照的收益，并明确结论仅适用于已验证的小规模实验。
