
import os
import sys
# Add the compiled directory to the path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

KEY = os.environ.get("GOOGLE_API_KEY")
if not KEY:
    print("No API Key found")
else:
    genai.configure(api_key=KEY)
    try:
        print("Listing models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print(e)
