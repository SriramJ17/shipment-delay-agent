import json
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from shipment_agent import state
from shipment_agent.judge_agent import evaluate_proposal
from shipment_agent.rules import calculate_eta_proposal
from shipment_agent.simulation import (
    current_scenario,
    load_rules,
    load_scenarios_config,
    load_shipment,
)

st.set_page_config(page_title="Shipment Delay Prediction Agent", page_icon="🚚", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1500px;}
      .app-title {font-size: 2.2rem; font-weight: 750; letter-spacing: -0.04em; color: #111a35; margin-bottom: 0;}
      .app-subtitle {font-size: .95rem; color: #596783; margin-top: .1rem; margin-bottom: 1.2rem;}
      .panel {border: 1px solid #dbe7fb; border-radius: 12px; padding: 16px 18px; background: #fff; height: 100%;}
      .panel-title {font-size: 1.25rem; font-weight: 700; color: #101a37; margin-bottom: 12px;}
      .kpi-strip {border: 1px solid #dbe7fb; border-radius: 12px; padding: 17px 12px; background: #f7faff; margin: 12px 0 18px;}
      .kpi-label {font-size: .88rem; color: #4d5c7a; margin-bottom: 7px;}
      .kpi-value {font-size: 1.42rem; font-weight: 750; color: #101a37; line-height: 1.2;}
      .kpi-sub {font-size: .83rem; color: #596783; margin-top: 4px;}
      .delay-pill {display:inline-block; background:#fff0cb; color:#a84300; border-radius:8px; padding:6px 10px; font-weight:700; font-size:.85rem; white-space:nowrap;}
      .weather-card {border-radius: 11px; padding: 14px; min-height: 165px; border: 1px solid #e7edf5;}
      .weather-normal {background: #effaf3; border-color:#d8f1e1;}
      .weather-moderate {background: #fff9e9; border-color:#f6e8bc;}
      .weather-severe, .weather-extreme {background: #fff1f2; border-color:#f8dadd;}
      .checkpoint-name {font-size:1rem; font-weight:750; color:#111a35;}
      .checkpoint-kind {font-size:.82rem; color:#52617e; margin-bottom:12px;}
      .weather-status {font-size:.93rem; font-weight:700; color:#17213c; margin-top:8px;}
      .weather-desc {font-size:.82rem; color:#52617e; min-height:35px;}
      .impact-normal {background:#ddf4e5; color:#163a2a; border-radius:7px; padding:7px 9px; font-weight:700; font-size:.85rem; margin-top:10px;}
      .impact-delayed {background:#ffe0e2; color:#b42318; border-radius:7px; padding:7px 9px; font-weight:700; font-size:.85rem; margin-top:10px;}
      .small-muted {font-size:.84rem; color:#65718a;}
      .detail-row {display:flex; justify-content:space-between; gap:16px; padding:8px 2px; border-bottom:1px solid #e7edf5; font-size:.88rem; color:#24314f;}
      .detail-row:last-child {border-bottom:0;}
      .eta-box {background:#f3f8ff; border:1px solid #e3edfc; border-radius:10px; padding:15px; min-height:118px;}
      .eta-box-delay {background:#fff3f3; border-color:#f8dfe0;}
      .eta-label {font-size:.86rem; color:#4d5c7a; margin-bottom:8px;}
      .eta-value {font-size:1.45rem; font-weight:750; color:#111a35;}
      .eta-note {font-size:.82rem; color:#52617e; margin-top:4px;}
      .weather-alert {background:#fff2f3; border:1px solid #f8dfe0; border-radius:10px; padding:13px 15px; color:#27324d;}
      .weather-alert-title {font-size:1rem; font-weight:750; color:#111a35; margin-bottom:6px;}
      .badge {display:inline-block; border-radius:7px; padding:5px 9px; font-size:.82rem; font-weight:700; background:#e9f2ff; color:#075dc8;}
      div[data-testid="stDataFrame"] {border:1px solid #dbe7fb; border-radius:8px; overflow:hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

shipment = load_shipment()
state.initialize(shipment)
shipment_id = shipment["shipment_id"]
scenario_index, scenario, elapsed, seconds_remaining = current_scenario()
rules = load_rules()
current_state = state.get_state(shipment_id)
pending = current_state["pending_proposal"]

# Run the existing assessment flow automatically in the background. The UI is read-only:
# no scenario controls, judge verdict, or approval/rejection actions are shown.
def perform_background_assessment():
    current = state.get_state(shipment_id)
    if current["pending_proposal"] is not None:
        return
    ship = dict(shipment)
    ship["current_approved_eta_day"] = current["current_approved_eta_day"]
    proposal = calculate_eta_proposal(ship, scenario, rules)
    state.log_event(shipment_id, "WEATHER_ASSESSED", {
        "scenario_id": scenario["id"],
        "scenario_label": scenario["label"],
        "proposal": proposal,
    })
    if not proposal["requires_change"]:
        state.clear_pending(shipment_id, scenario["id"])
        return
    payload = {
        "shipment": {
            "shipment_id": shipment_id,
            "origin": shipment["origin"],
            "destination": shipment["destination"],
            "current_day": shipment["current_day"],
            "remaining_transit_days": shipment["remaining_transit_days"],
            "current_approved_eta_day": current["current_approved_eta_day"],
        },
        "scenario": scenario,
        "delay_rules": rules,
        "proposal": proposal,
    }
    try:
        verdict = evaluate_proposal(payload)
        proposal["judge"] = verdict
        proposal["judge_status"] = verdict["verdict"]
        if verdict["verdict"] == "PASS":
            state.set_pending(shipment_id, proposal, scenario["id"])
            state.log_event(shipment_id, "JUDGE_PASSED_PROPOSAL_PENDING_HUMAN", {
                "scenario_id": scenario["id"], "verdict": verdict, "proposal": proposal
            })
        else:
            state.log_event(shipment_id, "JUDGE_DID_NOT_PASS", {
                "scenario_id": scenario["id"], "verdict": verdict, "proposal": proposal
            })
            state.clear_pending(shipment_id, scenario["id"])
    except Exception as exc:
        state.log_event(shipment_id, "JUDGE_ERROR_FAIL_CLOSED", {
            "scenario_id": scenario["id"], "error": str(exc)
        })
        state.clear_pending(shipment_id, scenario["id"])

if "last_background_scenario" not in st.session_state:
    st.session_state.last_background_scenario = None
if st.session_state.last_background_scenario != scenario["id"]:
    st.session_state.last_background_scenario = scenario["id"]
    if pending is None:
        perform_background_assessment()
        current_state = state.get_state(shipment_id)
        pending = current_state["pending_proposal"]

# A pending proposal is shown as the predicted ETA; the stored approved ETA is not changed.
approved_eta = float(current_state["current_approved_eta_day"])
if pending:
    predicted_eta = float(pending["proposed_eta_day"])
    delta_days = predicted_eta - float(shipment["original_eta_day"])
    applied_severity = str(pending.get("severity_applied", "normal")).lower()
    weather_delay = float(pending.get("delay_adjustment_days", max(0, delta_days)))
else:
    display_proposal = calculate_eta_proposal(
        {**shipment, "current_approved_eta_day": approved_eta}, scenario, rules
    )
    predicted_eta = float(display_proposal["proposed_eta_day"])
    delta_days = predicted_eta - float(shipment["original_eta_day"])
    applied_severity = str(display_proposal.get("severity_applied", "normal")).lower()
    weather_delay = float(display_proposal.get("delay_adjustment_days", max(0, delta_days)))

# Header
header_left, header_right = st.columns([5, 1.25], vertical_alignment="center")
with header_left:
    st.markdown('<div class="app-title">🚚 Shipment Delay Prediction Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">AI-powered ETA updates using weather conditions · Simulated shipment data</div>', unsafe_allow_html=True)
with header_right:
    st.markdown(
        f'<div style="background:#f5f8fc;border-radius:10px;padding:12px 14px;">'
        f'<div class="small-muted">Last updated</div><b>{datetime.now().strftime("%b %d, %Y %I:%M %p")}</b></div>',
        unsafe_allow_html=True,
    )

# KPI strip
kpis = st.columns([1, 1.2, 1, 1, 1.4])
with st.container():
    st.markdown('<div class="kpi-strip">', unsafe_allow_html=True)
    values = [
        ("Shipment ID", shipment_id, ""),
        ("Route", f"{shipment['origin']} → {shipment['destination']}", ""),
        ("Status", shipment["status"], ""),
        ("Original ETA", f"Day {shipment['original_eta_day']:g}", "Illustrative demo day"),
        ("Current / Predicted ETA", f"Day {predicted_eta:g}", f"{delta_days:+g} days vs. original ETA"),
    ]
    for col, (label, value, sub) in zip(kpis, values):
        with col:
            st.markdown(f'<div class="kpi-label">{escape(label)}</div><div class="kpi-value">{escape(value)}</div><div class="kpi-sub">{escape(sub)}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Main row: checkpoint weather + shipment details
left, right = st.columns([2.7, 1])
severity_names = {
    "normal": "Normal weather",
    "moderate": "Moderate weather",
    "severe": "Severe weather",
    "extreme": "Extreme weather",
}
severity_descriptions = {
    "normal": "Clear conditions",
    "moderate": "Possible disruption",
    "severe": "Heavy rain and storms expected",
    "extreme": "Severe disruption expected",
}
severity_icons = {"normal": "☀️", "moderate": "🌦️", "severe": "🌧️", "extreme": "⛈️"}

with left:
    st.markdown('<div class="panel-title">Route weather &amp; delay</div>', unsafe_allow_html=True)
    checkpoints = scenario.get("checkpoints", [])
    cols = st.columns(len(checkpoints))
    for index, cp in enumerate(checkpoints):
        severity = str(cp.get("severity", "normal")).lower()
        affects_route = bool(cp.get("affects_remaining_route", False)) and float(cp.get("hours_until_arrival", 0)) > 0
        delay_days = float(rules.get(severity, 0)) if affects_route else 0.0
        style = severity if severity in {"normal", "moderate", "severe", "extreme"} else "normal"
        location_type = "Origin" if index == 0 else ("Destination" if index == len(checkpoints) - 1 else "Transit checkpoint")
        with cols[index]:
            st.markdown(
                f'<div class="weather-card weather-{style}">'
                f'<div class="checkpoint-name">{escape(str(cp.get("name", "Checkpoint")))}</div>'
                f'<div class="checkpoint-kind">{location_type}</div>'
                f'<div style="font-size:1.35rem">{severity_icons.get(severity, "🌤️")}</div>'
                f'<div class="weather-status">{severity_names.get(severity, severity.title())}</div>'
                f'<div class="weather-desc">{severity_descriptions.get(severity, "Conditions unavailable")}</div>'
                f'<div class="{"impact-delayed" if delay_days else "impact-normal"}">Delay impact: {"+" if delay_days else ""}{delay_days:g} {"day" if delay_days == 1 else "days"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if index < len(checkpoints) - 1:
                st.markdown('<div style="text-align:center;color:#65718a;font-size:1.25rem;margin-top:-100px;pointer-events:none">→</div>', unsafe_allow_html=True)
    st.markdown('<div class="small-muted" style="margin-top:10px">Weather and delay values are simulated; configured delay rules are illustrative.</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel-title">Shipment details</div>', unsafe_allow_html=True)
    details = [
        ("Route", f"{shipment['origin']} → {shipment['destination']}"),
        ("Status", shipment["status"]),
        ("Current day (in transit)", f"Day {shipment['current_day']:g}"),
        ("Remaining transit baseline", f"{shipment['remaining_transit_days']:g} days"),
        ("Shipment type", shipment.get("shipment_type", "Demo parcel")),
        ("Priority", shipment.get("priority", "Standard")),
        ("Stacked delays", "None"),
    ]
    for label, value in details:
        st.markdown(f'<div class="detail-row"><span>{escape(str(label))}</span><b>{escape(str(value))}</b></div>', unsafe_allow_html=True)

# ETA impact + plain-language weather summary
st.divider()
left, right = st.columns([1.05, 1])
with left:
    st.markdown('<div class="panel-title">ETA impact summary</div>', unsafe_allow_html=True)
    a, plus, b, equals, c = st.columns([1, .2, 1, .2, 1])
    with a:
        st.markdown(f'<div class="eta-box"><div class="eta-label">Baseline ETA</div><div class="eta-value">Day {shipment["original_eta_day"]:g}</div><div class="eta-note">Original estimate</div></div>', unsafe_allow_html=True)
    with plus:
        st.markdown('<div style="font-size:1.7rem;text-align:center;padding-top:35px;color:#65718a">+</div>', unsafe_allow_html=True)
    with b:
        st.markdown(f'<div class="eta-box eta-box-delay"><div class="eta-label">Weather delay</div><div class="eta-value" style="color:#b42318">+{weather_delay:g} days</div><div class="eta-note">{escape(severity_names.get(applied_severity, applied_severity.title()))}</div></div>', unsafe_allow_html=True)
    with equals:
        st.markdown('<div style="font-size:1.7rem;text-align:center;padding-top:35px;color:#65718a">=</div>', unsafe_allow_html=True)
    with c:
        st.markdown(f'<div class="eta-box"><div class="eta-label">Predicted ETA</div><div class="eta-value">Day {predicted_eta:g}</div><div class="eta-note">Based on current conditions</div></div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="panel-title">Current weather impact</div>', unsafe_allow_html=True)
    impacted = [cp for cp in scenario.get("checkpoints", []) if str(cp.get("severity", "normal")).lower() in {"moderate", "severe", "extreme"} and cp.get("affects_remaining_route") and float(cp.get("hours_until_arrival", 0)) > 0]
    if impacted:
        cp = max(impacted, key=lambda item: float(rules.get(str(item.get("severity", "normal")).lower(), 0)))
        severity = str(cp.get("severity", "normal")).lower()
        impact_days = float(rules.get(severity, 0))
        st.markdown(
            f'<div class="weather-alert"><div class="weather-alert-title">{severity_icons.get(severity, "🌧️")} {escape(severity_names.get(severity, severity.title()))} at {escape(str(cp.get("name", "checkpoint")))}</div>'
            f'{escape(severity_descriptions.get(severity, "Weather conditions may affect delivery."))} during the shipment transit window.<br><br>'
            f'<b>Weather condition:</b> {escape(severity.title())}<br><b>Estimated delay:</b> <span style="color:#b42318;font-weight:750">+{impact_days:g} {"day" if impact_days == 1 else "days"}</span><br>'
            f'<b>Impact period:</b> During transit window</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="weather-alert" style="background:#effaf3;border-color:#d8f1e1"><div class="weather-alert-title">☀️ No significant weather disruption</div>Weather at the configured checkpoints is not expected to add a delay under the current demo rules.</div>', unsafe_allow_html=True)

# Audit history only; no route timeline, scenario IDs, judge verdict, or approval controls.
st.divider()
st.markdown('<div class="panel-title">Audit history</div>', unsafe_allow_html=True)
events = state.get_events(shipment_id, limit=30)
if events:
    rows = []
    for event in events:
        event_type = event["event_type"]
        details_obj = event.get("details", {})
        if event_type in {"WEATHER_ASSESSED", "JUDGE_PASSED_PROPOSAL_PENDING_HUMAN", "JUDGE_DID_NOT_PASS", "JUDGE_ERROR_FAIL_CLOSED"}:
            proposal = details_obj.get("proposal", {})
            if event_type == "WEATHER_ASSESSED":
                summary = f"Weather checked; predicted ETA Day {proposal.get('proposed_eta_day', '—')}"
            elif event_type == "JUDGE_PASSED_PROPOSAL_PENDING_HUMAN":
                summary = f"ETA prediction updated to Day {proposal.get('proposed_eta_day', '—')}"
            elif event_type == "JUDGE_DID_NOT_PASS":
                summary = "ETA prediction review could not be completed"
            else:
                summary = "Automated review unavailable; existing ETA retained"
            display_event = "ETA_ASSESSED" if event_type == "WEATHER_ASSESSED" else ("ETA_PREDICTED" if event_type == "JUDGE_PASSED_PROPOSAL_PENDING_HUMAN" else "ASSESSMENT_STATUS")
        else:
            summary = json.dumps(details_obj, ensure_ascii=False)[:240]
            display_event = event_type
        rows.append({"Time (UTC)": event["created_at"], "Event": display_event, "Details": summary})
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.caption("No audit events recorded yet.")

with st.expander("About this dashboard"):
    st.markdown(
        "- Weather and shipment values are simulated for this demo.\n"
        "- Delay rules are illustrative and are not calibrated delivery predictions.\n"
        "- The dashboard is read-only. Assessment, validation, and scenario progression run in the backend.\n"
        "- ETA shown as predicted is an estimate; it does not change the stored approved ETA.\n"
        "- A production deployment should use shared persistent storage and appropriate access controls."
    )

st_autorefresh(interval=5000, key="shipment_dashboard_refresh")
