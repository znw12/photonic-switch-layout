## Why

用户要求参考 Flexcompute WaveguideCrossing 的余弦渐变外形替换当前直条十字 crossing，同时保持现有 footprint。当前矩阵已有复用 CROSSING 单元，可在不移动路由的前提下替换内部形状。

## What Changes

- 增加参数化四臂凸余弦 crossing，保留默认 20×20 μm、1 μm 端口及直通配对。
- 最新 GSG 矩阵启用新形状，旧占位模型和旧文件保持可验证。
- 提供独立单元 GDS/图、几何合约和完整矩阵验证；不进行电磁优化或声称参考硅器件的性能。

## Capabilities

### New Capabilities
- `cosine-crossing`: 保持接口和占用的余弦渐变交叉单元。

### Modified Capabilities
无。

## Impact

影响 Beneš 配置、crossing 单元、几何验证、生成报告及最新示例。保持光学网络、器件、电学布局和层级，不改变 Waksman 原型，无新增依赖。
