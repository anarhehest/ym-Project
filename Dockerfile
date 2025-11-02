FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y --auto-remove build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
 && mkdir -p /var/log/radio && chown appuser:appgroup /var/log/radio

RUN mkdir -p /var/log/radio \
 && touch /var/log/radio/radio.log \
 && chown -R appuser:appgroup /var/log/radio \
 && chmod 664 /var/log/radio/radio.log

USER appuser

EXPOSE 9000

CMD ["python", "project.py"]
