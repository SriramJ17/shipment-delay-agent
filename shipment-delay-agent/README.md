# Shipment Delay Prediction Agent

A deployable hackathon prototype using **Google ADK**, Gemini as an LLM-as-a-Judge, Streamlit, simulated weather scenarios, deterministic ETA rules, human approval, and SQLite audit history.

> Demo only: weather and shipment data are simulated. Delay adjustments are illustrative rules, not real logistics forecasts.

## Features
- Delhi → Chennai demo shipment.
- Weather scenarios advance automatically every 60 seconds from `config/weather-scenarios.yaml`.
- Python rule engine calculates ETA proposals; the LLM does not calculate the numerical ETA.
- Google ADK judge evaluates the proposal and evidence. Judge errors or malformed responses fail closed.
- Human approval/rejection is required before changing the approved ETA or simulating a customer notification.
- SQLite persistence for approved ETA, pending proposal, and audit events.
- Streamlit dashboard with an immediate "Run assessment now" action for demos.
- Docker and Docker Compose support.

## Requirements
- Python 3.11+
- A Gemini API key for live LLM judge evaluation (Google AI Studio key supported by Google ADK's Gemini integration).
- Docker is optional.

## Run locally
```bash
git clone <your-repository-url>
cd shipment-delay-agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add GOOGLE_API_KEY to .env (or export it in your shell)
streamlit run dashboard/app.py
```

The app loads `.env` automatically. Never commit `.env`.

## Run with Docker
```bash
cp .env.example .env
# Set GOOGLE_API_KEY in .env
docker compose up --build
```
Open http://localhost:8501.

## Demo flow
1. Start the dashboard. The simulation begins with the first configured scenario.
2. The weather scenario advances every 60 seconds. The app reruns its monitoring logic when it observes a new scenario.
3. Use **Run assessment now** to evaluate the current scenario immediately.
4. Inspect the judge verdict and supporting evidence.
5. Approve or reject a pending proposal.
6. Watch the audit log and notification simulation.
7. Weather recovery triggers a fresh ETA calculation based on simulated remaining transit time; the original ETA is not automatically restored.

## Configuration
- `config/weather-scenarios.yaml`: scenario sequence and duration.
- `config/weather-rules.yaml`: delay adjustments by severity.
- `prompts/eta-judge.md`: judge rubric.
- `data/shipments.json`: simulated shipment fixture.

## Important behavior
- A proposal must receive a valid judge verdict of `PASS` before approval controls are enabled.
- If the judge is unavailable, the proposal is marked `JUDGE_ERROR` and cannot be approved.
- A pending proposal is not silently overwritten by a later scenario. The app records that a newer scenario is available and lets the operator decide the existing proposal.
- Only approval updates the approved ETA and records a simulated customer notification.
- SQLite is suitable for this single-instance prototype. For multi-instance deployment, replace it with a managed database and move the simulation worker/scheduler into a separate service.

## Publish to GitHub
```bash
git init
git add .
git commit -m "Build shipment delay prediction agent"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repository>.git
git push -u origin main
```

## Tests
```bash
pytest -q
```
The tests cover deterministic ETA rules and approval safeguards; they do not call Gemini.
