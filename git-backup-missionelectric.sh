#!/bin/bash
# git-backup-missionelectric.sh
# Daily backup of Mission Electric infra configs and site content to GitHub.
# Runs as matt via cron, 3:00 AM daily.
# Only commits/pushes if something actually changed. Logs all activity.
# Fails fast: if any source copy fails, the run stops before touching git.

set -uo pipefail

LOG_FILE="/var/log/git-backup-missionelectric.log"
INFRA_REPO="/home/matt/missionelectric-infra"
CONTENT_REPO="/home/matt/missionelectric-content"
WEB_ROOT="/var/www/missionelectric"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

fail() {
    log "FATAL: $1 — aborting run, no commit made"
    exit 1
}

log "=== Backup run started ==="

# --- INFRA REPO ---

sudo /usr/bin/cp /etc/nginx/sites-available/missionelectric "$INFRA_REPO/missionelectric" 2>>"$LOG_FILE" || fail "could not copy nginx site config"
sudo /usr/bin/cp /etc/nginx/nginx.conf "$INFRA_REPO/nginx.conf" 2>>"$LOG_FILE" || fail "could not copy nginx.conf"
cp /etc/cloudflared/config.yml "$INFRA_REPO/cloudflared-config.yml" 2>>"$LOG_FILE" || fail "could not copy cloudflared config"
cp /home/matt/scripts/fetch-reviews-count.py "$INFRA_REPO/fetch-reviews-count.py" 2>>"$LOG_FILE" || fail "could not copy fetch-reviews-count.py"
cp /home/matt/scripts/fetch-reviews-list.py "$INFRA_REPO/fetch-reviews-list.py" 2>>"$LOG_FILE" || fail "could not copy fetch-reviews-list.py"

crontab -l > "$INFRA_REPO/crontab.txt" 2>>"$LOG_FILE" || fail "could not read crontab"

N8N_IMAGE=$(sudo /usr/bin/docker inspect n8n --format '{{.Config.Image}}' 2>>"$LOG_FILE") || fail "docker inspect (image) failed"
N8N_ENV=$(sudo /usr/bin/docker inspect n8n --format '{{range .Config.Env}}{{.}} {{end}}' 2>>"$LOG_FILE") || fail "docker inspect (env) failed"
N8N_PORTS=$(sudo /usr/bin/docker inspect n8n --format '{{.NetworkSettings.Ports}}' 2>>"$LOG_FILE") || fail "docker inspect (ports) failed"

{
    echo "Image: $N8N_IMAGE"
    echo "Env: $N8N_ENV"
    echo "Ports: $N8N_PORTS"
} > "$INFRA_REPO/n8n-docker.txt"

cd "$INFRA_REPO" || fail "could not cd to $INFRA_REPO"

if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "Automated daily backup $(date '+%Y-%m-%d')" >> "$LOG_FILE" 2>&1
    if git push >> "$LOG_FILE" 2>&1; then
        log "Infra repo: changes committed and pushed"
    else
        log "ERROR: infra repo push failed"
    fi
else
    log "Infra repo: no changes"
fi

# --- CONTENT REPO ---

rsync -a --delete --exclude='.git' --exclude='.gitignore' "$WEB_ROOT/" "$CONTENT_REPO/" 2>>"$LOG_FILE" || fail "rsync of web root failed"

cd "$CONTENT_REPO" || fail "could not cd to $CONTENT_REPO"

if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "Automated daily backup $(date '+%Y-%m-%d')" >> "$LOG_FILE" 2>&1
    if git push >> "$LOG_FILE" 2>&1; then
        log "Content repo: changes committed and pushed"
    else
        log "ERROR: content repo push failed"
    fi
else
    log "Content repo: no changes"
fi

log "=== Backup run finished ==="
