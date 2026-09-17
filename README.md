# Parametric photonic switching layouts

项目现在提供两个独立生成器：`waksman-layout` 保留精确 N 端口网络；`benes-layout` 使用完整、等开关级数的 Beneš 内核。Beneš 默认外部 100×100、内部 128×128，采用 **整片面积优先、路径均匀性其次** 的优化顺序。

新版的运行方法、尺寸与验证结果见 [Beneš 使用与设计说明](docs/BENES.md)。以下保留原 Waksman 版本的说明。

最新版本在三排 pad 基础上减少电线转折：同排最小中心距扩大到 **120 μm**，按引出位置非均匀错列，**762 条连接只转一次**。左右尺寸保持，完整尺寸为 **36.394 × 10.764 mm**，总转折减少 **30.53%**、via 减少 **18.32%**；见 [pad 对齐与转折简化](docs/BENES_ALIGNED_PADS.md)。

原三排紧凑版仍保留，同排中心距固定 100 μm、排间横向错位 25 μm、纵向排距 70 μm，完整尺寸为 **36.394 × 10.792 mm**；见 [三排紧凑布局与验证](docs/BENES_THREE_ROW_ELECTRICAL.md)。

两排 pad 的共享置换区布局仍保留，完整尺寸为 **41.785 × 10.288 mm**，较原四排 continuous 版面积减少 **1.50%**；见 [两排电学布局与验证](docs/BENES_TWO_ROW_ELECTRICAL.md)。

此前的局部 40 μm 光学间距、按级分组四排 pad 布局约为 **40.086 × 10.464 mm**，见 [级间置换优化结果与运行方法](docs/BENES_INTERSTAGE.md)。MZI 接口行距仍为 60 μm；**45.486 × 10.464 mm** 的默认布局继续保留，见 [紧凑版基线](docs/BENES_DISTRIBUTED_PADS.md)。

连续斜线也支持三带折叠，保留西侧输入、东侧输出及南北四排错位 pad。完整尺寸约 **31.507 × 28.737 mm**；左右尺寸缩短，但总面积增加，见 [三带结果与运行方法](docs/BENES_CONTINUOUS_THREE_BANDS.md)。

一个可运行的任意 N 端口光子交换矩阵版图生成器。默认精确生成 100×100 Waksman：573 个占位 2×2 TFLN MZI，保留同时 100 条一对一连接能力，支持先只启用一条连接。

这是 **placeholder technology 的完整布线示例**。波导、耦合器、交叉、电极尺寸不是经过工艺验证的 TFLN 器件；bar/cross 状态也不是已校准的驱动电压。

## 安装与运行

已验证环境：Python 3.13.5、gdsfactory 9.51.0、KLayout 0.30.12。全部 Python 依赖版本保存在 `requirements.lock`。

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .

.venv/bin/waksman-layout generate --config examples/n100.json --out output/n100 --connections 0:73
.venv/bin/waksman-layout verify output/n100
```

当前工作目录已建立 `.venv`，可直接运行后两条命令。也可以使用提供的 Conda 配方：

```bash
conda env create -f environment.yml
conda activate waksman-layout
waksman-layout generate --config examples/n100.json --out output/n100
```

端口编号为 **0–N−1**。输入连接可以是 `0:73,1:4`、JSON 文件、`identity`、`reverse` 或 `none`。

```bash
.venv/bin/waksman-layout solve --n 100 --connections examples/connections.json --out output/settings.json
.venv/bin/waksman-layout generate --n 4 --out output/n4 --connections reverse
.venv/bin/waksman-layout generate --n 16 --out output/n16 --connections reverse
.venv/bin/waksman-layout benchmark --sizes 16,100,256,1024 --out output/scaling.json
.venv/bin/python -m pytest -q
```

没有显示器的环境可以设置 `MPLCONFIGDIR=/tmp/waksman-mpl`。生成器使用 Agg 渲染器，不需要图形桌面。`solve` 和 `benchmark` 不导入版图依赖，也不生成几何。

## 五项设计要求

| 要求 | 实现 |
|---|---|
| Parameterization | `Config` 校验 N、器件尺寸、端口、半径、金属/via、pads、层与搜索预算；输出完整解析配置 |
| Hierarchy | CHIP → 递归子网络 → MZI；复用 straight、swap/crossing、pad、via 单元；GDS 不扁平化 |
| Routing strategy | 显式相邻交换 crossing 网络；分栏电学逃逸通道；M1 横向引出、M2 纵向到 north/south pads |
| Scalability | 任意正整数 N；开关数 O(N log N)，逻辑深度 O(log N)；分别测量拓扑和完整几何的资源需求 |
| Verification | 独立状态遍历、端口/几何检查、空间索引查碰撞、GDS 回读和实际金属连通区域提取 |

网络使用 `S(n)=n−1+S(floor(n/2))+S(ceil(n/2))`，`S(1)=0`，不将 100 填充为 128。单个 MZI 可以同时传递两路光，要求各输入映射到不同输出。部分连接请求会被确定性补成完整排列；未请求的光路仍存在，单连接工作时其他输入需保持无光。重配置可以改变已有路径，不保证不中断。

## 光学和电学布局

- 西侧输入、东侧输出；光学中心线最小弯曲半径 20 um。
- 每次必要的端口换序使用显式、可定位的 crossing 单元；交叉点不被当成任意四通连接。
- 圆弧采用误差受控的多边形离散化，内部接缝有 5 nm 受控重叠，避免 1 nm 网格取整造成断点。外部端口在网格上对齐。
- 两层金属与 VIA 使用不同 GDS layer/datatype；只有显式 via 建立跨层电连接。
- M2 在预留的直波导窗口上绝缘跨越，窗口禁止放置 via。这是本示例明确采用的绝缘堆栈假设，需要真实工艺重新确认。
- 每个 MZI 默认两个独立电学端口，各接一个 pad：100 端口例子共 **1146 pads**。默认不合并公共回流。电学端口数量、名称和位置可配置。
- north/south pad 分配支持按位置分半的 `nearest` 和每个 MZI 上下分开的 `split`；同一 x 的相反方向 M2 干线必须在 y 方向分离。
- 搜索预算内比较不同 pad/channel pitch 与分配策略，最小化包含 pads 的完整 die 包围盒；随后比较最坏路径 crossing 数和总波导长度。搜索不宣称全局最优。

初始 profile 的单排 pads 下界：每侧 573 pads，100 um pitch、60 um pad 宽，对应至少 **57.26 mm** 的横向跨度。默认完整布线结果约 **89.098 × 8.240 mm**，包含 4522 个光学 crossings。该结果展示可扩展布线能力，不能视为低损耗或可直接投片的交换芯片；真实 MZI、电极与封装规则会显著改变尺寸。

## 输出与失败行为

| 文件 | 内容 |
|---|---|
| `layout.gds` | 带子网络和组件层次的完整几何 |
| `preview.png`, `detail.png` | 从真实多边形渲染的全局图与局部图 |
| `config.json` | 完整解析参数和层映射 |
| `network.json` | 与几何无关的逻辑边和开关端口映射 |
| `manifest.json`, `cell_names.json` | 物理位置、路由段、接口与 GDS 单元映射 |
| `pads.csv` | 每个电学端口与 north/south pad 的对应关系 |
| `settings.json` | 请求连接、补全连接、每个 MZI 的 bar/cross 状态 |
| `report.json` | 候选比较、检查结果、长度/面积/交叉/资源指标和假设 |

`report.json` 中的最坏路径长度包括 MZI 占位长度；`total_interconnect_length_um` 仅统计单元间波导。最大长度与最大 crossing 数分别对合法路径求最大值，不要求发生在同一条路径。峰值 RSS 是整个进程的高水位，不是各阶段独立内存。

不能合法布线或候选预算耗尽时，CLI 返回非零退出码，写出失败报告，不把残缺 GDS 当作成功结果。生成目录是派生输出，不要把手工编辑文件放在其中。`output/` 与 `.venv/` 不纳入 Git。

## 替换器件与修改参数

优先修改 JSON 配置后重新生成。例如改变 `mzi_length`、`terminal_offsets` 或 `pad_pitch`，逻辑开关编号保持不变，物理位置和路线会重算。完整可配置字段参见 `src/waksman_layout/config.py`。

Python API 的 `build_layout(config, mzi_factory=...)` 接受自定义器件工厂。工厂须在传入的 `Library` 注册并返回名为 `MZI` 的 `Cell`，包含：

- `i0/i1/o0/o1` 光端口，位置和方向符合配置；
- 配置声明的电学端口；
- bar/cross 传输对和合法方向声明；
- 自身几何、子单元与局部器件交互范围。

布局器检查接口，不兼容时直接报错。实际 PDK 的复杂器件需通过适配器转换到这个接口，并补充器件内部专用规则；当前校验器不代替 foundry DRC。请同时调整配置中的外形与端口位置，而非把更大的器件硬塞进旧占位尺寸。

## 验证覆盖

- N=1–7 的全部排列；N=100 的全部 10000 个单输入/输出组合。
- N=100 的恒等、反序、全部循环移位和 100 个固定种子的随机全排列。
- N=25、101 等奇数规模，以及 N=256、1024 的拓扑/状态验证。
- N=4、16、100 完整版图，以及小规模奇数网络的几何回读。
- 故障注入：断波导、交叉映射错误、半径不足、意外交叉、短路、缺失 via、via 包围不足和导出文件被修改。
- GDS 单元多边形与实例变换核对；从回读的 M1/M2/VIA 提取实际导体分区，检查每个端口是否到达对应 pad。

全排列抽样不等于遍历 100! 种组合。验证报告也不声称评估了 TFLN 损耗、串扰、消光比、电极高速性能或制造良率。

## 模块

- `network.py`：逻辑图、递归染色求解、独立遍历。
- `config.py`：配置和规则校验。
- `geometry.py`：显式组件几何、接口、gdsfactory 层次输出。
- `layout.py`：stage 放置、crossing 调度、电学通道和 pad 分配。
- `verify.py`：几何核对、GDS 回读和电学提取。
- `cli.py`：候选搜索、命令行、输出与规模指标。
- `preview.py`：实际几何的离线渲染。

Beneš 多排 pad 与折叠布局：见 [实验说明](docs/BENES_RESHAPE.md)，支持南北各 2/3 排 pad，附六种 100 端口布局的尺寸及验证比较。

单条带、南北各四排错位 pad：见 [实现与测量结果](docs/BENES_STAGGERED_PADS.md)，相邻排错开 25 μm，附完整 100 端口验证。
