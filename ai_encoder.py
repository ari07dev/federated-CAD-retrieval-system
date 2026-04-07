"""
Universal Multimodal Encoder with enhanced sketch search accuracy.
Combines CLIP (multi-augmentation), contour features, and edge-based encoding.
"""
from PIL import Image
import numpy as np
import cv2

from geometry.silhouette import (
    extract_silhouette, center_crop, normalize_rotation,
    compute_hu_moments, compute_contour_features,
    preprocess_for_clip, preprocess_db_image_edges, extract_edges
)


class UniversalEncoder:
    def __init__(self):
        print("Initializing UniversalEncoder (Lazy Loading)...")
        self.device = "cpu"
        self.text_model = None
        self.clip_model = None
        self.clip_preprocess = None
        self.TEXT_DIM = 384
        self.IMG_DIM = 512

    def _load_text_model(self):
        """Loads only the text model if needed."""
        if self.text_model is None:
            print("Loading UniversalEncoder text model...")
            global SentenceTransformer
            from sentence_transformers import SentenceTransformer
            self.text_model = SentenceTransformer("all-MiniLM-L6-v2", device=self.device)
            print("Text model loaded.")

    def _load_clip_model(self):
        """Loads only the CLIP model if needed."""
        if self.clip_model is None:
            print("Loading UniversalEncoder CLIP model...")
            global torch, clip
            import torch
            import clip
            self.clip_model, self.clip_preprocess = clip.load("ViT-B/32", device=self.device)
            self.clip_model.eval()
            print("CLIP model loaded.")

    def warmup(self):
        """
        Starts a background thread to load all models immediately.
        This moves the loading time to application startup (background) 
        rather than first request.
        """
        import threading
        def _loader():
            print("Warmup: Starting background model loading...")
            self._load_text_model()
            self._load_clip_model()
            print("Warmup: All models loaded in background.")
        
        t = threading.Thread(target=_loader, daemon=True)
        t.start()

    def encode_text(self, text):
        """Encodes text to 384-dim vector."""
        self._load_text_model()
        vec = self.text_model.encode(text, normalize_embeddings=True)
        return vec.astype("float32")

    def _clip_encode_pil(self, pil_img):
        """Core CLIP encoding for a single PIL image."""
        self._load_clip_model()
        image_input = self.clip_preprocess(pil_img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            features = self.clip_model.encode_image(image_input)
        features /= features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy().flatten().astype("float32")

    def _multi_augment_encode(self, pil_img, n_augments=5):
        """
        Encode the same image with multiple augmentations and average.
        This produces a more robust representation that's less sensitive
        to exact drawing style, line thickness, etc.
        """
        vectors = []
        
        # Original
        vectors.append(self._clip_encode_pil(pil_img))
        
        img_np = np.array(pil_img)
        h, w = img_np.shape[:2]
        
        # Augmentation 1: Slight scale up (110%)
        scaled = cv2.resize(img_np, None, fx=1.1, fy=1.1)
        sh, sw = scaled.shape[:2]
        crop_y, crop_x = (sh - h) // 2, (sw - w) // 2
        scaled = scaled[crop_y:crop_y+h, crop_x:crop_x+w]
        vectors.append(self._clip_encode_pil(Image.fromarray(scaled)))
        
        # Augmentation 2: Slight scale down (90%)
        scaled = cv2.resize(img_np, None, fx=0.9, fy=0.9)
        canvas = np.ones((h, w, 3), dtype=np.uint8) * 255  # white background
        sh, sw = scaled.shape[:2]
        y_off, x_off = (h - sh) // 2, (w - sw) // 2
        canvas[y_off:y_off+sh, x_off:x_off+sw] = scaled
        vectors.append(self._clip_encode_pil(Image.fromarray(canvas)))
        
        # Augmentation 3: Horizontal flip
        flipped = cv2.flip(img_np, 1)
        vectors.append(self._clip_encode_pil(Image.fromarray(flipped)))
        
        # Augmentation 4: Slight Gaussian blur (simulates rough sketches)
        blurred = cv2.GaussianBlur(img_np, (3, 3), 0.8)
        vectors.append(self._clip_encode_pil(Image.fromarray(blurred)))
        
        # Average all vectors
        avg = np.mean(vectors, axis=0).astype("float32")
        
        # Re-normalize
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg /= norm
        
        return avg

    def encode_image(self, image_source, partial=False):
        """
        Encodes image to 512-dim vector.
        
        image_source: str (path) or PIL.Image or file-like object
        partial: if True → sketch mode (full preprocessing + multi-augmentation)
                 if False → database mode (clean image, standard encoding)
        """
        try:
            # Load image
            if isinstance(image_source, str):
                pil_img = Image.open(image_source).convert("RGB")
            elif hasattr(image_source, "read"):
                pil_img = Image.open(image_source).convert("RGB")
            else:
                pil_img = image_source.convert("RGB")

            if partial:
                # === SKETCH MODE: Full preprocessing pipeline ===
                cv_img = np.array(pil_img)
                cv_img = cv_img[:, :, ::-1].copy()  # RGB to BGR

                # Use enhanced preprocessing (adaptive threshold + cleanup + aspect crop)
                processed_rgb = preprocess_for_clip(cv_img)
                pil_processed = Image.fromarray(processed_rgb)
                
                # Multi-augmentation encoding for robustness
                return self._multi_augment_encode(pil_processed)
            else:
                # === DATABASE MODE: Standard CLIP encoding ===
                return self._clip_encode_pil(pil_img)

        except Exception as e:
            print(f"Error encoding image: {e}")
            return np.zeros(self.IMG_DIM, dtype="float32")

    def encode_image_edges(self, image_source):
        """
        Encodes a database image as EDGES → same visual domain as sketches.
        This is used to build a second FAISS index that matches sketch queries better.
        """
        try:
            if isinstance(image_source, str):
                cv_img = cv2.imread(image_source)
            else:
                pil_img = Image.open(image_source).convert("RGB")
                cv_img = np.array(pil_img)[:, :, ::-1].copy()
            
            if cv_img is None:
                return np.zeros(self.IMG_DIM, dtype="float32")
            
            # Extract edges → white bg, dark lines (same as sketch preprocessing output)
            edge_rgb = preprocess_db_image_edges(cv_img)
            pil_edge = Image.fromarray(edge_rgb)
            
            return self._clip_encode_pil(pil_edge)
            
        except Exception as e:
            print(f"Error encoding image edges: {e}")
            return np.zeros(self.IMG_DIM, dtype="float32")

    def compute_shape_features(self, image_source):
        """
        Compute contour-based shape features (Hu moments + geometric descriptors).
        These are used for hybrid re-ranking alongside CLIP similarity.
        Returns 8-dim feature vector.
        """
        try:
            if isinstance(image_source, str):
                cv_img = cv2.imread(image_source)
            elif hasattr(image_source, "read"):
                img_bytes = np.frombuffer(image_source.read(), np.uint8)
                image_source.seek(0)
                cv_img = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
            else:
                cv_img = np.array(image_source)[:, :, ::-1].copy()
            
            if cv_img is None:
                return np.zeros(8, dtype="float32")
            
            sil = extract_silhouette(cv_img)
            return compute_contour_features(sil)
            
        except Exception as e:
            print(f"Error computing shape features: {e}")
            return np.zeros(8, dtype="float32")

    def score(self, vec_a, vec_b):
        return float(np.dot(vec_a, vec_b))


# Singleton instance
encoder = UniversalEncoder()
