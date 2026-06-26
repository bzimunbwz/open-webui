FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

ENV PORT=3000
ENV GATEWAY_DATA_DIR=/app/data

EXPOSE 3000

HEALTHCHECK CMD curl --silent --fail http://localhost:${PORT}/health || exit 1

CMD ["python", "main.py"]
