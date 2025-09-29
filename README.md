# Home Server Stack

A complete Docker Compose setup for running AdGuard Home, n8n, and Ollama on your home server.

## Services Included

- **AdGuard Home**: Network-wide ad blocking and DNS server
- **n8n**: Workflow automation platform
- **Ollama**: Local AI models for coding assistance and general chat

## System Requirements

**Minimum Requirements:**
- 8 GB RAM (16 GB recommended)
- 500 GB available storage (1 TB recommended for AI models)
- Linux-based OS (tested on Ubuntu Server 24.04 LTS)
- Docker and Docker Compose installed
- Static IP address configured for your server

## Quick Setup

1. **Clone or download this repository**
   ```bash
   git clone <your-repo-url>
   cd home-server-stack
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   nano .env
   ```

   Update the following:
   - `SERVER_IP`: Your server's local IP address
   - `TIMEZONE`: Your local timezone (e.g., `America/New_York`, `Europe/London`)
   - `N8N_PASSWORD`: A secure password for n8n access
   - `N8N_EDITOR_BASE_URL`: Your external domain (e.g., `https://your-domain.ddns.net:5678`)

3. **Generate SSL certificates** (for HTTPS support)
   ```bash
   cd ssl
   ./generate-cert.sh your-domain.ddns.net
   cd ..
   ```

4. **Start the services**
   ```bash
   docker compose up -d
   ```

5. **Initial model setup** (runs automatically)
   The setup will automatically download two optimized models:
   - `deepseek-coder-v2`: Lightweight coding assistant (8B parameters)
   - `llama3.1:8b`: General chat model (8B parameters)

## Service Access

After deployment, access your services at:

- **AdGuard Home**: `http://SERVER_IP:3000` (initial setup) then `http://SERVER_IP:80`
- **n8n**: `https://SERVER_IP:5678` (HTTPS with self-signed certificate)
- **Ollama**: `http://SERVER_IP:11434` (API endpoint)

Replace `SERVER_IP` with your actual server IP address.

## Initial Configuration

### AdGuard Home Setup
1. Navigate to `http://SERVER_IP:3000`
2. Follow the initial setup wizard
3. Set admin username and password
4. Configure DNS settings as needed
5. After setup, access the admin panel at `http://SERVER_IP:80`

### n8n Setup
1. Navigate to `https://SERVER_IP:5678`
2. Accept the self-signed certificate warning in your browser
3. Login with credentials from your `.env` file
4. Create your first workflow

**Note**: When accessing n8n via HTTPS with a self-signed certificate, your browser will show a security warning. This is expected for development certificates. Click "Advanced" and "Proceed to [your-domain]" to continue.

### Ollama Usage
Test the AI models:
```bash
# Chat with the general model
curl http://SERVER_IP:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Hello, how are you?",
  "stream": false
}'

# Get coding help
curl http://SERVER_IP:11434/api/generate -d '{
  "model": "deepseek-coder-v2",
  "prompt": "Write a Python function to calculate fibonacci numbers",
  "stream": false
}'
```

## Remote Access Setup

To access these services from outside your home network, configure port forwarding on your router:

### Router Configuration
1. Access your router's admin panel (usually `192.168.1.1` or `192.168.0.1`)
2. Navigate to "Port Forwarding" or "Virtual Servers" section
3. Add port forwarding rules based on your needs:

**Recommended for Remote Access (Most Common):**
| Service | External Port | Internal IP | Internal Port | Protocol | Purpose |
|---------|---------------|-------------|---------------|----------|---------|
| n8n | 5678 | SERVER_IP | 5678 | TCP | Remote workflow management (HTTPS) |
| Ollama (Optional) | 11434 | SERVER_IP | 11434 | TCP | Remote AI API access |

**AdGuard Home Port Information:**
- **Port 3000**: Initial setup only (do not forward - use local access)
- **Port 80**: Admin interface after setup (only forward if you need remote admin access)
- **Port 53**: DNS service (only forward if you want to provide public DNS service - NOT recommended for home use)

**Additional Ports (Only if Needed):**
| Service | External Port | Internal IP | Internal Port | Protocol | Purpose |
|---------|---------------|-------------|---------------|----------|---------|
| AdGuard Admin | 8080 | SERVER_IP | 80 | TCP | Remote admin access (consider VPN instead) |

### Security Considerations
- **AdGuard Home**: Keep admin interface (port 80) local-only for security. Access remotely via VPN if needed
- **DNS Service**: Do NOT forward port 53 unless you specifically want to run a public DNS service
- **Use VPN**: Consider setting up WireGuard/OpenVPN instead of exposing services directly
- **Non-standard ports**: Use different external ports (e.g., 15678 instead of 5678) for better security
- **Regular updates**: Keep all services updated and monitor access logs

### Dynamic DNS (Optional)
If your ISP provides a dynamic IP address, consider using a Dynamic DNS service like:
- No-IP
- DuckDNS
- Cloudflare DDNS

## Data Persistence

All service data is stored in the `./data/` directory:
- `./data/adguard/`: AdGuard Home configuration and data
- `./data/n8n/`: n8n workflows and data
- `./data/ollama/`: Downloaded AI models and data

## Managing the Stack

**Start services:**
```bash
docker compose up -d
```

**Stop services:**
```bash
docker compose down
```

**View logs:**
```bash
docker compose logs -f [service_name]
```

**Update services:**
```bash
docker compose pull
docker compose up -d
```

**Restart a specific service:**
```bash
docker compose restart [service_name]
```

## Model Management

**List downloaded models:**
```bash
docker exec ollama ollama list
```

**Download additional models:**
```bash
docker exec ollama ollama pull model_name
```

**Remove models:**
```bash
docker exec ollama ollama rm model_name
```

## Troubleshooting

**Services not starting:**
- Check if ports are already in use: `sudo netstat -tlnp`
- Verify Docker is running: `sudo systemctl status docker`
- Check logs: `docker compose logs`

**DNS not working:**
- Ensure port 53 isn't blocked by systemd-resolved
- Check AdGuard Home logs: `docker compose logs adguard`

**Ollama models not downloading:**
- Check available disk space
- Monitor download progress: `docker compose logs ollama-setup`

**Cannot access from outside network:**
- Verify port forwarding rules on router
- Check if ISP blocks residential hosting
- Confirm firewall settings on server

## Resource Usage

Expected resource consumption:
- **RAM**: 6-8 GB (varies with AI model usage)
- **Storage**: 20-30 GB for models and data
- **CPU**: Low idle usage, higher during AI inference

## Contributing

We welcome contributions to improve this home server stack! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- How to submit bug reports and feature requests
- Development workflow and branching strategy
- Pull request process
- Code review guidelines

### Quick Contribution Guide

1. **Fork the repository** on GitHub
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes** and test them locally
4. **Commit your changes**: Use descriptive commit messages
5. **Push to your fork**: `git push origin feature/your-feature-name`
6. **Submit a pull request** using our PR template

### Reporting Issues

- **Bug reports**: Use the bug report template
- **Feature requests**: Use the feature request template
- **Questions**: Use the question template or GitHub Discussions

## Support

For issues specific to individual services:
- AdGuard Home: [Official Documentation](https://adguard.com/kb/)
- n8n: [Official Documentation](https://docs.n8n.io/)
- Ollama: [Official Documentation](https://ollama.ai/)

For issues with this repository:
- Check existing [GitHub Issues](https://github.com/josephradford/home-server-stack/issues)
- Create a new issue using the appropriate template
- See our [Contributing Guidelines](CONTRIBUTING.md) for more help