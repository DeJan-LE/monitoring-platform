#!/bin/bash
# ============================================================
# heartbeat.sh – Sendet regelmässig einen Push an Uptime Kuma
# ============================================================
# Umgebungsvariablen (werden via docker-compose / .env gesetzt):
#   KUMA_URL          – Vollständige Push-URL von Uptime Kuma
#   INTERVAL_SECONDS  – Wartezeit zwischen den Heartbeats (Standard: 60s)

KUMA_URL="${KUMA_URL:-http://uptime-kuma:3001/api/push/KEIN_KEY}"
INTERVAL="${INTERVAL_SECONDS:-60}"

echo "======================================"
echo " Heartbeat Service gestartet"
echo " Ziel:     $KUMA_URL"
echo " Interval: ${INTERVAL}s"
echo "======================================"

while true; do
    START=$(date +%s)

    # Heartbeat senden (Timeout: 10 Sekunden)
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        "${KUMA_URL}?status=up&msg=OK&ping=0")

    END=$(date +%s)
    PING=$((END - START))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    if [ "$HTTP_STATUS" = "200" ]; then
        echo "[${TIMESTAMP}] Heartbeat OK (HTTP ${HTTP_STATUS}, ${PING}s)"
    else
        echo "[${TIMESTAMP}] Heartbeat FEHLER (HTTP ${HTTP_STATUS})"
    fi

    sleep "$INTERVAL"
done
