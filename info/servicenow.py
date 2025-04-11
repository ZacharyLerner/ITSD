from os import path as os_path
from json import dumps, loads, JSONDecodeError
from datetime import datetime, timedelta
import re
import requests
import getpass

from dotenv import load_dotenv
import os

instance = os.getenv('instance')
BASE_URL = BASE_URL = f"https://{instance}.service-now.com"

USERNAME = os.getenv("SN_USERNAME")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

import logging as log
log.basicConfig(format='%(levelname)s:%(message)s', level=log.ERROR)

TOKEN_FILE = 'refresh.token'

def update_access_token(srv_token = {}):
    """Renew an access_toekn using an existing refresh_token.

    Use a refresh_token provided from the format stored in the file TOKEN_FILE to
    obtain a valid access_token for future requests. It will update the file
    TOKEN_FILE with the updated response.

    Keyword arguments
    srv_token -- the file contents of TOKEN_FILE as a dict
    """
    if not bool(srv_token.get('refresh_token')):
        log.error("No refresh token found while trying to retrieve access token")
        return ''
    
    headers = {
        'Content-Type': "application/x-www-form-urlencoded",
        'Cache-Control': "no-cache",
    }
    payload = { 'grant_type': 'refresh_token',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'refresh_token': srv_token['refresh_token'],
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
        return ''
        
    try:
        new_token = response.json()
    except requests.exceptions.JSONDecodeError:
        log.error("Response does not contain valid JSON, unable to refresh access token")

    log.debug(new_token)
    with open(TOKEN_FILE, 'w') as fh:
        new_token['expires_at'] = (datetime.now() + timedelta(0,srv_token['expires_in'])).isoformat()
        fh.write(dumps(new_token))

    return new_token['access_token']


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
        with open(TOKEN_FILE, 'r') as token_file:
            try:
                srv_token = loads(token_file.read())
            except JSONDecodeError as e:
                log.error(f"Invalid TOKEN_FILE error {e}")
                return ''

            access_token_expiration = datetime.fromisoformat(srv_token['expires_at'])

            # Refresh the access token if needed
            if access_token_expiration > datetime.now() and not force_renew:
                log.debug("Found valid access token")
                return( srv_token['access_token'])
            else:
                return update_access_token(srv_token)

    # Otherwise report to the user to get a refresh token
    else:
        log.info("No Refresh or Access token found!")

        # Interactively ask the user enter the account passsword
        password = getpass.getpass(prompt='Enter SD-SN service account password: ')

        headers = {
            'Content-Type': "application/x-www-form-urlencoded",
            'Cache-Control': "no-cache"
        }
        payload = { 'grant_type': 'password',
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'username': USERNAME,
                    'password': password
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
            return ''
        
        try:
            srv_token = response.json()
        except requests.exceptions.JSONDecodeError:
            log.error("Response does not contain valid JSON, unable to retrieve refresh token")

        with open(TOKEN_FILE, 'w') as fh:
            srv_token['expires_at'] = (datetime.now() + timedelta(0,srv_token['expires_in'])).isoformat()
            fh.write(dumps(srv_token))

        return srv_token['access_token']

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
        return ''

    # Construct the request using url endpoint, headers, and query paramters
    url = f"{BASE_URL}/api/now/table/incident"
    query_params = {
        'sysparm_query': 'assignment_group=6555506a47995d50d544d698436d4367^state=1',
        'sysparm_fields': 'number, state',
    }
    headers = { 'Content-Type': "application/json",
                'Authorization': f"Bearer {access_token}",
                'Cache-Control': "no-cache"
    }
    
    try:
        response = requests.get(url, params=query_params, headers=headers)
    except Exception as e:
            log.error(f"Exception in network attempt: {e}")
    
    # Check if the request was successful
    if response.status_code == 200:
        log.debug(f"Query Response Body")
        log.debug(response.text)       

        try:
            inc_query = response.json()
        except requests.exceptions.JSONDecodeError:
            log.error("Response does not contain valid JSON, unable to retrieve refresh token")
            return "Response does not contain valid JSON, unable to retrieve refresh token"
        
        # Get the result array and sum up the count
        incidents = inc_query.get('result', [])
        return len(incidents)
    
    elif response.status_code == 401 and not one_shot:
        return incident_query(get_access_token(force_renew=True), one_shot=True)
    else:
        log.error(f"Server responded with {response.status_code}")
        return f"Incident query unable to complete, server responded {response.status_code}"

def get_kb(subcategory, access_token):
    url = (
        f"https://{instance}.service-now.com/api/now/table/kb_knowledge"
        f"?sysparm_query=kb_knowledge_base=dfc19531bf2021003f07e2c1ac0739ab"
        f"^kb_category={subcategory}&sysparm_limit=200"
    )

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get('result', [])
    else:
        print(f"Error fetching KBs for subcategory {subcategory}: {response.text}")
        return []
    
# Function to gather docs for a list of subcategory ids
def gather_docs(subcategory_ids, seen_texts=None, access_token=None):
    if seen_texts is None:
        seen_texts = set()

    gathered = []

    for subcategory_id in subcategory_ids:
        try:
            access_token = get_access_token()
        except Exception as e:
            print(f"Error getting access token: {e}")
            return []
        
        records = get_kb(subcategory_id, access_token)
        
        for record in records:
            short_desc = record.get('short_description', '').strip()
            meta_desc = record.get('meta_description', '').strip()
            text_key = (short_desc.lower(), meta_desc.lower())

            if text_key not in seen_texts:
                seen_texts.add(text_key)
                display_number = record.get('number', '')
                link = f"https://uriprod.service-now.com/kb?id=kb_article_view&sysparm_article={display_number}"
                combined_text = f"{short_desc} {meta_desc}. LINK: {link}"
                combined_text = re.sub(r',', '', combined_text)
                gathered.append(combined_text)

    return gathered
