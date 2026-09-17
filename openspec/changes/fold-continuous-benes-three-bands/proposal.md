## Why

用户明确要求将已完成的 Beneš 布局折叠成三条带，并选择连续斜线级间路由。现有连续模式只允许单带，而原折叠模式只支持旧置换和 2/3 排 pad，需要扩展兼容性及方向验证。

## What Changes

- 支持连续斜线、三条带、西侧输入/东侧输出、南北各四排 25 μm 错位 pad。
- 将 pad 按全局逃逸通道顺序分配到南北银行；不沿用无法在重叠 stage x 上成立的单带 stage pad 分组。
- 增加可配置的逐带级数，以完整布线面积比较多个 13 级分配方案。
- 保留 100/128 端口、832 MZI、1664 独立 pad、4992 via、7680 crossing 和最小半径 20 μm。
- 补充反向带的切向、几何及跨带金属验证，生成独立 GDS、配置、报告、预览并提交 Git。

## Capabilities

### New Capabilities
- `continuous-three-band-layout`：连续置换三带放置及四排错位 pad 的独立物理验证。

### Modified Capabilities
无。此前单带变更保留为基线；本轮是用户新授权的折叠扩展。

## Impact

涉及 Beneš 配置、级放置、几何/方向验证及测试。逻辑图和求解器不变；compressed 模式仍限定单带，不新增光学层或额外 MZI。
