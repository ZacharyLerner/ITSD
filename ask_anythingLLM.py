import requests
import time
import os
from dotenv import load_dotenv
load_dotenv()

def ask_anythingllm(question):
    # AnythingLLM API configuration
    base_url = os.getenv('ANYTHINGLLM_URL')
    api_key = os.getenv('ANYTHINGLLM_API_KEY')
    workspace_slug = os.getenv('ANYTHINGLLM_WORKSPACE')
    
    endpoint = f"{base_url}/api/v1/workspace/{workspace_slug}/chat"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    request_body = {
        "message": question,
        "mode": "chat",  # or "query" for just RAG without conversation
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
        
        return response_data.get('textResponse', 'No response received.')
            
    except requests.exceptions.RequestException as e:
        return f"An error occurred while communicating with AnythingLLM: {str(e)}"