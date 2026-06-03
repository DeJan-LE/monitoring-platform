# ============================================================
# Dockerfile – Nginx Reverse Proxy
# ============================================================

FROM nginx:1.25-alpine

# Standard-Config entfernen und eigene rein
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/monitoring.conf

EXPOSE 80
