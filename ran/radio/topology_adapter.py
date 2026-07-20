from __future__ import annotations

from ran.contracts import GnbSite, Position


GNB_ASSET_TYPE = "gnb_base_station"


def load_gnb_site_from_scene(scene) -> GnbSite:
    """Project implementation detail."""

    for area in getattr(scene, "areas", []):
        for element in getattr(area, "elements", []):
            details = getattr(element, "state_details", {}) or {}
            if details.get("asset_type") == GNB_ASSET_TYPE:
                return _site_from_element(element)
    return GnbSite(
        gnb_id="gnb_001",
        position=Position(80.0, 80.0),
        carrier_freq_mhz=3500.0,
        bandwidth_mhz=20.0,
        tx_power_dbm=46.0,
        total_prbs=106,
        antenna_elements=16,
        mimo_layers=2,
        nominal_pusch = 80,
        gscn = 0,
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
        nominal_pusch=int(details.get("nominal_pusch",80)),
        gscn=int(details.get("gscn",80)),
    )
