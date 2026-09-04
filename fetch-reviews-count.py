#!/usr/bin/env python3
import json, requests, os

API_URL = "https://app.housecallpro.com/website_builder/api/reviews/ratings/8c8eebdb-4761-484c-b3b4-c050c3c44711"
OUTPUT_FILE = "/var/www/missionelectric/reviews-count.json"

try:
    data = requests.get(API_URL, timeout=10).json()
    overall = next((s for s in data if s["source"] == "overall"), None)
    count = overall["total_ratings"] if overall else None
    if count is not None:
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"count": count}, f)
        print(f"Saved reviews count: {count}")
    else:
        print("Warning: Could not find overall rating in API response. File not updated.")
except Exception as e:
    print(f"Error fetching reviews count: {e}. File not updated.")
