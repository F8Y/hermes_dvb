FROM python:3.12-slim

WORKDIR /app

# proxychains-ng — заворачивает TCP-трафик PyMax через RU mobile SOCKS5
RUN apt-get update \
    && apt-get install -y --no-install-recommends proxychains-ng ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY collectors/max/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ /app/common/
COPY collectors/max/ /app/
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "collector.py"]