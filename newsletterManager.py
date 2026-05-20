import os
from datetime import datetime
from dotenv import load_dotenv
from newsletterLLMCalls import classify_message, classify_ticket, create_weekly_newsletter
import json

load_dotenv()


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


def _make_entry(message, timestamp=None):
    """Wrap a message with an ISO-8601 timestamp."""
    if timestamp is None:
        timestamp = datetime.now().isoformat(timespec='seconds')
    elif isinstance(timestamp, datetime):
        timestamp = timestamp.isoformat(timespec='seconds')
    return {"timestamp": timestamp, "message": message}


def check_jabber_message(jabber_message, timestamp=None):
    API_BASE = os.getenv("API_BASE")
    MODEL = os.getenv("ITSD_DEV_MODEL_HAIKU")
    API_KEY = os.getenv("ITSD_DEV_API_KEY")

    response = classify_message(API_BASE, MODEL, API_KEY, jabber_message)
    if response == 1:
        _append_to_json(
            'newsletter_files/jabber_data.json',
            _make_entry(jabber_message, timestamp),
        )


def check_ticket_message(ticket_message, timestamp=None):
    API_BASE = os.getenv("API_BASE")
    MODEL = os.getenv("ITSD_DEV_MODEL_HAIKU")
    API_KEY = os.getenv("ITSD_DEV_API_KEY")

    response = classify_ticket(API_BASE, MODEL, API_KEY, ticket_message)
    if response == 1:
        _append_to_json(
            'newsletter_files/sn_ticket_help_data.json',
            _make_entry(ticket_message, timestamp),
        )


def write_professional_chat(professional_chat_message, timestamp=None):
    _append_to_json(
        'newsletter_files/professional_chat_data.json',
        _make_entry(professional_chat_message, timestamp),
    )


def write_newsletter_managed():
    jabber_filename = 'newsletter_files/jabber_data.json'
    sn_filename = 'newsletter_files/sn_ticket_help_data.json'
    professional_filename = 'newsletter_files/professional_chat_data.json'

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

    return create_weekly_newsletter(API_BASE, MODEL, API_KEY, jabber_json, sn_json, professional_json)