from LLM_Upload_Manager import full_delete, full_upload, update_doc, check_needs_update, get_timestamp
import os
import json

LOCATIONS_FILE = "document_locations.json"
FILE_DIRECTORY = "LLM_Files"

def load_locations():
    if not os.path.exists(LOCATIONS_FILE):
        return {}
    with open(LOCATIONS_FILE, 'r') as f:
        return json.load(f)

def update_database():
    # Get current files in directory
    current_files = set()
    for file_name in os.listdir(FILE_DIRECTORY):
        file_path = os.path.join(FILE_DIRECTORY, file_name)
        if os.path.isfile(file_path):
            current_files.add(file_path)
    
    # Get tracked files from JSON
    tracked_files = set(load_locations().keys())
    
    # Find new files to add
    new_files = current_files - tracked_files
    for file_path in new_files:
        print(f"Adding: {file_path}")
        full_upload(file_path)
    
    # Find deleted files to remove
    deleted_files = tracked_files - current_files
    for file_path in deleted_files:
        print(f"Removing: {file_path}")
        full_delete(file_path)
    
    # Check existing files for timestamp changes (modified files)
    existing_files = current_files & tracked_files
    for file_path in existing_files:
        if check_needs_update(file_path):
            print(f"Updating (modified): {file_path}")
            update_doc(file_path)
    
    print("Database Updated")

def update_file(file_name):
    update_doc(file_name)
    print("Updated file")