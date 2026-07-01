from os import path as os_path
from json import dumps, loads, JSONDecodeError
from datetime import datetime, timedelta
import re
import requests
import getpass

from dotenv import load_dotenv
import os
import LLM_Upload_Manager as llm_upload_manager

load_dotenv()

instance = os.getenv("instance")
BASE_URL = f"https://{instance}.service-now.com"

USERNAME = os.getenv("SN_USERNAME")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

import logging as log

log.basicConfig(format="%(levelname)s:%(message)s", level=log.ERROR)

TOKEN_FILE = "refresh.token"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LLM_FILES_FOLDER = os.path.join(BASE_DIR, "LLM_Files")
KB_SUMMARY_FOLDER = os.path.join(LLM_FILES_FOLDER, "kb_docs")
KB_CONTENT_FOLDER = os.path.join(LLM_FILES_FOLDER, "kb_docs_with_content")
KB_DOC_FOLDERS = (KB_SUMMARY_FOLDER,)

llm_upload_manager.LOCATIONS_FILE = os.path.join(BASE_DIR, "document_locations.json")


def update_access_token(srv_token={}):
    """Renew an access_toekn using an existing refresh_token.

    Use a refresh_token provided from the format stored in the file TOKEN_FILE to
    obtain a valid access_token for future requests. It will update the file
    TOKEN_FILE with the updated response.

    Keyword arguments
    srv_token -- the file contents of TOKEN_FILE as a dict
    """
    if not bool(srv_token.get("refresh_token")):
        log.error("No refresh token found while trying to retrieve access token")
        return ""

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache",
    }
    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": srv_token["refresh_token"],
        "scope": "table_read",
    }
    url = f"{BASE_URL}/oauth_token.do"

    try:
        response = requests.post(url, data=payload, headers=headers)
    except Exception as e:
        log.error(f"Exception in server request to renew access token: {e}")

    if response.status_code and response.status_code != 200:
        log.error("Error in refreshing access token from server.")
        log.debug(f"\tResponse Code: {response.status_code}")
        log.debug(f"\tResponse Full-Headers: {response.headers}")
        log.debug(f"\tResponse Body: {response.text}")
        return ""

    try:
        new_token = response.json()
    except requests.exceptions.JSONDecodeError:
        log.error(
            "Response does not contain valid JSON, unable to refresh access token"
        )

    log.debug(new_token)
    with open(TOKEN_FILE, "w") as fh:
        new_token["expires_at"] = (
            datetime.now() + timedelta(0, new_token["expires_in"])
        ).isoformat()
        fh.write(dumps(new_token))

    return new_token["access_token"]


def get_access_token(force_renew=False):
    """Retrieve a valid access token to make subsequent queries.

    Attempt to retrieve an access token stored in a local file TOKEN_FILE. If the
    file does not exist the caller will be prompted for a password to retrieve
    a new refresh token. If the access token is expired it will use the refresh_token
    to renew it.

    Keyword arguments:
    force_renew -- bool, update the access token even if not expired
    """
    # Check to see if we have a valid token file
    if os_path.exists(TOKEN_FILE):
        log.debug("Found refresh token file.")
        with open(TOKEN_FILE, "r") as token_file:
            try:
                srv_token = loads(token_file.read())
            except JSONDecodeError as e:
                log.error(f"Invalid TOKEN_FILE error {e}")
                return ""

            access_token_expiration = datetime.fromisoformat(srv_token["expires_at"])

            # Refresh the access token if needed
            if access_token_expiration > datetime.now() and not force_renew:
                log.debug("Found valid access token")
                return srv_token["access_token"]
            else:
                return update_access_token(srv_token)

    # Otherwise report to the user to get a refresh token
    else:
        log.info("No Refresh or Access token found!")

        # Interactively ask the user enter the account passsword
        password = getpass.getpass(prompt="Enter SD-SN service account password: ")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        }
        payload = {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": USERNAME,
            "password": password,
            "scope": "table_read",
        }
        url = f"{BASE_URL}/oauth_token.do"

        try:
            response = requests.post(url, data=payload, headers=headers)
        except Exception as e:
            log.error(f"Exception in network attempting to get refresh token: {e}")

        if response.status_code != 200:
            log.error("Error in acquiring server token.")
            log.debug(f"\tResponse Code: {response.status_code}")
            log.debug(f"\tResponse Full-Headers: {response.headers}")
            log.debug(f"\tResponse Body: {response.text}")
            return ""

        try:
            srv_token = response.json()
        except requests.exceptions.JSONDecodeError:
            log.error(
                "Response does not contain valid JSON, unable to retrieve refresh token"
            )

        with open(TOKEN_FILE, "w") as fh:
            srv_token["expires_at"] = (
                datetime.now() + timedelta(0, srv_token["expires_in"])
            ).isoformat()
            fh.write(dumps(srv_token))

        return srv_token["access_token"]


def incident_query(access_token, one_shot=False):
    """Query NEW incidents assigned to the 'Service Desk Students' group

    This function uses an access token to query and return the count of NEW incidents. That
    are assigned to the group 'Service Desk Students' identified by the internal
    sys_id of the group: 6555506a47995d50d544d698436d4367.

    Keyword arguments:
    access_token -- the access token string
    one_shot -- bool, attempt recursive access_token renewal on 401 error
    """

    if not access_token:
        log.error("Incident query failed with empty access_token.")
        return ""

    # Construct the request using url endpoint, headers, and query paramters
    url = f"{BASE_URL}/api/now/table/incident"
    query_params = {
        "sysparm_query": "assignment_group=6555506a47995d50d544d698436d4367^state=1",
        "sysparm_fields": "number, state",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Cache-Control": "no-cache",
    }

    try:
        response = requests.get(url, params=query_params, headers=headers)
    except Exception as e:
        log.error(f"Exception in network attempt: {e}")

    # Check if the request was successful
    if response.status_code == 200:
        log.debug(f"Query Respons e Body")
        log.debug(response.text)

        try:
            inc_query = response.json()
        except requests.exceptions.JSONDecodeError:
            log.error(
                "Response does not contain valid JSON, unable to retrieve refresh token"
            )
            return (
                "Response does not contain valid JSON, unable to retrieve refresh token"
            )

        # Get the result array and sum up the count
        incidents = inc_query.get("result", [])
        return len(incidents)

    elif response.status_code == 401 and not one_shot:
        return incident_query(get_access_token(force_renew=True), one_shot=True)
    else:
        log.error(f"Server responded with {response.status_code}")
        return f"Incident query unable to complete, server responded {response.status_code}"


def get_kb_category_children(category_id, access_token, one_shot=False):
    url = f"{BASE_URL}/api/now/table/kb_category"
    query_params = {
        "sysparm_query": f"parent_id={category_id}^active=true",
        "sysparm_limit": 200,
        "sysparm_fields": "sys_id,label,parent_id",
    }
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}

    response = requests.get(url, params=query_params, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("result", [])
    elif response.status_code == 401 and not one_shot:
        new_access_token = get_access_token(force_renew=True)
        if not new_access_token:
            log.error(f"Category query failed: unable to refresh access token for {category_id}")
            return []

        return get_kb_category_children(category_id, new_access_token, one_shot=True)

    else:
        log.error(f"Error fetching child KB categories for {category_id}: {response.text}")
        return []


def get_kb_category_tree(category_id, access_token):
    category_ids = [category_id]
    seen_category_ids = {category_id}
    pending_category_ids = [category_id]

    while pending_category_ids:
        parent_id = pending_category_ids.pop()
        for child in get_kb_category_children(parent_id, access_token):
            child_id = child.get("sys_id")
            if child_id and child_id not in seen_category_ids:
                seen_category_ids.add(child_id)
                category_ids.append(child_id)
                pending_category_ids.append(child_id)

    return category_ids


def get_kb(subcategory, access_token, one_shot=False):
    url = f"{BASE_URL}/api/now/table/kb_knowledge"
    category_ids = get_kb_category_tree(subcategory, access_token)
    category_ids = [
        category_id
        for category_id in category_ids if category_id != "42d53f95c350b250e6922b8dc00131cd"
    ]
    query = (
        "kb_knowledge_base=dfc19531bf2021003f07e2c1ac0739ab"
        f"^kb_categoryIN{','.join(category_ids)}"
        "^latest=true"
        "^workflow_state=published"
        "^active=true"
    )
    query_params = {
        "sysparm_query": query,
        "sysparm_limit": 200,
        "sysparm_fields": (
            "number,short_description,meta_description,text,sys_id,"
            "kb_category,latest,workflow_state,active"
        ),
    }

    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}

    response = requests.get(url, params=query_params, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("result", [])
    elif response.status_code == 401 and not one_shot:
        new_access_token = get_access_token(force_renew=True)
        if not new_access_token:
            log.error(f"KB query failed: unable to refresh access token for {subcategory}")
            return []
        
        return get_kb(subcategory, new_access_token, one_shot=True)

    else:
        log.error(f"Error fetching KBs for subcategory {subcategory}: {response.text}")
        return []
    

# Function to gather docs for a list of subcategory ids
def gather_docs(subcategory_ids, seen_texts=None, access_token=None):
    if seen_texts is None:
        seen_texts = set()

    os.makedirs(KB_SUMMARY_FOLDER, exist_ok=True)
    os.makedirs(KB_CONTENT_FOLDER, exist_ok=True)

    for subcategory_id in subcategory_ids:
        try:
            access_token = get_access_token()
        except Exception as e:
            print(f"Error getting access token: {e}")
            return []

        records = get_kb(subcategory_id, access_token)

        for record in records:
            short_desc = record.get("short_description", "").strip()
            meta_desc = record.get("meta_description", "").strip()
            text_key = (short_desc.lower(), meta_desc.lower())
            article_content = record.get("text", "").strip()

            if text_key not in seen_texts:
                seen_texts.add(text_key)
                display_number = record.get("number", "")
                link = f"https://{instance}.service-now.com/kb?id=kb_article_view&sysparm_article={display_number}"

                safe_name = display_number or record.get("sys_id", "unknown")

                summary_doc = {
                    "number": display_number,
                    "short_description": short_desc,
                    "meta_description": meta_desc,
                    "link": link,
                }

                content_doc = {
                    "number": display_number,
                    "short_description": short_desc,
                    "meta_description": meta_desc,
                    "link": link,
                    "content": article_content,
                }

                summary_path = os.path.join(KB_SUMMARY_FOLDER, f"{safe_name}.json")
                content_path = os.path.join(KB_CONTENT_FOLDER, f"{safe_name}.json")

                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(dumps(summary_doc, indent=2, ensure_ascii=False))

                with open(content_path, "w", encoding="utf-8") as f:
                    f.write(dumps(content_doc, indent=2, ensure_ascii=False))

    return

def get_all_docs():
    gather_docs(["1c022b1683da861095c6e6d0deaad350"]) # Accounts and Access
    gather_docs(["a559edc74720ced0d544d698436d439e"]) # Communication and Collaboration
    gather_docs(["ee3ff96147786d1021080678436d43eb"]) # Help and Support
    gather_docs(["6521302197f0ba106cf6347e6253afdc"]) # Learning and Development
    gather_docs(["2bde140597c64650917fbf98c253af74"]) # Network and Connectivity
    gather_docs(["8eacc63c975eda50917fbf98c253af37"]) # Security and Privacy
    gather_docs(["152fb96147786d1021080678436d4314"]) # Software and Applications
    gather_docs(["a8fbdbcc470d0a1021080678436d4359"]) # Student Life


def _kb_doc_paths():
    doc_paths = []
    for folder in KB_DOC_FOLDERS:
        if not os.path.isdir(folder):
            continue

        for file_name in sorted(os.listdir(folder)):
            file_path = os.path.join(folder, file_name)
            if os.path.isfile(file_path) and file_name.endswith(".json"):
                doc_paths.append(file_path)

    return doc_paths


def _candidate_absolute_paths(file_name):
    if os.path.isabs(file_name):
        return {os.path.abspath(file_name)}

    return {
        os.path.abspath(file_name),
        os.path.abspath(os.path.join(BASE_DIR, file_name)),
    }


def _is_kb_doc_path(file_name):
    candidate_paths = _candidate_absolute_paths(file_name)
    kb_folders = {os.path.abspath(folder) for folder in KB_DOC_FOLDERS}

    for candidate_path in candidate_paths:
        if any(os.path.dirname(candidate_path) == folder for folder in kb_folders):
            return True

    return False


def _tracked_kb_doc_keys():
    locations = llm_upload_manager.load_locations()
    return [
        file_name
        for file_name in locations
        if _is_kb_doc_path(file_name)
    ]


def _tracked_key_for_path(file_path):
    absolute_file_path = os.path.abspath(file_path)

    for file_name in _tracked_kb_doc_keys():
        if absolute_file_path in _candidate_absolute_paths(file_name):
            return file_name

    return None


def deleteAll():
    results = {
        "deleted_uploads": [],
        "deleted_local_files": [],
        "errors": [],
    }

    for file_name in _tracked_kb_doc_keys():
        try:
            response = llm_upload_manager.full_delete(file_name)
            if "error" in response:
                results["errors"].append({"file": file_name, "error": response["error"]})
            else:
                results["deleted_uploads"].append(file_name)
        except Exception as e:
            results["errors"].append({"file": file_name, "error": str(e)})

    for file_path in _kb_doc_paths():
        try:
            os.remove(file_path)
            results["deleted_local_files"].append(file_path)
        except OSError as e:
            results["errors"].append({"file": file_path, "error": str(e)})

    return results

def uploadAll():
    results = {
        "uploaded": [],
        "errors": [],
    }

    for file_path in _kb_doc_paths():
        tracked_key = _tracked_key_for_path(file_path)
        if tracked_key:
            try:
                delete_response = llm_upload_manager.full_delete(tracked_key)
                if "error" in delete_response:
                    results["errors"].append({
                        "file": tracked_key,
                        "error": delete_response["error"],
                    })
                    continue
            except Exception as e:
                results["errors"].append({"file": tracked_key, "error": str(e)})
                continue

        try:
            response = llm_upload_manager.full_upload(file_path)
            results["uploaded"].append({
                "file": file_path,
                "response": response,
            })
        except Exception as e:
            results["errors"].append({"file": file_path, "error": str(e)})

    return results


def reuploadAll():
    delete_result = deleteAll()
    get_all_docs()
    upload_result = uploadAll()

    return {
        "delete": delete_result,
        "upload": upload_result,
    }
    
def get_ticket_emails(ticket_sys_id, access_token):
    url = f"{BASE_URL}/api/now/table/sys_email"

    query_params = {
        "sysparm_query": f"instance={ticket_sys_id}^ORDERBYsys_created_on",
        "sysparm_fields": "sys_created_on,type,subject,body_text,body,recipients,user",
        "sysparm_display_value": "true",
    }

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, params=query_params, headers=headers)
    response.raise_for_status()

    return response.json().get("result", [])

def get_ticket_activity(ticket_sys_id, access_token):
    url = f"{BASE_URL}/api/now/table/sys_journal_field"

    query_params = {
        "sysparm_query": f"element_id={ticket_sys_id}^ORDERBYsys_created_on",
        "sysparm_fields": "sys_created_on,sys_created_by,name,element,value",
        "sysparm_display_value": "true",
    }

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, params=query_params, headers=headers)
    response.raise_for_status()

    return response.json().get("result", [])
    
def getTicket(ticket_number):
    access_token = get_access_token()

    url = f"{BASE_URL}/api/now/table/incident"
    query_params = {
        "sysparm_query": f"number={ticket_number}",
        "sysparm_limit": 1,
        "sysparm_display_value": "true",
        "sysparm_fields": "sys_id,number,short_description,description,state,assigned_to,opened_by,opened_at",
    }

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, params=query_params, headers=headers)
    data = response.json()
    results = data.get("result", [])

    if not results:
        return None

    ticket = results[0]
    ticket_sys_id = ticket["sys_id"]

    ticket["activity"] = get_ticket_activity(ticket_sys_id, access_token)
    ticket["emails"] = get_ticket_emails(ticket_sys_id, access_token)
    return ticket

def format_ticket_for_llm(ticket):
    title = ticket.get("short_description", "").strip()
    description = ticket.get("description", "").strip()
    ticket_number = ticket.get("number", "").strip()

    def clean_text(text):
        text = text or ""

        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</p>|</div>|</tr>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)

        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")

        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                continue
            if line.lower().startswith("reply from:"):
                continue
            lines.append(line)

        return "\n".join(lines).strip()

    def remove_quoted_email(text):
        if "\nOn " in text:
            text = text.split("\nOn ", 1)[0].strip()
        return text.strip()

    def remove_footer(text):
        stop_markers = [
            "About this request",
            "About this incident",
            "Short description:",
            "You can view your request",
            "You can view the incident",
            "View incident",
            "Thank you,",
            "Unsubscribe",
            "Ref:MSG",
        ]

        for marker in stop_markers:
            if marker in text:
                text = text.split(marker, 1)[0].strip()

        return text.strip()

    def extract_sent_comment(text):
        text = clean_text(text)

        # ServiceNow templates usually contain one of these before the real comment.
        patterns = [
            rf"A comment has been added to\s+{ticket_number}\s*:",
            rf".+? left a comment on\s+{ticket_number}\s*:",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                text = text[match.end():].strip()
                return remove_footer(text)

        return ""

    def dedupe_key(text):
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^a-z0-9]+", "", text)
        return text

    def add_message(messages, seen, created, speaker, body):
        body = clean_text(body)
        body = remove_quoted_email(body)
        body = remove_footer(body)

        if not body:
            return

        if body == description:
            return

        key = dedupe_key(body)
        if not key or key in seen:
            return

        seen.add(key)
        messages.append({
            "created": created or "",
            "speaker": speaker or "Unknown",
            "body": body,
        })

    messages = []
    seen = set()

    # Include clean activity if ServiceNow provides it.
    for item in ticket.get("activity", []):
        element = item.get("element", "")
        if element not in ("comments", "work_notes"):
            continue

        created = item.get("sys_created_on", "")
        author = item.get("sys_created_by", "")
        body = item.get("value", "")

        if element == "work_notes":
            speaker = f"Internal note ({author})" if author else "Internal note"
        else:
            speaker = author or "Ticket comment"

        add_message(messages, seen, created, speaker, body)

    for email in ticket.get("emails", []):
        email_type = email.get("type", "")
        subject = email.get("subject", "")
        created = email.get("sys_created_on", "")
        sender = email.get("user", "")

        raw_body = email.get("body_text") or email.get("body") or ""

        if email_type == "received":
            speaker = f"User ({sender})" if sender else "User"
            body = raw_body

        elif email_type == "sent":
            # Only keep sent emails that are actual comment notifications.
            if "Comment added" not in subject:
                continue

            speaker = "IT Service Desk"
            body = extract_sent_comment(raw_body)

        else:
            continue

        add_message(messages, seen, created, speaker, body)

    def sort_time(message):
        try:
            return datetime.strptime(message["created"], "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            return datetime.max

    messages.sort(key=sort_time)

    conversation = "\n\n".join(
        f"{message['created']} - {message['speaker']}:\n{message['body']}"
        for message in messages
    )

    return f"""Title:
{title}

Description:
{description}

Conversation:
{conversation}
"""

def ticketInfo(ticket_number):
    ticket = getTicket(ticket_number)
    if not ticket:
        return f"No ticket found with number {ticket_number}."
    formatted_ticket = format_ticket_for_llm(ticket)
    return formatted_ticket

