# Базовый образ PlayWright
# Сделан под VPS amd-64
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

COPY collectors/tiktok/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

# Общий пакет для саппортов БД
COPY common/ /app/common/
COPY collectors/tiktok /app/

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
CMD ["python", "collector.py"]