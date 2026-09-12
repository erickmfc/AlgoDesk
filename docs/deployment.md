# Deployment

The project root is `E:\AlgoDesk` on the local HD. For direct development run
the FastAPI service on port 8000 and Vite on port 4173. For Docker Desktop use:

```powershell
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d --build
```

The VPS overlay uses the same images and configuration shape:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.vps.yml up -d --build
```

Both overlays use `restart: unless-stopped`; the base stack health-checks
PostgreSQL and the trader service. Secrets belong only in an ignored `.env` or
the VPS secret store.
