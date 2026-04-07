from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, abort, send_from_directory
import requests
import concurrent.futures
import time
from flask_cors import CORS

# IMPORT UNIVERSAL ENCODER
from ai_encoder import encoder
import generation.cad_synthesis as gen

app = Flask(__name__)
CORS(app)

# Warmup AI models in background when app starts (Production & Dev)
encoder.warmup()

import json
import os

# ---------------- CONFIG ----------------

# Load nodes from nodes.json if exists, else default to local
NODES_FILE = "nodes.json"
if os.path.exists(NODES_FILE):
    with open(NODES_FILE, "r") as f:
        NODES = json.load(f)
else:
    NODES = {
        "NODE_A": "http://127.0.0.1:6001",
        "NODE_B": "http://127.0.0.1:6002"
    }

# ---------------- HELPERS ----------------

def probe_node(node_name, url, endpoint, payload, files=None):
    """
    Helper to query a single node.
    """
    try:
        start = time.time()
        print(f"Probing {node_name}...")
        
        if files:
            # For file uploads
            # We need to re-open the file or just pass the bytes if possible, 
            # but requests.post files expects open file handles or tuples.
            # Here payload is ignored if files present for simplicity in this specific app structure
            r = requests.post(f"{url}/{endpoint}", files=files, timeout=30)
        else:
            # JSON payload
            r = requests.post(f"{url}/{endpoint}", json=payload, timeout=10)
            
        latency = time.time() - start
        
        if r.status_code == 200:
            data = r.json()
            print(f"{node_name} responded in {latency:.2f}s with {len(data)} results.")
            return data
        else:
            print(f"{node_name} error: {r.status_code}")
            return []
            
    except Exception as e:
        print(f"{node_name} DOWN: {e}")
        return []

def aggregate_results(results_list):
    """
    Flattens and sorts results.
    """
    flat = []
    for r in results_list:
        flat.extend(r)
    
    # Sort by score info descending
    flat.sort(key=lambda x: x.get("score", 0), reverse=True)
    return flat

# ---------------- SEARCH LOGIC ----------------

def federated_search(query_text=None, query_image=None):
    """
    Orchestrates the search across nodes using threads.
    """
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(NODES)) as executor:
        futures = {}
        
        # Prepare vector/payload
        payload = {}
        files = None
        endpoint = ""
        
        if query_text:
            vec = encoder.encode_text(query_text).tolist()
            payload = {"vector": vec}
            endpoint = "search"
            
        elif query_image:
            # We need to send the file to nodes. 
            # query_image is a FileStorage object from Flask.
            # We can't share one file handle across threads easily without seeking.
            # Better to read bytes once.
            img_bytes = query_image.read()
            endpoint = "search_sketch"
            
        # Dispatch
        for name, url in NODES.items():
            if query_text:
                futures[executor.submit(probe_node, name, url, endpoint, payload)] = name
            elif query_image:
                # Create a tuple for requests
                # (filename, bytes, content_type)
                f = {"image": (query_image.filename, img_bytes, query_image.content_type)}
                futures[executor.submit(probe_node, name, url, endpoint, None, f)] = name

        # Collect
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            
    # Aggregation
    final_results = aggregate_results(results)
    
    # Check for text query fallback
    if query_text:
        top_score = final_results[0]["score"] if final_results else 0.0
        
        # if top_score < 0.4:
        #     print(f"Low confidence ({top_score:.2f}). Generating fallback...")
        #     try:
        #         gen_result = gen.generate_model(query_text)
        #         final_results.insert(0, gen_result) # Put at top
        #     except Exception as e:
        #         print(f"Generation failed: {e}")
        pass
                
    return final_results

# ---------------- JSON API (for React frontend) ----------------

@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json()
    query = data.get("query", "") if data else ""
    if not query:
        return jsonify({"error": "Missing query"}), 400
        
    # Check cache for text queries
    results = get_cached_search(query)
    return jsonify({"results": results})

from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_search(query):
    print(f"Cache miss for: {query}")
    return federated_search(query_text=query)

@app.route("/api/search_sketch", methods=["POST"])
def api_search_sketch():
    image = request.files.get("image")
    if not image or not image.filename:
        return jsonify({"error": "Missing image"}), 400
    results = federated_search(query_image=image)
    return jsonify({"results": results})

@app.route("/api/nodes", methods=["GET"])
def api_nodes():
    status = {}
    for name, url in NODES.items():
        try:
            r = requests.get(f"{url}/search", timeout=2)
            status[name] = "online"
        except Exception:
            status[name] = "offline"
    return jsonify(status)

# ---------------- UI ----------------

@app.route("/", methods=["GET"])
def index():
    # Serve React App
    return send_from_directory("frontend/dist", "index.html")

@app.route("/assets/<path:path>")
def serve_assets(path):
    # Serve React Assets (JS/CSS)
    return send_from_directory("frontend/dist/assets", path)

# Legacy support for old Postman/HTML forms if needed, but React uses JSON API.


# ---------------- DOWNLOAD ----------------

@app.route("/download")
def download():
    node = request.args.get("node")
    file = request.args.get("file")
    
    if not file:
        return "Missing file parameter", 400
    
    # If generated, serve from local static
    if not node and "generated" in file:
        return redirect(url_for('static', filename=file))

    if node not in NODES:
        return "Invalid node", 400

    return redirect(f"{NODES[node]}/download?file={file}")

@app.route("/api/download_generated")
def api_download_generated():
    """Serves generated CAD files to the React frontend."""
    file = request.args.get("file", "")
    if not file:
        return abort(400)
    
    # Security: only allow files from the generated directory
    import os
    base = os.path.join(os.path.dirname(__file__), "static")
    path = os.path.normpath(os.path.join(base, file))
    
    if not path.startswith(os.path.normpath(base)):
        return abort(403)
    
    if not os.path.exists(path):
        return abort(404)
    
    return send_file(path, as_attachment=True)

# ---------------- RUN ----------------

if __name__ == "__main__":
    # Start loading models in background immediately
    encoder.warmup()
    app.run(port=5000, debug=True)
