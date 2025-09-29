# GitHub Branch Protection Rules Setup

This document provides step-by-step instructions for setting up branch protection rules for this repository.

## Prerequisites

- Repository admin access
- GitHub web interface access
- The repository should have the GitHub Actions workflow already set up

## Setting Up Branch Protection Rules

### 1. Navigate to Branch Protection Settings

1. Go to your repository on GitHub
2. Click on **Settings** tab
3. In the left sidebar, click on **Branches**
4. Click **Add rule** or **Add branch protection rule**

### 2. Configure the Main Branch Protection

Enter the following settings:

#### Branch Name Pattern
```
main
```

#### Protection Settings

**✅ Require a pull request before merging**
- ✅ Require approvals: `1`
- ✅ Dismiss stale reviews when new commits are pushed
- ✅ Require review from code owners (optional - if you have a CODEOWNERS file)

**✅ Require status checks to pass before merging**
- ✅ Require branches to be up to date before merging
- Required status checks (add these):
  - `validate-docker-compose`
  - `lint-yaml`

**✅ Require conversation resolution before merging**

**✅ Require signed commits** (optional but recommended)

**✅ Require linear history** (optional - prevents merge commits)

**✅ Include administrators**
- This ensures even admins follow the rules

**❌ Allow force pushes** (keep disabled for security)

**❌ Allow deletions** (keep disabled to prevent accidental deletion)

### 3. Save the Protection Rule

Click **Create** to save the branch protection rule.

## Additional Repository Settings

### General Settings

1. Go to **Settings** → **General**
2. Under **Pull Requests**:
   - ✅ Allow squash merging (recommended)
   - ✅ Allow merge commits (for releases)
   - ✅ Allow rebase merging (for clean commits)
   - ✅ Always suggest updating pull request branches
   - ✅ Allow auto-merge
   - ✅ Automatically delete head branches

### Actions Settings

1. Go to **Settings** → **Actions** → **General**
2. Under **Actions permissions**:
   - Select "Allow all actions and reusable workflows"
3. Under **Workflow permissions**:
   - Select "Read repository contents and packages permissions"

## Verifying the Setup

### Test the Protection Rules

1. Create a test branch:
   ```bash
   git checkout -b test/branch-protection
   ```

2. Make a small change and push:
   ```bash
   echo "# Test" >> test.md
   git add test.md
   git commit -m "Test branch protection"
   git push origin test/branch-protection
   ```

3. Try to merge directly to main (this should fail):
   ```bash
   git checkout main
   git merge test/branch-protection  # This should be blocked
   ```

4. Create a pull request instead and verify:
   - GitHub Actions run automatically
   - Review is required before merging
   - Status checks must pass

### Expected Behavior

With proper setup, you should see:

- ❌ Direct pushes to `main` are blocked
- ✅ Pull requests are required for all changes
- ✅ GitHub Actions run on every PR
- ✅ At least one review is required
- ✅ Status checks must pass before merging

## Troubleshooting

### Status Checks Not Appearing

If the required status checks don't appear in the dropdown:

1. Create a pull request first to trigger the GitHub Actions
2. Wait for the actions to run
3. Go back to branch protection settings
4. The status check names should now appear in the dropdown

### Actions Not Running

If GitHub Actions aren't running:

1. Check **Settings** → **Actions** → **General**
2. Ensure actions are enabled for the repository
3. Verify the workflow file syntax with `docker compose config`

### Review Requirements Not Working

If reviews aren't being required:

1. Verify "Include administrators" is checked
2. Make sure you're not the only collaborator
3. Consider adding specific reviewers or teams

## Maintenance

### Regular Updates

- Review and update status check requirements as new checks are added
- Monitor for any security alerts or recommendations from GitHub
- Periodically review who has admin access to the repository

### Adding New Status Checks

When adding new GitHub Actions workflows:

1. Let the new action run on a few PRs
2. Go to branch protection settings
3. Add the new status check to the required list
4. Update this document with the new requirement

## Security Considerations

- Never disable "Include administrators" unless absolutely necessary
- Regularly review who has write/admin access to the repository
- Consider enabling "Require signed commits" for additional security
- Monitor dependency alerts and update Docker images regularly

## Need Help?

If you encounter issues setting up branch protection:

1. Check GitHub's [official documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches)
2. Create an issue in this repository
3. Contact the repository maintainers