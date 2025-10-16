# Ticket 04: Self-Hosted Habitica Setup

## Objective
Deploy a self-hosted Habitica instance with HTTPS support, MongoDB, and Redis for gamified task management.

## Tasks

### 1. Create Habitica Docker Compose Configuration

Create `habitica/docker-compose.habitica.yml`:

```yaml
version: '3.8'

services:
  habitica:
    image: habitrpg/habitica:latest
    container_name: habitica
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: production
      BASE_URL: ${HABITICA_BASE_URL}
      SESSION_SECRET: ${HABITICA_SESSION_SECRET}
      
      # Database
      NODE_DB_URI: mongodb://${HABITICA_MONGO_USER}:${HABITICA_MONGO_PASSWORD}@habitica-mongo:27017/${HABITICA_DB_NAME}?authSource=admin
      
      # Redis
      REDIS_HOST: habitica-redis
      REDIS_PORT: 6379
      
      # Admin
      ADMIN_EMAIL: ${HABITICA_ADMIN_EMAIL}
      ADMIN_PASSWORD: ${HABITICA_ADMIN_PASSWORD}
      
      # Email (optional - configure later)
      # SMTP_HOST: smtp.gmail.com
      # SMTP_PORT: 587
      # SMTP_USER: your@email.com
      # SMTP_PASSWORD: your_password
      
    depends_on:
      - habitica-mongo
      - habitica-redis
    restart: unless-stopped
    networks:
      - home-server
    volumes:
      - ./data/habitica/uploads:/usr/src/habitica/website/static/uploads

  habitica-mongo:
    image: mongo:4.4
    container_name: habitica-mongo
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${HABITICA_MONGO_USER}
      MONGO_INITDB_ROOT_PASSWORD: ${HABITICA_MONGO_PASSWORD}
      MONGO_INITDB_DATABASE: ${HABITICA_DB_NAME}
    volumes:
      - ./data/habitica/mongo:/data/db
    restart: unless-stopped
    networks:
      - home-server

  habitica-redis:
    image: redis:6-alpine
    container_name: habitica-redis
    restart: unless-stopped
    networks:
      - home-server

networks:
  home-server:
    name: home-server
    external: true
```

### 2. Integrate Habitica into Main Dashboard Compose

Add to `docker-compose.dashboard.yml`:

```yaml
  # Include Habitica services
  habitica:
    extends:
      file: habitica/docker-compose.habitica.yml
      service: habitica

  habitica-mongo:
    extends:
      file: habitica/docker-compose.habitica.yml
      service: habitica-mongo

  habitica-redis:
    extends:
      file: habitica/docker-compose.habitica.yml
      service: habitica-redis
```

### 3. Set Up HTTPS for Habitica

Create `habitica/nginx-habitica.conf`:

```nginx
server {
    listen 443 ssl http2;
    server_name habitica.yourdomain.local;

    ssl_certificate /etc/nginx/ssl/habitica.crt;
    ssl_certificate_key /etc/nginx/ssl/habitica.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 20M;

    location / {
        proxy_pass http://habitica:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name habitica.yourdomain.local;
    return 301 https://$server_name$request_uri;
}
```

Add Nginx reverse proxy to docker-compose.dashboard.yml:

```yaml
  habitica-nginx:
    image: nginx:alpine
    container_name: habitica-nginx
    ports:
      - "443:443"  # HTTPS for Habitica
    volumes:
      - ./habitica/nginx-habitica.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl/habitica:/etc/nginx/ssl:ro
    depends_on:
      - habitica
    restart: unless-stopped
    networks:
      - home-server
```

### 4. Create SSL Certificate Generation Script

Create `ssl/generate-habitica-cert.sh`:

```bash
#!/bin/bash
# Generate self-signed certificate for Habitica

set -e

DOMAIN=${1:-habitica.yourdomain.local}
OUTPUT_DIR="./habitica"

echo "Generating self-signed certificate for ${DOMAIN}"

mkdir -p "${OUTPUT_DIR}"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "${OUTPUT_DIR}/habitica.key" \
    -out "${OUTPUT_DIR}/habitica.crt" \
    -subj "/C=AU/ST=NSW/L=Sydney/O=Home Server/CN=${DOMAIN}"

chmod 644 "${OUTPUT_DIR}/habitica.crt"
chmod 600 "${OUTPUT_DIR}/habitica.key"

echo "✅ Certificate generated:"
echo "   ${OUTPUT_DIR}/habitica.crt"
echo "   ${OUTPUT_DIR}/habitica.key"
echo ""
echo "⚠️  This is a self-signed certificate. You'll need to accept the security warning in your browser."
```

Make executable:
```bash
chmod +x ssl/generate-habitica-cert.sh
```

### 5. Create Habitica Setup Script

Create `scripts/setup-habitica.sh`:

```bash
#!/bin/bash
set -e

echo "🎮 Setting up Self-Hosted Habitica"
echo "==================================="

# Check environment variables
if [ -z "$HABITICA_SESSION_SECRET" ]; then
    echo "⚠️  HABITICA_SESSION_SECRET not set in .env"
    echo "Generate one with: openssl rand -base64 32"
    exit 1
fi

# Generate SSL certificate
echo "🔒 Generating SSL certificate..."
cd ssl
./generate-habitica-cert.sh habitica.yourdomain.local
cd ..

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/habitica/{mongo,redis,uploads}

# Start services
echo "🚀 Starting Habitica services..."
docker compose -f docker-compose.dashboard.yml up -d habitica habitica-mongo habitica-redis habitica-nginx

echo "⏳ Waiting for Habitica to initialize (this may take 2-3 minutes)..."
sleep 30

# Check if Habitica is running
if docker logs habitica 2>&1 | grep -q "Server listening"; then
    echo "✅ Habitica is running!"
    echo ""
    echo "📝 Access Habitica at: https://${SERVER_IP}"
    echo "   (or http://${SERVER_IP}:3000 without HTTPS)"
    echo ""
    echo "⚠️  Accept the self-signed certificate warning in your browser"
    echo ""
    echo "🔑 After first login, get your API credentials:"
    echo "   1. Go to Settings > API"
    echo "   2. Copy your User ID and API Token"
    echo "   3. Add to .env as HABITICA_USER_ID and HABITICA_API_TOKEN"
else
    echo "❌ Habitica failed to start. Check logs:"
    echo "   docker logs habitica"
fi
```

Make executable:
```bash
chmod +x scripts/setup-habitica.sh
```

### 6. Update Homepage services.yaml

Add to `data/homepage/config/services.yaml` under "Habitica RPG":

```yaml
- Habitica RPG:
    - Character Stats:
        icon: mdi-shield-account
        href: {{HOMEPAGE_VAR_HABITICA_URL}}
        description: Your RPG character
        widget:
          type: homeassistant
          url: {{HOMEPAGE_VAR_HOMEASSISTANT_URL}}
          key: {{HOMEPAGE_VAR_HOMEASSISTANT_TOKEN}}
          custom:
            - state: sensor.habitica_username_level
              label: Level
              field: state
            - state: sensor.habitica_username_health
              label: HP
              field: state
            - state: sensor.habitica_username_experience
              label: XP
              field: state
            - state: sensor.habitica_username_gold
              label: Gold
              field: state

    - Resources:
        icon: mdi-treasure-chest
        description: Character resources
        widget:
          type: homeassistant
          url: {{HOMEPAGE_VAR_HOMEASSISTANT_URL}}
          key: {{HOMEPAGE_VAR_HOMEASSISTANT_TOKEN}}
          custom:
            - state: sensor.habitica_username_mana
              label: Mana
              field: state
            - state: sensor.habitica_username_class
              label: Class
              field: state

    - Open Habitica:
        icon: habitica.png
        href: {{HOMEPAGE_VAR_HABITICA_URL}}
        description: Go to Habitica
```

### 7. Create Habitica Documentation

Create `docs/HABITICA_SETUP.md`:

```markdown
# Self-Hosted Habitica Setup Guide

## Initial Setup

1. Generate session secret:
   ```bash
   openssl rand -base64 32
   ```
   Add to `.env` as `HABITICA_SESSION_SECRET`

2. Run setup script:
   ```bash
   ./scripts/setup-habitica.sh
   ```

3. Access Habitica at https://SERVER_IP (or http://SERVER_IP:3000)

4. Accept self-signed certificate warning

5. Create your account:
   - Click "Sign Up"
   - Use the admin email/password from .env
   - Complete character creation

## Get API Credentials

1. Login to Habitica
2. Click Settings (gear icon) → API
3. Copy your User ID and API Token
4. Add to `.env`:
   ```bash
   HABITICA_USER_ID=abc123de-f456-7890-ghij-klmn12345678
   HABITICA_API_TOKEN=def456gh-i789-0123-jklm-nopq45678901
   ```

## Home Assistant Integration

See **Ticket 08** for connecting Habitica to Home Assistant.

## HTTPS Configuration

### Using Self-Signed Certificate (Default)
- Certificate generated automatically by setup script
- You'll see a security warning in browser (this is normal)
- Click "Advanced" → "Proceed to site"

### Using Let's Encrypt (Production)
If you have a domain name:

1. Install certbot:
   ```bash
   sudo apt install certbot
   ```

2. Generate certificate:
   ```bash
   sudo certbot certonly --standalone -d habitica.yourdomain.com
   ```

3. Update `habitica/nginx-habitica.conf`:
   ```nginx
   ssl_certificate /etc/letsencrypt/live/habitica.yourdomain.com/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/habitica.yourdomain.com/privkey.pem;
   ```

4. Mount certificates in docker-compose:
   ```yaml
   volumes:
     - /etc/letsencrypt:/etc/letsencrypt:ro
   ```

## Backup and Restore

### Backup
```bash
# Backup MongoDB
docker exec habitica-mongo mongodump \
  --username=$HABITICA_MONGO_USER \
  --password=$HABITICA_MONGO_PASSWORD \
  --out=/data/backup

# Copy backup
docker cp habitica-mongo:/data/backup ./backups/habitica-$(date +%Y%m%d)
```

### Restore
```bash
# Restore from backup
docker cp ./backups/habitica-20250101 habitica-mongo:/data/restore

docker exec habitica-mongo mongorestore \
  --username=$HABITICA_MONGO_USER \
  --password=$HABITICA_MONGO_PASSWORD \
  /data/restore
```

## Troubleshooting

### Habitica won't start
- Check logs: `docker logs habitica`
- Verify MongoDB is running: `docker ps | grep mongo`
- Ensure SESSION_SECRET is set in .env

### Cannot connect to MongoDB
- Check credentials in .env
- Verify MongoDB container is healthy: `docker inspect habitica-mongo`

### HTTPS certificate error
- This is expected with self-signed certificates
- To avoid: use Let's Encrypt or import certificate to system trust store

### Lost admin password
Reset in MongoDB:
```bash
docker exec -it habitica-mongo mongosh -u $HABITICA_MONGO_USER -p $HABITICA_MONGO_PASSWORD
use habitica
db.users.updateOne(
  {auth.local.email: "admin@example.com"},
  {$set: {"auth.local.hashed_password": "new_hash"}}
)
```

## Updating Habitica

```bash
# Pull latest image
docker pull habitrpg/habitica:latest

# Backup first (see above)

# Restart with new image
docker compose -f docker-compose.dashboard.yml up -d habitica
```
```

## Acceptance Criteria
- [ ] docker-compose.habitica.yml created with all services
- [ ] Habitica services added to docker-compose.dashboard.yml
- [ ] Nginx reverse proxy configured for HTTPS
- [ ] SSL certificate generation script created
- [ ] Setup script created and working
- [ ] Habitica accessible at https://SERVER_IP
- [ ] MongoDB and Redis running correctly
- [ ] API credentials obtained and documented
- [ ] Habitica widget added to Homepage
- [ ] Documentation created
- [ ] Backup/restore instructions provided

## Testing
```bash
# Generate session secret
openssl rand -base64 32

# Run setup
./scripts/setup-habitica.sh

# Wait for startup
docker logs -f habitica

# Test access
curl -k https://localhost:443  # HTTPS
curl http://localhost:3000      # HTTP direct

# Test API (after getting credentials)
curl -H "x-api-user: YOUR_USER_ID" \
     -H "x-api-key: YOUR_API_TOKEN" \
     http://localhost:3000/api/v3/user
```

## Dependencies
- Ticket 01: Project structure
- Ticket 02: Homepage dashboard
- Ticket 03: Home Assistant (for widget display)

## Notes
- First startup may take 2-3 minutes
- MongoDB 4.4 used for compatibility
- Session secret must be 32+ characters
- HTTPS uses self-signed cert by default (can upgrade to Let's Encrypt)
- API credentials generated after first login
- Integration with Home Assistant done in Ticket 08
- Keep MongoDB data backed up regularly
- Port 3000 used for direct HTTP access
- Port 443 used for HTTPS via Nginx
