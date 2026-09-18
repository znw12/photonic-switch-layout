# 固定 footprint 的余弦渐变 crossing

当前 GSG 矩阵采用四臂凸余弦 crossing，参考 [Flexcompute / Tidy3D：Waveguide crossing based on cosine tapers](https://www.flexcompute.com/tidy3d/examples/notebooks/WaveguideCrossing/) 的二维形状。该页面的器件基于硅波导；本项目沿用 TFLN 版图的波导层及接口，所选尺寸为项目初值，不代表已经复现其光学性能。

## 几何尺寸

| 参数 | 当前值 |
|---|---:|
| 局部坐标 footprint | **20 × 20 μm** |
| 四端口位置 | (±10, 0)、(0, ±10) μm |
| 端口宽度 | **1 μm** |
| 中心方形宽度 | **3 μm** |
| 渐变臂最大设计宽度 | **4 μm** |
| 每臂渐变长度 | **8 μm** |
| 每端口直段长度 | **0.5 μm** |
| 每臂单侧轮廓采样点 | 33 |
| GDS 网格 | 1 nm |

每臂从中心向端口先加宽再收窄，半宽为 `A cos(phi)`，其中 A=2 μm，phi 从 `acos(3/4)` 线性变至 `−acos(1/4)`。四臂经 90° 旋转得到，并与中心方形、四段直引线连续相接。32 段离散的最大宽度接近设计值 4 μm；折线近似满足当前 2 nm 轮廓误差预算。

四个端口的坐标、宽度、方向及 w↔e、s↔n 的直通配对保持不变。0° 下的包围框为 20×20 μm；45° 下为约 **14.849242×14.849242 μm**，与旧十字单元一致。其余允许旋转由四重对称覆盖，所以不需要移动已有 crossing 或改变级间路由。

crossing 内两条路径的中心线都是直线，各长 20 μm，没有新增中心线弯曲；余弦边界是波导宽度渐变，不是中心线弯曲。外围圆弧仍遵守 R≥20 μm。

## 参数、复用和检查

配置新增 `crossing_model`、`crossing_center_width`、`crossing_max_width`、`crossing_port_straight`。旧默认 `placeholder` 保持原直条十字，最新 [GSG 配置](../examples/benes/gsg/n100.json) 显式启用 `cosine`。`crossing_half_length` 继续控制原有占用范围。

完整矩阵的 7680 个实例继续复用一个 `CROSSING` 单元。检查包含实际轮廓、中心连接、四重对称、端口宽度、两种旋转包围框，以及邻近波导净距和实际 M2 避让窗口；并非只检查单元外框。验证报告标记 `optical_transfer_calibrated=false`。损耗、串扰和相位响应需要后续基于实际 TFLN 截面的电磁验证，本次未运行 FDTD 或云端仿真。

## 输出与运行

```bash
MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout generate \
  --config examples/benes/gsg/n100.json --out output/benes/gsg/n100

.venv/bin/benes-layout verify output/benes/gsg/n100

MPLCONFIGDIR=/tmp/layout-mpl .venv/bin/benes-layout gsg-study
```

完整矩阵保存在 `output/benes/gsg/n100/layout.gds`，crossing 独立 GDS、图、模型和尺寸报告位于 `output/benes/gsg/n100/crossing/`。图直接绘制真实版图多边形。主报告包含 `crossing_device`，独立回读会重新核对；重复生成也比较 crossing 报告。

## 验证结果

完整回归 **376 项通过**，包含 **19 项余弦 crossing 测试**；最终独立导出检查另有 2 项通过。测试覆盖参数限制、四重对称、各允许角度的占用范围、凸起/收窄形状、轮廓和端口破坏、1/4/16 活动端口矩阵及报告篡改。

100 活动/128 内部端口矩阵维持 **36.394307×10.853352 mm**、7680 个 crossing、8460 个 via、1 个 GND 与 832 个独立 S。与旧十字版逐单元对比，只有 `CROSSING` 的轮廓与元数据改变，其余单元及电学路线完全一致；开关设置、pad 和光端口表逐字节相同，中心线路径指标不变。扩大后的 crossing 按实际多边形重新通过波导净距及金属绝缘跨越检查。

完整矩阵重复生成、独立 GDS 回读及旧十字版回读证据见 [验证报告](../examples/benes/gsg/reports/verification.json)、[重复生成结果](../examples/benes/gsg/reports/study.json) 和 [单元参数](../examples/benes/gsg/reports/crossing.json)。
