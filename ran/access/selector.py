from __future__ import annotations

from ran.contracts import AccessSelection, GnbSite, UERequest


def select_access(request: UERequest, gnb: GnbSite) -> AccessSelection:
    """Select the most suitable access network."""

    if request.selected_access == "wifi":
        return AccessSelection(
            "wifi",
            "non_3gpp",
            "wifi_reserved",
            "User explicitly selected Wi-Fi."
        )

    if request.selected_access == "5g":
        return AccessSelection(
            "5g",
            "3gpp",
            gnb.gnb_id,
            "MVP uses the single-cell 5G gNB by default."
        )

    # Auto selection
    return AccessSelection(
        "5g",
        "3gpp",
        gnb.gnb_id,
        "MVP uses the single-cell 5G gNB by default."
    )