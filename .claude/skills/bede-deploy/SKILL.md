---
name: bede-deploy
description: >
  Commit, PR, merge, wait for GHCR build, and deploy Bede changes to the
  server. Use when changes have been made in the bede repo and need to be
  shipped.
---

# Bede Deploy Skill

End-to-end deployment of bede repo changes to the home server.

## Prerequisites

Read `.claude/server-test.local` in the home-server-stack project root to get
`SERVER_USER` and `SERVER_HOST`. If missing, tell the user to create it from
the template.

## Step 1 — Check bede repo state

```bash
git -C /Users/joeradford/dev/bede status
git -C /Users/joeradford/dev/bede log --oneline -5
git -C /Users/joeradford/dev/bede diff --stat
```

If there are uncommitted changes, ask the user if they want to commit them.
If there are no changes and HEAD is already on main with nothing ahead of
origin, tell the user there's nothing to deploy.

## Step 2 — Create branch and commit (if needed)

If on `main` with uncommitted changes, create a feature branch:
```bash
git -C /Users/joeradford/dev/bede checkout -b feat/<descriptive-name>
```

Stage and commit the changes. Follow the repo's commit style.

## Step 3 — Push and create PR

```bash
git -C /Users/joeradford/dev/bede push -u origin <branch>
```

Create a PR using `gh pr create --repo josephradford/bede`. Include a summary
of what changed and a test plan.

## Step 4 — Merge the PR

Ask the user for confirmation before merging. Then:
```bash
gh pr merge <number> --repo josephradford/bede --squash --delete-branch
```

## Step 5 — Wait for GHCR image build

Check the GitHub Actions build status:
```bash
gh run list --repo josephradford/bede --limit 1 --json status,conclusion,headSha
```

Poll every 30 seconds until the build completes. If it fails, show the logs
and stop.

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
