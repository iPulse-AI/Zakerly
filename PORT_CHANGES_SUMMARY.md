# Port Changes Summary - Zakerly Backend

## Overview
Updated all external port mappings to avoid conflicts with the Complipulse project running on the same server.

## Port Mapping Changes

### Before → After

| Service | Old Port | New Port | Description |
|---------|----------|----------|-------------|
| **Frontend** | 3000 | **3001** | React application |
| **API Gateway** | 8000 | **8007** | Main API entry point |
| **Ingestion Service** | 8002 | **8008** | Document upload & processing |
| **Chat Service** | 8001 | **8009** | RAG-based chat |
| **Exam Service** | 8003 | **8010** | Question generation |
| **Script Service** | 8004 | **8011** | Lecture script generation |
| **Presentation Service** | 8006 | **8012** | Presentation generation |
| **Auth Service** | 8005 | **8013** | Authentication |
| **PostgreSQL** | 5432 | **5433** | Database |
| **Redis** | 6379 | **6380** | Cache & sessions |
| **pgAdmin** | 8080 | **8081** | Database management UI |

## Avoided Ports (Used by Complipulse)
- 8888, 8002, 8003, 8004, 8005, 8006, 5000, 5434, 5051

## Files Modified

### 1. **docker-compose.yml**
- Updated all port mappings for external access
- Updated `VITE_API_URL` environment variable for frontend

### 2. **.env**
- Updated `INGESTION_SERVICE_URL`: `http://localhost:8008`
- Updated `CHAT_SERVICE_URL`: `http://localhost:8009`
- Updated `REACT_APP_API_URL`: `http://localhost:8007`

### 3. **.env.example**
- Updated service URLs template to match new ports

### 4. **frontend/src/lib/api.ts**
- Updated default `API_BASE_URL`: `http://localhost:8007`

### 5. **shared/database.py**
- Updated default database URL port: `localhost:5433`

### 6. **shared/utils.py**
- Updated default Redis URL port: `localhost:6380`

### 7. **README.md**
- Updated all documentation with new port references
- Updated health check examples
- Updated access URLs

## Files NOT Modified (Internal Ports)
The following files did NOT need changes because they use internal Docker network ports:
- **Service Dockerfiles** - EXPOSE directives remain the same (internal ports)
- **Service main.py files** - uvicorn.run ports remain the same (internal ports)
- **pgadmin/servers.json** - Uses internal Docker network name "postgres:5432"

## Access URLs After Changes

### User-Facing Services
- **Frontend**: http://localhost:3001
- **API Gateway**: http://localhost:8007
- **pgAdmin**: http://localhost:8081
  - Username: admin@zakerly.com
  - Password: admin123

### Service Health Checks
```bash
# Gateway
curl http://localhost:8007/api/v1/status

# Individual Services
curl http://localhost:8008/health  # Ingestion
curl http://localhost:8009/health  # Chat
curl http://localhost:8010/health  # Exam
curl http://localhost:8011/health  # Script
curl http://localhost:8012/health  # Presentation
curl http://localhost:8013/health  # Auth
```

### Direct Database Access (from host machine)
```bash
psql -h localhost -p 5433 -U zakerly_user -d zakerly_db
```

### Direct Redis Access (from host machine)
```bash
redis-cli -h localhost -p 6380
```

## Deployment Instructions

### 1. Stop Current Containers
```bash
docker compose down
```

### 2. Rebuild and Start with New Ports
```bash
docker compose up -d --build
```

### 3. Verify All Services
```bash
# Check container status
docker compose ps

# Check service health
curl http://localhost:8007/api/v1/status

# Check frontend
curl http://localhost:3001
```

### 4. Update Client Applications
If you have any external clients or mobile apps connecting to the backend:
- Update API endpoint from `http://[server]:8000` to `http://[server]:8007`
- Update any hardcoded service URLs

## Important Notes

1. **Internal Communication**: Services communicate internally using Docker network names and original ports (e.g., `http://chat-service:8000`). Only external access ports changed.

2. **Environment Variables**: The `.env` file service URLs are for development/testing outside Docker. Inside Docker, services use the environment variables defined in `docker-compose.yml`.

3. **Frontend Build**: The frontend container will need to be rebuilt to pick up the new `VITE_API_URL` environment variable.

4. **Database Connections**: Applications connecting directly to PostgreSQL from the host machine should now use port 5433 instead of 5432.

5. **No Conflicts**: These new ports do not conflict with Complipulse project ports.

## Troubleshooting

### Port Already in Use
If you still get port conflicts:
```bash
# Check what's using a specific port
sudo lsof -i :8007

# Or using ss
ss -tulpn | grep 8007
```

### Service Connection Issues
If services can't connect to each other:
- Verify all containers are on the same network: `docker network inspect zakerly_network`
- Check container logs: `docker compose logs [service-name]`
- Ensure environment variables are correctly set in docker-compose.yml

### Frontend Can't Connect to Backend
- Clear browser cache
- Check browser console for CORS errors
- Verify `VITE_API_URL` in docker-compose.yml is correct
- Rebuild frontend container: `docker compose up -d --build frontend`

## Rollback Instructions

If you need to revert to old ports:
1. Checkout the previous version of these files from git
2. Run `docker compose down`
3. Run `docker compose up -d --build`

---
**Date**: November 5, 2025
**Modified By**: Port Configuration Update
**Reason**: Avoid conflicts with Complipulse project on shared server
