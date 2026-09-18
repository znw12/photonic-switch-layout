## Context

参考 https://www.flexcompute.com/tidy3d/examples/notebooks/WaveguideCrossing/ 。该硅波导演示以四个凸余弦渐变臂连接中心方形，渐变臂先加宽再收窄至中心；此处仅参考二维轮廓。当前 CROSSING 半长 10 μm，端口宽 1 μm，矩阵中有 7680 个旋转复用实例。

## Goals / Non-Goals

**Goals:** 保持原接口、0°/45° 及对称旋转后的包围框、层级和路线；替换单元轮廓并可独立检查。

**Non-Goals:** 不复制硅器件材料或性能，不做 FDTD，不修改中心线弯曲半径、网络拓扑、电学或 pad。

## Decisions

1. 增加 crossing_model（默认 placeholder 保留旧行为）、crossing_center_width=3、crossing_max_width=4、crossing_port_straight=0.5，均为 μm。最新 GSG 示例明确启用 cosine。
2. 每个臂从中心半宽 c/2 到半长 h−lead，半宽为 A cos(phi)，A=max_width/2，phi 从 acos(c/max_width) 线性变到 −acos(wg_width/max_width)。这种分支具有一个凸起峰值；端口处保留短直段，四臂共享形状并绕中心旋转。
3. 中心方形和四臂组成一个连续四端口单元。端口沿直线中心线，原有 20 μm 半径约束仍用于路由弯曲，不将 taper 边缘曲率误认为波导中心线弯曲。
4. 轮廓在 1 nm 网格离散，采样满足 chord_error；检查 0° 和 45° 占用包围框、旋转对称、端口宽、中心连续和真实渐变形状，拒绝越界或未连接几何。
5. 增加 crossing 报告和 standalone GDS/图；全矩阵保持尺寸、crossing 数量、光程以及电学网络和过孔数。扩大后的光学区域重新检查间距和 M2 避让窗口。

## Risks / Trade-offs

- 硅波导余弦轮廓不等同 TFLN 优化结构 → 明确形状参考和未标定状态。
- 扩宽可能改变邻近净距 → 固定原旋转占用包围框，并重新验证全矩阵实际几何。
- 更多多边形顶点增加验证成本 → 由误差控制采样并继续复用单元。
