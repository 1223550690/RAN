from __future__ import annotations

from ran.contracts import GnbSite, Position


GNB_ASSET_TYPE = "gnb_base_station"


def load_gnb_site_from_scene(scene) -> GnbSite:
    """从地图拓扑读取单个 gNB 站点。

    输入:
    - scene: structure 构建出的场景对象。

    输出:
    - GnbSite: 基站位置、带宽、功率、OFDM/MIMO 参数。
    """

    for area in getattr(scene, "areas", []):
        for element in getattr(area, "elements", []):
            details = getattr(element, "state_details", {}) or {}
            if details.get("asset_type") == GNB_ASSET_TYPE:
                return _site_from_element(element)
    # MVP 兜底：若地图暂未保存基站元素，使用左上角默认站点。
    return GnbSite(
        gnb_id="gnb_001",
        position=Position(80.0, 80.0),
        carrier_freq_mhz=3500.0,
        bandwidth_mhz=20.0,
        tx_power_dbm=46.0,
        total_prbs=106,
        antenna_elements=16,
        mimo_layers=2,
    )


def _site_from_element(element) -> GnbSite:
    details = getattr(element, "state_details", {}) or {}
    return GnbSite(
        gnb_id=str(details.get("gnb_id", element.node_id)),
        position=Position(float(element.center[0]), float(element.center[1])),
        carrier_freq_mhz=float(details.get("carrier_freq_mhz", 3500.0)),
        bandwidth_mhz=float(details.get("bandwidth_mhz", 20.0)),
        tx_power_dbm=float(details.get("tx_power_dbm", 46.0)),
        total_prbs=int(details.get("total_prbs", 106)),
        antenna_elements=int(details.get("antenna_elements", 16)),
        mimo_layers=int(details.get("mimo_layers", 2)),
    )
