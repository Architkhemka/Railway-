# Project: AI-Powered Intelligent Railway Travel & Autonomous AI Governance Platform

The official problem statement is in `docs/problem_statement.md`. Treat it as the source of truth. If any task conflicts with it, follow the problem statement and flag the conflict in the PR description.

## Rules for every task
- Work only on the phase or task given. Do not build features from later phases.
- No TODO stubs in core logic, no hardcoded secrets, no real personal data.
- Every PR must include tests, type hints, and updated docs, and must pass CI.
- The PR description must list: files created, how to run and test, known limitations.
- Governance events from every module must be written to the audit trail.

## Tech stack
- Python 3.11, FastAPI, Pydantic v2, SQLAlchemy + PostgreSQL, Redis, Celery
- ML: scikit-learn, XGBoost/LightGBM, SHAP, statsmodels/Prophet
- MLOps: MLflow (tracking + registry), Evidently AI (drift, data quality), Great Expectations or Pandera (validation)
- Agents/GenAI: LangGraph, LangChain, pluggable LLM client via env var, FAISS/Chroma for RAG
- Multilingual: English, Hindi, Marathi, Kannada
- Frontend: React + TypeScript + Vite + Tailwind, Recharts
- Observability: Prometheus, Grafana, structured JSON logs, OpenTelemetry
- Infra: Docker, docker-compose, Kubernetes manifests, GitHub Actions
- Quality: pytest, ruff, mypy, pre-commit, at least 80% coverage on core modules

## Repository structure
```
railway-ai-platform/
├── README.md, ARCHITECTURE.md, docker-compose.yml, Makefile, .env.example
├── .github/workflows/        (ci.yml, cd.yml, retrain.yml)
├── data/                     (synthetic generators + samples)
├── services/
│   ├── gateway/
│   ├── ticket_confirmation/
│   ├── train_recommendation/
│   ├── delay_prediction/
│   ├── travel_planner_agent/
│   ├── fare_prediction/
│   ├── support_assistant/
│   └── fraud_detection/
├── governance/
│   ├── monitoring/
│   ├── data_quality/
│   ├── drift/
│   ├── fairness_hallucination/
│   ├── root_cause/
│   ├── lifecycle/
│   ├── explainability/
│   ├── audit/
│   └── supervisor_agents/
├── frontend/
├── infra/
├── tests/
└── docs/
```

## Data
Use seeded, reproducible synthetic data generators for bookings, cancellations, schedules, delays, fares, user behavior, support conversations, and fraud/bot patterns. Support injecting controllable drift and anomalies so governance can be demonstrated. Provide a data-loader interface so real datasets can be swapped in later.

## Non-functional requirements
- Scalability: stateless services, async I/O, Redis caching, event-driven (Kafka or Redis Streams), Locust load test
- Reliability: health/readiness probes, retries with backoff, circuit breakers, graceful degradation, DR notes
- Security: JWT auth, RBAC (passenger, analyst, governance-admin, auditor), PII masking, rate limiting, input validation
- Compliance: hash-chained audit trail, explainability on every prediction, governance policies as YAML, alignment with India's DPDP Act
- Performance: near real-time inference, low-latency chat streaming

## Governance principles
- Every model exposes metrics, version, and a health endpoint.
- Every prediction returns a confidence score and an explanation.
- Low-risk remediation may run automatically; high-risk actions require human approval.
- Booking by the Travel Planner Agent always requires explicit user approval.

## Phases
0: Scaffold, tooling, CI, docker-compose, ARCHITECTURE.md
1: Synthetic data generators + shared libs (config, logging, auth, DB models)
2: Ticket confirmation, delay, and fare services with MLflow + SHAP
3: Recommendation engine + fraud/bot detection
4: Governance core (data quality, drift, health, fairness, audit trail)
5: Lifecycle automation (retrain, registry, canary, rollback) + root cause analysis
6: Travel Planner Agent + Support Assistant (RAG) + hallucination monitor
7: Supervisory multi-agent layer with closed-loop remediation
8: Frontend (passenger app + governance console)
9: Observability, load tests, security hardening, k8s, final docs, end-to-end demo script