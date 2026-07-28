# 3GPP Path-Loss Stage 1 验收记录

## 1. 执行结论

截至 `2026-07-28`，本地分支 `zhiqian/3gpp` 已完成：

```text
Stage 1A: 内部 request/result contract 与输入验证
Stage 1B: UMi Street Canyon LOS/NLOS
Stage 1C: InH Office LOS/NLOS
```

本阶段只增加独立公式库和测试。没有接入 `channel.py`，没有修改
Geometry、Coordinate Calibration、`ChannelState`、scheduler、PHY、metrics
或 editor schema。

## 2. 标准与实现范围

主要依据：

- 3GPP TR 38.901 V19.4.0，Release 19。
- Table 7.4.1-1 中的 UMi Street Canyon 和 InH Office path-loss 模型。

已实现：

- 确定性平均 path loss。
- 公式对应的 shadow-fading 标准差元数据。
- UMi effective breakpoint。
- LOS/NLOS 公式选择。
- NLOS 的 `max(PL_LOS, PL_NLOS_candidate)` 保护。
- 适用范围检查与显式 debug 外推。
- 2D/3D 距离和天线高度一致性检查。

尚未实现：

- 随机 shadow-fading realization。
- Geometry/Calibration adapter。
- O2I building penetration。
- 材料损耗组合。
- CKM。
- `channel.py` runtime integration。
- `ChannelState` 或 scheduler 接口扩展。

## 3. 新增内部接口

实现文件：

```text
ran/radio/pathloss_3gpp.py
```

主要对象：

```text
PathLossRequest
PathLossResult
PathLossInputError
PathLossApplicabilityError
estimate_path_loss_3gpp()
```

输入频率单位固定为 MHz；模块内部按公式集中转换为 GHz 和 Hz。输入距离必须
已经是米，模块不会把 map units 猜测成米。

支持的 scenario：

```text
umi_street_canyon
inh_office
```

支持的 LOS state：

```text
los
nlos
```

## 4. 公式回归结果

测试文件：

```text
tests/radio/test_pathloss_3gpp.py
```

UMi，`fc=3500 MHz`、`hBS=10 m`、`hUT=1.5 m`：

| 检查点 | 预期与结果 |
| --- | --- |
| effective breakpoint | `210.0 m` |
| LOS，`d2D=10 m` | `66.7610328085 dB`，PL1 |
| LOS，`d2D=100 m` | `85.3141891025 dB`，PL1 |
| LOS，`d2D=210 m` | `92.0554308623 dB`，PL1 |
| LOS，`d2D=300 m` | `98.2442606638 dB`，PL2 |
| NLOS，`d2D=100 m` | `104.6438320117 dB` |
| shadow-fading std | LOS `4.0 dB`；NLOS `7.82 dB` |

InH，`fc=3500 MHz`、`hBS=3 m`、`hUT=1 m`：

| 检查点 | 预期与结果 |
| --- | --- |
| LOS，`d3D=10 m` | `60.5813608870 dB` |
| NLOS，`d3D=10 m` | `69.1472943043 dB` |
| NLOS，`d2D=0 m, d3D=2 m` | `48.4891798120 dB`，由 LOS max guard 决定 |
| shadow-fading std | LOS `3.0 dB`；NLOS `8.03 dB` |

## 5. 防误用规则

- 默认拒绝超出模型适用范围的输入。
- 只有调用者显式设置 `allow_extrapolation=True` 时才返回外推结果。
- 外推结果带 `is_extrapolated=True` 和具体 warning。
- UMi 要求 `10 <= d2D <= 5000 m`、`1.5 <= hUT <= 22.5 m`。
- InH 要求 `1 <= d3D <= 150 m`。
- 频率要求 `0.5 < fc_GHz < 100`。
- 非参考天线高度保留计算结果，但返回 `non_reference_height` warning。
- `distance_3d_m` 必须与 `distance_2d_m` 和高度差一致。

这些规则用于防止 map units、频率单位、距离或场景被静默误用。

## 6. 验收结果

执行命令：

```powershell
python -m unittest tests.radio.test_pathloss_3gpp -v
python -m unittest discover -v
python -m simulation.main -s bristol_topology --ran-mvp --ran-mvp-mode aggregate --ticks 10
git diff --check
```

结果：

```text
3GPP path-loss tests: 23/23 passed
All repository tests: 59/59 passed
MVP: 100 MB upload completed, undelivered=0, loss_rate=0
Shared interface changed: no
Runtime behavior changed: no
Existing channel fallback retained: yes
Push status: local only, not pushed
```

## 7. 本地提交

```text
c484927 Add validated 3GPP path-loss request contract
05dfc85 Implement 3GPP UMi path-loss formulas
7dfbf71 Implement 3GPP InH path-loss formulas
```

所有提交作者均为：

```text
Zhiqian He <xa25139@bristol.ac.uk>
```

## 8. 下一步 Gate

Stage 1C 到此停止。进入 Stage 2 前先 review：

1. 标准版本和公式是否由信道组共同接受。
2. Bristol 室外是否暂用 UMi Street Canyon。
3. Stage 2 是否只做独立 CLI/JSON debug 和当前 baseline 对比。
4. Stage 3 的 Geometry link type 到 3GPP scenario 映射由谁批准。
5. O2I 链路继续返回 unsupported，直到材料与 penetration 规则被确认。

在这些问题确认前，不应修改 `channel.py`、`ChannelState` 或 scheduler。
