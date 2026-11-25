# RepoSage Production Deployment Guide

## 1. Quick Local Docker Compose Deployment

The repository includes a complete production-ready Docker Compose orchestration.

### Prerequisites
- Docker Engine 24.0+
- Docker Compose v2+

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/your-org/reposage.git
cd reposage
cp .env.example .env
```
Edit `.env` and set:
- `OPENAI_API_KEY` (or `GEMINI_API_KEY`)
- `APP_SECRET_KEY` (generate a strong random secret)
- `JWT_SECRET_KEY` (generate a 64-char random secret)

### Step 2: Build and Launch Services
```bash
docker compose up --build -d
```

### Step 3: Verify Service Health
```bash
docker compose ps
curl http://localhost/health
curl http://localhost/ready
```
Access the application:
- **Web UI**: `http://localhost`
- **Swagger API Docs**: `http://localhost/docs`

---

## 2. Cloud Platform Deployment (AWS / GCP / DigitalOcean)

### Nginx SSL Termination
In production, place Certbot / Let's Encrypt certificates in `infrastructure/nginx/certs/`:
```nginx
server {
    listen 443 ssl http2;
    server_name reposage.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/reposage.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/reposage.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://frontend_app;
    }
    location /api/ {
        proxy_pass http://backend_api;
    }
}
```

---

## 3. Production Security Checklist
- [x] Run backend as non-root user (`appuser`).
- [x] Passwords hashed with bcrypt / argon2.
- [x] Anti-SSRF guards blocking loopback and cloud metadata (`169.254.169.254`).
- [x] Zip Slip & archive bomb decompression limits.
- [x] Sensitive files (`.env`, `*.pem`, `*.key`) filtered from ingestion.
- [x] Code execution sandbox isolation enabled.
- [x] Strict CORS origin validation.
- [x] Structured logs with automated secret redaction.
