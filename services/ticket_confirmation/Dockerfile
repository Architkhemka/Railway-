FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY services ./services
RUN python -m pip install --no-cache-dir .
EXPOSE 8000
CMD ["sh", "-c", "python -m services.ticket_confirmation.train && uvicorn services.ticket_confirmation.app:app --host 0.0.0.0 --port 8000"]
