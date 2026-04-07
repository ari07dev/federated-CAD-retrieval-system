"""
Enhanced silhouette & shape feature extraction for sketch-based search.
Provides multiple preprocessing strategies and contour-based features.
"""
import cv2
import numpy as np


def extract_silhouette(img):
    """Extract binary silhouette using adaptive thresholding (better for varied sketches)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # CLAHE for contrast enhancement (handles faint pencil lines)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    # Adaptive threshold (handles uneven lighting better than Otsu)
    th = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15, C=8
    )
    
    # Morphological cleanup — close gaps, remove noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
    
    return th


def extract_edges(img):
    """Extract clean edges using Canny (matches edge-encoded DB images)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    # Bilateral filter — smooth while preserving edges
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Auto Canny thresholds
    median = np.median(gray)
    low = int(max(0, 0.5 * median))
    high = int(min(255, 1.5 * median))
    
    edges = cv2.Canny(gray, low, high)
    
    # Dilate slightly to connect broken edges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    edges = cv2.dilate(edges, kernel, iterations=1)
    
    return edges


def center_crop(bin_img, size=256):
    """Crop to bounding box of content and resize with padding to preserve aspect ratio."""
    pts = cv2.findNonZero(bin_img)
    if pts is None:
        return cv2.resize(bin_img, (size, size))
    
    x, y, w, h = cv2.boundingRect(pts)
    crop = bin_img[y:y+h, x:x+w]
    
    # Preserve aspect ratio with padding
    max_dim = max(w, h)
    pad = int(max_dim * 0.1)  # 10% padding
    canvas = np.zeros((max_dim + 2*pad, max_dim + 2*pad), dtype=np.uint8)
    
    y_offset = (max_dim + 2*pad - h) // 2
    x_offset = (max_dim + 2*pad - w) // 2
    canvas[y_offset:y_offset+h, x_offset:x_offset+w] = crop
    
    return cv2.resize(canvas, (size, size))


def normalize_rotation(bin_img):
    """Normalize rotation using image moments (PCA-like alignment)."""
    m = cv2.moments(bin_img)
    
    if abs(m["mu20"]) < 1e-6:
        return bin_img
    
    angle = 0.5 * np.arctan2(
        2*m["mu11"],
        m["mu20"] - m["mu02"]
    )
    angle = angle * 180 / np.pi
    
    h, w = bin_img.shape
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    
    return cv2.warpAffine(bin_img, M, (w, h))


def compute_hu_moments(bin_img):
    """Compute log-transformed Hu moments (rotation/scale invariant shape descriptor)."""
    m = cv2.moments(bin_img)
    hu = cv2.HuMoments(m).flatten()
    
    # Log transform for better numerical stability
    hu = -np.sign(hu) * np.log10(np.abs(hu) + 1e-10)
    
    return hu.astype("float32")


def compute_contour_features(bin_img):
    """Extract contour-based shape features for structural comparison."""
    contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return np.zeros(8, dtype="float32")
    
    # Use largest contour
    cnt = max(contours, key=cv2.contourArea)
    
    area = cv2.contourArea(cnt)
    perimeter = cv2.arcLength(cnt, True)
    
    # Shape descriptors
    circularity = (4 * np.pi * area / (perimeter**2 + 1e-6))
    
    # Bounding rect aspect ratio
    _, _, w, h = cv2.boundingRect(cnt)
    aspect = w / (h + 1e-6)
    
    # Convexity
    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull)
    solidity = area / (hull_area + 1e-6)
    
    # Extent (ratio of contour area to bounding rect area)
    extent = area / (w * h + 1e-6)
    
    # Hu moments of this contour
    hu = compute_hu_moments(bin_img)[:4]  # First 4 Hu moments
    
    features = np.array([circularity, aspect, solidity, extent] + hu.tolist(), dtype="float32")
    return features


def preprocess_for_clip(img, size=224):
    """
    Full preprocessing pipeline for sketch → CLIP encoding.
    Returns a clean RGB PIL-compatible image.
    """
    # Extract silhouette
    sil = extract_silhouette(img)
    
    # Center and crop with aspect ratio preservation
    cropped = center_crop(sil, size)
    
    # Normalize rotation
    normed = normalize_rotation(cropped)
    
    # Convert binary to 3-channel (white lines on dark background → invert for CLIP)
    # CLIP expects natural-looking images, so white background + dark lines
    inverted = cv2.bitwise_not(normed)
    rgb = cv2.cvtColor(inverted, cv2.COLOR_GRAY2RGB)
    
    return rgb


def preprocess_db_image_edges(img, size=224):
    """
    Extract edges from a database image to create an edge-based representation.
    This bridges the domain gap between clean DB images and hand-drawn sketches.
    """
    edges = extract_edges(img)
    cropped = center_crop(edges, size)
    
    # White background, dark edges (same domain as processed sketches)
    inverted = cv2.bitwise_not(cropped)
    rgb = cv2.cvtColor(inverted, cv2.COLOR_GRAY2RGB)
    
    return rgb
