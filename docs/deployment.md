# Deployment

The project root is `E:\AlgoDesk` on the local HD. For direct development run
the API service on port 8000 and Next.js on port 4173. For Docker Desktop use:

```powershell
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d --build
```

The VPS overlay uses the same images and configuration shape. Set a DNS name
before starting it; Caddy terminates HTTPS and proxies the dashboard, API and
internal market WebSocket while the API/dashboard ports stay private:

```bash
export ALGODESK_DOMAIN=algo.example.com
docker compose -f docker-compose.yml -f deploy/docker-compose.vps.yml up -d --build
```

Both overlays use `restart: unless-stopped`; the base stack health-checks
PostgreSQL, the API service and the trader worker. Secrets belong only in an ignored `.env` or
the VPS secret store. The local dashboard serves the container's production
build: do not mount Windows `node_modules` into its Linux container, because
the frontend's native bindings are platform-specific. The source, Python
environment, YAML controls and PostgreSQL data remain under `E:\AlgoDesk`. The
dashboard resolves the API from `NEXT_PUBLIC_API_URL` when explicitly
provided. Otherwise local ports `3000`/`4173` use API port `8000`, while a VPS
origin uses the same origin, which Caddy routes to the API. Set
`ALLOWED_ORIGINS` in the VPS secret/environment store to the dashboard origin.
