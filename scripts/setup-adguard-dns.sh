#!/bin/bash
# setup-adguard-dns.sh
# Configures AdGuard Home DNS rewrites for domain-based access
#
# This script creates an AdGuardHome.yaml configuration with DNS rewrites
# that enable *.home.local domains to resolve to the server IP address.

set -e

# Configuration
CONFIG_DIR="data/adguard/conf"
CONFIG_FILE="$CONFIG_DIR/AdGuardHome.yaml"
SERVER_IP="${SERVER_IP:-192.168.1.100}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "AdGuard Home DNS Rewrite Configuration"
echo "======================================="
echo ""

# Check if SERVER_IP is set
if [ -z "$SERVER_IP" ]; then
    echo -e "${RED}ERROR: SERVER_IP environment variable not set${NC}"
    echo "Please set SERVER_IP in your .env file or export it:"
    echo "  export SERVER_IP=192.168.1.100"
    exit 1
fi

echo "Using SERVER_IP: $SERVER_IP"
echo ""

# Create configuration directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Backup existing configuration if it exists
if [ -f "$CONFIG_FILE" ]; then
    BACKUP_FILE="$CONFIG_FILE.backup.$(date +%Y%m%d-%H%M%S)"
    echo -e "${YELLOW}⚠️  Warning: $CONFIG_FILE already exists${NC}"
    echo "Creating backup: $BACKUP_FILE"
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    echo -e "${GREEN}✓${NC} Backup created"
    echo ""
fi

# Create AdGuardHome.yaml with DNS rewrites
echo "Creating AdGuardHome.yaml configuration..."

cat > "$CONFIG_FILE" <<EOF
http:
  pprof:
    port: 6060
    enabled: false
  address: 0.0.0.0:3000
  session_ttl: 720h
users:
  - name: admin
    password: \$2a\$10\$IYkkr0pMzVQQFqzq0K9TyOULwOy1BQQC5qZZbqJXqQKf1VsQxc9n6
auth_attempts: 5
block_auth_min: 15
http_proxy: ""
language: ""
theme: auto
dns:
  bind_hosts:
    - 0.0.0.0
  port: 53
  anonymize_client_ip: false
  ratelimit: 20
  ratelimit_subnet_len_ipv4: 24
  ratelimit_subnet_len_ipv6: 56
  ratelimit_whitelist: []
  refuse_any: true
  upstream_dns:
    - https://dns10.quad9.net/dns-query
    - tls://dns.cloudflare.com
    - https://dns.google/dns-query
  upstream_dns_file: ""
  bootstrap_dns:
    - 9.9.9.10
    - 149.112.112.10
    - 2620:fe::10
    - 2620:fe::fe:10
  fallback_dns: []
  upstream_mode: load_balance
  fastest_timeout: 1s
  allowed_clients: []
  disallowed_clients: []
  blocked_hosts:
    - version.bind
    - id.server
    - hostname.bind
  trusted_proxies:
    - 127.0.0.0/8
    - ::1/128
  cache_enabled: true
  cache_size: 4194304
  cache_ttl_min: 0
  cache_ttl_max: 0
  cache_optimistic: false
  bogus_nxdomain: []
  aaaa_disabled: false
  enable_dnssec: false
  edns_client_subnet:
    custom_ip: ""
    enabled: false
    use_custom: false
  max_goroutines: 300
  handle_ddr: true
  ipset: []
  ipset_file: ""
  bootstrap_prefer_ipv6: false
  upstream_timeout: 10s
  private_networks: []
  use_private_ptr_resolvers: true
  local_ptr_upstreams: []
  use_dns64: false
  dns64_prefixes: []
  serve_http3: false
  use_http3_upstreams: false
  serve_plain_dns: true
  hostsfile_enabled: true
  pending_requests:
    enabled: true
tls:
  enabled: false
  server_name: ""
  force_https: false
  port_https: 443
  port_dns_over_tls: 853
  port_dns_over_quic: 853
  port_dnscrypt: 0
  dnscrypt_config_file: ""
  allow_unencrypted_doh: false
  certificate_chain: ""
  private_key: ""
  certificate_path: ""
  private_key_path: ""
  strict_sni_check: false
querylog:
  dir_path: ""
  ignored: []
  interval: 2160h
  size_memory: 1000
  enabled: true
  file_enabled: true
statistics:
  dir_path: ""
  ignored: []
  interval: 24h
  enabled: true
filters:
  - enabled: true
    url: https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt
    name: AdGuard DNS filter
    id: 1
  - enabled: true
    url: https://adguardteam.github.io/HostlistsRegistry/assets/filter_2.txt
    name: AdAway Default Blocklist
    id: 2
whitelist_filters: []
user_rules: []
dhcp:
  enabled: false
  interface_name: ""
  local_domain_name: lan
  dhcpv4:
    gateway_ip: ""
    subnet_mask: ""
    range_start: ""
    range_end: ""
    lease_duration: 86400
    icmp_timeout_msec: 1000
    options: []
  dhcpv6:
    range_start: ""
    lease_duration: 86400
    ra_slaac_only: false
    ra_allow_slaac: false
filtering:
  blocking_ipv4: ""
  blocking_ipv6: ""
  blocked_services:
    schedule:
      time_zone: UTC
    ids: []
  protection_disabled_until: null
  safe_search:
    enabled: false
    bing: true
    duckduckgo: true
    ecosia: true
    google: true
    pixabay: true
    yandex: true
    youtube: true
  blocking_mode: default
  parental_block_host: family-block.dns.adguard.com
  safebrowsing_block_host: standard-block.dns.adguard.com
  rewrites:
    - domain: '*.home.local'
      answer: $SERVER_IP
  safe_fs_patterns:
    - /opt/adguardhome/work/data/userfilters/*
  safebrowsing_cache_size: 1048576
  safesearch_cache_size: 1048576
  parental_cache_size: 1048576
  cache_time: 30
  filters_update_interval: 24
  blocked_response_ttl: 10
  filtering_enabled: true
  parental_enabled: false
  safebrowsing_enabled: false
  protection_enabled: true
clients:
  runtime_sources:
    whois: true
    arp: true
    rdns: true
    dhcp: true
    hosts: true
  persistent: []
log:
  enabled: true
  file: ""
  max_backups: 0
  max_size: 100
  max_age: 3
  compress: false
  local_time: false
  verbose: false
os:
  group: ""
  user: ""
  rlimit_nofile: 0
schema_version: 30
EOF

echo -e "${GREEN}✓${NC} Configuration file created: $CONFIG_FILE"
echo ""

# Verify DNS rewrite was added
if grep -q "'\*.home.local'" "$CONFIG_FILE"; then
    echo -e "${GREEN}✓${NC} DNS rewrite configured: *.home.local → $SERVER_IP"
else
    echo -e "${RED}ERROR: DNS rewrite not found in configuration${NC}"
    exit 1
fi

echo ""
echo "Configuration complete!"
echo ""
echo "DNS rewrites configured for domain-based access:"
echo "  - glance.home.local      → $SERVER_IP"
echo "  - grafana.home.local     → $SERVER_IP"
echo "  - hortusfox.home.local   → $SERVER_IP"
echo "  - traefik.home.local     → $SERVER_IP"
echo "  - n8n.home.local         → $SERVER_IP"
echo "  - bookwyrm.home.local    → $SERVER_IP"
echo "  - ollama.home.local      → $SERVER_IP"
echo "  - prometheus.home.local  → $SERVER_IP"
echo "  - alerts.home.local      → $SERVER_IP"
echo "  - adguard.home.local     → $SERVER_IP"
echo ""
echo "Next steps:"
echo "  1. Restart AdGuard: docker compose restart adguard"
echo "  2. Test DNS resolution: dig @127.0.0.1 glance.home.local +short"
echo "  3. Configure clients to use $SERVER_IP as DNS server"
echo ""
echo "Default admin credentials:"
echo "  Username: admin"
echo "  Password: admin (change immediately after first login)"
echo ""
