from flask import Flask, request, jsonify, send_file, abort
import sqlite3, os, uuid, threading
import numpy as np
import faiss
from pdf2image import convert_from_path

# IMPORT UNIVERSAL ENCODER
from ai_encoder import encoder

# ================= CONFIG =================

BASE = os.getcwd()
DB = os.path.join(BASE, "cad_b.db")
NODE = "NODE_B"

# POPPLER path (keep existing)
POPPLER = r"C:\Users\scs83\Videos\Screen Recordings\poppler\poppler\poppler-25.12.0\Library\bin"

TOP_K = 3

# Weights for hybrid sketch scoring
CLIP_RAW_WEIGHT = 0.3
CLIP_EDGE_WEIGHT = 0.5
SHAPE_WEIGHT = 0.2

# ================= CONSTANTS =================
TEXT_DIM = 384
GEO_DIM = 512

from flask_cors import CORS

app = Flask(__name__)
CORS(app)
index_lock = threading.Lock()

# Warmup AI models on startup
encoder.warmup()

# ================= HELPERS =================

def ensure_png(pdf):
    base, ext = os.path.splitext(pdf)
    if ext.lower() != ".pdf":
        return None
    png = base + ".png"
    out = os.path.join(BASE,png)

    if os.path.exists(out):
        return png

    try:
        pages = convert_from_path(
            os.path.join(BASE,pdf),
            dpi=120,
            poppler_path=POPPLER
        )
        if pages:
            pages[0].save(out,"PNG")
            return png
    except Exception as e:
        print(f"PDF convert error: {e}")
    
    return None

# ================= LOAD DATABASE =================

print("Loading DB...")

try:
    conn = sqlite3.connect(DB,check_same_thread=False)
    rows = list(conn.execute("SELECT name,description,file_path FROM cad_assets").fetchall())
    
    if not rows:
        print("NODE_B database empty or query failed")
        rows = []
        
    print("Assets:",len(rows))

except Exception as e:
    print(f"DB Error: {e}")
    rows = []

# ================= TEXT INDEX =================

try:
    if rows:
        texts = [r[1] for r in rows]
        print(f"DEBUG: Encoding {len(texts)} texts...")
        text_vecs = encoder.encode_text(texts)
        print(f"DEBUG: Encoded shape: {text_vecs.shape}")
    else:
        text_vecs = np.zeros((0, TEXT_DIM), dtype="float32")

    print(f"DEBUG: Creating FAISS index dim={TEXT_DIM}...")
    text_index = faiss.IndexFlatIP(TEXT_DIM)
    print("DEBUG: Adding to FAISS...")
    text_index.add(text_vecs)
    print("DEBUG: Text index ready.")

except Exception as e:
    print(f"CRITICAL INIT ERROR in NODE_B: {e}")
    import traceback
    traceback.print_exc()
    # Don't crash immediately, let it run empty? Or crash loudly.
    raise e

# ================= GEOMETRY INDEX (RAW CLIP) =================

geo_vecs = []
print("Encoding geometry (raw CLIP)...")
for r in rows:
    try:
        png = ensure_png(r[2])
        if png:
            p = os.path.join(BASE,png)
            geo_vecs.append(encoder.encode_image(p, partial=False))
        else:
            geo_vecs.append(np.zeros(GEO_DIM, dtype="float32"))
    except Exception as e:
        print(f"Error encoding {r[0]}: {e}")
        geo_vecs.append(np.zeros(GEO_DIM, dtype="float32"))

if geo_vecs:
    geo_vecs = np.stack(geo_vecs).astype("float32")
else:
    geo_vecs = np.zeros((0, GEO_DIM), dtype="float32")

geo_index = faiss.IndexFlatIP(GEO_DIM)
geo_index.add(geo_vecs)
print("Raw geometry vectors:", geo_vecs.shape)

# ================= EDGE GEOMETRY INDEX (DOMAIN-MATCHED) =================

edge_vecs = []
print("Encoding geometry (edge-domain)...")
for r in rows:
    try:
        png = ensure_png(r[2])
        if png:
            p = os.path.join(BASE, png)
            edge_vecs.append(encoder.encode_image_edges(p))
        else:
            edge_vecs.append(np.zeros(GEO_DIM, dtype="float32"))
    except Exception as e:
        print(f"Error edge-encoding {r[0]}: {e}")
        edge_vecs.append(np.zeros(GEO_DIM, dtype="float32"))

if edge_vecs:
    edge_vecs = np.stack(edge_vecs).astype("float32")
else:
    edge_vecs = np.zeros((0, GEO_DIM), dtype="float32")

edge_index = faiss.IndexFlatIP(GEO_DIM)
edge_index.add(edge_vecs)
print("Edge geometry vectors:", edge_vecs.shape)

# ================= SHAPE FEATURES (Hu Moments + Contours) =================

shape_features = []
print("Computing shape features...")
for r in rows:
    try:
        png = ensure_png(r[2])
        if png:
            p = os.path.join(BASE, png)
            shape_features.append(encoder.compute_shape_features(p))
        else:
            shape_features.append(np.zeros(8, dtype="float32"))
    except Exception as e:
        print(f"Error computing shape for {r[0]}: {e}")
        shape_features.append(np.zeros(8, dtype="float32"))

if shape_features:
    shape_features = np.stack(shape_features).astype("float32")
else:
    shape_features = np.zeros((0, 8), dtype="float32")

print("Shape features:", shape_features.shape)

# ================= PACK =================

def pack(scores, ids):
    out=[]
    for sc,ix in zip(scores[0],ids[0]):
        if ix < 0 or ix >= len(rows): continue
        r=rows[ix]
        out.append({
            "node":NODE,
            "name":r[0],
            "description":r[1],
            "file":r[2],
            "score":float(sc)
        })
    return out

def pack_hybrid(indices, hybrid_scores):
    """Pack results with hybrid scores."""
    out = []
    for idx, score in zip(indices, hybrid_scores):
        if idx < 0 or idx >= len(rows):
            continue
        r = rows[idx]
        out.append({
            "node": NODE,
            "name": r[0],
            "description": r[1],
            "file": r[2],
            "score": float(score)
        })
    return out

# ================= ROUTES =================

@app.route("/search",methods=["POST"])
def search_text():
    v=np.array(request.json["vector"],dtype="float32").reshape(1,-1)
    s,i=text_index.search(v,TOP_K)
    return jsonify(pack(s,i))

@app.route("/search_sketch",methods=["POST"])
def search_sketch():
    if "image" not in request.files:
        return jsonify([])

    f=request.files["image"]
    
    # Save sketch bytes for vision re-ranking later
    sketch_bytes = f.read()
    f.seek(0)
    
    # Encode uploaded sketch (partial=True → full preprocessing + multi-augmentation)
    sketch_vec = encoder.encode_image(f, partial=True).reshape(1,-1)
    
    # Reset file pointer for shape features
    f.seek(0)
    sketch_shape = encoder.compute_shape_features(f)

    # === HYBRID SEARCH ===
    
    # 1. Raw CLIP search
    raw_scores, raw_ids = geo_index.search(sketch_vec, min(TOP_K * 2, len(rows)))
    
    # 2. Edge-domain CLIP search  
    edge_scores, edge_ids = edge_index.search(sketch_vec, min(TOP_K * 2, len(rows)))
    
    # 3. Fuse scores for all candidate indices
    candidates = {}
    
    for sc, ix in zip(raw_scores[0], raw_ids[0]):
        if ix < 0 or ix >= len(rows):
            continue
        candidates[int(ix)] = {"raw": float(sc), "edge": 0.0, "shape": 0.0}
    
    for sc, ix in zip(edge_scores[0], edge_ids[0]):
        if ix < 0 or ix >= len(rows):
            continue
        if int(ix) in candidates:
            candidates[int(ix)]["edge"] = float(sc)
        else:
            candidates[int(ix)] = {"raw": 0.0, "edge": float(sc), "shape": 0.0}
    
    # 4. Compute shape similarity for candidates
    for idx in candidates:
        db_shape = shape_features[idx]
        dot = np.dot(sketch_shape, db_shape)
        norm_a = np.linalg.norm(sketch_shape)
        norm_b = np.linalg.norm(db_shape)
        if norm_a > 0 and norm_b > 0:
            candidates[idx]["shape"] = float(dot / (norm_a * norm_b))
    
    # 5. Weighted fusion
    hybrid_results = []
    for idx, scores in candidates.items():
        fused = (
            CLIP_RAW_WEIGHT * max(scores["raw"], 0) +
            CLIP_EDGE_WEIGHT * max(scores["edge"], 0) +
            SHAPE_WEIGHT * max(scores["shape"], 0)
        )
        hybrid_results.append((idx, fused))
    
    # Sort by fused score descending
    hybrid_results.sort(key=lambda x: x[1], reverse=True)
    hybrid_results = hybrid_results[:TOP_K]
    
    print(f"CLIP hybrid top scores: {[(idx, f'{s:.3f}') for idx, s in hybrid_results]}")
    
    # === GEMINI VISION RE-RANKING ===
    try:
        from generation.vision_reranker import rerank_with_vision
        
        # Prepare candidate image paths for Gemini
        candidate_images = []
        for idx, clip_score in hybrid_results:
            r = rows[idx]
            png = ensure_png(r[2])
            if png:
                abs_png = os.path.join(BASE, png)
                candidate_images.append((idx, abs_png, clip_score))
            else:
                candidate_images.append((idx, "", clip_score))
        
        # Determine sketch MIME type
        f.seek(0)
        sketch_mime = f.content_type if hasattr(f, 'content_type') else "image/png"
        
        vision_results = rerank_with_vision(sketch_bytes, candidate_images, sketch_mime)
        
        if vision_results is not None:
            # Blend CLIP and Gemini scores (60% Gemini, 40% CLIP)
            clip_scores = {idx: score for idx, score in hybrid_results}
            blended = []
            for idx, gemini_score in vision_results:
                clip_score = clip_scores.get(idx, 0.0)
                final = 0.6 * gemini_score + 0.4 * clip_score
                blended.append((idx, final))
            
            blended.sort(key=lambda x: x[1], reverse=True)
            
            indices = [r[0] for r in blended]
            scores_final = [r[1] for r in blended]
            
            print(f"Vision-reranked scores: {[f'{s:.3f}' for s in scores_final]}")
            return jsonify(pack_hybrid(indices, scores_final))
        
    except Exception as e:
        print(f"Vision re-ranking failed, using CLIP scores: {e}")
    
    # Fallback: use CLIP-only scores if vision re-ranking failed
    indices = [r[0] for r in hybrid_results]
    scores = [r[1] for r in hybrid_results]
    
    print(f"Final scores (CLIP-only): {[f'{s:.3f}' for s in scores]}")
    return jsonify(pack_hybrid(indices, scores))

@app.route("/download")
def download():
    f=request.args.get("file")
    if not f: return abort(400)
    
    p=os.path.join(BASE,f)

    if not os.path.exists(p):
        abort(404)

    return send_file(p,as_attachment=True)

@app.route("/add", methods=["POST"])
def add_asset():
    try:
      with index_lock:
        name = request.form.get("name")
        desc = request.form.get("description")
        file = request.files.get("file")

        if not name or not file:
            return jsonify({"error": "Missing name or file"}), 400

        # Save file
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        save_path = os.path.join(BASE, "cad_files_b", filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file.save(save_path)

        # Rel path for DB
        rel_path = f"cad_files_b/{filename}"

        # DB Insert
        with sqlite3.connect(DB) as c:
            c.execute("INSERT INTO cad_assets (name, description, file_path) VALUES (?, ?, ?)", 
                      (name, desc, rel_path))
            c.commit()

        # Update Memory & Indices
        new_row = (name, desc, rel_path)
        rows.append(new_row)
        
        # Text Index
        txt_vec = encoder.encode_text(desc if desc else name).reshape(1, -1)
        text_index.add(txt_vec)
        
        # Raw Geo + Edge + Shape
        png = ensure_png(rel_path)
        if png:
            p = os.path.join(BASE, png)
            geo_vec = encoder.encode_image(p, partial=False).reshape(1, -1)
            edge_vec = encoder.encode_image_edges(p).reshape(1, -1)
            shape_feat = encoder.compute_shape_features(p).reshape(1, -1)
        else:
            geo_vec = np.zeros((1, GEO_DIM), dtype="float32")
            edge_vec = np.zeros((1, GEO_DIM), dtype="float32")
            shape_feat = np.zeros((1, 8), dtype="float32")
            
        geo_index.add(geo_vec)
        edge_index.add(edge_vec)
        
        global shape_features
        shape_features = np.vstack([shape_features, shape_feat])
        
        return jsonify({"status": "success", "file": rel_path})

    except Exception as e:
        print(f"ADD ERROR: {e}")
        return jsonify({"error": str(e)}), 500

# ================= RUN =================

if __name__=="__main__":
    app.run(port=6002)
