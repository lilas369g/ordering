FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn>=21.2,<22.0

COPY backend/ .
COPY backend/.env /app/.env

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--workers", "4", "--threads", "2", "--bind", "0.0.0.0:8000"]
