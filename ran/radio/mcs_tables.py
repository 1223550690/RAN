"""标准 CQI / MCS / BLER 查表(环节十一,文档 15.3)。

数据来源:TS 38.214 表 5.2.2.1-2(CQI,4-bit)与表 5.1.3.1-1(MCS,64QAM 上限)。
SINR→CQI 阈值与 BLER 采用 3GPP AWGN 仿真常用工作点(BLER 10%)。

用法:
    cqi = sinr_to_cqi(sinr_db)
    mcs = cqi_to_mcs(cqi)
    eff = mcs_spectral_efficiency(mcs)          # bits/symbol
    bler = sinr_to_bler(sinr_db, cqi)
"""
from __future__ import annotations

# (modulation_order, code_rate_1024, spectral_eff)——TS 38.214 表 5.2.2.1-2
# modulation_order: 0=QPSK, 1=16QAM, 2=64QAM, 3=256QAM
CQI_TABLE: list[tuple[int, int, float]] = [
    (0, 78, 0.1523),   # CQI 1
    (0, 120, 0.2344),  # 2
    (0, 193, 0.3770),  # 3
    (0, 308, 0.6016),  # 4
    (1, 449, 0.8770),  # 5
    (1, 602, 1.1758),  # 6
    (2, 378, 1.4766),  # 7
    (2, 434, 1.6953),  # 8
    (2, 490, 1.9141),  # 9
    (2, 553, 2.1602),  # 10
    (2, 616, 2.4063),  # 11
    (2, 658, 2.5703),  # 12
    (1, 466, 3.3223),  # 13
    (2, 517, 4.0391),  # 14
    (3, 490, 4.5234),  # 15
    (3, 616, 5.1152),  # 16(4-bit 表的 15 之后为 256QAM 扩展,这里取满表)
]

# SINR 工作点(3GPP AWGN,BLER≈10%):CQI 1-16 对应阈值 dB
SINR_CQI_THRESHOLDS_DB = [
    -6.7, -4.7, -2.3, 0.2, 2.4, 4.3, 5.9, 8.1, 10.3, 11.7, 14.1, 16.3, 18.7, 21.0, 22.7, 24.0,
]

# TS 38.214 表 5.1.3.1-1(MCS 0-27,64QAM 上限):(modulation_order, code_rate_1024)
MCS_TABLE: list[tuple[int, int]] = [
    (0, 120), (0, 157), (0, 193), (0, 251), (0, 308), (0, 379), (0, 449), (0, 526), (0, 602),  # 0-8 QPSK
    (1, 340), (1, 378), (1, 434), (1, 490), (1, 553), (1, 616), (1, 658),                      # 9-15 16QAM
    (2, 438), (2, 466), (2, 517), (2, 567), (2, 616), (2, 666), (2, 719), (2, 772),            # 16-23 64QAM
    (2, 822), (2, 873), (2, 910), (2, 948),                                                     # 24-27 64QAM
]

MAX_CQI = len(CQI_TABLE)          # 16
MAX_MCS = len(MCS_TABLE)          # 28


def sinr_to_cqi(sinr_db: float) -> int:
    """SINR → CQI(选择不超过阈值的最高 CQI;低于最差阈值 → 1)。"""

    cqi = 1
    for index, threshold in enumerate(SINR_CQI_THRESHOLDS_DB, start=1):
        if sinr_db >= threshold:
            cqi = index
        else:
            break
    return max(1, min(MAX_CQI, cqi))


def cqi_to_mcs(cqi: int) -> int:
    """CQI → MCS(取 MCS 表中频谱效率最接近且不超过 CQI 的索引)。"""

    cqi = max(1, min(MAX_CQI, int(cqi)))
    target_eff = CQI_TABLE[cqi - 1][2]
    best = 1
    for index in range(MAX_MCS):
        if mcs_spectral_efficiency(index) <= target_eff + 1e-9:
            best = index
    return max(1, best)


# modulation_order 索引 → 每符号比特:0=QPSK(2), 1=16QAM(4), 2=64QAM(6)
_MODULATION_BITS = (2, 4, 6)


def mcs_spectral_efficiency(mcs: int) -> float:
    """MCS → 频谱效率(bits/symbol)。"""

    mcs = max(0, min(MAX_MCS - 1, int(mcs)))
    modulation_order, code_rate = MCS_TABLE[mcs]
    return code_rate / 1024.0 * _MODULATION_BITS[modulation_order]


def mcs_modulation_order(mcs: int) -> int:
    """MCS → 调制阶数(QPSK=2, 16QAM=4, 64QAM=6)。"""

    mcs = max(0, min(MAX_MCS - 1, int(mcs)))
    return _MODULATION_BITS[MCS_TABLE[mcs][0]]


def sinr_to_bler(sinr_db: float, cqi: int) -> float:
    """预测 BLER:在 CQI 工作点附近呈 sigmoid 衰减(BLER 10% 工作点)。"""

    cqi = max(1, min(MAX_CQI, int(cqi)))
    working_point = SINR_CQI_THRESHOLDS_DB[cqi - 1]
    delta = sinr_db - working_point
    bler = 0.1 * math_exp(-1.2 * delta) if delta >= 0 else min(0.5, 0.1 * math_exp(1.6 * -delta))
    return max(0.001, min(0.5, bler))


def math_exp(x: float) -> float:
    import math

    return math.exp(x)
