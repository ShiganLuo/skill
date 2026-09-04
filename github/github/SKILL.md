---
name: github
description: "GitHub operations via gh CLI and REST API — auth setup, issues, PR lifecycle, repo management, releases, Actions workflows."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Authentication, Issues, Pull-Requests, Repositories, CI/CD, Git, gh-cli, Releases, Automation]
    related_skills: [code-review]
---

# GitHub Operations

Complete guide for working with GitHub: authentication, issues, pull requests, repository management, releases, and Actions workflows. Each section shows `gh` CLI first, then `git` + `curl` fallback for machines without `gh`.

---

## Part A: Authentication

### Detection Flow

```bash
# Check what's available
git --version
gh --version 2>/dev/null || echo "gh not installed"
gh auth status 2>/dev/null || echo "gh not authenticated"
git config --global credential.helper 2>/dev/null || echo "no git credential helper"
```

**Decision tree:**
1. `gh auth status` shows authenticated → use `gh` for everything
2. `gh` installed but not authenticated → use "gh auth" method
3. `gh` not installed → use "git-only" method (no sudo needed)

### Method 1: Git-Only Authentication (No gh, No sudo)

#### Option A: HTTPS with Personal Access Token (Recommended)

**Step 1: Create token** at https://github.com/settings/tokens
- Scopes: `repo`, `workflow`, `read:org` (if org repos)
- Expiration: 90 days default

**Step 2: Configure credential storage**
```bash
git config --global credential.helper store
# Then trigger auth:
git ls-remote https://github.com/<username>/<any-repo>.git
# Username: <github-username>, Password: <personal-access-token>
```

**Alternative: cache helper (8-hour TTL)**
```bash
git config --global credential.helper 'cache --timeout=28800'
```

**Alternative: embed token in remote URL (per-repo)**
```bash
git remote set-url origin https://<username>:<token>@github.com/<owner>/<repo>.git
```

**Step 3: Configure git identity**
```bash
git config --global user.name "Their Name"
git config --global user.email "their-email@example.com"
```

#### Option B: SSH Key Authentication

```bash
# Check for existing keys
ls -la ~/.ssh/id_*.pub 2>/dev/null || echo "No SSH keys found"

# Generate ed25519 key
ssh-keygen -t ed25519 -C "their-email@example.com" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub  # Add to https://github.com/settings/keys

# Test
ssh -T git@github.com

# Auto-rewrite HTTPS to SSH
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

### Method 2: gh CLI Authentication

```bash
# Interactive browser login
gh auth login  # Select GitHub.com → HTTPS → browser

# Token-based (headless)
echo "<TOKEN>" | gh auth login --with-token
gh auth setup-git

# Verify
gh auth status
```

### Using the GitHub API Without gh

```bash
export GITHUB_TOKEN="<token>"
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Extract token from git credentials
grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|'
```

### Auth Detection Helper (use at start of any GitHub workflow)

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  echo "AUTH_METHOD=gh"
elif [ -n "$GITHUB_TOKEN" ]; then
  echo "AUTH_METHOD=curl"
elif [ -f ~/.hermes/.env ] && grep -q "^GITHUB_TOKEN=" ~/.hermes/.env; then
  export GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\n\r')
  echo "AUTH_METHOD=curl"
elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
  export GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')
  echo "AUTH_METHOD=curl"
else
  echo "AUTH_METHOD=none"
fi
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `git push` asks for password | GitHub disabled password auth. Use PAT as password, or switch to SSH |
| `Permission to X denied` | Token may lack `repo` scope — regenerate with correct scopes |
| `ssh: connect to host github.com port 22` | Add `Host github.com` with `Port 443` and `Hostname ssh.github.com` to `~/.ssh/config` |
| Multiple GitHub accounts | Use SSH with different keys per host alias in `~/.ssh/config` |

---

## Part B: Issues Management

### Quick Auth Setup

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="git"
  # Extract GITHUB_TOKEN from .env or git-credentials (see Part A)
fi
REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

### Viewing Issues

**With gh:**
```bash
gh issue list --state open --label "bug"
gh issue list --assignee @me
gh issue list --search "authentication error" --state all
gh issue view 42
```

**With curl:**
```bash
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?state=open&per_page=20" \
  | python3 -c "
import sys, json
for i in json.load(sys.stdin):
    if 'pull_request' not in i:
        labels = ', '.join(l['name'] for l in i['labels'])
        print(f\"#{i['number']:5}  {i['state']:6}  {labels:30}  {i['title']}\")"
```

### Creating Issues

**With gh:**
```bash
gh issue create \
  --title "Login redirect ignores ?next= parameter" \
  --body "## Description\n..." \
  --label "bug,backend" \
  --assignee "username"
```

**With curl:**
```bash
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues \
  -d '{"title": "...", "body": "...", "labels": ["bug"], "assignees": ["username"]}'
```

### Managing Issues

```bash
# Labels
gh issue edit 42 --add-label "priority:high,bug"
gh issue edit 42 --remove-label "needs-triage"

# Assignment
gh issue edit 42 --add-assignee @me

# Commenting
gh issue comment 42 --body "Root cause identified in auth middleware."

# Close/Reopen
gh issue close 42 --reason "not planned"
gh issue reopen 42

# Create branch from issue
gh issue develop 42 --checkout
```

### Issue Triage Workflow

1. List untriaged: `gh issue list --label "needs-triage" --state open`
2. Read and categorize each issue
3. Apply labels and priority
4. Assign if owner is clear
5. Comment with triage notes if needed

### Bulk Operations

```bash
# Close all with a label
gh issue list --label "wontfix" --json number --jq '.[].number' | \
  xargs -I {} gh issue close {} --reason "not planned"
```

### Quick Reference

| Action | gh | curl endpoint |
|--------|-----|--------------|
| List | `gh issue list` | `GET /repos/{o}/{r}/issues` |
| View | `gh issue view N` | `GET /repos/{o}/{r}/issues/N` |
| Create | `gh issue create ...` | `POST /repos/{o}/{r}/issues` |
| Add labels | `gh issue edit N --add-label ...` | `POST /repos/{o}/{r}/issues/N/labels` |
| Assign | `gh issue edit N --add-assignee ...` | `POST /repos/{o}/{r}/issues/N/assignees` |
| Close | `gh issue close N` | `PATCH /repos/{o}/{r}/issues/N` |

---

## Part C: Pull Request Workflow

### 1. Branch Creation

```bash
git fetch origin
git checkout main && git pull origin main
git checkout -b feat/add-user-authentication
```

Branch naming: `feat/`, `fix/`, `refactor/`, `docs/`, `ci/`

### 2. Making Commits

```bash
git add src/auth.py src/models/user.py tests/test_auth.py
git commit -m "feat: add JWT-based user authentication"
```

See `references/conventional-commits.md` for commit message format.

### 3. Pushing and Creating a PR

**With gh:**
```bash
gh pr create --title "feat: add JWT-based user authentication" \
  --body "## Summary\n...\nCloses #42" \
  --draft --reviewer user1,user2 --label "enhancement"
```

**With curl:**
```bash
BRANCH=$(git branch --show-current)
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls \
  -d "{\"title\": \"...\", \"body\": \"...\", \"head\": \"$BRANCH\", \"base\": \"main\"}"
```

### 4. Monitoring CI Status

**With gh:**
```bash
gh pr checks
gh pr checks --watch  # Polls until done
```

**With curl:**
```bash
SHA=$(git rev-parse HEAD)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/check-runs
```

### 5. Auto-Fixing CI Failures

```bash
# Get failure details
gh run list --branch $(git branch --show-current) --limit 5
gh run view <RUN_ID> --log-failed

# Fix → commit → push → re-check
git add . && git commit -m "fix: resolve CI failure" && git push
```

Auto-fix loop (up to 3 attempts):
1. Check CI status → identify failures
2. Read failure logs → understand error
3. Fix code with `patch`/`write_file`
4. Commit and push
5. Wait for CI → re-check
6. Repeat if still failing

### 6. Merging

**With gh:**
```bash
gh pr merge --squash --delete-branch
gh pr merge --auto --squash --delete-branch  # Auto-merge when green
```

**With curl:**
```bash
curl -s -X PUT -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER/merge \
  -d '{"merge_method": "squash"}'
```

### PR Reference

| Action | gh | curl |
|--------|-----|------|
| List my PRs | `gh pr list --author @me` | `GET /repos/{o}/{r}/pulls?state=open` |
| View diff | `gh pr diff` | `git diff main...HEAD` |
| Request review | `gh pr edit N --add-reviewer user` | `POST .../pulls/N/requested_reviewers` |
| Check out PR | `gh pr checkout N` | `git fetch origin pull/N/head:pr-N && git checkout pr-N` |

---

## Part D: Repository Management

### Cloning

```bash
git clone https://github.com/owner/repo-name.git
git clone --depth 1 https://github.com/owner/repo-name.git  # Shallow
gh repo clone owner/repo-name
```

### Creating Repositories

**With gh:**
```bash
gh repo create my-new-project --public --clone
gh repo create my-new-project --private --description "A useful tool" --license MIT
gh repo create my-project --source . --public --push  # From existing dir
gh repo create my-new-app --template owner/template-repo --public --clone
```

**With curl:**
```bash
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos \
  -d '{"name": "my-new-project", "private": false, "auto_init": true, "license_template": "mit"}'
```

### Forking

```bash
gh repo fork owner/repo-name --clone
# Keep fork in sync:
gh repo sync $GH_USER/repo-name
```

### Repository Settings

```bash
gh repo edit --description "Updated" --visibility public
gh repo edit --enable-wiki=false --enable-issues=true
gh repo edit --add-topic "machine-learning,python"
gh repo edit --enable-auto-merge
```

### Branch Protection

```bash
curl -s -X PUT -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/branches/main/protection \
  -d '{
    "required_status_checks": {"strict": true, "contexts": ["ci/test"]},
    "required_pull_request_reviews": {"required_approving_review_count": 1}
  }'
```

### Secrets Management (GitHub Actions)

```bash
gh secret set API_KEY --body "your-secret-value"
gh secret list
gh secret delete API_KEY
```

### Releases

```bash
gh release create v1.0.0 --title "v1.0.0" --generate-notes
gh release create v2.0.0-rc1 --draft --prerelease --generate-notes
gh release create v1.0.0 ./dist/binary --notes "Release notes"
gh release list
gh release download v1.0.0 --dir ./downloads
```

### GitHub Actions Workflows

```bash
gh workflow list
gh run list --limit 10
gh run view <RUN_ID> --log-failed
gh run rerun <RUN_ID> --failed
gh workflow run ci.yml --ref main
gh workflow run deploy.yml -f environment=staging
```

### Gists

```bash
gh gist create script.py --public --desc "Useful script"
gh gist list
```

### Repo Management Reference

| Action | gh | curl |
|--------|-----|------|
| Clone | `gh repo clone o/r` | `git clone https://github.com/o/r.git` |
| Create | `gh repo create name --public` | `POST /user/repos` |
| Fork | `gh repo fork o/r --clone` | `POST /repos/o/r/forks` |
| Info | `gh repo view o/r` | `GET /repos/o/r` |
| Release | `gh release create v1.0` | `POST /repos/o/r/releases` |
| Workflows | `gh workflow list` | `GET /repos/o/r/actions/workflows` |
| Secrets | `gh secret set KEY` | `PUT /repos/o/r/actions/secrets/KEY` |
