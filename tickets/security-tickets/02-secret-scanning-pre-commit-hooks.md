# Implement Secret Scanning Pre-Commit Hooks

## Priority: 1 (Critical)
## Estimated Time: 2-3 hours
## Phase: Week 1 - Critical Fixes

## Description
Implement automated secret scanning using pre-commit hooks to prevent accidental commits of sensitive information like passwords, API keys, tokens, and private keys. This creates a critical defense layer against credential leakage.

## Acceptance Criteria
- [ ] Pre-commit framework installed and configured
- [ ] detect-secrets or gitleaks integrated
- [ ] Hooks prevent commits containing secrets
- [ ] Baseline file created for existing false positives
- [ ] CI/CD validation added to catch bypassed hooks
- [ ] Documentation updated with developer workflow
- [ ] Team notified of new requirements

## Technical Implementation Details

### Files to Create/Modify
1. `.pre-commit-config.yaml` - Pre-commit hook configuration (new file)
2. `.secrets.baseline` - Baseline for existing false positives (new file)
3. `.github/workflows/secret-scan.yml` - CI/CD secret scanning (new file)
4. `CONTRIBUTING.md` - Update with pre-commit setup instructions
5. `.gitignore` - Add pre-commit cache directories

### Option 1: Using detect-secrets (Recommended)

#### Install Pre-commit Framework
```bash
# Install pre-commit (one-time setup per developer)
pip install pre-commit

# Or using homebrew on macOS
brew install pre-commit
```

#### Create `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
        args: ['--unsafe']  # Allow custom YAML tags
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: detect-private-key
      - id: check-merge-conflict

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: .*/package-lock\.json|.*\.lock

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.1
    hooks:
      - id: gitleaks
```

#### Create Initial Baseline
```bash
# Generate baseline for existing repository
pip install detect-secrets
detect-secrets scan --baseline .secrets.baseline

# Review and audit the baseline
detect-secrets audit .secrets.baseline
```

#### Custom `.gitleaks.toml` Configuration
```toml
title = "Home Server Stack Gitleaks Configuration"

[extend]
useDefault = true

[[rules]]
id = "env-file-password"
description = "Detects passwords in .env files"
regex = '''(?i)(password|passwd|pwd|secret|token|api_key|apikey)\s*=\s*[^\s#]+'''
path = '''\.env$'''

[[rules]]
id = "docker-compose-secrets"
description = "Detects hardcoded secrets in docker-compose files"
regex = '''(?i)(password|secret|token|key):\s*[^\s$\{][^\s#]+'''
path = '''docker-compose.*\.ya?ml$'''

[allowlist]
description = "Allowlist for false positives"
paths = [
  '''.secrets.baseline''',
  '''.pre-commit-config.yaml''',
]

regexes = [
  '''your_secure_password_here''',  # Example placeholder
  '''your_secure_grafana_password''', # Example placeholder
]
```

### Option 2: Using Gitleaks (Standalone)

#### Create `.github/workflows/secret-scan.yml`
```yaml
name: Secret Scanning

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for comprehensive scan

      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}  # Optional for pro features

  detect-secrets:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install detect-secrets
        run: pip install detect-secrets

      - name: Run detect-secrets
        run: |
          detect-secrets scan --baseline .secrets.baseline
          detect-secrets audit --report .secrets.baseline

      - name: Verify no new secrets
        run: |
          # Scan current state
          detect-secrets scan --baseline .secrets.baseline.new
          # Compare with existing baseline
          diff .secrets.baseline .secrets.baseline.new || \
            (echo "New secrets detected! Run 'detect-secrets scan --baseline .secrets.baseline' and audit." && exit 1)
```

### Setup and Installation Steps

#### 1. Install Pre-commit Hooks
```bash
# Navigate to repository
cd /path/to/home-server-stack

# Install pre-commit framework
pip install pre-commit

# Install the git hooks
pre-commit install

# (Optional) Run against all files to test
pre-commit run --all-files
```

#### 2. Create Baseline for Existing Files
```bash
# Install detect-secrets
pip install detect-secrets

# Create baseline
detect-secrets scan --baseline .secrets.baseline

# Audit baseline to mark false positives
detect-secrets audit .secrets.baseline
# Use 'y' to mark as real secret, 'n' for false positive, 's' to skip
```

#### 3. Update .gitignore
```bash
# Add to .gitignore
echo "" >> .gitignore
echo "# Pre-commit cache" >> .gitignore
echo ".pre-commit-cache/" >> .gitignore
```

### Testing Commands
```bash
# Test pre-commit hooks
pre-commit run --all-files

# Test with a dummy secret (should fail)
echo "API_KEY=sk-1234567890abcdef" >> test.txt
git add test.txt
git commit -m "Test commit"  # Should be blocked
rm test.txt

# Update baseline after legitimate changes
detect-secrets scan --baseline .secrets.baseline

# Test CI/CD workflow locally (if using act)
act -j gitleaks
```

### Developer Workflow Documentation

Add to `CONTRIBUTING.md`:
```markdown
## Secret Scanning Setup

This repository uses pre-commit hooks to prevent accidental commits of secrets.

### First-Time Setup
1. Install pre-commit:
   ```bash
   pip install pre-commit
   # or
   brew install pre-commit
   ```

2. Install the hooks:
   ```bash
   pre-commit install
   ```

### Daily Usage
Pre-commit hooks will automatically run when you commit. If secrets are detected:

1. **Review the finding**: Determine if it's a real secret or false positive
2. **If real secret**: Remove it and use environment variables instead
3. **If false positive**: Update `.secrets.baseline`:
   ```bash
   detect-secrets scan --baseline .secrets.baseline
   detect-secrets audit .secrets.baseline
   ```

### Bypassing Hooks (Emergency Only)
```bash
# ONLY use in emergencies, CI will still catch secrets
git commit --no-verify -m "Emergency commit"
```
```

## Success Metrics
- Pre-commit hooks block commits containing secrets (tested)
- CI/CD pipeline fails on secret detection
- Zero secrets in `.env.example` beyond placeholders
- All team members have pre-commit installed
- Baseline contains only legitimate false positives
- No hardcoded credentials in codebase

## Dependencies
- Git repository
- Python 3.8+ (for detect-secrets)
- Pre-commit framework
- GitHub Actions (for CI/CD validation)

## Risk Considerations
- **False Positives**: May block legitimate strings (mitigated by baseline)
- **Bypass Risk**: Developers can use `--no-verify` (mitigated by CI/CD)
- **Performance**: Pre-commit adds 2-5 seconds to commit time
- **Onboarding**: Requires team training and setup time

## Rollback Plan
```bash
# Remove pre-commit hooks
pre-commit uninstall

# Delete configuration files
rm .pre-commit-config.yaml .secrets.baseline

# Remove from CI/CD
git rm .github/workflows/secret-scan.yml
```

## Security Impact
- **Before**: No automated detection of committed secrets
- **After**: Automated scanning at commit time and in CI/CD
- **Risk Reduction**: 90% reduction in accidental secret commits

## Common Secret Patterns Detected
- AWS Access Keys: `AKIA[0-9A-Z]{16}`
- Generic API Keys: `api_key\s*=\s*['\"][a-zA-Z0-9]{32,}['\"]`
- Private SSH Keys: `-----BEGIN.*PRIVATE KEY-----`
- JWT Tokens: `eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*`
- Passwords in configs: `password\s*:\s*[^\s$][^\s]+`
- Database URLs: `(postgres|mysql|mongodb)://[^@]+:[^@]+@`

## References
- [detect-secrets Documentation](https://github.com/Yelp/detect-secrets)
- [Gitleaks Documentation](https://github.com/gitleaks/gitleaks)
- [Pre-commit Framework](https://pre-commit.com/)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)

## Follow-up Tasks
- Enable GitHub secret scanning (Settings > Security > Secret scanning)
- Schedule quarterly secret audits
- Train team on secure credential management
- Consider implementing HashiCorp Vault for production
- Set up secret rotation policies
