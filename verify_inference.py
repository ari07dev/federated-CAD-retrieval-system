import time
import sys
from ai_encoder import encoder

print("Starting inference check...")
try:
    # Trigger model loading
    start = time.time()
    vec = encoder.encode_text("test query")
    end = time.time()
    print(f"First inference took {end - start:.4f} seconds (should include loading time)")
    
    if encoder.text_model is None:
        print("FAIL: Text model not loaded after inference!")
        sys.exit(1)
        
    if len(vec) != 384:
         print(f"FAIL: Vector dimension mismatch. Expected 384, got {len(vec)}")
         sys.exit(1)
         
    print("SUCCESS: Inference worked and models loaded.")
except Exception as e:
    print(f"FAIL: Inference failed with error: {e}")
    sys.exit(1)
