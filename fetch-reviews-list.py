#!/usr/bin/env python3
import json, requests, os, shutil, datetime, sys, re

BASE_URL = "https://app.housecallpro.com/alpha/organizations/8c8eebdb-4761-484c-b3b4-c050c3c44711/reviews/all"
OUTPUT_FILE = "/var/www/missionelectric/reviews-list.json"
LOG_FILE = "/home/matt/scripts/logs/fetch-reviews-list.log"
BACKUP_DIR = "/home/matt/missionelectric-backups"
BACKUP_KEEP = 8
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def normalize_rating(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        n = v
    elif isinstance(v, float):
        try:
            n = int(round(v))
        except (ValueError, OverflowError):
            return None
    else:
        return None
    if 1 <= n <= 5:
        return n
    return None

def validate_review(r):
    if not isinstance(r, dict):
        return False
    if normalize_rating(r.get("rating")) is None:
        return False
    text = r.get("text")
    if not isinstance(text, str) or not text.strip():
        return False
    if not isinstance(r.get("author"), str) or not r["author"].strip():
        return False
    date = r.get("date")
    if not isinstance(date, str) or not DATE_RE.match(date):
        return False
    return True

def validate_reviews(reviews):
    if not isinstance(reviews, list) or len(reviews) == 0:
        return False
    return all(validate_review(r) for r in reviews)

def prune_backups():
    try:
        entries = [f for f in os.listdir(BACKUP_DIR) if f.startswith("reviews-list.json.auto-bak.")]
        for old in sorted(entries, reverse=True)[BACKUP_KEEP:]:
            os.remove(os.path.join(BACKUP_DIR, old))
    except Exception as e:
        log(f"Backup prune warning: {e}")

def fetch_all_reviews():
    reviews = []
    page = 1
    while True:
        params = {"page": page, "count": 100, "sort_by": "created_at", "sort_direction": "desc"}
        resp = requests.get(BASE_URL, params=params, timeout=15)
        data = resp.json()
        if not isinstance(data, dict):
            log(f"Warning: API page {page} returned {type(data).__name__}, not dict. Stopping.")
            break
        batch = data.get("data", [])
        if not isinstance(batch, list):
            log(f"Warning: API page {page} 'data' field is {type(batch).__name__}, not list. Stopping.")
            break
        if not batch:
            break
        for r in batch:
            if not isinstance(r, dict):
                continue
            comment = (r.get("comments") or "").strip()
            if not comment:
                continue
            rating = normalize_rating(r.get("rating"))
            if rating is None:
                continue
            reviews.append({
                "rating": rating,
                "text": comment,
                "author": r.get("customer_name", "Customer"),
                "date": (r.get("created_at", "") or "")[:10],
            })
        if len(batch) < 100:
            break
        page += 1
    return reviews

try:
    reviews = fetch_all_reviews()

    if not reviews:
        log("Warning: No reviews returned from API. File not updated.")
        sys.exit(0)

    if not validate_reviews(reviews):
        bad = [i for i, r in enumerate(reviews) if not validate_review(r)]
        log(f"Warning: {len(bad)} review(s) failed validation (first bad index {bad[0]}). File not updated.")
        sys.exit(0)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_path = None
    if os.path.exists(OUTPUT_FILE):
        backup_path = os.path.join(BACKUP_DIR, f"reviews-list.json.auto-bak.{stamp}")
        shutil.copy2(OUTPUT_FILE, backup_path)
        log(f"Backed up reviews-list.json to {os.path.basename(backup_path)}")

    tmp_path = OUTPUT_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(reviews, f)
    os.replace(tmp_path, OUTPUT_FILE)
    log(f"Wrote {len(reviews)} reviews to reviews-list.json (atomic).")

    with open(OUTPUT_FILE, "r") as f:
        verify = json.load(f)
    if not isinstance(verify, list) or len(verify) != len(reviews):
        log(f"ERROR: Post-write verification failed. Expected {len(reviews)} reviews, got {len(verify) if isinstance(verify, list) else type(verify).__name__}.")
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, OUTPUT_FILE)
            log(f"Restored from {os.path.basename(backup_path)}")
        sys.exit(1)
    if verify != reviews:
        log("ERROR: Post-write verification failed. Content mismatch. Restoring backup.")
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, OUTPUT_FILE)
            log(f"Restored from {os.path.basename(backup_path)}")
        sys.exit(1)

    log(f"Verified: reviews-list.json contains {len(verify)} reviews.")
    prune_backups()

except Exception as e:
    log(f"Error fetching reviews list: {e}. File not updated.")
    sys.exit(1)
