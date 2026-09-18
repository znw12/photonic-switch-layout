# 25 µm 光端口与局部共地版

本版保留单带 Beneš 网络、100 个有效输入/输出、128 条内部通道、13 级和 832 个 MZI。输入在西侧，输出在东侧；芯片面积优先于各光路几何长度的均匀性。

## 结果

| 项目 | 上一版 | 本版 |
|---|---:|---:|
| 芯片左右长度 | 36.394307 mm | 22.462870 mm |
| 芯片南北高度 | 10.853352 mm | 4.484092 mm |
| 面积 | 395.000225 mm² | 100.725576 mm² |
| MZI 光端口间距 | 60 µm | 25 µm |
| 每个 MZI 总长度 / 有效电极长度 | 1000 / 680 µm | 1000 / 680 µm |
| 最小圆弧半径 | 20 µm | 20 µm |
| 独立 S pad | 832 | 832 |
| G pad | 832 | 8（南北各 4） |
| 总 pad | 1664 | 840 |
| 每侧 pad 排数 / 最小同排中心距 | 3 / 120 µm | 3 / 120 µm |
| Via 数量 | 8460 | 5398 |
| Crossing 数量 / 单元 footprint | 7680 / 20×20 µm | 7680 / 20×20 µm |

左右长度减少 38.3%，面积减少 74.5%。尚未达到 20 mm 的软目标；保留了完整器件长度、波导半径、pad 间距和经过检查的电学引出空间。

## 参数化与层级

配置文件为 `examples/benes/compact-gsg/n100.json`。`ground_pads_per_side` 为每侧地 pad 数；0 保留原先的逐器件 G pad 方案。紧凑参考接口使用 `lane_pitch=25`、`mzi_height=50`、`metal_width=4`。原有 `examples/benes/gsg/n100.json` 保持可用，原配置序列化和摘要不受新增默认字段影响。

顶层继续引用 MZI 阵列、置换模块、电学布线和南北 pad bank；MZI 内仍复用定向耦合器和 via 单元。所有 crossing 均为独立可复用的 cosine 单元。局部共地网络单独保存在 `COMMON_GROUND` cell 中。

## 光学布线

两条调制臂仍相隔 25 µm，20/5/10 µm 的 S 宽度、GSG 间隙、G 宽度保持不变。外部光端口与调制臂对齐。器件之间按 50 µm 排距布置，相邻同电位 G 电极可在边界连接。

置换区内部保持连续 45° 斜线，同方向波导间距为 25√2≈35.355 µm。入口非直通通道交替偏移 4.672 µm，出口按上下半束偏移；两端用 R=20 µm 的圆弧 S 弯回到标准网格。S 弯的反曲率圆弧之间保留 2 µm 切线段以保证网格化后的实际多边形连接。最外侧直通波导保持原位。

这些过渡避免首末 crossing 紧贴圆弧。128 通道最大置换模块宽度从 3796.569 µm 缩至 1638.645 µm，包含两端过渡。模块的真实路径、切线、物理连接、交叉单元成对端口和间距均接受几何验证。

## 电学布线

每级用 M2 纵向地母线连接该级全部 G 桥，再由光学区域上下方的 M1 母线连接各级。第 1、4、8、11 级（从 0 开始编号）各在南北引出一个 G pad，共八个。所有器件的两个 G、所有这些 G pad 都属于同一个 GND。

每个 MZI 的 S 保持独立。S 从电极 pickup 沿中线直出，不再使用原先两个小转折；外部引线宽度为 4 µm，保证在两条间距 25 µm、宽 1 µm 的外部直波导之间有 10 µm 净距。M1 电极及 via landing 尺寸保持不变。器件内部获准的绝缘 M2 光波导上跨仍需由实际工艺确认。

Pad 优先对齐纵向引线，余下 pad 从附近可用位置分配；南北关于 y=0 对齐，三排 pad 的横向坐标由实际布线决定，并非所有位置都固定错开 25 µm。每排中心距始终不小于 120 µm。这个分配把所需水平布线通道由初版的 78 条降为 22 条。

转折统计必须区分范围：仅统计器件端口到 pad，832 条 S 的转折数由 1734 增至 2028，这是更窄布局的取舍；加上器件内 pickup 到端口的路径，S 总转折数由 3398 降至 2028，减少 40.3%。八条 G pad 引出均为直线。MZI 内原先短小的 S 引出台阶已消除。

共地组织参考 [Luceda 的阵列公共地设计](https://academy.lucedaphotonics.com/designs/opa_shuksan/opa_shuksan) 与 [Cornell 的 512 通道相控阵报告，第 12 页](https://www.cnf.cornell.edu/sites/default/files/2019-RA/2018cnfRA_6OPTS.pdf)。这些是热光阵列的连接组织参考，不是 TFLN 高速电气性能验证。当前采用直流/准静态驱动模型。

## 复现与验证

```bash
.venv/bin/benes-layout generate --config examples/benes/compact-gsg/n100.json --out output/benes/compact-gsg/n100
.venv/bin/benes-layout verify output/benes/compact-gsg/n100
.venv/bin/benes-layout gsg-study --config examples/benes/compact-gsg/n100.json --out output/benes/compact-gsg --reuse
.venv/bin/pytest -q
```

主版图：`output/benes/compact-gsg/n100/layout.gds`；总览、局部、pad 和单器件图随同导出。`pads.csv` 列出实际 840 个 pad，`manifest.json` 的 `ground_network.members` 列出全部 832 个器件地端口，避免将没有独立 pad 的 G 误判为未连接。

验证包含光学连接/间距/R≥20、三排 pad 间距、实际 GDS 中的 via enclosure、金属宽度/间距，以及独立导体提取：一个 GND 加 832 个独立 S，共 833 个电学网络，无未分配金属岛。新增 4/8/16/32 内部通道测试包含反向行映射；完整 128 通道版覆盖所有置换模块大小。断开公共地、断开电极 via、短接 G/S 和非法金属侵入都会被拒绝。

全部 393 项测试通过；最终兼容性和命令接口调整后另有 19 项针对性测试通过。两次完整生成的几何摘要、连接表及归一化 hash 一致，独立读回复核通过。相关报告保存在 `examples/benes/compact-gsg/reports/`。此版本不宣称已校准耦合比、插入损耗、串扰、Vπ 或射频性能。
