# Architecture

1. Streamlit renders shipment state, scenario, judge evaluation, pending proposal, and audit log.
2. Scenario configuration advances every 60 seconds based on elapsed time; no external weather API or scheduler is required.
3. A deterministic Python rules module computes a candidate ETA.
4. A Google ADK agent evaluates the candidate against a Markdown rubric.
5. Only a `PASS` judge verdict enables human approval.
6. Approval updates the current ETA and writes a simulated customer notification event to SQLite.
7. Rejection leaves the previously approved ETA unchanged.

For a multi-instance deployment, move persistent state to a managed database and simulation progression to a dedicated worker or scheduled service.
