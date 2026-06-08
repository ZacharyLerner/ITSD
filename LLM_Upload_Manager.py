import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

# This file allows for control of the custom LLM RAG Backend for File Upload

# Configuration
# ---------------------------------------------------------------------- #
LOCATIONS_FILE = "document_locations.json"
LLM_ENDPOINT_URL = os.getenv('LLM_BACKEND_URL', 'http://10.140.2.31:3001')
API_KEY = os.getenv('LLM_BACKEND_API_KEY')
WORKSPACE_SLUG = os.getenv("LLM_BACKEND_WORKSPACE")
HEADERS = {'X-API-Key': API_KEY} if API_KEY else {}
# ---------------------------------------------------------------------- #

# File Store Helpers
# ---------------------------------------------------------------------- #
def load_locations():
    if not os.path.exists(LOCATIONS_FILE):
        return {}
    with open(LOCATIONS_FILE, 'r') as f:
        return json.load(f)

def save_location(file_name, doc_id):
    locations = load_locations()
    # Get the file's modification timestamp
    mtime = os.path.getmtime(file_name) if os.path.exists(file_name) else None
    locations[file_name] = {
        "doc_id": doc_id,
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

def get_doc_id(file_name):
    locations = load_locations()
    entry = locations.get(file_name)
    return entry["doc_id"] if entry else None

def get_timestamp(file_name):
    """Gets the stored timestamp for a file."""
    locations = load_locations()
    entry = locations.get(file_name)
    return entry.get("timestamp") if entry else None
# ---------------------------------------------------------------------- #

# Document Handlers
# ---------------------------------------------------------------------- #
def upload_and_embed(file_name, workspace_slug=None):
    """Uploads and embeds a document into the workspace in one call.

    Returns the full response JSON including doc_id and chunks_embedded.
    """
    slug = workspace_slug or WORKSPACE_SLUG
    url = f"{LLM_ENDPOINT_URL}/workspace/{slug}/embed"
    with open(file_name, 'rb') as f:
        response = requests.post(url, headers=HEADERS, files={'file': (os.path.basename(file_name), f)})
    response.raise_for_status()
    return response.json()

def delete_embed(doc_id, workspace_slug=None):
    """Deletes embedded document chunks from Vector DB by doc_id."""
    slug = workspace_slug or WORKSPACE_SLUG
    url = f"{LLM_ENDPOINT_URL}/workspace/{slug}/embed/{doc_id}"
    response = requests.delete(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()
# ---------------------------------------------------------------------- #

# Main Functions (Use These)
# ---------------------------------------------------------------------- #
def full_upload(file_name):
    """Uploads and embeds file, saves doc_id and timestamp to JSON."""
    resp = upload_and_embed(file_name)
    doc_id = resp["doc_id"]
    save_location(file_name, doc_id)
    return resp

def full_delete(file_name):
    """Deletes document from Vector DB using stored doc_id."""
    doc_id = get_doc_id(file_name)
    if not doc_id:
        return {"error": f"No stored doc_id found for {file_name}"}

    resp = delete_embed(doc_id)
    remove_location(file_name)
    return resp

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
