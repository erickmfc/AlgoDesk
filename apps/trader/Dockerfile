FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY alembic.ini .
COPY migrations ./migrations
CMD ["sh", "-c", "if [ \"${RUN_MIGRATIONS:-true}\" = \"true\" ]; then alembic upgrade head; fi && uvicorn src.main:app --host 0.0.0.0 --port ${APP_PORT:-8000}"]
