"""
Gemini Re-ranker for Search (Vision + Text).

After CLIP returns initial candidates, this module uses Gemini to re-rank them.
- Vision: compares sketch vs CAD images (1 batched API call)
- Text: compares query vs candidate names/descriptions (1 API call)

Both functions have a 10-second timeout — if Gemini doesn't respond in time,
they return None and the system falls back to CLIP-only scores.
"""
import os
import base64
import re
import threading
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Models to try (in order of preference)
VISION_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

# Max seconds to wait for Gemini before falling back to CLIP
GEMINI_TIMEOUT = 10


def _get_client():
    """Get a Gemini client, or None if unavailable."""
    if not GOOGLE_API_KEY:
        return None
    try:
        from google import genai
        return genai.Client(api_key=GOOGLE_API_KEY)
    except Exception as e:
        print(f"RERANKER: Client init failed: {e}")
        return None


def _call_gemini_with_timeout(client, model_name, contents, timeout=GEMINI_TIMEOUT):
    """
    Call Gemini with a timeout. Returns response text or None.
    """
    result = [None]
    error = [None]
    
    def _call():
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config={"temperature": 0.0}
            )
            result[0] = response.text.strip()
        except Exception as e:
            error[0] = e
    
    t = threading.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout=timeout)
    
    if t.is_alive():
        print(f"RERANKER: {model_name} timed out after {timeout}s")
        return None
    
    if error[0]:
        raise error[0]
    
    return result[0]


def _load_image_as_part(image_path):
    """Load an image file and return it as a Gemini inline_data part."""
    with open(image_path, "rb") as f:
        data = f.read()
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    mime = mime_map.get(ext, "image/png")
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}


def _load_bytes_as_part(image_bytes, mime_type="image/png"):
    """Load raw image bytes as a Gemini inline_data part."""
    return {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}}


# ==================== VISION RE-RANKER ====================

def rerank_with_vision(sketch_bytes, candidate_image_paths, sketch_mime="image/png"):
    """
    Re-rank sketch search candidates using Gemini Vision (1 batched API call).
    Returns list of (index, score) or None if unavailable.
    """
    client = _get_client()
    if not client:
        return None
    
    valid = [(idx, p, s) for idx, p, s in candidate_image_paths if p and os.path.exists(p)]
    if not valid:
        return None
    
    n = len(valid)
    prompt = f"""You are an expert CAD engineer. Compare the SKETCH (first image) against {n} CAD drawings (images 2 to {n+1}).

Score each CAD drawing 1-10 on how well it matches the sketch:
- 10: Same object (same shape, proportions, features)
- 7-9: Similar with minor differences
- 4-6: Some resemblance
- 1-3: Does not match

Focus on STRUCTURAL similarity. Ignore line quality.

Respond with ONLY comma-separated integers. Example for 3 candidates: 8,3,5"""

    contents = [prompt, _load_bytes_as_part(sketch_bytes, sketch_mime)]
    for idx, img_path, _ in valid:
        contents.append(_load_image_as_part(img_path))
    
    for model_name in VISION_MODELS:
        try:
            print(f"VISION RERANKER: Trying {model_name} ({n} candidates)...")
            text = _call_gemini_with_timeout(client, model_name, contents)
            
            if text is None:
                continue  # Timed out, try next model
            
            print(f"VISION RERANKER: Response: {text}")
            nums = re.findall(r'\d+', text)
            
            results = []
            for i, (idx, img_path, orig_score) in enumerate(valid):
                score = min(max(int(nums[i]), 1), 10) if i < len(nums) else max(1, int(orig_score * 10))
                results.append((idx, float(score) / 10.0))
                print(f"  {os.path.basename(img_path)}: {score}/10")
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results
            
        except Exception as e:
            print(f"VISION RERANKER: {model_name} failed: {e}")
            continue
    
    print("VISION RERANKER: All models failed")
    return None


# ==================== TEXT RE-RANKER ====================

def rerank_text_results(query, candidates):
    """
    Re-rank text search candidates using Gemini (1 API call).
    Returns re-ranked list of candidates, or None if unavailable.
    """
    client = _get_client()
    if not client:
        return None
    
    if not candidates:
        return candidates
    
    n = len(candidates)
    lines = []
    for i, c in enumerate(candidates):
        lines.append(f"{i+1}. \"{c.get('name', '?')}\" — {c.get('description', 'N/A')}")
    
    prompt = f"""You are an expert CAD/engineering parts search engine.

User searched for: "{query}"

Here are {n} candidate results:
{chr(10).join(lines)}

Score each candidate 1-10 on relevance:
- 10: Exact match
- 7-9: Very relevant (same category or closely related)
- 4-6: Somewhat relevant
- 1-3: Not relevant

Consider engineering synonyms (tank=storage vessel, reactor=pressure vessel).

Respond with ONLY comma-separated integers. Example: 9,4,2"""

    for model_name in VISION_MODELS:
        try:
            print(f"TEXT RERANKER: Trying {model_name} ({n} candidates)...")
            text = _call_gemini_with_timeout(client, model_name, [prompt])
            
            if text is None:
                continue  # Timed out, try next model
            
            print(f"TEXT RERANKER: Response: {text}")
            nums = re.findall(r'\d+', text)
            
            reranked = []
            for i, c in enumerate(candidates):
                gemini_score = min(max(int(nums[i]), 1), 10) / 10.0 if i < len(nums) else c.get("score", 0.0)
                clip_score = c.get("score", 0.0)
                blended = 0.6 * gemini_score + 0.4 * clip_score
                
                entry = dict(c)
                entry["score"] = float(f"{blended:.4f}")
                reranked.append(entry)
                print(f"  {c.get('name', '?')}: gemini={gemini_score:.1f} clip={clip_score:.3f} → {blended:.3f}")
            
            reranked.sort(key=lambda x: x["score"], reverse=True)
            return reranked
            
        except Exception as e:
            print(f"TEXT RERANKER: {model_name} failed: {e}")
            continue
    
    print("TEXT RERANKER: All models failed")
    return None
