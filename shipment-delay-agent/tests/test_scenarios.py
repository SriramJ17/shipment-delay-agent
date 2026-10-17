from shipment_agent.simulation import scenario_for_elapsed


def test_scenario_advances_each_minute():
    config = {
        "scenario_duration_seconds": 60,
        "loop": True,
        "scenarios": [{"id": "normal"}, {"id": "severe"}, {"id": "recovery"}],
    }
    assert scenario_for_elapsed(0, config)[1]["id"] == "normal"
    assert scenario_for_elapsed(60, config)[1]["id"] == "severe"
    assert scenario_for_elapsed(120, config)[1]["id"] == "recovery"
    assert scenario_for_elapsed(180, config)[1]["id"] == "normal"
