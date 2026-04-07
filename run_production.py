import os
import sys
import subprocess
import time
import threading

def run_service(name, script, port):
    """Runs a Flask app using Waitress for production stability."""
    print(f"[{name}] Starting on port {port}...")
    # waitress-serve --port=PORT script:app
    # identifying the app object: script is filename 'node_a.py', app object is 'app'
    module_name = script.replace(".py", "")
    
    cmd = [
        sys.executable, "-m", "waitress", 
        "--port", str(port),
        f"{module_name}:app"
    ]
    
    try:
        # Run as subprocess
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"[{name}] CRASHED: {e}")

if __name__ == "__main__":
    print("--- STARTING FUSION-CAD SYSTEM (PRODUCTION MODE) ---")
    print("Using Waitress optimized for Windows")
    
    threads = []
    
    # Node A
    t1 = threading.Thread(target=run_service, args=("NODE A", "node_a.py", 6001))
    t1.start()
    threads.append(t1)
    
    import urllib.request
    import urllib.error
    
    # Smart Wait: Poll Node A until it's responsive
    print("Waiting for Node A to initialize models (Smart Polling)...")
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:6001/", timeout=1) as response:
                if response.status == 404: # Flask default 404 is fine, means server is UP
                    print("Node A is ready!")
                    break
        except urllib.error.HTTPError:
             print("Node A is ready (HTTP Error)! ") # 404/405 means listening
             break
        except Exception:
            time.sleep(1)
            sys.stdout.write(".")
            sys.stdout.flush()
    else:
        print("\nWarning: Node A took too long. Starting Node B anyway.")
    
    print("\nStarting Node B...")
    # Node B
    t2 = threading.Thread(target=run_service, args=("NODE B", "node_b.py", 6002))
    t2.start()
    threads.append(t2)
    
    # Broker
    # Wait a bit for nodes
    time.sleep(2)
    t3 = threading.Thread(target=run_service, args=("BROKER", "broker_app.py", 5000))
    t3.start()
    threads.append(t3)
    
    print("\nSystem Running. Press Ctrl+C to stop (might need to close window).")
    print("Broker accessible at: http://127.0.0.1:5000")
    
    for t in threads:
        t.join()
