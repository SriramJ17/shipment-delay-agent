from datetime import datetime, timezone
from typing import Any


def calculate_eta_proposal(
    shipment: dict[str, Any],
    scenario: dict[str, Any],
    delay_rules: dict[str, float],
) -> dict[str, Any]:
    """Compute an illustrative ETA candidate from route-impacting weather.

    Weather severity is applied only to checkpoints that affect the remaining
    route and have a positive estimated time to arrival. The maximum applicable
    severity is used to avoid adding delays multiple times for the same event.
    """
    severity_rank = {"normal": 0, "moderate": 1, "severe": 2, "extreme": 3}
    relevant = [
        cp for cp in scenario.get("checkpoints", [])
        if cp.get("affects_remaining_route", False)
        and float(cp.get("hours_until_arrival", 0)) > 0
    ]
    if not relevant:
        severity = "normal"
    else:
        severity = max(
            (cp.get("severity", "normal").lower() for cp in relevant),
            key=lambda item: severity_rank.get(item, 0),
        )
    delay_days = float(delay_rules.get(severity, 0.0))

    # Use current progress as the baseline. The demo fixture represents
    # remaining transit in days; the rule adjustment is applied to that value.
    current_day = float(shipment.get("current_day", 0.0))
    remaining_days = max(0.0, float(scenario.get(
        "remaining_transit_days", shipment.get("remaining_transit_days", 0.0)
    )))
    proposed_eta_day = round(current_day + remaining_days + delay_days, 2)

    current_approved_eta = float(
        shipment.get("current_approved_eta_day", shipment.get("original_eta_day", proposed_eta_day))
    )
    delta = round(proposed_eta_day - current_approved_eta, 2)

    return {
        "scenario_id": scenario.get("id", "unknown"),
        "scenario_label": scenario.get("label", "Unknown scenario"),
        "severity_applied": severity,
        "delay_adjustment_days": delay_days,
        "current_approved_eta_day": current_approved_eta,
        "proposed_eta_day": proposed_eta_day,
        "delta_days": delta,
        "requires_change": abs(delta) >= 0.25,
        "relevant_checkpoints": [
            {
                "name": cp.get("name"),
                "severity": cp.get("severity"),
                "hours_until_arrival": cp.get("hours_until_arrival"),
            }
            for cp in relevant
        ],
        "calculation_note": (
            f"ETA = current day ({current_day}) + remaining transit "
            f"({remaining_days} days) + weather adjustment ({delay_days} days)."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
