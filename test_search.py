
import requests
import json

URL = "http://127.0.0.1:5000/api/search"

def test_search(query):
    print(f"Searching for: {query}")
    try:
        r = requests.post(URL, json={"query": query})
        if r.status_code == 200:
            results = r.json().get("results", [])
            print(f"Found {len(results)} results:")
            for res in results:
                print(f" - {res['name']} ({res['score']:.2f}) from {res.get('node')}")
        else:
            print(f"Error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Request Error: {e}")

if __name__ == "__main__":
    test_search("tank")
    test_search("reactor")
