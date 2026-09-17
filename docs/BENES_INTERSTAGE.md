# Beneš 级间置换优化

本轮保持 100 活动 / 128 内部端口、13 级、832 个 1000 × 100 μm MZI、单条光学带、20 μm 最小半径、南北各四排错位 pad。以完整芯片面积为首要目标，路径均匀性作为次级排序依据。

## 实现与接口

| 要求 | 本轮实现 |
|---|---|
| Parameterization | `interstage_routing` 选择 `legacy`、`continuous`、`compressed`；`shuffle_pitch` 独立控制纯光学置换区间距，MZI 接口仍为 60 μm |
| Hierarchy | shuffle/transition → 显式 CROSSING、圆弧、斜直段；相同模块复用；逆向模块复用正向层级并反向追踪对穿端口 |
| Routing strategy | A 合并同方向交换之间的冗余弯曲；B 在递归子块内收束、交叉、展开，逐规模比较完整过渡开销；两层金属逃逸及 pad 位置重新生成 |
| Scalability | A/B 验证至 100/128 全尺寸；正反模块覆盖 4–128 通道；C 搜索严格限制在 8、16 端口 |
| Verification | 从基本段验证端口、切向、半径、多边形、间距、两条 crossing 对穿路径；独立还原规范图；GDS 回读及真实金属连通提取；最佳候选重复生成 |

默认仍为 `legacy`，既有配置与 bundle 可回读。本节的单带 A/B 模式使用 `pad_distribution="stage"`、`pad_rows=4`、`fold_bands=1`。后续新增的连续斜线三带配置与实测结果见 [三带说明](BENES_CONTINUOUS_THREE_BANDS.md)；compressed 模式仍限定单带。`shuffle_pitch` 仅能用于 `compressed`，必须是有限、正值、在 1 nm 网格上，并且大于波导宽度与间距之和、不超过接口行距。进一步的弯曲、crossing 和过渡可行性由几何检查决定；参数通过并不保证所有布局都能通过验证。

后续单带 continuous 还支持独立的 `electrical_routing="two-row"` 配置：两排 100 μm 中心距 pad、居中电学布局和 M2 共享置换区，见 [两排电学布局](BENES_TWO_ROW_ELECTRICAL.md)。该配置不改变本节 A/B 四排对照结果。

C 不改变逻辑 Network 或求解器：输出显式 `placement_map`，保持开关 ID、外部端口编号和电学 stage 分组。实验配置记录在 bundle 的 `candidate.stage_orders` 中，采用同一确定性相邻交换后端进行恒等/重排对照；不会自动应用于 100 端口。

## 测量结果

| 候选 | 宽 (mm) | 高 (mm) | 面积 (mm²) | 实际压缩边界数 |
|---|---:|---:|---:|---:|
| legacy | 45.486328 | 10.464212 | 475.978579 | 0 |
| continuous | 41.708596 | 10.464212 | 436.447591 | 0 |
| compressed-q40 | 40.085584 | 10.464212 | 419.464049 | 6 |
| compressed-q45 | 40.583416 | 10.464212 | 424.673469 | 6 |
| compressed-q50 | 41.081248 | 10.464212 | 429.882888 | 6 |
| compressed-q55 | 41.523244 | 10.464212 | 434.508028 | 4 |
| compressed-q60 | 41.708596 | 10.464212 | 436.447591 | 0 |

最佳已验证候选为 **compressed-q40**，相对旧基线宽度和面积均减少 **11.87%**。压缩用于边界 0、1、2、9、10、11；其余边界保留 A。重复生成的规范化几何 hash、设置、端口/pad 表、尺寸和路径统计全部一致。

压缩模式对每种递归子块分别计入 fan-in、交叉核心、fan-out。只有完整模块变小才在该规模采用压缩，否则保留 A，逐边界实际选择写入 `report.json/interstage/boundaries`。q=60 是无压缩对照，不能作为 B 的压缩收益。不同候选各自生成完整 bundle，不受单个配置的 `max_candidates=1` 截断。

A/B 总 crossing 仍为 7680；A 的收益来自删去重复弯曲和缩短核心，不来自更改网络或减少 crossing。13 级不代表等光学损耗。目标 20 mm 尚未达到，不能仅通过当前级间波导整理宣称达到该尺寸。

## 8/16 端口重排实验

每个规模的候选包含恒等排列、递归子组交换、子组反序和索引位反转，固定首末级。前向/后向有限搜索最多进行 128 次逻辑评分，并筛选恒等对照及最多 8 个非恒等映射进行完整物理布局。

本次分别评估 13 和 31 个不同映射，并各生成 9 个主对照布局。全部包含 IO、电学、四排 pad 和 GDS 验证。两种规模均未找到比同后端恒等布局面积更小的结果；8 端口存在面积相同、次级指标排序更优的排列。结论仅适用于此次有界搜索，不代表全局最优。现版和 A 的小规模结果另存于 `reference-legacy` / `reference-continuous`，因后端不同不参与重排收益排序。

## 运行

```bash
# 生成最佳压缩参考配置；连接也可以指定为 0:73 或 reverse。
MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout generate \
  --config examples/benes/interstage/compressed-q40.json \
  --out output/benes/interstage/compressed-q40
.venv/bin/benes-layout verify output/benes/interstage/compressed-q40

# 完整 A/B 扫描、面积排序和最佳候选重复生成。
MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout interstage-study --scope full

# 独立进行 C 的两个小规模实验。
MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout interstage-study --scope placement

# 全部实验；--reuse 仅复用配置相同且重新独立验证通过的 bundle。
MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout interstage-study --scope all --reuse
.venv/bin/python -m pytest -q
```

每个完整 bundle 包含 GDS、整体/局部/pad 预览、manifest、解析配置、设置、端口与 pad 表、验证及资源报告。全尺寸汇总位于 `output/benes/interstage/study.json`，比较图和 CSV 位于 `comparison/`；重排实验的搜索与物理结果位于 `placement/n8/`、`placement/n16/`。配置与报告快照纳入 Git，派生 GDS 和完整 manifest 留在 `output/`。

## 检查边界

新模式独立检查 crossing 的四个端口、两条对穿关系、允许方向及物理实例数量，不将 crossing 视为任意四通节点。反向路径保留原对穿关系。连续斜直段在接缝处增加 3 nm 多边形搭接，以吸收 1 nm 网格舍入；端口、中心线长度及半径不变。短直段两端的相邻圆弧只在同一条已重建光路的局部连接邻域内处理，第三条波导和邻域之外仍须满足间距。

本次全项目回归 **237 项通过**，7 个全尺寸候选及最佳方案重复生成通过完整光电检查；C 的 18 个主对照布局和 4 个参考布局也全部通过。汇总证据见 `examples/benes/interstage/reports/verification.json`。

新模式可查出错误连接、端点间断、切向突变、过小半径、非法朝向、未声明几何、统计与过渡宽度篡改。GDS 检查覆盖层级/多边形一致性、金属开短路、宽度/间距、via 包围、pad 分组及光电窗口。旧 distributed/pitch60 bundle 也重新回读验证。

这些仍是 TFLN 占位器件与占位层叠。允许旋转的 crossing 合约不表示真实 TFLN 器件各朝向性能等效；替换为真实 PDK 时需声明允许朝向并重新做器件级检查。当前没有验证损耗、串扰、驱动响应或封装可达性。文献依据及适用边界记录在本变更的设计文档中。
