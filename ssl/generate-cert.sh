#!/bin/bash

# SSL Certificate Generation Script for n8n Development
# This script creates a self-signed certificate for development use

set -e

DOMAIN=${1:-"your-domain"}
DAYS=${2:-365}
KEY_FILE="server.key"
CERT_FILE="server.crt"

echo "Generating self-signed SSL certificate for domain: $DOMAIN"
echo "Valid for $DAYS days"

# Generate private key
openssl genrsa -out "$KEY_FILE" 2048

# Generate certificate signing request
openssl req -new -key "$KEY_FILE" -out server.csr -subj "/C=US/ST=Development/L=Development/O=Development/OU=Development/CN=$DOMAIN"

# Generate self-signed certificate
openssl x509 -req -days "$DAYS" -in server.csr -signkey "$KEY_FILE" -out "$CERT_FILE" -extensions v3_req -extfile <(
cat <<EOF
[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $DOMAIN
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF
)

# Clean up CSR file
rm server.csr

# Set appropriate permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo "SSL certificate generated successfully!"
echo "Key file: $KEY_FILE"
echo "Certificate file: $CERT_FILE"
echo ""
echo "To use with a different domain, run:"
echo "./generate-cert.sh your-actual-domain.ddns.net"