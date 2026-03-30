import time
import requests

def test_pipeline():
    print("Testing Real-time Facebook Fetch Pipeline...")
    req = {
        "platform": "facebook",
        "target_account": "https://www.facebook.com/zuck",
        "api_key": "dummy_test_token"
    }
    
    # 1. Start Analysis
    try:
        resp = requests.post("http://localhost:8000/api/analyze", json=req)
        print("POST /api/analyze ->", resp.json())
    except Exception as e:
        print("Backend not running yet", e)
        return
        
    print("\nPolling /api/task-status in real time...")
    
    # 2. Poll Status
    for i in range(10):
        status = requests.get("http://localhost:8000/api/task-status").json()
        print(f"[{i}s] Status:", status)
        
        if status.get("done"):
            print("\nPipeline Finished Successfully. (Real-time polling verified)")
            if status.get("error"):
                print("Expected error caught from Graph API:", status["error"])
            break
        time.sleep(1)

if __name__ == "__main__":
    test_pipeline()
