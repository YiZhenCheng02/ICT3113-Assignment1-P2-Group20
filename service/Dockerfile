FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

EXPOSE 8000
# 1) Delete the old database so the service ALWAYS starts empty (spec: "The service starts empty").
#    Every container start = a fresh, empty service, so each test run begins from the same state.
# 2) Baseline server config: 1 worker process with 8 threads. Each thread handles one request and
#    waits synchronously for Ollama. Tuning this is Assignment 2.
CMD ["sh", "-c", "rm -f /data/tickets.db /data/tickets.db-journal && gunicorn app.main:app --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-1} --threads ${GUNICORN_THREADS:-8} --timeout 900"]
