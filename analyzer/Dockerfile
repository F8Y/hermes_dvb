FROM python:3.12-slim

WORKDIR /app

COPY analyzer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ /app/common/
COPY analyzer/ /app/

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
CMD ["python", "worker.py"]