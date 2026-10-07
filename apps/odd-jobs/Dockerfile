FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY oddjobs ./oddjobs

EXPOSE 8080

# Single process on purpose: the daily scheduler runs inside the app, so more workers
# would run every job several times.
CMD ["uvicorn", "oddjobs.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
