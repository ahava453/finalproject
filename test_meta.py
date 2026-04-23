import requests
import json
import sys
import os

# Test 1: Webhook Handshake Verification
print("--- Test 1: Webhook Handshake Verification ---")
try:
    resp = requests.get(
        "http://127.0.0.1:8000/webhook/meta",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "mock_verify_token",
            "hub.challenge": "12345"
        }
    )
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
    if resp.status_code == 200 and "12345" in resp.text:
        print("[PASS] Webhook Verification")
    else:
        print("[FAIL] Webhook Verification")
except Exception as e:
    print(f"[ERROR] {e}")

# Test 2: URL to ID mapping logic
print("\n--- Test 2: URL to ID Mapping ---")
sys.path.append(os.path.join(os.path.dirname(__file__), "agents"))
try:
    from agents.fetcher import resolve_instagram_id
    test_target = "https://www.instagram.com/mrbeast/"
    result = resolve_instagram_id(test_target, "fake_token")
    print(f"Target: {test_target} -> Resolved: {result}")
    if result == "mrbeast":
        print("[PASS] ID Mapping Logic (Fallback applied correctly)")
    else:
        print("[FAIL] ID Mapping Logic")
except Exception as e:
    print(f"[ERROR] {e}")

# Test 3: Cross-Platform Report
print("\n--- Test 3: Cross-Platform Report Generation ---")
try:
    from agents.analyzer import SentimentAnalyzerAgent
    
    agent = SentimentAnalyzerAgent()
    
    yt_comment = {"platform": "youtube", "text": "This video is amazing! :fire:", "author": "User1"}
    ig_comment = {"platform": "instagram", "text": "Loved the new post! :heart:", "author": "User2"}
    
    yt_score = agent.analyze_text(yt_comment["text"])
    ig_score = agent.analyze_text(ig_comment["text"])
    
    report = {
        "youtube_result": {
            "text": yt_comment["text"],
            "sentiment": yt_score
        },
        "instagram_result": {
            "text": ig_comment["text"],
            "sentiment": ig_score
        }
    }
    
    print(json.dumps(report, indent=2))
    print("[PASS] Cross-Platform Report Generation")
except Exception as e:
    print(f"[ERROR] {e}")
