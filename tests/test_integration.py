"""Integration tests: scenario, engine, contract roundtrip, backward compat."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from ran.contracts import RlcQueue
from ran.protocol import (
    PdcpEntity,
    RlcEntity,
    RlcRetxBlock,
    apply_transmission_to_rlc,
    build_pdcp_batch,
    build_rlc_queue,
    map_qos_flow_to_drb,
)
from ran.ue import state


# ---------------------------------------------------------------------------
# RlcQueue contract backward compatibility
# ---------------------------------------------------------------------------

class TestRlcQueueContract:
    def test_new_fields_in_asdict(self):
        d = asdict(RlcQueue("u", 3, 9, "embb", "UL", "AM", 100, 0, 0.0))
        assert "delivered_bytes" in d
        assert "dropped_bytes" in d
        assert d["delivered_bytes"] == 0
        assert d["dropped_bytes"] == 0

    def test_roundtrip_full_dict(self):
        q = RlcQueue("u", 3, 9, "embb", "UL", "AM", 100, 50, 1.5, 200, 10)
        d = asdict(q)
        q2 = RlcQueue(**d)
        assert q2 == q

    def test_roundtrip_partial_dict_missing_new_fields(self):
        """Old Java output missing new keys → defaults to 0."""
        d = {"ue_id": "u", "drb_id": 3, "qfi": 9, "slice_id": "embb",
             "direction": "UL", "rlc_mode": "AM", "queued_bytes": 100,
             "retransmission_bytes": 0, "head_of_line_delay_ms": 0.0}
        q = RlcQueue(**d)
        assert q.delivered_bytes == 0
        assert q.dropped_bytes == 0

    def test_to_queue_state_matches_contract(self):
        """RlcEntity.to_queue_state produces a valid RlcQueue."""
        rlc = RlcEntity(ue_id="u", drb_id=3, qfi=9, slice_id="embb",
                        direction="UL", mode="AM")
        rlc.enqueue(build_pdcp_batch.__wrapped__ if hasattr(build_pdcp_batch, '__wrapped__') else
                    _dummy_batch())
        qs = rlc.to_queue_state()
        d = asdict(qs)
        q2 = RlcQueue(**d)
        assert q2.queued_bytes == qs.queued_bytes
        assert q2.delivered_bytes == 0


def _dummy_batch():
    from ran.protocol.pdcp import PdcpBatch
    return PdcpBatch(3, 9, "embb", 1000, 2, 1002, 0, 0)


# ---------------------------------------------------------------------------
# Existing exports still work
# ---------------------------------------------------------------------------

class TestBackwardCompatExports:
    def test_old_imports_still_work(self):
        """Old import paths must not break."""
        from ran.protocol import (
            apply_transmission_to_rlc,
            build_pdcp_batch,
            build_rlc_queue,
            map_qos_flow_to_drb,
        )
        assert callable(apply_transmission_to_rlc)
        assert callable(build_pdcp_batch)
        assert callable(build_rlc_queue)
        assert callable(map_qos_flow_to_drb)

    def test_new_imports_work(self):
        from ran.protocol import PdcpEntity, RlcEntity, RlcRetxBlock
        assert callable(PdcpEntity)
        assert callable(RlcEntity)
        assert callable(RlcRetxBlock)


# ---------------------------------------------------------------------------
# Scenario integration (smoke test via import + construction)
# ---------------------------------------------------------------------------

class TestScenarioSmoke:
    def test_scenario_imports_cleanly(self):
        from ran.scenario import RanUploadScenario
        assert callable(RanUploadScenario)

    def test_engine_imports_cleanly(self):
        from ran.engine import RanEngine
        assert callable(RanEngine)

    def test_demo_imports_cleanly(self):
        from ran.demo import main
        assert callable(main)


# ---------------------------------------------------------------------------
# End-to-end tick mode (uses scene if available, otherwise skips)
# ---------------------------------------------------------------------------

class TestE2ETick:
    def test_tick_mode_runs(self):
        """Full tick-mode run for a few ticks — verifies no crashes."""
        try:
            from services.scene_service import SceneService
            scene = SceneService().load_scene("bristol_topology")
        except Exception:
            pytest.skip("bristol_topology scene not available")

        from ran.scenario import RanUploadScenario
        scenario = RanUploadScenario(scene)

        for tick in range(1, 6):
            state = scenario.step(tick)
            assert "rlc_grant" in state

            assert (
                state["rlc_grant"]["actual_sent_bytes"]
                == state["transmission"]["attempted_bytes"]
            )

            assert sum(
                segment["segment_bytes"]
                for segment in state["rlc_grant"]["segments"]
            ) == state["rlc_grant"]["actual_sent_bytes"]
            
            assert "rlc_queue_after" in state
            rlc = state["rlc_queue_after"]
            assert "delivered_bytes" in rlc
            assert "dropped_bytes" in rlc
            assert rlc["delivered_bytes"] >= 0
            assert rlc["dropped_bytes"] >= 0

    def test_aggregate_completes(self):
        """Aggregate mode should reach 'completed' within 5000 ticks."""
        try:
            from services.scene_service import SceneService
            scene = SceneService().load_scene("bristol_topology")
        except Exception:
            pytest.skip("bristol_topology scene not available")

        from ran.scenario import RanUploadScenario
        scenario = RanUploadScenario(scene)

        for tick in range(1, 5001):
            state = scenario.step(tick)
            if state.get("status") == "completed":
                break

        assert state["status"] == "completed"
        rlc = state["rlc_queue_after"]
        assert rlc["queued_bytes"] == 0
        assert rlc["retransmission_bytes"] == 0
        assert rlc["delivered_bytes"] > 0
