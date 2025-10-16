# Troubleshooting Domain Access & Let's Encrypt

## Issue: "Safari can't find the server" when accessing your domain

This usually means DNS is not resolving correctly. Here's how to diagnose:

### Step 1: Verify DOMAIN is set in .env

```bash
grep DOMAIN .env
```

Should show:
```
DOMAIN=example.com
```

### Step 2: Check if AdGuard is running

```bash
docker ps | grep adguard
```

Should show `adguard-home` container running.

### Step 3: Test DNS resolution from the server

```bash
# Replace example.com with your actual domain
dig @127.0.0.1 glance.example.com +short
```

Should return your SERVER_IP (e.g., `192.168.1.101`)

If it returns nothing or your public IP, AdGuard DNS rewrites aren't configured.

### Step 4: Test DNS resolution from your client device

```bash
# Check what DNS server your device is using
scutil --dns | grep nameserver  # macOS
# or
cat /etc/resolv.conf  # Linux

# Test resolution (replace with your domain)
dig glance.example.com +short
```

**Expected result**: Should return your local SERVER_IP

**If you get a public IP or nothing**: Your device isn't using AdGuard as DNS.

### Step 5: Configure your device to use AdGuard DNS

**Option A: Router-level (Recommended)**
1. Log into your router (usually 192.168.1.1)
2. Find DHCP settings
3. Set DNS server to your SERVER_IP (e.g., `192.168.1.101`)
4. Save and restart router
5. Restart your device to get fresh DHCP lease

**Option B: Device-level (Quick test)**

**macOS:**
1. System Settings → Network
2. Select your connection (Wi-Fi or Ethernet)
3. Click "Details"
4. Go to "DNS" tab
5. Click "+" and add your SERVER_IP
6. Click "OK"

**Linux:**
Edit `/etc/resolv.conf`:
```
nameserver 192.168.1.101  # Your SERVER_IP
```

### Step 6: Verify AdGuard DNS rewrite configuration

```bash
# Check AdGuard config file
grep -A 2 "rewrites:" data/adguard/conf/AdGuardHome.yaml
```

Should show (with your actual domain):
```yaml
  rewrites:
    - domain: '*.example.com'
      answer: 192.168.1.101
```

If it shows `'*.home.local'`, you need to re-run:
```bash
make adguard-setup
docker compose restart adguard
```

### Step 7: Check if Traefik is running

```bash
docker ps | grep traefik
```

Should show `traefik` container running.

### Step 8: Check if your service is running

```bash
docker ps | grep glance  # or whatever service you're testing
```

Should show the container running.

### Step 9: Test Traefik HTTP routing

```bash
# Replace example.com with your domain
curl -I -H "Host: glance.example.com" http://YOUR_SERVER_IP
```

Should redirect to HTTPS:
```
HTTP/1.1 301 Moved Permanently
Location: https://glance.example.com/
```

### Step 10: Test HTTPS with curl

```bash
# Replace example.com with your domain
curl -I -k https://YOUR_SERVER_IP -H "Host: glance.example.com"
```

Should return:
```
HTTP/2 200
```

### Step 11: Check Traefik logs

```bash
docker logs traefik --tail 50
```

Look for:
- Errors about certificate generation
- Errors about routing to services
- ACME challenge status

### Step 12: Check if Let's Encrypt certificate was issued

```bash
# Check acme.json file
ls -lh data/traefik/certs/acme.json

# Check if it has content (more than 0 bytes)
wc -c data/traefik/certs/acme.json
```

If acme.json is empty or very small, certificates haven't been issued yet.

Check Traefik logs for ACME:
```bash
docker logs traefik 2>&1 | grep -i acme
docker logs traefik 2>&1 | grep -i certificate
```

## Common Issues & Solutions

### Issue: DNS resolves to public IP instead of local IP

**Cause**: Device isn't using AdGuard DNS

**Solution**: Configure router or device to use AdGuard (Step 5 above)

### Issue: "Connection refused" when accessing domain

**Cause**: Service isn't running or Traefik isn't routing

**Solution**:
```bash
docker compose ps  # Check all services are up
docker logs traefik | grep SERVICE_NAME  # Check Traefik sees the service
```

### Issue: Certificate error in browser

**Cause**: Let's Encrypt hasn't issued certificate yet

**Solution**:
1. Check DNS at your registrar points to your public IP
2. Check GANDIV5_API_KEY is set correctly in .env
3. Check Traefik logs for ACME errors:
   ```bash
   docker logs traefik 2>&1 | grep -i "error"
   ```

### Issue: Let's Encrypt rate limit

**Cause**: Too many certificate requests (50 per week limit)

**Solution**:
1. Use staging certificates for testing:
   - Edit docker-compose.yml
   - Uncomment the staging line in Traefik command section
   - Restart: `docker compose up -d traefik`
2. Wait 7 days for rate limit to reset
3. When ready for production, delete acme.json and retry:
   ```bash
   rm data/traefik/certs/acme.json
   make traefik-setup
   # Comment out staging line in docker-compose.yml
   docker compose restart traefik
   ```

## DNS Configuration Requirements

For Let's Encrypt to work, you need:

1. **At your DNS provider (Gandi)**: Records pointing to your PUBLIC IP
   ```
   example.com          A    YOUR_PUBLIC_IP
   *.example.com        A    YOUR_PUBLIC_IP
   ```

2. **At AdGuard (local)**: DNS rewrites pointing to LOCAL IP
   ```
   *.example.com  →  192.168.1.101
   ```

3. **Personal Access Token**: From Gandi for DNS-01 challenge
   - Set in .env as: `GANDIV5_API_KEY=your_token_here`

## How It Works

This setup uses **split DNS** (also called split-horizon DNS):

1. **Public DNS** (Gandi): Points your domain to your public IP
   - Used by Let's Encrypt to validate domain ownership
   - Used by external services

2. **Local DNS** (AdGuard): Overrides public DNS on your network
   - Points your domain to your local server IP
   - Keeps traffic on local network (faster, more secure)
   - Avoids hairpin NAT issues

3. **Result**:
   - ✅ Let's Encrypt validates via public DNS
   - ✅ Local devices use local IP (no external traffic)
   - ✅ Valid certificates for your real domain

## Quick Diagnostic Script

Save this as `diagnose-domain.sh`:

```bash
#!/bin/bash
echo "=== DNS & Service Diagnostics ==="
echo ""

# Load DOMAIN from .env
if [ -f .env ]; then
    source .env
fi

if [ -z "$DOMAIN" ]; then
    echo "ERROR: DOMAIN not set in .env"
    exit 1
fi

echo "Domain: $DOMAIN"
echo "Server IP: $SERVER_IP"
echo ""
echo "1. AdGuard running:"
docker ps | grep adguard
echo ""
echo "2. DNS resolution (from server):"
dig @127.0.0.1 glance.$DOMAIN +short
echo ""
echo "3. DNS resolution (from system):"
dig glance.$DOMAIN +short
echo ""
echo "4. Traefik running:"
docker ps | grep traefik
echo ""
echo "5. Glance running:"
docker ps | grep glance
echo ""
echo "6. HTTP test:"
curl -I -H "Host: glance.$DOMAIN" http://$SERVER_IP 2>&1 | head -n 1
echo ""
echo "7. HTTPS test:"
curl -I -k -H "Host: glance.$DOMAIN" https://$SERVER_IP 2>&1 | head -n 1
echo ""
echo "8. ACME.json status:"
ls -lh data/traefik/certs/acme.json 2>&1
```

Make executable and run:
```bash
chmod +x diagnose-domain.sh
./diagnose-domain.sh
```
