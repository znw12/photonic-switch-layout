## Why

用户希望当前三排 pad 版减少电线横纵切换，允许 pad 间距扩大，并选择尽量保持约 36.4 mm 左右尺寸的折中方案。现有统一 pad 阵列与各级引出线错位，每网有三次方向转折、五个 via。

## What Changes

- 新增三排紧凑对齐扇出，按真实引出位置分布 pad，同排中心距不小于 100 μm，允许非均匀间距。
- 固定现有光学级放置，尽可能令 pad 与引出线同 x；部分网络只保留一次方向转折，其余允许三次。
- 用 M1 末段直接到 pad，减少中间换层，通过间隔和有序通道分配避免短路。
- 保存原版与新方案的实际宽高、转折、via 和线长对比，并验证完整 GDS 和重复生成。

## Capabilities

### New Capabilities
- `aligned-pad-fanout`: 在有限宽度内按引出位置调整三排 pad，减少转折并独立验证几何与连接。

### Modified Capabilities
无。原 two-row / three-row channel 模式保留。

## Impact

影响 Beneš 配置、分层电学扇出、pad 验证、统计、CLI、示例和文档。不改变光学网络、MZI、crossing、金属层数或最小弯曲半径；无需新增依赖。
