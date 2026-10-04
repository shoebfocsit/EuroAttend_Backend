FROM python:3.12-slim
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["sh", "-c", "alembic upgrade head || true; python -m scripts.seed || true; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
