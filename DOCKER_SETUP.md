# Docker Setup Guide for AI Spotter

This guide explains how to run the AI Spotter application using Docker.

## Architecture

The application consists of three containerized services:

1. **Frontend** (React + nginx) - Port 80
2. **.NET Backend** (API Gateway) - Port 5246
3. **Python Backend** (AI Processing with MediaPipe) - Port 8000

All services communicate through a Docker network, with shared volumes for video storage.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (includes Docker Compose)
- At least 6GB of free RAM (4GB for Python AI processing)
- At least 10GB of free disk space

## Quick Start

### 1. Build and Start All Services

From the project root directory:

```bash
docker-compose up --build
```

This will:
- Build all three Docker images
- Create network and volumes
- Start all services

### 2. Access the Application

Open your browser and navigate to:
```
http://localhost
```

The application is now ready to use!

### 3. Stop the Application

Press `Ctrl+C` in the terminal, then run:
```bash
docker-compose down
```

## Docker Commands

### Start in detached mode (background)
```bash
docker-compose up -d
```

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f python-backend
docker-compose logs -f dotnet-backend
docker-compose logs -f frontend
```

### Rebuild a specific service
```bash
docker-compose build python-backend
docker-compose up -d python-backend
```

### Stop and remove everything (including volumes)
```bash
docker-compose down -v
```

### Check service status
```bash
docker-compose ps
```

## Development vs Production

### Development Mode (Current Setup)
- Run backends and frontend separately
- Use `npm run dev` for frontend with hot reload
- Direct access to logs and debugging

### Production Mode (Docker)
- All services containerized
- Nginx serves optimized React build
- Better performance and isolation
- Ready for deployment

### Switching Between Modes

**Local Development:**
```bash
# Terminal 1 - Python backend
cd AI
uvicorn api.main:app --reload

# Terminal 2 - .NET backend
cd Backend
dotnet run

# Terminal 3 - Frontend
cd frontend
npm run dev
```

**Docker Production:**
```bash
# From project root
docker-compose up
```

## Configuration

### Environment Variables

#### .NET Backend
- `ASPNETCORE_ENVIRONMENT`: Production/Development
- `ASPNETCORE_URLS`: Listening URL (default: http://+:8080)
- `PythonBackendUrl`: Python backend URL (default: http://python-backend:8000)

#### Python Backend
- `PYTHONUNBUFFERED`: Enable real-time logging (default: 1)

### Volumes

Three persistent volumes store data:
- `video-storage`: Uploaded videos
- `processed-storage`: Processed videos with skeleton overlay
- `landmarks-storage`: MediaPipe pose landmarks (.npy files)

View volumes:
```bash
docker volume ls
```

## Troubleshooting

### Port Conflicts

If ports 80, 5246, or 8000 are already in use, edit `docker-compose.yml`:

```yaml
services:
  frontend:
    ports:
      - "8080:80"  # Change 80 to 8080
```

### Memory Issues

If the Python backend crashes, increase memory in `docker-compose.yml`:

```yaml
python-backend:
  deploy:
    resources:
      limits:
        memory: 8G  # Increase from 4G
```

### Rebuilding from Scratch

```bash
# Stop everything
docker-compose down -v

# Remove all images
docker-compose rm -f

# Rebuild and restart
docker-compose up --build
```

### Video Processing Timeout

If video processing times out, increase nginx timeout in `frontend/nginx.conf`:

```nginx
proxy_read_timeout 1200s;  # Increase from 600s to 20 minutes
```

Then rebuild:
```bash
docker-compose build frontend
docker-compose up -d frontend
```

## Deployment

### Deploy to Cloud

#### Option 1: Azure Container Instances
```bash
# Login to Azure
az login

# Create resource group
az group create --name ai-spotter-rg --location eastus

# Deploy
az container create \
  --resource-group ai-spotter-rg \
  --file docker-compose.yml
```

#### Option 2: AWS ECS
```bash
# Install ECS CLI
# Configure credentials
ecs-cli configure --cluster ai-spotter --region us-east-1

# Deploy
ecs-cli compose --file docker-compose.yml up
```

#### Option 3: Docker Swarm / Kubernetes
Convert `docker-compose.yml` to Kubernetes manifests:
```bash
kompose convert -f docker-compose.yml
kubectl apply -f .
```

### Environment-Specific Configs

Create multiple compose files:
- `docker-compose.yml` - Base configuration
- `docker-compose.prod.yml` - Production overrides
- `docker-compose.dev.yml` - Development overrides

Run with specific config:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```

## Performance Optimization

### Multi-Stage Builds
All Dockerfiles use multi-stage builds to minimize image size:
- Frontend: 1.2GB → 50MB (after build)
- .NET Backend: 800MB → 200MB (after build)
- Python Backend: 2GB (includes MediaPipe)

### Caching
Docker caches layers for faster rebuilds. To leverage caching:
- Only change code, not dependencies → Fast rebuild
- Change package.json or requirements.txt → Slower rebuild

### Scaling
Scale the Python backend for parallel processing:
```bash
docker-compose up --scale python-backend=3
```

Add a load balancer to distribute requests.

## Security Notes

### Production Checklist
- [ ] Change default ports
- [ ] Add HTTPS with SSL certificates (Let's Encrypt)
- [ ] Set up authentication
- [ ] Enable CORS properly
- [ ] Use secrets management for sensitive data
- [ ] Set up monitoring and logging
- [ ] Regular security updates

### SSL/HTTPS Setup
Add to nginx.conf:
```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    # ... rest of config
}
```

## License

This Docker setup is free to use for both development and commercial deployment.
All included tools (Docker, nginx, .NET, Python) are open source and free for commercial use.

## Support

For issues specific to Docker setup, check:
1. Docker logs: `docker-compose logs`
2. Service status: `docker-compose ps`
3. Network connectivity: `docker network inspect tempspotter_app-network`
4. Volume data: `docker volume inspect tempspotter_video-storage`