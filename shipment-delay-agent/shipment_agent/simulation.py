import json
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_FILE = ROOT / "config" / "weather-scenarios.yaml"
SHIPMENT_FILE = ROOT / "data" / "shipments.json"
RULE_FILE = ROOT / "config" / "weather-rules.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_shipment() -> dict[str, Any]:
    return json.loads(SHIPMENT_FILE.read_text(encoding="utf-8"))


def load_rules() -> dict[str, float]:
    return load_yaml(RULE_FILE)["delay_days"]


def load_scenarios_config() -> dict[str, Any]:
    return load_yaml(SCENARIO_FILE)


def scenario_for_elapsed(elapsed_seconds: float, config: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    scenarios = config["scenarios"]
    duration = max(1, int(config.get("scenario_duration_seconds", 60)))
    index = int(max(0, elapsed_seconds) // duration)
    if config.get("loop", True):
        index %= len(scenarios)
    else:
        index = min(index, len(scenarios) - 1)
    return index, scenarios[index]


def ensure_simulation_start() -> float:
    """Persist start time in a tiny file so Streamlit reruns don't restart the sequence."""
    marker = ROOT / "data" / "runtime" / "simulation_started_at.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        marker.write_text(str(time.time()), encoding="utf-8")
    try:
        return float(marker.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        start = time.time()
        marker.write_text(str(start), encoding="utf-8")
        return start


def current_scenario() -> tuple[int, dict[str, Any], float, int]:
    config = load_scenarios_config()
    start = ensure_simulation_start()
    elapsed = max(0.0, time.time() - start)
    index, scenario = scenario_for_elapsed(elapsed, config)
    duration = max(1, int(config.get("scenario_duration_seconds", 60)))
    seconds_remaining = duration - int(elapsed % duration)
    return index, scenario, elapsed, seconds_remaining
