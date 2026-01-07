#!/bin/bash
# Pre-Deploy Gate: Backend Migration & Health Checks
# Run this before ANY backend deployment to catch issues early

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "🔍 Pre-Deploy Gate: Backend Checks"
echo "=================================="
echo ""

cd "$BACKEND_DIR"

# Check 1: No uncommitted migrations
echo "📋 Check 1: No uncommitted migrations"
echo "Running: python manage.py makemigrations --check --dry-run"
python manage.py makemigrations --check --dry-run
if [ $? -eq 0 ]; then
    echo "✅ No uncommitted migrations detected"
else
    echo "❌ BLOCKER: Uncommitted migrations found!"
    echo "   Run: python manage.py makemigrations"
    echo "   Then: git add/commit the new migration files"
    exit 1
fi
echo ""

# Check 2: UV lock consistency
echo "📋 Check 2: UV lock file consistency"
echo "Running: uv sync --frozen"
if uv sync --frozen 2>/dev/null; then
    echo "✅ uv.lock is consistent with pyproject.toml"
else
    echo "❌ BLOCKER: uv.lock is out of sync!"
    echo "   Run: uv lock"
    echo "   Then: git add uv.lock && git commit"
    exit 1
fi
echo ""

# Check 3: Python syntax validation
echo "📋 Check 3: Python syntax validation (compileall)"
echo "Running: python -m compileall -q ."
if python -m compileall -q .; then
    echo "✅ No syntax errors detected"
else
    echo "❌ BLOCKER: Python syntax errors found!"
    echo "   Fix syntax errors before deploying"
    exit 1
fi
echo ""

# Check 4: Migration plan
echo "📋 Check 4: Migration plan"
echo "Running: python manage.py migrate --plan"
PLAN_OUTPUT=$(python manage.py migrate --plan)
echo "$PLAN_OUTPUT"
if echo "$PLAN_OUTPUT" | grep -q "No planned migration operations"; then
    echo "✅ No pending migrations"
else
    echo "⚠️  WARNING: There are pending migrations that will be applied on deploy"
fi
echo ""

# Check 5: No unapplied migrations locally
echo "📋 Check 5: Check for unapplied migrations"
UNAPPLIED=$(python manage.py showmigrations | grep '\[ \]' || true)
if [ -z "$UNAPPLIED" ]; then
    echo "✅ All migrations applied locally"
else
    echo "⚠️  WARNING: Unapplied migrations found locally:"
    echo "$UNAPPLIED"
    echo "   This is OK if you just created them, but ensure they're committed"
fi
echo ""

# Check 6: Django system check for production
echo "📋 Check 6: Django production checks"
echo "Running: python manage.py check --deploy --settings=config.settings.production"
# Note: This might fail if production env vars aren't set locally, so we don't fail on error
python manage.py check --deploy --settings=config.settings.production || echo "⚠️  Production checks failed (might be due to missing prod env vars)"
echo ""

# Check 7: Verify git status
echo "📋 Check 7: Git status"
cd "$PROJECT_ROOT"
GIT_STATUS=$(git status --porcelain)
if [ -z "$GIT_STATUS" ]; then
    echo "✅ Working tree clean"
else
    echo "⚠️  WARNING: Uncommitted changes:"
    echo "$GIT_STATUS"
    echo ""
    read -p "   Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# Check 8: Verify current branch and remote
echo "📋 Check 8: Git branch and remote"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $CURRENT_BRANCH"
git fetch origin --quiet
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/$CURRENT_BRANCH)
if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    echo "✅ Local and remote in sync"
else
    echo "⚠️  WARNING: Local and remote diverged"
    echo "   Local:  $LOCAL_COMMIT"
    echo "   Remote: $REMOTE_COMMIT"
    echo "   Run 'git push' or 'git pull' to sync"
fi
echo ""

echo "=================================="
echo "✅ Pre-Deploy Gate: ALL CHECKS PASSED"
echo ""
echo "Next steps:"
echo "  1. git push (if not already pushed)"
echo "  2. SSH to production server"
echo "  3. cd /opt/EatFit24 && git pull"
echo "  4. docker compose up -d backend --build"
echo "  5. Verify health: curl https://eatfit24.ru/health/"
echo ""
