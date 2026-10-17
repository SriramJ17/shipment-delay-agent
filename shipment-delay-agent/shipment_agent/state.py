import json
import sqlite3
from pathlib import Path
from typing import Any
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "data" / "runtime"
DB_PATH = RUNTIME_DIR / "shipment.db"


def _connect() -> sqlite3.Connection:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipment_state (
            shipment_id TEXT PRIMARY KEY,
            current_approved_eta_day REAL NOT NULL,
            pending_proposal_json TEXT,
            last_scenario_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def initialize(shipment: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO shipment_state
               (shipment_id, current_approved_eta_day, pending_proposal_json, last_scenario_id)
               VALUES (?, ?, NULL, NULL)""",
            (shipment["shipment_id"], float(shipment["original_eta_day"])),
        )


def get_state(shipment_id: str) -> dict[str, Any]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM shipment_state WHERE shipment_id = ?", (shipment_id,)
        ).fetchone()
    if not row:
        raise KeyError(f"Unknown shipment {shipment_id}")
    return {
        "shipment_id": row["shipment_id"],
        "current_approved_eta_day": row["current_approved_eta_day"],
        "pending_proposal": json.loads(row["pending_proposal_json"]) if row["pending_proposal_json"] else None,
        "last_scenario_id": row["last_scenario_id"],
    }


def set_pending(shipment_id: str, proposal: dict[str, Any], scenario_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE shipment_state SET pending_proposal_json = ?, last_scenario_id = ?
               WHERE shipment_id = ?""",
            (json.dumps(proposal), scenario_id, shipment_id),
        )


def clear_pending(shipment_id: str, scenario_id: Optional[str] = None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE shipment_state SET pending_proposal_json = NULL, last_scenario_id = ? WHERE shipment_id = ?",
            (scenario_id, shipment_id),
        )


def approve(shipment_id: str, eta_day: float, reviewer: str = "Demo reviewer") -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE shipment_state SET current_approved_eta_day = ?, pending_proposal_json = NULL
               WHERE shipment_id = ?""",
            (float(eta_day), shipment_id),
        )
        conn.execute(
            "INSERT INTO audit_events (shipment_id, event_type, details_json) VALUES (?, ?, ?)",
            (shipment_id, "ETA_APPROVED_AND_CUSTOMER_NOTIFIED",
             json.dumps({"eta_day": eta_day, "reviewer": reviewer, "notification": "SIMULATED"})),
        )


def reject(shipment_id: str, reviewer: str = "Demo reviewer", reason: str = "Rejected by reviewer") -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE shipment_state SET pending_proposal_json = NULL WHERE shipment_id = ?",
            (shipment_id,),
        )
        conn.execute(
            "INSERT INTO audit_events (shipment_id, event_type, details_json) VALUES (?, ?, ?)",
            (shipment_id, "ETA_REJECTED", json.dumps({"reviewer": reviewer, "reason": reason})),
        )


def log_event(shipment_id: str, event_type: str, details: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO audit_events (shipment_id, event_type, details_json) VALUES (?, ?, ?)",
            (shipment_id, event_type, json.dumps(details)),
        )


def get_events(shipment_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT event_type, details_json, created_at FROM audit_events
               WHERE shipment_id = ? ORDER BY id DESC LIMIT ?""",
            (shipment_id, limit),
        ).fetchall()
    return [
        {"event_type": row["event_type"], "details": json.loads(row["details_json"]), "created_at": row["created_at"]}
        for row in rows
    ]
