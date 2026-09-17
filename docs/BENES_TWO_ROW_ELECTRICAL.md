# 两排 pad 与共享置换区电学布局

后续三排优化版将完整尺寸缩至 36.394 × 10.792 mm，同排中心距仍为 100 μm，见 [三排布局与验证](BENES_THREE_ROW_ELECTRICAL.md)。本文保留两排基线结果。

本版恢复折叠前的单带 continuous 光学网络，以 y=0 为光学束中心，西侧输入、东侧输出。南北各两排 pad，每排 416 个，60 μm 方形 pad、100 μm 同排中心距、100 μm 排距、25 μm 排间错位。没有缩小 pad 中心距，也没有合并独立端子。

保留 100 活动/128 内部端口、13 级、832 个 1000 × 100 μm MZI 占位器件、1664 个独立 pad、7680 个 crossing、20 μm 最小弯曲半径。器件接口行距仍为 60 μm，不使用 compressed 局部间距方案。

## 实测结果

| 方案 | 宽 (mm) | 高 (mm) | 面积 (mm²) | via |
|---|---:|---:|---:|---:|
| 原单带 continuous，四排 pad | 41.708596 | 10.464212 | 436.447591 | 4992 |
| 两排，独立电学引出区 | 43.353084 | 10.960340 | 475.164541 | 8320 |
| **两排，共享置换区** | **41.785000** | **10.288244** | **429.894276** | **8320** |

共享方案面积在上述候选中最小，相对用户选定的原四排 continuous 版减少 **1.50%**。宽度增加 **76.404 μm**，高度减少 **175.968 μm**。未达到 20 mm 横向软目标；这不是全局最优证明。

原 pad 组间空白被连续两排利用。pad 阵列含错位占宽为 41.585 mm，外框每侧增加 100 μm 边距，因此宽度为 41.785 mm。光学 IO 的备用端口终止仍计入包围盒。

报告的器件至最后电学引出端实际横向跨度为 **41.288570 mm**；各级 M2 trunk 与置换区共同使用的横向范围合计 **7.450864 mm**。后者是逐级重叠宽度之和，不是整片缩短量。放置器把可用空间用于靠近连续 pad 阵列，减少长距离扇出；不能把共享宽度从最终芯片宽度直接减去。

新版本可实现光路的几何长度范围为 **41.505–47.449 mm**（含 MZI 占位长度），每条路径仍经过 13 个 MZI。光学损耗、串扰、驱动性能未由几何验证确定。

## 布线组织和外观

每个器件端子先通过短 M1 引线，到达 MZI 右侧直波导区内的 via，再通过 M2 形成有序 L 形引出。南侧按端子 y 递增分配 trunk x，北侧反序分配，因此主要电线整体上下协调。南北 pad 行、波导束和外框关于 y=0 对齐；独立网络名称保持正确，不强制每个逻辑端子具有镜像配对。

芯片外侧的扇出分用两层金属：M2 竖线、M1 横线、M2 pad 引出竖线。在 pad 阵列之前统一换回 M1，穿过内排 pad 下方后，再经 via 接入自己的 M2 pad。横线按区间冲突分层，可复用互不相交的高度；本次共享候选为 60 层横向通道，独立候选为 84 层。这里的“通道层级”是平面 y 位置，金属工艺层数始终只有两层。

每网实际五个 via，共 8320 个；新增换层是尺寸与电阻、寄生、良率之间的代价。同一网靠得很近的 M2 换层落点直接连成金属，避免留下小于规则的缝隙；没有放松线宽或间距检查。

## 置换区跨越合约

此前规则只允许 M2 跨过登记的水平直波导，导致电学通道与置换区分开占宽。本版明确采用 `insulated-placeholder-v1` 合约：允许 M2 在绝缘覆盖层上方跨过被动直段、斜段、弯曲和 crossing。M1 和 via 仍避开未授权的光学区域；M2 不能进入未授权 MZI 光学区域。

窗口绑定具体光学单元实例和所属电网，由实际金属多边形与光学间距区域的相交推导。共享参考版共有 67014 条邻近/跨越窗口记录，其中 crossing 类型 5836 条，涉及 2650 个不同 crossing 实例。它们包含间距邻域，不等同于独立光学 crossing 数；全芯片 crossing 总数仍为 7680。

独立验证重新核对窗口与实际金属、光学实例的对应关系。没有把整个置换区变成免检区域。这个合约仍为布局占位假设，真实 TFLN 工艺需验证介质厚度、金属吸收和 crossing/弯曲覆盖条件，不能据此直接流片。

## 参数、层级与运行

新模式参数：`electrical_routing="two-row"`、`share_interstage=true|false`。模式限定为 continuous、单带、central 两排 pad，并锁定同排中心距 100 μm；其他光学和金属尺寸继续由 Config 控制。旧模式、旧配置及旧产物回读保持兼容。

GDS 保留 stage、置换模块、crossing、MZI、各网金属路径、pad 与 via 层级；共享重复器件单元。规划使用有界的逐级放置和有序金属轨道分配，扇出使用区间调度；物理验证使用空间索引。小规模和 100/128 已验证，更大规模需重新生成并实测，不能从拓扑可扩展性推断工艺可行性。

```bash
MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout generate \
  --config examples/benes/two-row/shared.json --out output/benes/two-row/shared

MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout generate \
  --config examples/benes/two-row/separate.json --out output/benes/two-row/separate

.venv/bin/benes-layout verify output/benes/two-row/shared

MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout compare \
  output/benes/interstage/continuous output/benes/two-row/shared \
  output/benes/two-row/separate --out output/benes/two-row/comparison
```

CLI 也支持 `--electrical-routing two-row --share-interstage`，其余必要参数由配置提供。采用 `--no-share-interstage` 生成独立引出对照。`--n` 仍可改变规模，内部端口补齐到二次幂。

输出包括完整 `layout.gds`、`preview.png`、`detail.png`、`pads_detail.png`、配置、manifest、端口及 pad 表、开关设置和 report。示例和报告快照见 `examples/benes/two-row/`；派生 GDS 与大尺寸 manifest 保存在 `output/`。

## 验证证据

完整回归 **284 项通过**；最终报告一致性检查和格式调整后的相关测试 **47 项通过**。新增测试覆盖合法/非法参数、小规模正反行序、两排中心距和居中几何、光电实际连接、错误 pad、via、层、窗口、金属短路及未授权 MZI 覆盖。原四排单带 continuous bundle 已通过新版验证器回读。

共享与独立引出两个完整候选均通过验证。共享候选重复生成后，规范化几何摘要、尺寸、路径与电学统计一致，开关设置、端口表和 pad 表逐字节一致；随后独立 GDS 回读及金属网络提取通过。结果见 [验证摘要](../examples/benes/two-row/reports/verification.json)、[候选比较](../examples/benes/two-row/reports/comparison.json) 和 [独立回读](../examples/benes/two-row/reports/independent-readback.json)。
