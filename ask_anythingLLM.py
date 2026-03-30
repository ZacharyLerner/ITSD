import requests
import time
import os
from dotenv import load_dotenv
import json
load_dotenv()

def ask_anythingllm(question):
    # AnythingLLM API configuration
    base_url = os.getenv('ANYTHINGLLM_URL')
    api_key = os.getenv('ANYTHINGLLM_API_KEY')
    workspace_slug = os.getenv('ANYTHINGLLM_WORKSPACE')
    DATA_FOLDER = "data"
    file = "LLM_Source_Data.json"
    
    endpoint = f"{base_url}/api/v1/workspace/{workspace_slug}/chat"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    request_body = {
        "message": question,
        "mode": "query",  # or "query" for just RAG without conversation
        "reset": True
    }

    start_time = time.time()
    try:
        response = requests.post(endpoint, headers=headers, json=request_body)
        response.raise_for_status()
        
        end_time = time.time()
        print(f"AnythingLLM response time: {end_time - start_time} seconds")
        
        response_data = response.json()
        
        if response_data.get('error'):
            return f"Error from AnythingLLM: {response_data['error']}"
        
        
        sources = (response_data.get('sources'))

        source_text = ""
        for source in sources:
            source_text += source.get('title').replace(",","") + ", "
            print(source.get('title'))

        source_text = source_text[:-2]
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
        
        return response_data.get('textResponse', 'No response received.')
            
    except requests.exceptions.RequestException as e:
        return f"An error occurred while communicating with AnythingLLM: {str(e)}"