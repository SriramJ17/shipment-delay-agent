from shipment_agent.rules import calculate_eta_proposal


def test_severe_weather_affecting_route_adds_one_day():
    shipment = {
        "current_day": 1,
        "remaining_transit_days": 2,
        "original_eta_day": 3,
        "current_approved_eta_day": 3,
    }
    scenario = {
        "id": "severe",
        "label": "Severe",
        "checkpoints": [
            {"name": "Delhi", "severity": "normal", "hours_until_arrival": 0, "affects_remaining_route": False},
            {"name": "Transit", "severity": "severe", "hours_until_arrival": 18, "affects_remaining_route": True},
        ],
    }
    result = calculate_eta_proposal(
        shipment, scenario,
        {"normal": 0, "moderate": 0.5, "severe": 1, "extreme": 2},
    )
    assert result["severity_applied"] == "severe"
    assert result["delay_adjustment_days"] == 1
    assert result["proposed_eta_day"] == 4
    assert result["requires_change"] is True


def test_weather_at_checkpoint_not_affecting_remaining_route_is_ignored():
    shipment = {
        "current_day": 1,
        "remaining_transit_days": 2,
        "original_eta_day": 3,
        "current_approved_eta_day": 3,
    }
    scenario = {
        "id": "origin-severe",
        "label": "Origin severe",
        "checkpoints": [
            {"name": "Delhi", "severity": "extreme", "hours_until_arrival": 0, "affects_remaining_route": False},
        ],
    }
    result = calculate_eta_proposal(
        shipment, scenario,
        {"normal": 0, "moderate": 0.5, "severe": 1, "extreme": 2},
    )
    assert result["severity_applied"] == "normal"
    assert result["proposed_eta_day"] == 3
    assert result["requires_change"] is False
