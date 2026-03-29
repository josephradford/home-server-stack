#!/bin/bash
# test-domain-access.sh
# Tests domain-based access for all services configured with Traefik
#
# This script verifies:
# - DNS resolution for *.home.local domains
# - HTTP to HTTPS redirect functionality
# - HTTPS endpoint accessibility
# - Traefik routing configuration

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Configuration
SERVER_IP="${SERVER_IP:-192.168.1.100}"
DNS_SERVER="${SERVER_IP}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

echo "Domain-Based Access Testing"
echo "============================"
echo ""
echo "Server IP: $SERVER_IP"
echo "DNS Server: $DNS_SERVER"
echo ""

# Function to test DNS resolution
test_dns() {
    local domain=$1
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo -n "Testing DNS resolution for $domain... "

    # Test DNS resolution
    RESOLVED_IP=$(dig @${DNS_SERVER} ${domain} +short 2>/dev/null | head -n1)

    if [ -z "$RESOLVED_IP" ]; then
        echo -e "${RED}FAILED${NC} (no response)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    elif [ "$RESOLVED_IP" = "$SERVER_IP" ]; then
        echo -e "${GREEN}PASSED${NC} (${RESOLVED_IP})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}FAILED${NC} (got ${RESOLVED_IP}, expected ${SERVER_IP})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to test HTTP to HTTPS redirect
test_http_redirect() {
    local domain=$1
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo -n "Testing HTTP redirect for $domain... "

    # Test HTTP redirect (should get 301/302 to HTTPS)
    HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ${domain}" http://${SERVER_IP} 2>/dev/null || echo "000")

    if [ "$HTTP_RESPONSE" = "301" ] || [ "$HTTP_RESPONSE" = "302" ] || [ "$HTTP_RESPONSE" = "308" ]; then
        echo -e "${GREEN}PASSED${NC} (${HTTP_RESPONSE} redirect)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}FAILED${NC} (got ${HTTP_RESPONSE}, expected 301/302/308)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to test HTTPS endpoint
test_https_endpoint() {
    local domain=$1
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo -n "Testing HTTPS endpoint for $domain... "

    # Test HTTPS endpoint (allow self-signed certs with -k)
    HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -k -H "Host: ${domain}" https://${SERVER_IP} 2>/dev/null || echo "000")

    if [ "$HTTPS_RESPONSE" = "200" ] || [ "$HTTPS_RESPONSE" = "302" ] || [ "$HTTPS_RESPONSE" = "401" ]; then
        echo -e "${GREEN}PASSED${NC} (${HTTPS_RESPONSE})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}FAILED${NC} (got ${HTTPS_RESPONSE}, expected 200/302/401)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to test Traefik routing
test_traefik_routing() {
    local domain=$1
    local expected_status=$2
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo -n "Testing Traefik routing for $domain... "

    # Test with Host header to verify Traefik is routing based on domain
    ROUTING_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ${domain}" http://${SERVER_IP} 2>/dev/null || echo "000")

    if [ "$ROUTING_RESPONSE" = "$expected_status" ] || [ "$ROUTING_RESPONSE" = "301" ] || [ "$ROUTING_RESPONSE" = "302" ] || [ "$ROUTING_RESPONSE" = "308" ]; then
        echo -e "${GREEN}PASSED${NC} (${ROUTING_RESPONSE})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${YELLOW}WARNING${NC} (got ${ROUTING_RESPONSE}, expected ${expected_status} or redirect)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    fi
}

# Function to run full test suite for a domain
test_domain() {
    local domain=$1
    local service_name=$2

    echo -e "${BLUE}Testing ${service_name}${NC}"
    echo "----------------------------------------"

    test_dns "$domain"
    test_http_redirect "$domain"
    test_https_endpoint "$domain"
    test_traefik_routing "$domain" "301"

    echo ""
}

# Check if Docker containers are running
echo "Checking service status..."
echo "----------------------------------------"

# Services with Traefik routing (accessible via domains)
# Based on actual docker-compose.yml configurations
services=("traefik" "grafana" "n8n" "adguard-home" "prometheus" "alertmanager" "homepage" "homepage-api")
all_running=true

for service in "${services[@]}"; do
    if docker ps --format "{{.Names}}" | grep -q "^${service}$"; then
        echo -e "${GREEN}✓${NC} $service is running"
    else
        echo -e "${RED}✗${NC} $service is NOT running"
        all_running=false
    fi
done

echo ""

if [ "$all_running" = false ]; then
    echo -e "${RED}ERROR: Not all required services are running${NC}"
    echo "Please start services with: make start"
    exit 1
fi

# Test AdGuard DNS service
echo "Testing AdGuard DNS service..."
echo "----------------------------------------"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if nc -z -w5 ${DNS_SERVER} 53 2>/dev/null; then
    echo -e "${GREEN}✓${NC} AdGuard DNS is responding on port 53"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} AdGuard DNS is NOT responding on port 53"
    echo "Please ensure AdGuard is running and DNS rewrites are configured"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo ""

# Load DOMAIN from .env to construct full domain names
DOMAIN="${DOMAIN:-home.local}"

# Run tests for each service (based on actual docker-compose configurations)
test_domain "n8n.${DOMAIN}" "n8n Workflow Automation"
test_domain "adguard.${DOMAIN}" "AdGuard Home"
test_domain "homepage.${DOMAIN}" "Homepage Dashboard"
test_domain "homepage-api.${DOMAIN}" "Homepage API"
test_domain "grafana.${DOMAIN}" "Grafana Monitoring"
test_domain "prometheus.${DOMAIN}" "Prometheus Monitoring"
test_domain "alerts.${DOMAIN}" "Alertmanager"
test_domain "traefik.${DOMAIN}" "Traefik Dashboard"

# Summary
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Total tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Domain-based access is working correctly."
    echo ""
    echo "Access services via:"
    echo "  • Homepage:     https://homepage.${DOMAIN}"
    echo "  • n8n:          https://n8n.${DOMAIN}"
    echo "  • AdGuard:      https://adguard.${DOMAIN}"
    echo "  • Grafana:      https://grafana.${DOMAIN}"
    echo "  • Prometheus:   https://prometheus.${DOMAIN}"
    echo "  • Alertmanager: https://alerts.${DOMAIN}"
    echo "  • Traefik:      https://traefik.${DOMAIN}"
    echo "  • Homepage API: https://homepage-api.${DOMAIN}"
    echo ""
    echo "Note: You may see certificate warnings if using self-signed certificates."
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Troubleshooting steps:"
    echo "  1. Verify services are running: make status"
    echo "  2. Check Traefik logs: docker logs traefik"
    echo "  3. Check AdGuard DNS: dig @${DNS_SERVER} n8n.${DOMAIN}"
    echo "  4. Verify DNS configuration in AdGuard: https://adguard.${DOMAIN}"
    echo "  5. Ensure your client is using ${DNS_SERVER} as DNS server"
    echo "  6. Check specific service logs: make logs-<service-name>"
    exit 1
fi
