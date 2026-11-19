# ==============================================================================
# EKS Beverage Store - Frontend UI Service Dockerfile
# Lightweight unprivileged Nginx Alpine container serving static assets & reverse-proxying APIs
# ==============================================================================

FROM nginxinc/nginx-unprivileged:1.27-alpine

LABEL maintainer="EKS Beverage Store Team"
LABEL description="Responsive frontend web interface with unprivileged Nginx reverse proxy for EKS"

# Remove default Nginx welcome assets
RUN rm -rf /usr/share/nginx/html/*

# Copy static frontend web files
COPY --chown=nginx:nginx public/ /usr/share/nginx/html/

# Copy custom reverse proxy configuration
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf

# Expose unprivileged port 8080
EXPOSE 8080

# Container healthcheck
HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/healthz || exit 1

# Launch Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
