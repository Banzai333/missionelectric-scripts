#!/usr/bin/env python3
import json, requests, os, re, shutil, datetime, sys

API_URL = "https://app.housecallpro.com/website_builder/api/reviews/ratings/8c8eebdb-4761-484c-b3b4-c050c3c44711"
OUTPUT_FILE = "/var/www/missionelectric/reviews-count.json"
TARGETS = [
    "/var/www/missionelectric/index.html",
    "/var/www/missionelectric/reviews.html",
]
LOG_FILE = "/home/matt/scripts/logs/fetch-reviews-count.log"
BACKUP_DIR = "/home/matt/missionelectric-backups"
BACKUP_KEEP = 8

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def validate_count(count):
    if not isinstance(count, int):
        return False
    if isinstance(count, bool):
        return False
    return 1 <= count <= 100000

def prune_backups():
    try:
        entries = [f for f in os.listdir(BACKUP_DIR) if '.auto-bak.' in f]
        by_file = {}
        for e in entries:
            base = e.rsplit('.auto-bak.', 1)[0]
            by_file.setdefault(base, []).append(e)
        for base, files in by_file.items():
            for old in sorted(files, reverse=True)[BACKUP_KEEP:]:
                os.remove(os.path.join(BACKUP_DIR, old))
    except Exception as e:
        log(f"Backup prune warning: {e}")

def update_target(path, count):
    if not os.path.exists(path):
        log(f"Warning: {path} not found. Skipping.")
        return
    with open(path, "r") as f:
        original = f.read()
    pattern = re.compile(r'^(\s*"reviewCount":\s*)(\d+)', re.MULTILINE)
    matches = pattern.findall(original)
    if len(matches) != 1:
        log(f"Warning: {path} has {len(matches)} reviewCount matches, expected 1. Skipping.")
        return
    old_count = int(matches[0][1])
    if old_count == count:
        log(f"{os.path.basename(path)}: no change needed, already {count}.")
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.basename(path)
    backup_path = os.path.join(BACKUP_DIR, f"{base}.auto-bak.{stamp}")
    shutil.copy2(path, backup_path)
    new_content = pattern.sub(lambda m: f"{m.group(1)}{count}", original, count=1)
    with open(path, "w") as f:
        f.write(new_content)
    with open(path, "r") as f:
        verify = f.read()
    verify_matches = pattern.findall(verify)
    if len(verify_matches) != 1 or int(verify_matches[0][1]) != count:
        log(f"ERROR: Post-write verification failed for {path}. Restoring backup.")
        shutil.copy2(backup_path, path)
        return
    a_lines = original.split("\n")
    b_lines = new_content.split("\n")
    if len(a_lines) != len(b_lines):
        log(f"WARNING: {base} line count changed ({len(a_lines)} to {len(b_lines)}). Review manually.")
    else:
        diff_count = sum(1 for x, y in zip(a_lines, b_lines) if x != y)
        if diff_count != 1:
            log(f"WARNING: {base} had {diff_count} lines change, expected 1. Review manually.")
        else:
            log(f"{base}: updated reviewCount {old_count} to {count}.")

try:
    data = requests.get(API_URL, timeout=10).json()
    overall = next((s for s in data if s["source"] == "overall"), None)
    count = overall["total_ratings"] if overall else None

    if count is None:
        log("Warning: No overall rating in API response. No files updated.")
        sys.exit(0)
    if not validate_count(count):
        log(f"Warning: Fetched count {count!r} failed validation. No files updated.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w") as f:
        json.dump({"count": count}, f)
    log(f"Saved reviews-count.json: {count}")

    for target in TARGETS:
        update_target(target, count)

    prune_backups()

except Exception as e:
    log(f"Error: {e}")
