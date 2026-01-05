import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Load JSON string from environment variable
json_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

if not json_str:
    raise ValueError("Missing GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable")

# Convert JSON string → Python dict
json_dict = json.loads(json_str)

# Initialize Firebase only once
if not firebase_admin._apps:
    cred = credentials.Certificate(json_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()
