import time
import sys
from ai_encoder import encoder

print("Check 1: Models should be None initially (if imported fast)")
if encoder.text_model is not None:
    print("WARN: Text model already loaded? (Maybe imported by something else)")

print("Starting warmup...")
encoder.warmup()

print("Waiting for background loading (max 20s)...")
start = time.time()
while time.time() - start < 20:
    if encoder.text_model is not None and encoder.clip_model is not None:
        print(f"SUCCESS: Models loaded in background after {time.time() - start:.2f}s")
        sys.exit(0)
    time.sleep(1)

print("FAIL: Models did not load within timeout")
sys.exit(1)
