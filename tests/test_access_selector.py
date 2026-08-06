"""Access selection (haoyu Module 1) tests: explicit 5G/Wi-Fi, auto selection, unknown fallback."""
from __future__ import annotations

import unittest

from ran.access.selector import select_access
from ran.contracts import AgentIntent, GnbSite, Position
from ran.ue.request import build_ue_request

GNB = GnbSite(
    gnb_id="gnb_001",
    position=Position(90.0, 90.0),
    carrier_freq_mhz=3500.0,
    bandwidth_mhz=20.0,
    tx_power_dbm=46.0,
    total_prbs=106,
    antenna_elements=16,
    mimo_layers=2,
)


def _request(selected_access: str = "5g") -> "object":
    intent = AgentIntent(
        intent_id="i1",
        agent_id="agent_1",
        agent_pos=Position(100.0, 100.0),
        action="upload",
        target="youtube_server",
        content_type="video",
        service_type="video_upload",
        requested_payload_bytes=1024,
    )
    return build_ue_request(intent, ue_id="ue_1", service_instance_id="s1", selected_access=selected_access)


class AccessSelectionTests(unittest.TestCase):
    def test_explicit_5g(self) -> None:
        selection = select_access(_request("5g"), GNB)
        self.assertEqual(selection.selected_access, "5g")
        self.assertEqual(selection.access_type, "3gpp")
        self.assertEqual(selection.access_node_id, GNB.gnb_id)
        self.assertIn("single-cell", selection.reason.lower())

    def test_explicit_wifi(self) -> None:
        selection = select_access(_request("wifi"), GNB)
        self.assertEqual(selection.selected_access, "wifi")
        self.assertEqual(selection.access_type, "non_3gpp")
        self.assertEqual(selection.access_node_id, "wifi_reserved")

    def test_auto_selection_defaults_to_5g(self) -> None:
        selection = select_access(_request("auto"), GNB)
        self.assertEqual(selection.selected_access, "5g")
        self.assertEqual(selection.access_type, "3gpp")
        self.assertEqual(selection.access_node_id, GNB.gnb_id)

    def test_unknown_access_falls_back_to_5g(self) -> None:
        selection = select_access(_request("satellite"), GNB)
        self.assertEqual(selection.selected_access, "5g")

    def test_registration_flow_uses_selected_access(self) -> None:
        """Registration-access flow (haoyu Module 1 wiring): UERequest -> select_access consistency."""
        request = _request("wifi")
        selection = select_access(request, GNB)
        self.assertEqual(selection.selected_access, request.selected_access)
        self.assertEqual(selection.access_type, "non_3gpp")


if __name__ == "__main__":
    unittest.main()
