# Architecture

## Target platform

The diagrams describe the intended platform boundaries from the problem statement. Phases 0-2 deliver repository tooling, shared libraries, initial data models and synthetic data loaders, plus the ticket confirmation, delay/disruption, and fare prediction services.

```mermaid
flowchart LR
    Passenger[Passenger] --> Gateway[API Gateway]
    Gateway --> Ticket[Ticket Confirmation]
    Gateway --> Recommendation[Train Recommendation]
    Gateway --> Delay[Delay and Disruption Prediction]
    Gateway --> Planner[Travel Planner Agent]
    Gateway --> Fare[Dynamic Fare Prediction]
    Gateway --> Support[Customer Support Assistant]
    Gateway --> Fraud[Fraud and Bot Detection]

    Ticket --> Data[(Schedules and booking data)]
    Recommendation --> Data
    Delay --> Data
    Planner --> Data
    Fare --> Data
    Support --> Knowledge[(Railway policy knowledge)]
    Fraud --> Data

    Ticket -. MLflow registered model .-> MLflow[MLflow]
    Delay -. MLflow registered model .-> MLflow
    Fare -. MLflow registered models .-> MLflow
    Ticket -. hash-chained events .-> Audit[(Audit JSONL volume)]
    Delay -. hash-chained events .-> Audit
    Fare -. hash-chained events .-> Audit

    Ticket --> Governance[AI Governance Layer]
    Recommendation --> Governance
    Delay --> Governance
    Planner --> Governance
    Fare --> Governance
    Support --> Governance
    Fraud --> Governance
```

## Governance layer

Every model-backed service is expected to publish predictions, confidence, explanations, model version, and health/metrics information to the governance layer. Governance decisions and service events must be auditable. High-risk actions require human approval; travel booking always requires explicit passenger approval.

```mermaid
flowchart TB
    Services[Passenger AI Services] --> Quality[Data Quality Validation]
    Services --> Health[Model and Service Health]
    Services --> Drift[Drift and Performance Monitoring]
    Services --> Fairness[Fairness and Hallucination Checks]
    Services --> Explain[Explainability and Transparency]

    Quality --> Monitor[Governance Monitoring]
    Health --> Monitor
    Drift --> Monitor
    Fairness --> Monitor
    Explain --> Monitor

    Monitor --> RCA[Root Cause Analysis]
    RCA --> Lifecycle[Model Lifecycle: Retrain, Deploy, Roll Back]
    Lifecycle --> Registry[(Model Registry)]
    Monitor --> Audit[(Hash-Chained Audit Trail)]
    RCA --> Audit
    Lifecycle --> Approval{Human approval required?}
    Approval -->|Yes| Human[Governance Operator]
    Approval -->|No, low risk| Action[Controlled remediation]
    Human --> Action
    Action --> Services

    Supervisor[Supervisory Agents] -. observe and recommend .-> Monitor
    Supervisor -. governed actions .-> Approval
```

## Phase 0 local dependencies

```mermaid
flowchart LR
    App[Local application development] --> PostgreSQL[(PostgreSQL)]
    App --> Redis[(Redis)]
    App --> MLflow[MLflow Tracking Server]
    MLflow --> PostgreSQL
    MLflow --> Artifacts[(Persistent artifact volume)]
```

PostgreSQL, Redis, and MLflow are exposed on localhost for development. The Compose stack uses named volumes for database, Redis, MLflow artifacts, and service audit events. MLflow is unauthenticated and must not be exposed to an untrusted network. The Phase 2 APIs run on ports 8001-8003; each trains seeded synthetic-data models, registers them in MLflow, loads the latest registered versions, and exposes health and Prometheus metrics. Model-registration, model-load, and prediction events are stored in a shared hash-chained JSONL volume. This is not the centralized governance monitoring scheduled for Phase 4.
