# ============================================================
# Dockerfile – Heartbeat Service
# Basis-Image: Alpine Linux (sehr klein, ca. 5 MB)
# ============================================================

FROM alpine:3.19

# curl und bash installieren (curl für den Heartbeat-Request)
RUN apk add --no-cache curl bash

# Unser Script ins Image kopieren
COPY heartbeat.sh /heartbeat.sh
RUN chmod +x /heartbeat.sh

# Script beim Container-Start ausführen
CMD ["/heartbeat.sh"]
