#!/usr/bin/env bash
# Deploy home-server-stack to remote server via SSH
# Usage: ./scripts/deploy-to-server.sh [server-user@server-host] [optional-git-branch]

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVER="${1:-}"
BRANCH="${2:-main}"
REMOTE_PATH="${REMOTE_PATH:-~/home-server-stack}"

# Show usage if no server specified
if [ -z "$SERVER" ]; then
    echo -e "${RED}Error: Server address required${NC}"
    echo ""
    echo "Usage: $0 <user@server> [branch]"
    echo ""
    echo "Examples:"
    echo "  $0 joe@192.168.1.100"
    echo "  $0 joe@homeserver.local main"
    echo "  REMOTE_PATH=/opt/home-server $0 joe@server feature/new-service"
    echo ""
    echo "Environment variables:"
    echo "  REMOTE_PATH - Remote directory path (default: ~/home-server-stack)"
    exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Home Server Stack - Remote Deployment               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  Server:       ${GREEN}$SERVER${NC}"
echo -e "  Remote path:  ${GREEN}$REMOTE_PATH${NC}"
echo -e "  Branch:       ${GREEN}$BRANCH${NC}"
echo ""

# Step 1: Check local git status
echo -e "${BLUE}[1/6]${NC} Checking local git status..."
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}Warning: You have uncommitted changes${NC}"
    echo "Uncommitted files:"
    git status --short
    echo ""
    read -p "Continue deployment anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Deployment cancelled${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Local git status checked${NC}"
echo ""

# Step 2: Push to remote repository
echo -e "${BLUE}[2/6]${NC} Pushing to git repository..."
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "$BRANCH" ]; then
    git push origin "$BRANCH"
    echo -e "${GREEN}✓ Pushed branch '$BRANCH' to origin${NC}"
else
    echo -e "${YELLOW}Warning: Current branch ($CURRENT_BRANCH) != target branch ($BRANCH)${NC}"
    echo "You're deploying branch '$BRANCH' but you're on '$CURRENT_BRANCH'"
    read -p "Continue? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Deployment cancelled${NC}"
        exit 1
    fi
fi
echo ""

# Step 3: Connect to server and pull changes
echo -e "${BLUE}[3/6]${NC} Connecting to server and pulling changes..."
ssh "$SERVER" bash -c "'
set -e
cd $REMOTE_PATH || exit 1

echo \"Current directory: \$(pwd)\"
echo \"Fetching latest changes...\"
git fetch origin

echo \"Checking out branch: $BRANCH\"
git checkout $BRANCH

echo \"Pulling changes...\"
git pull origin $BRANCH

echo \"Current commit: \$(git log -1 --oneline)\"
'"
echo -e "${GREEN}✓ Changes pulled on server${NC}"
echo ""

# Step 4: Validate configuration
echo -e "${BLUE}[4/6]${NC} Validating docker-compose configuration on server..."
ssh "$SERVER" bash -c "'
set -e
cd $REMOTE_PATH || exit 1

if [ ! -f .env ]; then
    echo \"ERROR: .env file not found on server\"
    echo \"Please create .env from .env.example and configure it\"
    exit 1
fi

make validate
'"
echo -e "${GREEN}✓ Configuration validated${NC}"
echo ""

# Step 5: Pull updated images
echo -e "${BLUE}[5/6]${NC} Pulling updated Docker images on server..."
ssh "$SERVER" bash -c "'
set -e
cd $REMOTE_PATH || exit 1
make pull
'"
echo -e "${GREEN}✓ Images updated${NC}"
echo ""

# Step 6: Restart services
echo -e "${BLUE}[6/6]${NC} Restarting services on server..."
ssh "$SERVER" bash -c "'
set -e
cd $REMOTE_PATH || exit 1
make restart
echo \"\"
echo \"Waiting 5 seconds for services to stabilize...\"
sleep 5
echo \"\"
echo \"Service status:\"
make status
'"
echo -e "${GREEN}✓ Services restarted${NC}"
echo ""

# Show deployment summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            Deployment Complete! ✓                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "View logs: ${YELLOW}ssh $SERVER 'cd $REMOTE_PATH && make logs'${NC}"
echo -e "Check status: ${YELLOW}ssh $SERVER 'cd $REMOTE_PATH && make status'${NC}"
echo ""
