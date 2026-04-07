import time
import sys

print("Starting import check...")
start = time.time()
try:
    from ai_encoder import encoder
    end = time.time()
    print(f"Import took {end - start:.4f} seconds")
    
    if (end - start) > 1.0:
        print("FAIL: Import took too long!")
        sys.exit(1)
        
    print("Checking if models are loaded (should be None)...")
    if encoder.text_model is not None or encoder.clip_model is not None:
        print("FAIL: Models are already loaded!")
        sys.exit(1)
        
    print("SUCCESS: Fast startup confirmed.")
except Exception as e:
    print(f"FAIL: Import failed with error: {e}")
    sys.exit(1)
