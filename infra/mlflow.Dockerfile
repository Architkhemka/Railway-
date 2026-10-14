FROM python:3.11-slim

RUN pip install --no-cache-dir mlflow==2.22.0 'psycopg[binary]==3.2.6'

EXPOSE 5000

ENTRYPOINT ["mlflow"]
