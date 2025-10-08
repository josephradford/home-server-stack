# Set Up Regular Security Audits

## Priority: 4 (Low - Enhancement)
## Estimated Time: 2-3 hours
## Phase: Month 3 - Ongoing Security

## Description
Establish quarterly security audit procedures including penetration testing, configuration reviews, access audits, and dependency updates.

## Acceptance Criteria
- [ ] Quarterly audit schedule defined
- [ ] Audit checklist created
- [ ] Automated audit tools configured
- [ ] Results tracked over time
- [ ] Remediation process documented

## Technical Implementation Details

**Security Audit Checklist (docs/SECURITY_AUDIT_CHECKLIST.md):**
```markdown
# Quarterly Security Audit Checklist

## Q1 2024 Audit - Due: March 31

### 1. Access Control Review
- [ ] Review all user accounts in Authelia
- [ ] Verify MFA enabled for all admin accounts
- [ ] Audit SSH keys and access logs
- [ ] Review firewall rules (UFW status)
- [ ] Check for unused service accounts

### 2. Credential Rotation
- [ ] Rotate Grafana admin password
- [ ] Update Authelia secrets (JWT, session)
- [ ] Regenerate SSL certificates if >90 days old
- [ ] Review API keys and tokens in n8n
- [ ] Update backup encryption passphrase

### 3. Software Updates
- [ ] Update all Docker images to latest versions
- [ ] Review and apply Docker Bench Security recommendations
- [ ] Update host OS packages (apt update && apt upgrade)
- [ ] Check for EOL software components

### 4. Vulnerability Assessment
- [ ] Run Trivy scans on all images
- [ ] Review GitHub Dependabot alerts
- [ ] Check CVE databases for known issues
- [ ] Perform external port scan (nmap)

### 5. Configuration Review
- [ ] Verify resource limits on all containers
- [ ] Check security_opt settings
- [ ] Review network segmentation
- [ ] Audit Traefik routing rules
- [ ] Verify log retention policies

### 6. Backup & Recovery
- [ ] Test backup restoration
- [ ] Verify backup encryption
- [ ] Check off-site backup sync
- [ ] Test disaster recovery procedures
- [ ] Verify backup monitoring alerts

### 7. Monitoring & Alerting
- [ ] Test AlertManager notifications
- [ ] Review alert fatigue metrics
- [ ] Check Prometheus targets health
- [ ] Verify Loki log collection
- [ ] Test security alert workflows

### 8. Penetration Testing
- [ ] External port scanning
- [ ] Authentication bypass attempts
- [ ] SQL injection testing (if applicable)
- [ ] XSS testing on web interfaces
- [ ] Rate limiting verification

### 9. Compliance
- [ ] Run Docker Bench Security
- [ ] Review CIS benchmark compliance
- [ ] Document exceptions
- [ ] Update security policies

### 10. Documentation
- [ ] Update network diagrams
- [ ] Review incident response playbook
- [ ] Update runbooks
- [ ] Document new risks
- [ ] Archive audit results
```

**Automated audit script (scripts/security-audit.sh):**
```bash
#!/bin/bash
# Automated security audit script

AUDIT_DATE=$(date +%Y%m%d)
AUDIT_DIR="audits/$AUDIT_DATE"

mkdir -p "$AUDIT_DIR"

echo "🔒 Starting security audit: $AUDIT_DATE"

# 1. Port scan
echo "1. Running external port scan..."
nmap -sV -sC localhost > "$AUDIT_DIR/port-scan.txt"

# 2. Vulnerability scan
echo "2. Scanning for vulnerabilities..."
./scripts/local-scan.sh
mv scan-results "$AUDIT_DIR/"

# 3. Docker Bench
echo "3. Running Docker Bench Security..."
docker run --rm --net host --pid host --userns host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  docker/docker-bench-security > "$AUDIT_DIR/docker-bench.txt"

# 4. SSL/TLS check
echo "4. Checking SSL/TLS configuration..."
testssl --jsonfile "$AUDIT_DIR/tls-scan.json" https://yourdomain.com

# 5. Access log analysis
echo "5. Analyzing access logs..."
docker logs traefik --since 24h | grep -E "(40[134]|50[023])" > "$AUDIT_DIR/error-logs.txt"

# 6. User audit
echo "6. Auditing user accounts..."
docker exec authelia cat /config/users_database.yml > "$AUDIT_DIR/users-audit.yml"

# 7. Firewall rules
echo "7. Exporting firewall rules..."
sudo ufw status numbered > "$AUDIT_DIR/firewall-rules.txt"

# 8. Generate report
echo "8. Generating audit report..."
cat > "$AUDIT_DIR/AUDIT_SUMMARY.md" << EOF
# Security Audit Report - $AUDIT_DATE

## Executive Summary
- Audit Date: $(date)
- Auditor: Automated
- Status: Review Required

## Findings
- Port Scan: See port-scan.txt
- Vulnerabilities: See scan-results/
- Docker Security: See docker-bench.txt
- TLS Configuration: See tls-scan.json

## Action Items
<!-- To be filled manually -->

## Next Audit
- Scheduled: $(date -d "+3 months" +%Y-%m-%d)
EOF

echo "✅ Audit complete! Results in $AUDIT_DIR/"
```

**Add to crontab:**
```bash
# Quarterly security audit (first day of quarter)
0 6 1 1,4,7,10 * /opt/home-server-stack/scripts/security-audit.sh
```

## Testing Commands
```bash
# Run manual audit
chmod +x scripts/security-audit.sh
./scripts/security-audit.sh

# View audit results
ls -la audits/
cat audits/$(date +%Y%m%d)/AUDIT_SUMMARY.md

# Compare audits over time
diff audits/20240101/docker-bench.txt audits/20240401/docker-bench.txt
```

## Success Metrics
- Quarterly audits completed on time
- All findings documented and tracked
- High/critical items remediated within 30 days
- Audit results show improvement trends

## References
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Security Audit Best Practices](https://owasp.org/www-community/controls/Security_Audit)
