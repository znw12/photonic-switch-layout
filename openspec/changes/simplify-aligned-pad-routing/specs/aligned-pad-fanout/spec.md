## Purpose

为单带 Beneš 三排 pad 版提供保持横向尺寸的对齐扇出，通过非均匀 pad 分布减少实际电线转折及换层，并保留独立物理验证、完整端子覆盖和旧布局兼容性。

## ADDED Requirements

### Requirement: Width-preserving nonuniform pads
系统 SHALL 支持紧凑对齐扇出，在原级放置的横向边界内安排三排 pad。同排最小中心距 SHALL 可参数化且不小于 100 μm，允许扩大和非均匀排布；南北 bank SHALL 关于 y=0 对齐。

#### Scenario: Full reference layout
- **WHEN** 生成 100/128 三排对齐方案
- **THEN** 保留 1664 独立 pad，每侧行计数 278/277/277，光学级位置和左右边界与紧凑参考版一致。

### Requirement: Reduce actual direction changes
系统 SHALL 优先使可行 pad 与其电学引出线同 x，消除对应横向扇出；其他连接 SHALL 保留必要转折，不通过合并端子或放松金属间距实现减少。报告 SHALL 按真实线路方向统计转折、via 和线长，并比较完整宽高及面积。

#### Scenario: Mixed direct and lateral routes
- **WHEN** 部分 pad 可直接对齐而其他 pad 不可对齐
- **THEN** 对齐网一次几何转折、三个 via；未对齐网三次转折、五个 via，全部网络到达正确 pad。

### Requirement: Verification and compatibility
系统 SHALL 保留 M1/M2 两层金属、via、20 μm 半径和绝缘跨越合约，并独立验证 pad 间距、开短路、路由多边形及 via。旧 channel 模式 SHALL 保持可用。

#### Scenario: Corruption and repeatability
- **WHEN** pad、路由段或 via 被破坏，或重复生成合法方案
- **THEN** 破坏被验证器拒绝；重复方案几何和端口表一致且通过独立 GDS 回读，旧三排 bundle 也通过新版回读。
