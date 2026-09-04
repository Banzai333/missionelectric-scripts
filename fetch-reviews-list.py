#!/usr/bin/env python3
import json, requests, os

BASE_URL = "https://app.housecallpro.com/alpha/organizations/8c8eebdb-4761-484c-b3b4-c050c3c44711/reviews/all"
OUTPUT_FILE = "/var/www/missionelectric/reviews-list.json"

try:
    reviews = []
    page = 1
    while True:
        params = {"page": page, "count": 100, "sort_by": "created_at", "sort_direction": "desc"}
        resp = requests.get(BASE_URL, params=params, timeout=15)
        data = resp.json()
        batch = data.get("data", [])
        if not batch:
            break
        for r in batch:
            comment = (r.get("comments") or "").strip()
            if not comment:
                continue
            reviews.append({
                "rating": r.get("rating", 5),
                "text": comment,
                "author": r.get("customer_name", "Customer"),
                "date": r.get("created_at", "")[:10]
            })
        if len(batch) < 100:
            break
        page += 1

    if reviews:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(reviews, f)
        print(f"Saved {len(reviews)} reviews with comments.")
    else:
        print("Warning: No reviews returned from API. File not updated.")

except Exception as e:
    print(f"Error fetching reviews list: {e}. File not updated.")
