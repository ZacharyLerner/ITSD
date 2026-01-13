import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

# This file allows for control of the Anything LLM Backend for File Upload

# Configuration
# ---------------------------------------------------------------------- #
LOCATIONS_FILE = "document_locations.json"
LLM_ENDPOINT_URL = f"{os.getenv('ANYTHINGLLM_URL')}/api/v1"
API_KEY = os.getenv('ANYTHINGLLM_API_KEY')
WORKSPACE_SLUG = os.getenv("ANYTHINGLLM_WORKSPACE")
HEADERS = {'Authorization': f'Bearer {API_KEY}'}
# ---------------------------------------------------------------------- #

# File Store Helpers
# ---------------------------------------------------------------------- #
def load_locations():
    if not os.path.exists(LOCATIONS_FILE):
        return {}
    with open(LOCATIONS_FILE, 'r') as f:
        return json.load(f)

def save_location(file_name, doc_location):
    locations = load_locations()
    # Get the file's modification timestamp
    mtime = os.path.getmtime(file_name) if os.path.exists(file_name) else None
    locations[file_name] = {
        "location": doc_location,
        "workspace": WORKSPACE_SLUG,
        "timestamp": mtime
    }
    with open(LOCATIONS_FILE, 'w') as f:
        json.dump(locations, f, indent=2)

def remove_location(file_name):
    locations = load_locations()
    if file_name in locations:
        del locations[file_name]
        with open(LOCATIONS_FILE, 'w') as f:
            json.dump(locations, f, indent=2)

def get_location(file_name):
    locations = load_locations()
    entry = locations.get(file_name)
    return entry["location"] if entry else None

def get_timestamp(file_name):
    """Gets the stored timestamp for a file."""
    locations = load_locations()
    entry = locations.get(file_name)
    return entry.get("timestamp") if entry else None
# ---------------------------------------------------------------------- #

# Document Handlers
# ---------------------------------------------------------------------- #
def upload_doc(file_name):
    """Uploads document to general file area."""
    url = f"{LLM_ENDPOINT_URL}/document/upload"
    with open(file_name, 'rb') as f:
        response = requests.post(url, headers=HEADERS, files={'file': f})
    return response.json()

def embed_doc(document_location):
    """Embeds document into Vector DB for specific workspace."""
    url = f"{LLM_ENDPOINT_URL}/workspace/{WORKSPACE_SLUG}/update-embeddings"
    body = {"adds": [document_location], "deletes": []}
    response = requests.post(url, headers=HEADERS, json=body)
    return response.json()

def delete_embed(document_location):
    """Deletes embedded document from Vector DB."""
    url = f"{LLM_ENDPOINT_URL}/workspace/{WORKSPACE_SLUG}/update-embeddings"
    body = {"adds": [], "deletes": [document_location]}
    response = requests.post(url, headers=HEADERS, json=body)
    return response.json()

def delete_doc(document_location):
    """Deletes document from system storage."""
    url = f"{LLM_ENDPOINT_URL}/system/remove-documents"
    body = {"names": [document_location]}
    response = requests.delete(url, headers=HEADERS, json=body)
    return response.json()
# ---------------------------------------------------------------------- #

# Main Functions (Use These)
# ---------------------------------------------------------------------- #
def full_upload(file_name):
    """Uploads file, embeds it, and saves location with timestamp to JSON."""
    upload_resp = upload_doc(file_name)
    doc_location = upload_resp["documents"][0]["location"]
    embed_resp = embed_doc(doc_location)
    save_location(file_name, doc_location)
    return embed_resp

def full_delete(file_name):
    """Deletes document from Vector DB and system storage using stored location."""
    location = get_location(file_name)
    if not location:
        return {"error": f"No stored location found for {file_name}"}
    
    embed_resp = delete_embed(location)
    doc_resp = delete_doc(location)
    remove_location(file_name)
    return {"embed": embed_resp, "doc": doc_resp}

def update_doc(file_name):
    """Deletes and re-uploads a document."""
    full_delete(file_name)
    full_upload(file_name)
    print("Document Updated")

def check_needs_update(file_name):
    """Checks if a file needs to be updated based on timestamp comparison."""
    stored_timestamp = get_timestamp(file_name)
    if stored_timestamp is None:
        return False  # File not tracked, not an update scenario
    
    if not os.path.exists(file_name):
        return False  # File doesn't exist
    
    current_timestamp = os.path.getmtime(file_name)
    return current_timestamp > stored_timestamp
# ---------------------------------------------------------------------- #