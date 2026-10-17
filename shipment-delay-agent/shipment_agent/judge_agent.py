import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "shipment_delay_agent"
USER_ID = "dashboard_user"


def _load_judge_instruction() -> str:
    rubric = (ROOT / "prompts" / "eta-judge.md").read_text(encoding="utf-8")
    return (
        "You are the ETA Proposal Judge. Follow the rubric exactly. "
        "Return only valid JSON, no Markdown fences.\n\n" + rubric
    )


async def _evaluate_async(payload: dict[str, Any]) -> dict[str, Any]:
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    judge = Agent(
        name="eta_proposal_judge",
        model=model,
        description="Independently evaluates rule-based shipment ETA proposals.",
        instruction=_load_judge_instruction(),
    )
    session_service = InMemorySessionService()
    runner = Runner(
        agent=judge,
        app_name=APP_NAME,
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(payload, indent=2))],
    )
    result_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            result_text = "".join(part.text or "" for part in event.content.parts)
    if not result_text:
        raise RuntimeError("The ADK judge returned no final response.")
    match = re.search(r"\{.*\}", result_text, flags=re.DOTALL)
    if not match:
        raise ValueError("The ADK judge response did not contain a JSON object.")
    verdict = json.loads(match.group(0))
    if verdict.get("verdict") not in {"PASS", "FLAG", "REJECT"}:
        raise ValueError("The ADK judge returned an invalid verdict.")
    required = {"evidence_quality", "rule_compliance", "eta_plausibility", "reasoning"}
    if not required.issubset(verdict):
        raise ValueError("The ADK judge response is missing required fields.")
    verdict.setdefault("missing_information", [])
    verdict["model"] = model
    return verdict


def evaluate_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    """Call Google ADK judge. Raises on failure; callers must fail closed."""
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY is not configured. Set it in .env.")
    return asyncio.run(_evaluate_async(payload))
