<<<<<<< HEAD
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
=======
# federated-CAD-retrieval-system
>>>>>>> aaf12933d15ca4c4a1e12369747d792310f74231
# Federated CAD Retrieval System

## 🚀 Overview
A distributed AI-powered CAD search engine...

## 🧠 Features
- Text-based search
- Sketch-based retrieval (CLIP)
- Federated multi-node architecture
- Dynamic asset addition
- FAISS indexing

## 🏗️ Architecture
Frontend → Broker → Nodes (A, B, C)

## ⚙️ Tech Stack
- Python (Flask)
- FAISS
- CLIP / Encoder
- SQLite
- React (Frontend)

## ▶️ How to Run
1. Start Node A
2. Start Node B
3. Run Broker
4. Run Frontend

## 📸 Demo
(Add screenshots)

## 📌 Future Improvements
- Add RAG
- Improve ranking
- Add explanation layer
