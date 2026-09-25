FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 kioskuser && chown -R kioskuser:kioskuser /app
USER kioskuser

EXPOSE 5100

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5100/api/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5100", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "app:app"]
