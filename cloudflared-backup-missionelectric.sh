#!/bin/bash
# cloudflared-backup-missionelectric.sh
# Nightly encrypted backup of CT201's Cloudflare tunnel credentials
# (config.yml, credentials json), pushed to private GitHub repo.
# Reuses the same GPG passphrase already set up for n8n-backup-missionelectric.sh.

set -uo pipefail

DATE=$(date '+%Y-%m-%d_%H%M%S')
SOURCE_DIR="/etc/cloudflared"
BACKUP_DIR="/home/matt/missionelectric-infra/cloudflared-backups"
TAR_FILE="$BACKUP_DIR/cloudflared-missionelectric_${DATE}.tar.gz"
ENC_FILE="${TAR_FILE}.gpg"
LOG_FILE="/home/matt/cloudflared-backup-missionelectric.log"
PASSPHRASE_FILE="/etc/backup-secrets/gpg-passphrase"
RETAIN_DAYS=30

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

fail() {
    log "FATAL: $1"
    [ -f "$TAR_FILE" ] && rm -f "$TAR_FILE"
    exit 1
}

log "=== Backup run started ==="

mkdir -p "$BACKUP_DIR" || fail "could not create $BACKUP_DIR"

if [ ! -f "$PASSPHRASE_FILE" ]; then
    fail "passphrase file missing at $PASSPHRASE_FILE"
fi

sudo /usr/bin/tar -czf "$TAR_FILE" -C "$SOURCE_DIR" . 2>>"$LOG_FILE" || fail "tar of $SOURCE_DIR failed"

sudo chown matt:matt "$TAR_FILE" || fail "could not chown tar file"

gpg --batch --yes --passphrase-file "$PASSPHRASE_FILE" \
    --symmetric --cipher-algo AES256 \
    --output "$ENC_FILE" "$TAR_FILE" 2>>"$LOG_FILE" || fail "gpg encryption failed"

rm -f "$TAR_FILE" || fail "could not remove plaintext tar after encryption"

find "$BACKUP_DIR" -name "*.tar.gz.gpg" -mtime +"$RETAIN_DAYS" -delete 2>>"$LOG_FILE"

cd "$BACKUP_DIR/.." || fail "could not cd to repo root"

git add "cloudflared-backups/" || fail "git add failed"

if git diff --cached --quiet; then
    log "No changes to commit"
else
    git commit -m "Encrypted cloudflared backup: $DATE" >> "$LOG_FILE" 2>&1
    if git push origin main >> "$LOG_FILE" 2>&1; then
        log "Backup successful: pushed $ENC_FILE"
    else
        fail "git push failed"
    fi
fi

log "=== Backup run finished ==="
