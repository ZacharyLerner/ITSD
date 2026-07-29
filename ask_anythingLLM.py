import requests
import time
import os
from dotenv import load_dotenv
import json
import base64
import litellm
from PIL import Image, ImageOps
from io import BytesIO
load_dotenv()

def ask_anythingllm(question, ticket=None, image_urls=None, message_id=None):
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

    question_sections = [question]

    # If a ticket is provided, add it to the question sections for context
    if ticket:
        question_sections.append(f"Attached Ticket/s Information:\n{ticket}")

    # If image URLs are provided, summarize the images and add the summary to the question sections for context
    if image_urls and len(image_urls) > 0:
        image_summary = summarize_images(image_urls)
        if image_summary:
            question_sections.append(f"Attached Image/s Information:\n{image_summary}")
            if message_id:
                save_image_description(message_id, image_summary)


    request_body = {
        "question": "\n\n".join(question_sections)
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

# Send images to a smaller model to summarize the image and return a text description of the image to be used as context for the main LLM
def summarize_images(image_attachments):
    API_BASE = os.getenv("API_BASE")
    MODEL = os.getenv("ITSD_DEV_MODEL_HAIKU")
    API_KEY = os.getenv("ITSD_DEV_API_KEY")

    if not image_attachments:
        return ""

    image_content = [
        {
            "type": "text",
            # Prompt for model to summarize image
            "text": (
                """You are a visual context summarizer. Given an image — and optionally the user's question or conversation context — translate it into a comprehensive, highly detailed, self-contained text description that performs well as visual context for another text-only LLM. Rules: 
                    - Output ONLY the image description. No explanation, no introductory filler, no conversational text. 
                    - NEVER ask clarifying questions. NEVER request a better image. NEVER output anything except the description itself. 
                    - If the image is extremely simple (e.g., a single icon or flat color), describe it concisely exactly as it is — do not over-expand or guess deeper meaning. 
                    - Transcribe any visible text, numbers, code, or chart data exactly as they appear. 
                    - Focus on objective visual facts: subjects, spatial relationships, colors, layout, and structural elements. 
                    - If conversation context or a specific user question is provided, ensure your description highlights the visual elements most relevant to that context. 
                    - When in doubt about an ambiguous object, describe its literal visual traits (shape, color, position) rather than guessing its identity.
                    - ONLY describe the image, do not rephrase or return the provided context.
                    """
            ),
        }
    ]

    for attachment in image_attachments:
        try:
            response = requests.get(attachment.url, timeout=20)
            response.raise_for_status()

            image_bytes = response.content
            image_bytes, content_type = compress_image_if_needed(image_bytes)
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")

            image_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{encoded_image}"
                },
            })

        except requests.exceptions.RequestException as e:
            image_content.append({
                "type": "text",
                "text": f"Could not read image {attachment.filename}: {e}",
            })

    try:
        response = litellm.completion(
            model=MODEL,
            api_key=API_KEY,
            api_base=API_BASE,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": image_content,
                }
            ],
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Error: {e}"
    

# Detect the media type of an image based on its byte signature, with a fallback option of png if the type cannot be determined.
def detect_image_media_type(image_bytes, fallback="image/png"):
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"

    if (
        image_bytes.startswith(b"RIFF")
        and len(image_bytes) >= 12
        and image_bytes[8:12] == b"WEBP"
    ):
        return "image/webp"

    return fallback


# Saves the image description to a JSON file for later retrieval, keyed by the message ID. This allows the bot to provide context for images in future interactions without needing to reprocess the image.
def save_image_description(message_id, description):
    DATA_FOLDER = "data"
    IMAGE_CONTEXT_FILE = "image_contexts.json"
    os.makedirs(DATA_FOLDER, exist_ok=True)
    filepath = os.path.join(DATA_FOLDER, IMAGE_CONTEXT_FILE)

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    data[str(message_id)] = description

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
TARGET_IMAGE_BYTES = int(3.75 * 1024 * 1024)

# Compresses images if they are above the 5MB limit of the anthropic haiku models
def compress_image_if_needed(image_bytes, max_bytes=TARGET_IMAGE_BYTES):
    if len(image_bytes) <= max_bytes:
        return image_bytes, detect_image_media_type(image_bytes)
    with Image.open(BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img)

        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            img = background
        else:
            img = img.convert("RGB")

        quality = 85

        while img.width > 1 and img.height > 1:
            output = BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            compressed = output.getvalue()

            if len(compressed) <= max_bytes:
                return compressed, "image/jpeg"

            if quality > 45:
                quality -= 10
            else:
                new_size = (
                    max(1, int(img.width * 0.85)),
                    max(1, int(img.height * 0.85)),
                )
                img = img.resize(new_size, Image.LANCZOS)
                quality = 75

        return compressed, "image/jpeg"