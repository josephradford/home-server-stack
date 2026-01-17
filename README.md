# Home Server Stack - AWS Deployment

**A lightweight, cost-effective self-hosted application stack optimized for AWS EC2**

Deploy n8n workflow automation, Mealie recipe management, Actual Budget finance tracking, and a custom dashboard on AWS for **under $50 AUD/month**.

> **Note:** This repository is forked from [josephradford/home-server-stack](https://github.com/josephradford/home-server-stack), which is designed for local home server deployment. This AWS version has been streamlined to remove services that don't make sense in the cloud (VPN, DNS, local monitoring) and optimized for cost-effective cloud deployment.

## 🚀 Services Included

| Service | Purpose | URL |
|---------|---------|-----|
| **n8n** | Workflow automation platform | `https://n8n.${DOMAIN}` |
| **Mealie** | Meal planning & recipe management | `https://mealie.${DOMAIN}` |
| **Actual Budget** | Personal finance & budgeting | `https://actual.${DOMAIN}` |
| **Homepage** | Unified dashboard | `https://${DOMAIN}` |
| **Homepage API** | Custom backend integrations | `https://homepage-api.${DOMAIN}` |
| **Traefik** | Reverse proxy & SSL management | `https://traefik.${DOMAIN}` |

## 💰 Cost

**~$35 AUD/month** (~$22 USD/month)

- **EC2 t3.small:** 2 vCPU, 2 GB RAM - $23 AUD/month
- **EBS 20GB:** SSD storage - $3 AUD/month
- **Route53:** DNS hosting - $0.75 AUD/month
- **Data transfer:** Estimated - $8 AUD/month

## ⚡ Quick Start

### Prerequisites

- AWS Account
- Domain name or subdomain
- SSH key pair
- 1 hour of time

### Deployment Steps

1. **Launch EC2 instance** (t3.small, Ubuntu 24.04)
2. **Configure Route53 DNS** (point domain to EC2 Elastic IP)
3. **SSH into instance and install Docker**
4. **Clone this repo and configure `.env`**
5. **Run `make setup`**
6. **Access services via HTTPS** (automatic Let's Encrypt SSL)

**Full deployment guide:** See [DEPLOYMENT.md](DEPLOYMENT.md)

## 🏗️ Architecture

```
Internet
    ↓
Route53 DNS
    ↓
EC2 t3.small (Ubuntu 24.04)
├── Traefik (reverse proxy + Let's Encrypt SSL)
├── n8n (workflow automation)
├── Mealie (recipe management)
├── Actual Budget (finance tracking)
└── Homepage + API (dashboard)
    ↓
CloudWatch (monitoring)
```

**Key Features:**
- ✅ Automatic SSL via Let's Encrypt
- ✅ Domain-based routing (n8n.yourdomain.com, etc.)
- ✅ CloudWatch monitoring integration
- ✅ Simple deployment with Docker Compose
- ✅ One-command setup

## 📋 Services Removed vs Home Server

This AWS version removes services that don't make sense in the cloud:

| Service | Why Removed |
|---------|-------------|
| **AdGuard Home** | Route53 provides DNS |
| **WireGuard VPN** | AWS Security Groups handle access control |
| **Home Assistant** | Requires local IoT devices |
| **Prometheus/Grafana** | Replaced by AWS CloudWatch |
| **Fail2ban** | AWS infrastructure handles DDoS/attacks |

## 🔒 Security

- **HTTPS:** Automatic via Let's Encrypt
- **Authentication:** n8n and Traefik protected by basic auth
- **Access Control:** AWS Security Groups restrict access
- **SSL Certificates:** Auto-renewal every 90 days

## 📊 Monitoring

Uses **AWS CloudWatch** for:
- CPU utilization
- Memory usage
- Disk space
- Network traffic
- Custom application metrics

## 🔄 Common Commands

```bash
# First-time setup
make setup

# Start services
make start

# Stop services
make stop

# View logs
make logs

# Check service status
make status

# Cleanup (preserves data)
make clean
```

## 📁 Project Structure

```
.
├── docker-compose.yml          # AWS-optimized service definitions
├── .env.example               # Configuration template
├── Makefile                   # Deployment commands
├── DEPLOYMENT.md              # Full deployment guide
├── homepage-api/              # Custom Flask backend
│   ├── app.py                 # API endpoints
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile             # Container build
└── data/                      # Persistent data (volumes)
    ├── traefik/               # SSL certificates, logs
    ├── n8n/                   # Workflows database
    ├── mealie/                # Recipes database
    ├── actualbudget/          # Finance data
    └── homepage/              # Dashboard config
```

## 🔧 Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Domain (should point to EC2 Elastic IP)
DOMAIN=aws.example.com

# Email for Let's Encrypt
ACME_EMAIL=admin@example.com

# Service credentials
N8N_USER=admin
N8N_PASSWORD=change_this_secure_password
TRAEFIK_PASSWORD=change_this_secure_password

# Timezone
TIMEZONE=UTC
```

## 🌐 AWS Services Used

- **EC2:** Compute (t3.small instance)
- **VPC & Security Groups:** Networking & access control
- **Elastic IP:** Static IP addressing
- **Route53:** DNS management (optional)
- **CloudWatch:** Monitoring & logging
- **EBS:** Block storage (20GB SSD)

## 📈 Resume Talking Points

> "Deployed a multi-service containerized application stack on AWS EC2 with automated SSL certificate management, CloudWatch monitoring, and Route53 DNS routing. Implemented cost-effective architecture under $50/month using Docker Compose, Traefik reverse proxy, and Let's Encrypt. Services include n8n workflow automation, personal finance tracking, and a custom Flask API backend."

## 🚀 Next Steps

Want to expand your AWS knowledge?

1. **Add RDS** - Replace SQLite with PostgreSQL (~$15/month)
2. **Add S3** - Store files in S3 instead of local disk (~$1/month)
3. **Add ALB** - Application Load Balancer for scaling (~$25/month)
4. **Add ECS Fargate** - Serverless containers (~$30/month)
5. **Add Terraform** - Infrastructure as Code

Start simple, add complexity as you learn!

## 📝 License

MIT License - See [LICENSE](LICENSE)

## 🔗 Links

- **Original Home Server Repo:** [josephradford/home-server-stack](https://github.com/josephradford/home-server-stack)
- **n8n Documentation:** https://docs.n8n.io/
- **Mealie Documentation:** https://docs.mealie.io/
- **Actual Budget Documentation:** https://actualbudget.org/docs/
- **Traefik Documentation:** https://doc.traefik.io/traefik/

## 🤝 Contributing

This is a personal project forked for AWS deployment. For the original home server stack, see the [main repository](https://github.com/josephradford/home-server-stack).

## 📧 Questions?

Open an issue or check the [deployment guide](DEPLOYMENT.md) for troubleshooting tips.

---

**Happy deploying! 🎉**
