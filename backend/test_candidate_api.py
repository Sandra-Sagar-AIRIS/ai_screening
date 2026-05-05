import requests
import uuid
import time
import json

BASE_URL = "http://localhost:8000/api/v1"

ORG_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "22222222-2222-2222-2222-222222222222"
WORKSPACE_ID = "33333333-3333-3333-3333-333333333333"

HEADERS = {
    "X-User-Id": USER_ID,
    "X-Organization-Id": ORG_ID,
    "X-User-Role": "admin",
    "X-Workspace-Id": WORKSPACE_ID
}

def run_tests():
    print("--- STARTING CANDIDATE MANAGEMENT API TESTS ---")
    
    # 1. Test Manual Creation
    try:
        print("\n1. Testing Manual Candidate Creation...")
        payload = {
            "first_name": "QA",
            "last_name": "Tester",
            "email": f"qa_{uuid.uuid4().hex[:8]}@example.com",
            "phone": "555-0100",
            "location": "Remote",
            "source": "manual",
            "stage": "applied"
        }
        res = requests.post(f"{BASE_URL}/candidates", json=payload, headers=HEADERS)
        if res.status_code == 201:
            data = res.json()
            candidate_id = data.get("data", {}).get("id")
            print(f"SUCCESS. Candidate ID: {candidate_id}")
        else:
            print(f"FAILED: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"ERROR: {e}")

    # 2. Test Get Candidates
    try:
        print("\n2. Testing List Candidates...")
        res = requests.get(f"{BASE_URL}/candidates", headers=HEADERS)
        if res.status_code == 200:
            count = res.json().get("data", {}).get("total_count", 0)
            print(f"SUCCESS. Total candidates found: {count}")
        else:
            print(f"FAILED: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    run_tests()
