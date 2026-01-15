# Docker Setup for Thoth Backend

This document explains how to use Docker for the Thoth backend instead of managing Python virtual environments.

## Benefits

- ✅ Works on both Windows and Ubuntu (and macOS)
- ✅ No venv management needed
- ✅ Consistent environment across all developers
- ✅ Easy to scale and deploy
- ✅ Handles all dependencies automatically

## Prerequisites

- **Docker Desktop** installed and running
  - Windows: [Download Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
  - Ubuntu: `sudo apt-get install docker.io docker-compose`
  - macOS: [Download Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)

## Usage

### Starting the Backend Manually

From the `backend/` directory:

```bash
docker-compose up --build
```

This will:
1. Build the Docker image
2. Start the container
3. Run the Flask backend on port `5000`

### Starting from Electron App

The Electron app can automatically start the Docker backend when needed. The backend will be started in the background.

### Stopping the Backend

```bash
docker-compose down
```

## Troubleshooting

### Docker not found
Make sure Docker is installed and running:
```bash
docker --version
docker-compose --version
```

### Port 5000 already in use
Another process is using port 5000. Either stop that process or change the port in `docker-compose.yml`:
```yaml
ports:
  - "5001:5000"  # Map host port 5001 to container port 5000
```

### Container won't start
Check the logs:
```bash
docker-compose logs
```

### Slow on Windows
Docker on Windows can be slow. Consider using:
- WSL 2 (Windows Subsystem for Linux 2) backend in Docker Desktop
- Exclude the project from Windows Defender scans

## Environment Variables

You can set environment variables in `docker-compose.yml`:

```yaml
environment:
  - FLASK_ENV=development
  - DEBUG=true
```

## Rebuilding the Image

If you change `requirements.txt` or `Dockerfile`, rebuild:

```bash
docker-compose build --no-cache
docker-compose up
```

## Production Deployment

For production, you may want to add:
- Nginx reverse proxy
- SSL/TLS certificates
- Environment-specific configs
- Health checks
- Auto-restart policies

See the existing comments in `docker-compose.yml` for guidance.
