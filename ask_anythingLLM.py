import requests
import time
import os
from dotenv import load_dotenv
import json
load_dotenv()

def ask_anythingllm(question, ticket=None):
    # LLM RAG Backend API configuration
    base_url = os.getenv('LLM_BACKEND_URL', 'http://10.140.2.31:3001')
    api_key = os.getenv('LLM_BACKEND_API_KEY')
    workspace_slug = os.getenv('LLM_BACKEND_WORKSPACE')
    DATA_FOLDER = "data"
    file = "LLM_Source_Data.json"

    endpoint = f"{base_url}/workspace/{workspace_slug}/query"

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    if ticket:
        request_body = {
            "question": question + "\n\nTicket Information:\n" + ticket
        }
        print("Request body with ticket information:", request_body)
    else:
        request_body = {
            "question": question
        }

    start_time = time.time()
    try:
        response = requests.post(endpoint, headers=headers, json=request_body)
        response.raise_for_status()

        end_time = time.time()
        print(f"LLM Backend response time: {end_time - start_time} seconds")

        response_data = response.json()

        # sources is {"documents": [...], "web": [...]} — extract the documents list
        raw_sources = response_data.get('sources', [])
        if isinstance(raw_sources, dict):
            sources = raw_sources.get('documents', [])
        else:
            sources = raw_sources  # backwards compat if format ever reverts

        source_text = ""
        for source in sources:
            filename = source.get('filename') or ''
            source_text += filename.replace(",", "") + ", "
            print(filename)

        source_text = source_text[:-2] if source_text else ""
        os.makedirs(DATA_FOLDER, exist_ok=True)

        filepath = os.path.join(DATA_FOLDER, file)

        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    f.seek(0)
                    data = [json.loads(line) for line in f if line.strip()]
        else:
            data = []

        data.append(source_text)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        return response_data.get('answer', 'No response received.')

    except requests.exceptions.RequestException as e:
        return f"An error occurred while communicating with the LLM backend: {str(e)}"
