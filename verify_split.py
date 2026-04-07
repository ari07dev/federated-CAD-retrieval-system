from ai_encoder import encoder
import sys

print("Loading text model only...")
encoder._load_text_model()

if encoder.text_model is None:
    print("FAIL: Text model not loaded")
    sys.exit(1)

if encoder.clip_model is not None:
    print("FAIL: CLIP model loaded unexpectedly!")
    sys.exit(1)

print("SUCCESS: Text model loaded without CLIP.")
