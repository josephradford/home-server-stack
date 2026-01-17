# AWS Deployment Guide

Deploy your home-server-stack to AWS EC2 for **under $50 AUD/month**.

## Architecture

```
Internet
    ↓
Route53 DNS → aws.yourdomain.com
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

## Cost Breakdown

| Service | Monthly Cost (USD) | Monthly Cost (AUD) |
|---------|-------------------|-------------------|
| EC2 t3.small | $15 | ~$23 |
| EBS 20GB | $2 | ~$3 |
| Route53 | $0.50 | ~$0.75 |
| Data transfer | $5 | ~$8 |
| **Total** | **~$22.50** | **~$35** |

## Prerequisites

- AWS Account
- Domain name (or subdomain)
- SSH key pair

## Step 1: Launch EC2 Instance (15 min)

### 1.1 Create EC2 Instance

1. Go to **EC2 Dashboard** → **Launch Instance**
2. **Name:** `home-server-stack-aws`
3. **AMI:** Ubuntu Server 24.04 LTS (Free tier eligible)
4. **Instance type:** `t3.small`
   - 2 vCPU, 2 GB RAM
   - Enough for n8n + services
5. **Key pair:** Create new or select existing
6. **Network settings:**
   - Allow SSH (port 22) from **My IP**
   - Allow HTTP (port 80) from **Anywhere** (0.0.0.0/0)
   - Allow HTTPS (port 443) from **Anywhere** (0.0.0.0/0)
7. **Storage:** 20 GB gp3 (SSD)
8. **Launch instance**

### 1.2 Allocate Elastic IP

1. Go to **EC2** → **Elastic IPs** → **Allocate Elastic IP address**
2. **Allocate**
3. Select the IP → **Actions** → **Associate Elastic IP address**
4. Select your instance → **Associate**
5. **Note the Elastic IP** (e.g., 54.123.45.67)

## Step 2: Configure DNS (10 min)

### 2.1 Create Route53 Hosted Zone (Optional)

If using Route53 for DNS:
1. Go to **Route53** → **Hosted zones** → **Create hosted zone**
2. **Domain name:** Your domain (e.g., `example.com`)
3. **Create hosted zone**
4. **Update nameservers** at your domain registrar

### 2.2 Create DNS Records

Create the following records (in Route53 or your DNS provider):

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | aws.example.com | [Elastic IP] | 300 |
| CNAME | *.aws.example.com | aws.example.com | 300 |

Replace `aws.example.com` with your chosen subdomain.

## Step 3: Install Docker on EC2 (10 min)

SSH into your instance:

```bash
ssh -i your-key.pem ubuntu@[ELASTIC_IP]
```

### 3.1 Update system

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.2 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker ubuntu

# Log out and back in for group changes
exit
ssh -i your-key.pem ubuntu@[ELASTIC_IP]

# Verify Docker works
docker ps
```

### 3.3 Install Docker Compose

```bash
sudo apt install docker-compose-plugin -y
docker compose version
```

### 3.4 Install htpasswd (for Traefik auth)

```bash
sudo apt install apache2-utils -y
```

## Step 4: Deploy Stack (15 min)

### 4.1 Clone Repository

```bash
git clone https://github.com/YOUR-USERNAME/home-server-stack-aws.git
cd home-server-stack-aws
```

### 4.2 Configure Environment

```bash
# Copy AWS environment template
cp .env.example.aws .env

# Edit configuration
nano .env
```

Update these values:
- `DOMAIN=aws.example.com` (your subdomain)
- `ACME_EMAIL=your@email.com`
- `N8N_PASSWORD=strong_password_here`
- `TRAEFIK_PASSWORD=strong_password_here`
- `TIMEZONE=Australia/Sydney` (or your timezone)

Save and exit (Ctrl+X, Y, Enter)

### 4.3 Deploy Services

```bash
# Use AWS-specific Makefile
make -f Makefile.aws setup
```

This will:
- Generate Traefik authentication
- Create data directories
- Build custom services
- Start all containers
- Configure Let's Encrypt SSL automatically

### 4.4 Verify Deployment

```bash
# Check all containers are running
docker ps

# Should see: traefik, n8n, mealie, actualbudget, homepage, homepage-api
```

## Step 5: Access Services (2 min)

Wait 2-3 minutes for Let's Encrypt SSL certificates to generate, then access:

- **Homepage:** https://aws.example.com
- **n8n:** https://n8n.aws.example.com
- **Mealie:** https://mealie.aws.example.com
- **Actual Budget:** https://actual.aws.example.com
- **Traefik Dashboard:** https://traefik.aws.example.com

All services automatically get SSL certificates via Let's Encrypt!

## Step 6: Configure CloudWatch Monitoring (15 min)

### 6.1 Create IAM Role

1. Go to **IAM** → **Roles** → **Create role**
2. **Trusted entity:** AWS service → EC2
3. **Permissions:** `CloudWatchAgentServerPolicy`
4. **Name:** `CloudWatchAgentRole`
5. **Create role**

### 6.2 Attach Role to EC2

1. Go to **EC2** → Select your instance
2. **Actions** → **Security** → **Modify IAM role**
3. Select `CloudWatchAgentRole`
4. **Update IAM role**

### 6.3 Install CloudWatch Agent

```bash
# Download agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb

# Install
sudo dpkg -i amazon-cloudwatch-agent.deb

# Run configuration wizard
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
```

Configuration wizard options:
- Monitor: **EC2 instance**
- Metrics: **Standard** (CPU, Memory, Disk, Network)
- StatsD daemon: **No**
- CollectD: **No**

### 6.4 View Metrics

Go to **CloudWatch** → **Metrics** → **CWAgent** to see:
- CPU utilization
- Memory usage
- Disk usage
- Network traffic

## Backup Strategy

### Option 1: EBS Snapshots (Recommended)

1. Go to **EC2** → **Elastic Block Store** → **Volumes**
2. Select your instance volume
3. **Actions** → **Create snapshot**
4. **Enable** Data Lifecycle Manager for automated daily snapshots

### Option 2: Manual Backups to S3

```bash
# Create backup
tar -czf backup-$(date +%Y%m%d).tar.gz data/ .env

# Upload to S3 (requires AWS CLI configured)
aws s3 cp backup-*.tar.gz s3://your-backup-bucket/
```

## Updating Services

```bash
cd ~/home-server-stack-aws

# Pull latest code
git pull

# Rebuild and restart
make -f Makefile.aws stop
make -f Makefile.aws start
```

## Cost Optimization Tips

1. **Use t3.micro for testing** ($7/month vs $15/month)
   - 1 vCPU, 1GB RAM
   - Good for light usage

2. **Stop instance when not needed**
   - Only pay for EBS storage (~$2/month)
   - Start when you want to demo

3. **Use Reserved Instances** for long-term
   - 1-year: ~30% savings
   - 3-year: ~60% savings

## Troubleshooting

### Services won't start

```bash
# Check logs
make -f Makefile.aws logs

# Check specific service
docker logs n8n
docker logs traefik
```

### SSL certificates not generating

1. Verify DNS points to Elastic IP: `dig aws.example.com`
2. Check port 80 is accessible: `curl http://[ELASTIC_IP]`
3. View Traefik logs: `docker logs traefik`

### Can't connect to services

1. Check Security Group allows ports 80, 443
2. Verify Elastic IP is associated
3. Test: `curl -I https://n8n.aws.example.com`

## Security Notes

- **SSH access:** Restricted to your IP (update Security Group if IP changes)
- **Service access:** Protected by HTTPS + basic authentication (n8n, Traefik)
- **No VPN needed:** AWS Security Groups handle access control
- **SSL certificates:** Automatic via Let's Encrypt

## What's Different from Home Server?

**Removed:**
- AdGuard Home (DNS via Route53)
- WireGuard VPN (Security Groups handle access)
- Home Assistant (needs local devices)
- Prometheus/Grafana (CloudWatch for monitoring)
- Fail2ban (AWS handles DDoS/attacks)

**Kept:**
- Traefik (reverse proxy + SSL)
- n8n (main showcase service)
- Mealie (recipe management)
- Actual Budget (finance tracking)
- Homepage (dashboard)

## Resume Talking Points

You can now say:

> "Deployed a multi-service containerized application stack on AWS EC2 with automated SSL certificate management, CloudWatch monitoring, and Route53 DNS routing. Implemented cost-effective architecture under $50/month using Docker Compose, Traefik reverse proxy, and Let's Encrypt. Services include n8n workflow automation, personal finance tracking, and a custom Flask API backend."

**AWS Services Used:**
- EC2 (compute)
- VPC & Security Groups (networking)
- Elastic IP (static IP addressing)
- Route53 (DNS management)
- CloudWatch (monitoring & logging)
- EBS (block storage)

## Next Steps

Want to add more AWS services?

1. **RDS for databases** - Replace SQLite with PostgreSQL (~$15/month)
2. **S3 for storage** - Store files in S3 instead of local disk (~$1/month)
3. **ALB for load balancing** - Add auto-scaling (~$25/month)
4. **ECS Fargate** - Serverless containers (~$30/month)
5. **Terraform** - Infrastructure as Code

Start simple, add complexity as you learn!
