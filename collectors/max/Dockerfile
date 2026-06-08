FROM python:3.12-slim

WORKDIR /app

COPY collectors/max/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ /app/common/
COPY collectors/max/ /app/

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
CMD ["python", "collector.py"]