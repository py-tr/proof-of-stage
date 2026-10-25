# Proof of Stage: the case page in sample mode by default (no keys, no network).
#   docker build -t proof-of-stage .
#   docker run --rm -p 8000:8000 proof-of-stage            # sample mode: open http://localhost:8000
#   docker run --rm -p 8000:8000 --env-file .env proof-of-stage   # live mode (Zetaris, Nightshift on the host)
FROM python:3.13.1-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "app.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
