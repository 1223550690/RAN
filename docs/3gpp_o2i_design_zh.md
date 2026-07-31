# 3GPP O2I 建筑穿透模型设计（Stage 4A-4B）

## 1. 状态与边界

| 项目 | 内容 |
| --- | --- |
| 状态 | Stage 4A 决策已冻结；Stage 4B 独立实现与测试已完成 |
| 标准 | 3GPP TR 38.901 V19.4.0 Clause 7.4.3.1 |
| 支持链路 | outdoor gNB 到 indoor UE（`outdoor_to_indoor`） |
| 场景 | UMi Street Canyon + low-loss/high-loss building profile |
| Runtime | 未接入 `channel.py`，原 MVP 路径不变 |
| 明确未做 | I2O、跨建筑 indoor link、随机场、shadow-fading realization |

官方参考：[ETSI TR 138 901 V19.4.0](https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf)。

## 2. 标准模型

确定性平均 O2I path loss 为：

```text
mean PL = PLb + PLtw + PLin
total PL = mean PL + penetration residual
```

- `PLb`：Clause 7.4.1 的 UMi outdoor basic path loss。
- `PLtw`：Table 7.4.3-2 的外墙材料组合损耗。
- `PLin = 0.5 × d2D-in`：UE 进入建筑后的深度损耗。
- penetration residual：零均值高斯项；Stage 4B 默认 realization 为 0，
  只返回标准差 metadata。

在 3.5 GHz 下：

| Profile | 材料组合 | `PLtw` | `sigmaP` |
| --- | --- | ---: | ---: |
| low-loss | 30% standard multi-pane glass + 70% concrete | 12.70 dB | 4.4 dB |
| high-loss | 70% IRR glass + 30% concrete | 27.50 dB | 6.5 dB |

Release 19 使用 `L_IRRglass = 25.4 + 0.11f`，`f` 的单位为 GHz。
不可沿用旧版本常见的 IRR glass 系数。

## 3. Stage 4A 决策

1. **Outdoor LOS/NLOS**：`blocking_building_ids` 非空时使用 UMi NLOS，
   否则使用 UMi LOS。目标建筑外墙不参与这个判断。
2. **Geometry 接口**：不扩展或修改 Geometry；只读已有距离、link type、
   blocking building 和目标 exterior crossing。
3. **建筑 profile**：调用者必须明确传入 `low_loss` 或 `high_loss`。
   Bristol dry-run 使用 `low_loss`，这不是对真实建筑材料的测量结论。
4. **材料比例**：严格使用 Table 7.4.3-2 的比例，不从地图的 `brick`、
   `drywall` 等标签临时推断。
5. **入射损耗**：使用 Table 7.4.3-2 中固定的 5 dB 项；Stage 4B 不增加
   自定义射线入射角修正。
6. **Indoor depth**：使用 Geometry 的 `indoor_distance_m`，而不是标准的
   UT-specific 随机深度。这是项目的 map-aware 扩展，结果会带 warning。
7. **随机项**：默认 residual 为 0 dB，同时返回 `sigmaP`。不做每 tick
   独立随机采样，空间相关随机场留到 Stage 5。
8. **防止双算**：地图中的 raw `penetration_loss_db` 仅供 debug 比较，
   不加入 3GPP O2I 总损耗。

标准 UMi O2I 随机深度支持到 25 m。Geometry 实测深度超过 25 m 时，严格
模式报错；只有显式设置 `allow_extrapolation=True` 才计算并标注外推。

## 4. 数据流与接口

```text
PropagationGeometry + GnbSite + heights + building profile
    -> o2i_path_loss_request_from_geometry()
    -> O2IPathLossRequest
    -> estimate_o2i_path_loss_3gpp()
    -> O2IPathLossResult
       {PLb, PLtw, PLin, residual, mean, total, sigmaP, warnings}
```

`PLb` 使用 gNB 到 UE 的完整 3D 直线路径。对当前 2.5D 直线几何，这等价于
标准所写的 `d3D-out + d3D-in`。adapter 不复制 raw wall-loss 字段，因此不会
意外双算。

旧的 `path_loss_request_from_geometry()` 仍保持 Stage 3 行为并拒绝 O2I。
新的 O2I 入口是附加接口，不改变任何已有调用方。

## 5. Bristol 结果

使用 provisional `300 m × 400 m` calibration、3.5 GHz、gNB 10 m、UE 1.5 m、
low-loss profile：

| Case | Outdoor state | `PLb` | `PLtw` | `PLin` | Mean total |
| --- | --- | ---: | ---: | ---: | ---: |
| Student Union centre | LOS | 82.70 | 12.70 | 12.97 | 108.37 dB |
| Gym centre | NLOS（Student Union blocker） | 107.40 | 12.70 | 10.66 | 130.76 dB |

Student Union 的 Geometry depth 为 25.94 m，略超标准随机深度支持，因此该
dry-run 必须显式允许外推。坐标标定仍是 provisional，数字用于工程验证，
不是现场测量的最终结果。

## 6. 复现

```bash
python -m unittest tests.radio.test_pathloss_3gpp_o2i -v
python -m unittest tests.radio.test_pathloss_3gpp_adapter -v
python -m unittest tests.radio.test_pathloss_3gpp_o2i_bristol -v
python -m experiments.debug_bristol_3gpp_o2i --gnb-height-m 10 --allow-extrapolation --pretty
```

Stage 4B 完成不表示 runtime 已切换。接入 `channel.py`、`ChannelState` 或
scheduler 属于后续跨模块评审范围。
