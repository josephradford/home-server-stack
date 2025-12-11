# System Requirements

Detailed hardware and software requirements for running the Home Server Stack.

## Minimum Requirements

### Hardware

| Component | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| **CPU** | 2 cores | 4+ cores | Higher core count improves performance |
| **RAM** | 4 GB | 8 GB | Comfortable for all services |
| **Storage** | 100 GB | 500 GB | Sufficient for logs and data |
| **Network** | 100 Mbps | 1 Gbps | For reliable service access |

### Software

- **Operating System:** Linux-based OS
  - Tested on: Ubuntu Server 24.04 LTS
  - Also works on: Debian, Fedora, CentOS, Arch Linux
  - **Not supported:** Windows, macOS (use WSL2/Docker Desktop with caveats)

- **Docker:** Version 20.10+
  - Install via: https://docs.docker.com/engine/install/

- **Docker Compose:** Version 2.0+
  - Usually bundled with Docker
  - Verify: `docker compose version`

- **Network:** Static IP address recommended
  - Configure via netplan (Ubuntu) or network manager
  - Prevents service access issues after DHCP lease renewal

## Resource Usage by Service

### Core Services

| Service | RAM (Idle) | RAM (Active) | Storage | CPU (Idle) | CPU (Active) |
|---------|------------|--------------|---------|------------|--------------|
| **AdGuard Home** | 100 MB | 200 MB | 200 MB | 1% | 5% |
| **n8n** | 200 MB | 500 MB | 500 MB | 1% | 10% |
| **WireGuard** | 50 MB | 100 MB | 100 MB | 1% | 5% |
| **Traefik** | 50 MB | 100 MB | 100 MB | 1% | 3% |

### Monitoring Stack (Optional)

| Service | RAM (Idle) | RAM (Active) | Storage | CPU (Idle) | CPU (Active) |
|---------|------------|--------------|---------|------------|--------------|
| **Grafana** | 150 MB | 300 MB | 1 GB | 1% | 5% |
| **Prometheus** | 500 MB | 1 GB | 5-10 GB | 2% | 10% |
| **Alertmanager** | 50 MB | 100 MB | 500 MB | 1% | 3% |
| **Node Exporter** | 20 MB | 30 MB | 50 MB | 1% | 2% |
| **cAdvisor** | 100 MB | 200 MB | 100 MB | 1% | 5% |

### Total Estimates

**Basic Stack (AdGuard + n8n + WireGuard + Traefik):**
- **Idle:** ~0.5 GB RAM, 4% CPU
- **Active:** ~1.3 GB RAM, 23% CPU
- **Storage:** ~2-5 GB

**With Monitoring Stack:**
- **Idle:** ~1.3 GB RAM, 9% CPU
- **Active:** ~2.8 GB RAM, 38% CPU
- **Storage:** ~10-20 GB

## Storage Breakdown

### Initial Installation

```
/home/user/home-server-stack/
├── data/                    # ~5-15 GB (varies with usage)
│   ├── adguard/            # ~200 MB (logs + config)
│   ├── n8n/                # ~500 MB (workflows + database)
│   ├── wireguard/          # ~100 MB (configs + keys)
│   └── traefik/            # ~100 MB (certs + logs)
├── monitoring/ (optional)  # ~10-20 GB (metrics + logs)
│   ├── grafana/            # ~1 GB
│   └── prometheus/         # ~5-15 GB (grows over time)
└── docker images           # ~3-5 GB
```

### Growth Over Time

- **AdGuard logs:** ~10-50 MB/day (configurable retention)
- **n8n workflows:** Minimal (unless storing large files)
- **Prometheus metrics:** ~1-2 GB/month (configurable retention)
- **Grafana dashboards:** Minimal growth

**Recommended:**
- Start with 500 GB
- Monitor with `df -h` regularly
- Configure log rotation and metric retention

## Network Requirements

### Bandwidth

| Activity | Bandwidth | Notes |
|----------|-----------|-------|
| **DNS queries** | <1 Mbps | Minimal overhead |
| **n8n workflows** | Varies | Depends on workflow (webhooks, API calls) |
| **Remote access (VPN)** | 5-50 Mbps | Depends on usage (streaming, file access) |

### Ports

Required open ports (internal only, VPN-first model):

| Port | Service | Protocol | Required For |
|------|---------|----------|--------------|
| 53 | AdGuard DNS | TCP/UDP | DNS resolution |
| 80 | Traefik HTTP | TCP | HTTP redirect to HTTPS |
| 443 | Traefik HTTPS | TCP | All service access |
| 5678 | n8n | TCP | Direct n8n access (legacy) |
| 8888 | AdGuard UI | TCP | Direct AdGuard access (legacy) |
| 51820 | WireGuard | UDP | VPN access |

**Monitoring Stack Ports:**
| Port | Service | Protocol |
|------|---------|----------|
| 3001 | Grafana | TCP |
| 9090 | Prometheus | TCP |
| 9093 | Alertmanager | TCP |
| 9100 | Node Exporter | TCP |
| 8080 | cAdvisor | TCP |

**Security Note:** Only port 51820 (WireGuard) should be exposed to the internet. All other services should be VPN-only.

## Performance Considerations

### CPU

**Single-Core vs Multi-Core:**
- **AI Inference:** Benefits from multiple cores (4+ recommended)
- **n8n workflows:** Can run concurrent workflows on multiple cores
- **AdGuard/WireGuard:** Low CPU usage, 2 cores sufficient

**CPU Features:**
- **Virtualization:** Not required (bare metal or VM both work)
- **Multi-core:** Improves workflow performance

### RAM

**Memory Speed:**
- DDR4-2666 or higher recommended for AI workloads
- Memory speed less critical for other services

**Swap:**
- Enable swap for better stability (8-16 GB recommended)
- SSD swap better than HDD
- Not a substitute for sufficient RAM

```bash
# Check current swap
free -h

# Add 16GB swap (if needed)
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# Add to /etc/fstab for persistence
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Storage

**Drive Types:**
- **SSD:** Strongly recommended for Docker containers and Ollama models
  - Faster model loading
  - Better database performance (n8n, Prometheus)
- **HDD:** Acceptable for backups and logs only
  - Avoid running Docker on HDD (slow performance)

**RAID:**
- Not required for home use
- Consider RAID1/10 for data redundancy if critical
- Backups more important than RAID

**File System:**
- **ext4:** Recommended (most tested)
- **btrfs:** Good for snapshots (advanced users)
- **ZFS:** Excellent but requires more RAM overhead

## Operating System Requirements

### Tested Distributions

| Distribution | Version | Status | Notes |
|--------------|---------|--------|-------|
| **Ubuntu Server** | 24.04 LTS | ✅ Recommended | Official testing platform |
| **Ubuntu Server** | 22.04 LTS | ✅ Supported | Fully compatible |
| **Debian** | 12 (Bookworm) | ✅ Supported | Very similar to Ubuntu |
| **Fedora** | 39+ | ✅ Compatible | May need SELinux adjustments |
| **CentOS Stream** | 9 | ✅ Compatible | Enterprise option |
| **Arch Linux** | Rolling | ✅ Compatible | Advanced users |
| **Raspberry Pi OS** | 64-bit | ⚠️ Limited | See below |

### Raspberry Pi Considerations

**Raspberry Pi 4 (4GB+ RAM):**
- ✅ AdGuard Home: Excellent
- ✅ n8n: Good
- ✅ WireGuard: Excellent
- ✅ Traefik: Good
- ⚠️ Monitoring: Use lightweight configuration

**Limitations:**
- ARM architecture requires ARM-compatible Docker images
- SD card I/O limitations (use USB SSD strongly recommended)
- Limited RAM for heavy workflows

**Recommendation:** Raspberry Pi 4 with 4GB+ RAM works well for the basic stack.

## Virtualization

### Docker on VMs

Works well in:
- **Proxmox VE:** Excellent, LXC containers or VMs
- **VMware ESXi:** Good, ensure nested virtualization enabled
- **VirtualBox:** Fair, performance overhead
- **Hyper-V:** Good, Windows users

**VM Recommendations:**
- Allocate full cores (not shares) for better AI performance
- Use virtio drivers for better disk/network performance
- Pass through storage directly if possible (better I/O)

### LXC Containers (Proxmox)

- ✅ Excellent performance (near bare metal)
- ✅ Lower overhead than VMs
- ⚠️ Docker-in-LXC requires privileged container or proper nesting
- See: https://pve.proxmox.com/wiki/Linux_Container

## Pre-Installation Checklist

Before installing, verify:

- [ ] **Hardware meets minimum requirements** (8GB RAM, 500GB storage)
- [ ] **Linux OS installed** (Ubuntu Server 24.04 LTS recommended)
- [ ] **Docker installed** (`docker --version`)
- [ ] **Docker Compose installed** (`docker compose version`)
- [ ] **Static IP configured** (check with `ip addr`)
- [ ] **Sufficient disk space** (`df -h /`)
- [ ] **Root/sudo access** (`sudo whoami`)
- [ ] **Internet connectivity** (`ping -c 3 8.8.8.8`)
- [ ] **Ports available** (`sudo netstat -tlnp | grep -E ':(53|80|5678|11434|51820)'`)

**Recommended Tools:**
```bash
# Install helpful utilities
sudo apt update
sudo apt install -y htop iotop nethogs ncdu curl wget git make
```

## Next Steps

- **Ready to install?** See [SETUP.md](SETUP.md)
- **Questions about configuration?** See [CONFIGURATION.md](CONFIGURATION.md)
- **Need help?** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
