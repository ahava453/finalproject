#!/usr/bin/env python3
"""
Simple test client to POST sample webhook payloads to /webhook/meta.
Usage: python scripts/test_webhook_client.py [instagram|facebook]
"""
import sys
import os
import requests
import json

API_ENDPOINT = os.environ.get("API_ENDPOINT", "http://localhost:8000/webhook/meta")

instagram_payload = {
    "object": "instagram",
    "entry": [
        {
            "id": "17841400000000000",
            "time": 1670000000,
            "changes": [
                {
                    "field": "comments",
                    "value": {
                        "comment_id": "17895695668004550",
                        "media_id": "17896450804000000",
                        "text": "Nice photo!",
                        "from": {"id": "12345", "username": "tester"},
                        "created_time": "2024-01-01T12:00:00+0000"
                    }
                }
            ]
        }
    ]
}

facebook_payload = {
    "object": "page",
    "entry": [
        {
            "id": "PAGE_ID",
            "time": 1458692752478,
            "changes": [
                {
                    "field": "feed",
                    "value": {
                        "item": "comment",
                        "verb": "add",
                        "comment_id": "1234567890",
                        "post_id": "0987654321",
                        "sender_name": "Jane Doe",
                        "message": "Great post!",
                        "created_time": "2024-01-02T10:00:00+0000"
                    }
                }
            ]
        }
    ]
}

if __name__ == '__main__':
    kind = (sys.argv[1].lower() if len(sys.argv) > 1 else 'instagram')
    if kind == 'facebook':
        payload = facebook_payload
    else:
        payload = instagram_payload

    print(f"Posting sample {kind} payload to {API_ENDPOINT}...")
    try:
        r = requests.post(API_ENDPOINT, json=payload, timeout=10)
        print("Status:", r.status_code)
        try:
            print("Response:", json.dumps(r.json(), indent=2))
        except Exception:
            print("Raw response:", r.text)
    except Exception as e:
        print('Request failed:', e)
