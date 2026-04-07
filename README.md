# FUSION-CAD System

## 🚀 How to Run (Reliable Method)
Always use the production runner. **Do not** run python scripts individually.

```bash
python run_production.py
```

## ✅ What this does
1.  **Starts Node A** (Port 6001)
2.  **Waits** until Node A completely loads its AI models (Smart System).
3.  **Starts Node B** (Port 6002)
4.  **Starts Broker** (Port 5000)
5.  **Serves Frontend** at http://127.0.0.1:5000

## 🛠 Troubleshooting
*   **"Port already in use"**: Run `taskkill /F /IM python.exe` in terminal and try again.
*   **"ImportError"**: Make sure you installed dependencies (`pip install -r requirements.txt`).
*   **Slow First Search**: The very first search might take 1s to wake up the cache, afterwards it is instant.
