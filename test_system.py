import unittest
import numpy as np
import os
import shutil
from ai_encoder import encoder
from generation.cad_synthesis import generate_model

class TestSystem(unittest.TestCase):
    def test_text_encoder(self):
        print("\nTesting Text Encoder...")
        vec = encoder.encode_text("fuel tank")
        self.assertEqual(vec.shape, (384,))
        self.assertTrue(np.linalg.norm(vec) > 0)
        
    def test_image_encoder(self):
        print("\nTesting Image Encoder...")
        # Create dummy image
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        vec = encoder.encode_image(img)
        self.assertEqual(vec.shape, (512,))
        
    def test_generation(self):
        print("\nTesting Generation...")
        res = generate_model("tank 500")
        self.assertIn("file", res)
        self.assertTrue(res["file"].endswith(".pdf"), f"Expected .pdf file, got: {res['file']}")
        self.assertTrue(os.path.exists(os.path.join(r"C:\Users\scs83\PhysicalProbe\static", res["file"])))
        print(f"Generated: {res['file']}")

if __name__ == "__main__":
    unittest.main()
