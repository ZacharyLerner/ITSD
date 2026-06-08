import os
from datetime import datetime
from dotenv import load_dotenv
import litellm
import json

from prompts import Newsletter_System_Prompt, Message_System_Prompt, Ticket_System_Prompt

load_dotenv()

jabber_filename = 'newsletter_files/jabber_data.json'
sn_filename = 'newsletter_files/sn_ticket_help_data.json'
professional_filename = 'newsletter_files/professional_chat_data.json'

# Local function for writing json entries 
def _append_to_json(filename, entry):
    """Ensure file exists, load it, append entry, write back."""
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        with open(filename, 'w') as file:
            json.dump([], file)

    with open(filename, 'r') as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            data = []

    data.append(entry)
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)

# function to make entries with message and timestamp
def _make_entry(message, timestamp=None):
    """Wrap a message with an ISO-8601 timestamp."""
    if timestamp is None:
        timestamp = datetime.now().isoformat(timespec='seconds')
    elif isinstance(timestamp, datetime):
        timestamp = timestamp.isoformat(timespec='seconds')
    return {"timestamp": timestamp, "message": message}

# checks jabber messages and classifies them, either writing to json or ignoring  
def check_jabber_message(jabber_message, timestamp=None):
    API_BASE = os.getenv("API_BASE")
    MODEL = os.getenv("ITSD_DEV_MODEL_HAIKU")
    API_KEY = os.getenv("ITSD_DEV_API_KEY")

    response = _classify_message(API_BASE, MODEL, API_KEY, jabber_message)
    if response == 1:
        _append_to_json(
            jabber_filename,
            _make_entry(jabber_message, timestamp),
        )

# checks service now ticket messages either writing or ignoring 
def check_ticket_message(ticket_message, timestamp=None):
    API_BASE = os.getenv("API_BASE")
    MODEL = os.getenv("ITSD_DEV_MODEL_HAIKU")
    API_KEY = os.getenv("ITSD_DEV_API_KEY")

    response = _classify_ticket(API_BASE, MODEL, API_KEY, ticket_message)
    if response == 1:
        _append_to_json(
            sn_filename,
            _make_entry(ticket_message, timestamp),
        )


# always writes all professional chat annoucments
def write_professional_chat(professional_chat_message, timestamp=None):
    _append_to_json(
        professional_filename,
        _make_entry(professional_chat_message, timestamp),
    )

# gives all local data for the LLM to write a newsletter 
def write_newsletter_managed():

    API_BASE = os.getenv("API_BASE")
    MODEL = os.getenv("ITSD_DEV_MODEL_OPUS")
    API_KEY = os.getenv("ITSD_DEV_API_KEY")

    with open(jabber_filename, 'r') as file:
        try:
            jabber_json = json.load(file)
        except json.JSONDecodeError:
            jabber_json = []

    with open(sn_filename, 'r') as file:
        try:
            sn_json = json.load(file)
        except json.JSONDecodeError:
            sn_json = []

    with open(professional_filename, 'r') as file:
        try:
            professional_json = json.load(file)
        except json.JSONDecodeError:
            professional_json = []

    return _create_weekly_newsletter(API_BASE, MODEL, API_KEY, jabber_json, sn_json, professional_json)

def clear_newsletter_files():
    os.remove(jabber_filename)
    os.remove(sn_filename)
    os.remove(professional_filename)

# Local functions for LLM calls 
# ----------------------------------------------------------------------------------------------------------------------------------------------------

def _classify_message(API_BASE, MODEL, API_KEY, message):
    System_Prompt = Message_System_Prompt
    response = litellm.completion(
        model=MODEL,               # add `openai/` prefix to model so litellm knows to route to OpenAI
        api_key=API_KEY,                  # api key to your openai compatible endpoint
        api_base=API_BASE,
        temperature=0,
        messages=[
                    {
                        "role": "system",
                        "content": System_Prompt
                    },
                    {
                        "role": "user",
                        "content": message,
                    } 
        ],
    )
    content = response.choices[0].message.content
    if content[0] == "1" or content[0] == "0":
        return int(content[0])

def _classify_ticket(API_BASE, MODEL, API_KEY, message):
    System_Prompt = Ticket_System_Prompt
    response = litellm.completion(
        model=MODEL,               # add `openai/` prefix to model so litellm knows to route to OpenAI
        api_key=API_KEY,                  # api key to your openai compatible endpoint
        api_base=API_BASE,
        temperature=0,
        messages=[
                    {
                        "role": "system",
                        "content": System_Prompt
                    },
                    {
                        "role": "user",
                        "content": message,
                    } 
        ],
    )
    content = response.choices[0].message.content
    if content[0] == "1" or content[0] == "0":
        return int(content[0])

def _create_weekly_newsletter(API_BASE, MODEL, API_KEY, jabber_json, sn_json, profession_json):
    Newsletter_Prompt = Newsletter_System_Prompt
    response = litellm.completion(
        model=MODEL,               # add `openai/` prefix to model so litellm knows to route to OpenAI
        api_key=API_KEY,                  # api key to your openai compatible endpoint
        api_base=API_BASE,
        temperature=0.7,
        messages=[
                    {
                        "role": "system",
                        "content": Newsletter_Prompt
                    },
                    {
                        "role": "user",
                        "content": f"""<announcements>
                            {profession_json}
                            </announcements>

                            <jabber>
                            {jabber_json}
                            </jabber>

                            <tickets>
                            {sn_json}
                            </tickets>""",
                    } 
        ],
    )
    return response.choices[0].message.content

