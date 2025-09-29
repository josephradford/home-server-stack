# Contributing to Home Server Stack

Thank you for your interest in contributing to the Home Server Stack project! This document provides guidelines for contributing to this repository.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a new branch for your changes
4. Make your changes and test them
5. Submit a pull request

## Development Workflow

### Branch Naming Conventions

Use descriptive branch names that follow these patterns:

- **Features**: `feature/add-service-name` or `feat/improve-documentation`
- **Bug fixes**: `fix/adguard-dns-issue` or `bugfix/docker-compose-error`
- **Hotfixes**: `hotfix/security-update`
- **Documentation**: `docs/update-readme` or `doc/add-troubleshooting`
- **Infrastructure**: `infra/github-actions` or `devops/monitoring`

### Branching Strategy

We follow **GitHub Flow** for this repository:

1. **Main Branch**: `main` contains production-ready code
   - Always deployable
   - Protected with branch protection rules
   - Requires pull request reviews

2. **Feature Branches**: Create from `main` for new work
   - Keep focused on a single feature or fix
   - Use descriptive names
   - Regularly sync with `main` to avoid conflicts

3. **Pull Requests**: All changes must go through pull requests
   - Use the provided PR template
   - Ensure all checks pass
   - Require at least one review

### Making Changes

#### Before You Start

1. **Check existing issues**: Look for existing issues or discussions about your proposed change
2. **Create an issue**: For new features or significant changes, create an issue first to discuss the approach
3. **Test locally**: Ensure your changes work in your local environment

#### Development Guidelines

1. **Docker Compose Changes**:
   - Test all services start successfully: `docker compose up -d`
   - Verify services are accessible at expected ports
   - Check logs for errors: `docker compose logs`

2. **Configuration Changes**:
   - Update `.env.example` if new environment variables are added
   - Document any new configuration options in README.md
   - Ensure backwards compatibility when possible

3. **Documentation**:
   - Update README.md for user-facing changes
   - Add comments to complex configuration sections
   - Include troubleshooting steps for common issues

#### Security Guidelines

- **Never commit secrets**: No passwords, API keys, or sensitive data
- **Use environment variables**: All secrets should be in `.env` files
- **Review dependencies**: Ensure Docker images are from trusted sources
- **Document security implications**: Note any security considerations in your PR

### Testing Your Changes

#### Required Testing

Before submitting a PR, ensure:

1. **Docker Compose Validation**:
   ```bash
   docker compose config --quiet
   docker compose pull
   docker compose up -d
   ```

2. **Service Accessibility**:
   - AdGuard Home: `http://localhost:3000` (setup) then `http://localhost:80`
   - n8n: `https://localhost:5678`
   - Ollama: `http://localhost:11434`

3. **Environment Configuration**:
   - Copy `.env.example` to `.env`
   - Update variables as needed
   - Verify all required variables are present

4. **Clean Shutdown**:
   ```bash
   docker compose down
   ```

#### Automated Testing

Our GitHub Actions will automatically:
- Validate Docker Compose syntax
- Check for security issues
- Lint YAML files
- Verify environment variables

### Pull Request Process

#### Creating a Pull Request

1. **Use the PR template**: Fill out all relevant sections
2. **Write a clear title**: Summarize the change in the title
3. **Describe your changes**: Explain what you changed and why
4. **Link related issues**: Reference any related issues or discussions
5. **Request reviews**: Tag relevant maintainers for review

#### PR Requirements

- [ ] All GitHub Actions checks pass
- [ ] At least one approving review
- [ ] Up-to-date with `main` branch
- [ ] Clear, descriptive commit messages
- [ ] Documentation updated (if needed)

#### Merge Strategy

- **Squash and merge**: Default for feature branches (keeps history clean)
- **Create merge commit**: For release branches (preserves branch history)
- **Rebase and merge**: For small, well-crafted commits

## Code Review Guidelines

### For Authors

- **Keep PRs focused**: One feature or fix per PR
- **Write clear descriptions**: Explain the "why" not just the "what"
- **Respond to feedback**: Address reviewer comments promptly
- **Test thoroughly**: Ensure changes work as expected

### For Reviewers

- **Be constructive**: Provide specific, actionable feedback
- **Check functionality**: Verify changes work as described
- **Review security**: Look for potential security issues
- **Validate documentation**: Ensure docs are updated appropriately

### Review Checklist

- [ ] Code follows project conventions
- [ ] No hardcoded secrets or sensitive data
- [ ] Documentation is updated
- [ ] Changes are tested
- [ ] Backwards compatibility considered
- [ ] Security implications reviewed

## Environment Setup

### Prerequisites

- Docker and Docker Compose
- Git
- Text editor or IDE
- Basic understanding of containerization

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/josephradford/home-server-stack.git
   cd home-server-stack
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

3. **Start services**:
   ```bash
   docker compose up -d
   ```

## Getting Help

- **Issues**: Create a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and general discussion
- **Documentation**: Check the README.md for setup and usage information

## Release Process

Releases are managed by maintainers and follow semantic versioning:

- **Major**: Breaking changes
- **Minor**: New features (backwards compatible)
- **Patch**: Bug fixes (backwards compatible)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Maintain a positive community environment

## Questions?

If you have questions about contributing, please:
1. Check existing documentation
2. Search closed issues and discussions
3. Create a new issue with the "question" label
4. Tag maintainers if urgent

Thank you for contributing to the Home Server Stack project!