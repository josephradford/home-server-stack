---
name: bede-deploy
description: >
  Commit, PR, merge, wait for GHCR build, and deploy Bede changes to the
  server. Use whenever changes have been made in the bede repo and need to
  be shipped — including "deploy bede", "ship the bot changes", "push bede
  to the server", or any request to get bede repo code onto production.
---

# Bede Deploy Skill

End-to-end deployment of bede repo changes to the home server.

Read CLAUDE.local.md to find the bede repo path. The GitHub remote is
referenced in the repo's git config. The server deploys from GHCR images
built by GitHub Actions on merge to main.

## Prerequisites

- Read CLAUDE.local.md for the bede repo path (referred to as `BEDE_REPO`
  below)
- Read `.claude/server-test.local` in the home-server-stack project root to
  get `SERVER_USER` and `SERVER_HOST`. If missing, tell the user to create it
  from the template.
- Determine the GitHub owner/repo from the bede repo's git remote:
  ```bash
  git -C $BEDE_REPO remote get-url origin
  ```

## Step 1 — Check bede repo state

```bash
git -C $BEDE_REPO status
git -C $BEDE_REPO log --oneline -5
git -C $BEDE_REPO diff --stat
```

Determine the current situation:
- **On main, no changes:** nothing to deploy — tell the user.
- **On main, uncommitted changes:** create a feature branch, then commit.
- **On a feature branch, uncommitted changes:** commit to the current branch.
- **On a feature branch, clean:** check if there's already a PR open for it.

## Step 2 — Commit (if needed)

Stage and commit the changes. Follow the repo's commit style (conventional
commits: `feat:`, `fix:`, `docs:`).

## Step 3 — Push and create PR

```bash
git -C $BEDE_REPO push -u origin <branch>
```

Check for an existing PR first:
```bash
gh pr list --repo <owner/repo> --head <branch>
```

If a PR already exists, show it and ask if the user wants to update it or
merge it. If no PR exists, create one:
```bash
gh pr create --repo <owner/repo> --title "<title>" --body "<body>"
```

## Step 4 — Merge the PR

Ask the user for confirmation before merging. Then:
```bash
gh pr merge <number> --repo <owner/repo> --squash --delete-branch
```

## Step 5 — Wait for GHCR image build

Use `gh run watch` which blocks until the run completes:
```bash
gh run watch --repo <owner/repo> $(gh run list --repo <owner/repo> --limit 1 --json databaseId --jq '.[0].databaseId')
```

If the build fails, show the logs and stop.

## Step 6 — Deploy to server

```bash
ssh ${SERVER_USER}@${SERVER_HOST} "cd ~/home-server-stack && make bede-pull && make bede-restart"
```

## Step 7 — Verify

```bash
ssh ${SERVER_USER}@${SERVER_HOST} "cd ~/home-server-stack && make bede-status"
```

Confirm Bede is running and the container was created within the last few
minutes (indicating the new image was pulled).

Report the full pipeline result: commit SHA, PR number, build status,
container status.
