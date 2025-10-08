# Create Security Training Materials

## Priority: 4 (Low - Enhancement)
## Estimated Time: 4-6 hours
## Phase: Month 3 - Ongoing Security

## Description
Develop security training materials and documentation for team members covering secure development practices, incident response, and operational security procedures.

## Acceptance Criteria
- [ ] Security onboarding guide created
- [ ] Common attack scenarios documented
- [ ] Secure development guidelines written
- [ ] Operational runbooks created
- [ ] Training completion tracked

## Technical Implementation Details

**docs/SECURITY_TRAINING.md:**
```markdown
# Security Training Guide

## Module 1: Security Basics

### Authentication
- Always enable MFA (TOTP or WebAuthn)
- Use strong, unique passwords (password manager)
- Never share credentials
- Rotate passwords quarterly

### Secure Access
- SSH key authentication only (no passwords)
- VPN for remote admin access
- Check for HTTPS (look for padlock)
- Verify certificate validity

## Module 2: Common Attack Vectors

### Phishing
- Suspicious emails requesting credentials
- Unexpected attachments or links
- Urgency or threats in messaging
- **Action**: Report to security team, don't click

### Brute Force
- Multiple failed login attempts
- Slow/distributed attacks
- **Detection**: Check Authelia logs
- **Response**: Account lockout, IP blocking

### SQL Injection / XSS
- Input validation bypass
- Malicious scripts in forms
- **Prevention**: Use prepared statements, sanitize input

### DDoS
- Sudden traffic spike
- Service degradation
- **Mitigation**: Rate limiting, Cloudflare

## Module 3: Incident Response

### If You Suspect a Breach:
1. **DON'T PANIC**
2. Isolate affected service: `docker stop <container>`
3. Alert security team immediately
4. Preserve logs: `docker logs <container> > incident.log`
5. Follow incident response playbook

### Recovery Steps:
```bash
# 1. Isolate
docker network disconnect homeserver_frontend compromised-container

# 2. Snapshot
docker commit compromised-container forensics-$(date +%Y%m%d)

# 3. Investigate logs
docker logs compromised-container | grep -i "error\|fail\|attack"

# 4. Restore from backup
./backup/restic-restore.sh --snapshot latest
```

## Module 4: Secure Operations

### Daily Checklist
- [ ] Review security alerts in Slack
- [ ] Check Grafana for anomalies
- [ ] Verify backup completion
- [ ] Review access logs for suspicious activity

### Weekly Tasks
- [ ] Update Docker images (check for security patches)
- [ ] Review failed login attempts
- [ ] Check certificate expiry dates
- [ ] Test alert notifications

### Monthly Tasks
- [ ] Rotate credentials
- [ ] Review user access
- [ ] Update documentation
- [ ] Test backup restoration

## Module 5: Secure Development

### Pre-Commit Checklist
- [ ] No hardcoded secrets
- [ ] Dependencies updated
- [ ] Security headers added
- [ ] Input validation implemented
- [ ] Error messages don't leak info

### Code Review Focus
- Authentication logic
- Authorization checks
- Input sanitization
- Cryptography usage
- Logging sensitive data

### CI/CD Security
- Secrets in environment variables (not code)
- Vulnerability scanning on every PR
- Image signing and verification
- SBOM generation
```

**docs/RUNBOOKS.md:**
```markdown
# Operational Runbooks

## Runbook: Certificate Expiry

**Trigger**: Alert "SSLCertificateExpiringSoon"

**Steps**:
1. Check certificate status:
   ```bash
   openssl x509 -in ssl/server.crt -noout -dates
   ```

2. If using Let's Encrypt:
   ```bash
   docker compose run --rm certbot renew
   docker compose exec nginx nginx -s reload
   ```

3. If using self-signed:
   ```bash
   cd ssl
   ./generate-cert.sh yourdomain.com 365 ecdsa
   docker compose restart n8n
   ```

4. Verify new certificate:
   ```bash
   curl -vI https://yourdomain.com 2>&1 | grep "expire"
   ```

## Runbook: High Failed Login Rate

**Trigger**: Alert "HighFailedLoginRate"

**Steps**:
1. Check Authelia logs:
   ```bash
   docker logs authelia | grep -i "failed\|denied"
   ```

2. Identify source IPs:
   ```bash
   docker logs authelia | grep "authentication failed" | awk '{print $NF}' | sort | uniq -c | sort -rn
   ```

3. Block malicious IPs:
   ```bash
   sudo ufw deny from <IP_ADDRESS>
   ```

4. Review banned users:
   ```bash
   curl http://localhost:9091/api/regulation/banned
   ```

## Runbook: Container Compromised

**Trigger**: Suspicious activity detected

**Steps**:
1. **Immediate containment**:
   ```bash
   docker network disconnect homeserver_frontend <container>
   docker stop <container>
   ```

2. **Preserve evidence**:
   ```bash
   docker commit <container> forensics-$(date +%Y%m%d)
   docker logs <container> > /forensics/logs-$(date +%Y%m%d).txt
   ```

3. **Investigate**:
   - Check Loki logs for anomalies
   - Review file changes
   - Analyze network connections

4. **Remediate**:
   - Remove container: `docker rm <container>`
   - Deploy clean image
   - Restore data from backup if needed
   - Rotate all credentials

5. **Post-incident**:
   - Document timeline
   - Update security controls
   - Share lessons learned
```

**Training exercises (docs/SECURITY_EXERCISES.md):**
```markdown
# Security Training Exercises

## Exercise 1: Breach Simulation
**Objective**: Practice incident response procedures

**Scenario**: Container shows signs of compromise
1. Detect: Review logs for indicators
2. Contain: Isolate the container
3. Investigate: Analyze what happened
4. Remediate: Clean and restore
5. Document: Write post-incident report

## Exercise 2: Backup Restoration
**Objective**: Verify backup procedures work

**Steps**:
1. Stop a non-critical service
2. Delete its data volume
3. Restore from Restic backup
4. Verify service functionality
5. Document any issues

## Exercise 3: Certificate Renewal
**Objective**: Practice certificate management

**Steps**:
1. Generate new self-signed cert
2. Update Traefik/nginx configuration
3. Reload services without downtime
4. Verify HTTPS still working
5. Monitor for errors

## Exercise 4: Penetration Test
**Objective**: Test defenses

**Tools**: nmap, nikto, sqlmap, burp suite

**Tasks**:
1. Port scan from external network
2. Test authentication bypass
3. Try SQL injection (if applicable)
4. Test rate limiting
5. Document findings and remediate
```

## Files to Create
1. `docs/SECURITY_TRAINING.md` - Main training guide
2. `docs/RUNBOOKS.md` - Operational procedures
3. `docs/SECURITY_EXERCISES.md` - Hands-on exercises
4. `docs/SECURE_DEVELOPMENT.md` - Development guidelines

## Success Metrics
- All team members complete training
- Runbooks tested and working
- Incident response time < 30 minutes
- Training materials kept up to date

## References
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SANS Security Training](https://www.sans.org/security-awareness-training/)
