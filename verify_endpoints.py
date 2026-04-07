import requests
import json
import traceback

def test_node(port, name):
    print(f"Testing {name} on port {port}...")
    try:
        # Test Root/Simple get if exists (nodes don't have root route, only /search /add etc)
        # So we test /search which requires POST
        
        vec = [0.1] * 384
        url = f"http://127.0.0.1:{port}/search"
        print(f"POST {url}")
        
        try:
            res = requests.post(url, json={"vector": vec}, timeout=5)
            print(f"Status: {res.status_code}")
            if res.status_code == 200:
                print(f"Response: {res.json()}")
            else:
                print(f"Error Response: {res.text}")
        except Exception as e:
            print(f"Request failed: {e}")
            traceback.print_exc()

    except Exception as e:
        print(f"Setup failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_node(6001, "NODE_A")
    test_node(6002, "NODE_B")
