from __future__ import annotations

from ran.contracts import AccessSelection, GnbSite, UERequest


def select_access(request: UERequest, gnb: GnbSite) -> AccessSelection:
    """Project implementation detail."""

    if request.selected_access == "wifi":
        return AccessSelection("wifi", "non_3gpp", "wifi_reserved", "Wi-Fi access is reserved only; the MVP does not execute a separate Wi-Fi path")
    return AccessSelection("5g", "3gpp", gnb.gnb_id, "MVP uses the single-cell 5G gNB by default")
