"""
Quick diagnostic: lists every model your Groq API key currently has access to.
Run this if you get a 'model not found' error from run_diagnosis.py.

Usage:
    python check_models.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    print("ERROR: GROQ_API_KEY not found. Make sure your .env file exists and contains GROQ_API_KEY=your-key")
    exit(1)

url = "https://api.groq.com/openai/v1/models"
headers = {"Authorization": f"Bearer {api_key}"}

response = requests.get(url, headers=headers)

if response.status_code != 200:
    print(f"Request failed with status {response.status_code}")
    print(response.text)
else:
    data = response.json()
    print("Models available to your API key:\n")
    for model in data.get("data", []):
        print(" -", model.get("id"))