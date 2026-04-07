import torch
import cv2
import numpy as np

model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14")
model.eval()

DIM = 384   # DINOv2 ViT-S14 output

def encode_sketch(path):
    img = cv2.imread(path)

    if img is None:
        return np.zeros(DIM, dtype="float32")

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (224,224))

    img = img.astype("float32") / 255.0
    img = torch.from_numpy(img).permute(2,0,1).unsqueeze(0)

    with torch.no_grad():
        feat = model(img)

    v = feat.squeeze().numpy().astype("float32")

    # normalize
    n = np.linalg.norm(v)
    if n > 0:
        v /= n

    return v
