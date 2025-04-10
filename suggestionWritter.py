import os

import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SAMPLE_SPREADSHEET_ID = "1OZzXw8_oK-5Qr-fJhQqyoYd2-T4JX0M_XAKMd0RF65c"
SAMPLE_RANGE_NAME = "Sheet1"

def write_values(value):
    """
    Appends a row to the sheet with checkboxes in columns A and B, and the given value in column C.
    """
    values_to_write = [["FALSE", "FALSE", value]]

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)

        # Append the values starting from A1
        append_result = service.spreadsheets().values().append(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            range="Sheet1!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values_to_write}
        ).execute()

        # Extract the row index from the updated range
        updated_range = append_result["updates"]["updatedRange"]  # e.g., 'Sheet1!A4:C4'
        match = re.search(r'[A-Z]+(\d+):', updated_range)
        if match:
            row_index = int(match.group(1)) - 1
        else:
            raise ValueError("Unable to parse updated row index from range")

        # Apply checkboxes to columns A and B of that row
        checkbox_request = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,  # Update if you're using a different sheet
                            "startRowIndex": row_index,
                            "endRowIndex": row_index + 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 2  # A and B
                        },
                        "cell": {
                            "dataValidation": {
                                "condition": {"type": "BOOLEAN"},
                                "strict": True,
                                "showCustomUi": True
                            }
                        },
                        "fields": "dataValidation"
                    }
                }
            ]
        }

        service.spreadsheets().batchUpdate(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            body=checkbox_request
        ).execute()

        print(f"Row {row_index + 1} added with checkboxes and value: {value}")

    except HttpError as err:
        print(f"An error occurred: {err}")



def get_values():
    """
    Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            range=SAMPLE_RANGE_NAME
        ).execute()
        values = result.get("values", [])
        if not values:
            print("No data found.")
            return
        # get all values that have a length of 3
        suggestion_values = []
        for value in values:
            if len(value) == 3:
                suggestion_values.append(value)
        return suggestion_values[1::]
    except HttpError as err:
        print(err)
        return None
    
def delete_rows_with_true():
    """
    Deletes rows in the spreadsheet where column A or B has the value TRUE.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        # Get sheet ID dynamically
        metadata = sheet.get(spreadsheetId=SAMPLE_SPREADSHEET_ID).execute()
        sheet_id = metadata["sheets"][0]["properties"]["sheetId"]

        # Read A2:B (skipping header row)
        result = sheet.values().get(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            range="Sheet1!A2:B"
        ).execute()
        values = result.get("values", [])

        rows_to_delete = []

        for i, row in enumerate(values):
            val_a = row[0].strip().upper() if len(row) > 0 else ""
            val_b = row[1].strip().upper() if len(row) > 1 else ""
            if val_a == "TRUE" or val_b == "TRUE":
                # i is 0-based starting from A2 → actual row index in sheet is i + 1
                rows_to_delete.append(i + 1)

        # Delete from bottom to top
        for row in sorted(rows_to_delete, reverse=True):
            request_body = {
                "requests": [
                    {
                        "deleteDimension": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "ROWS",
                                "startIndex": row,  # i + 1 from above
                                "endIndex": row + 1
                            }
                        }
                    }
                ]
            }

            sheet.batchUpdate(
                spreadsheetId=SAMPLE_SPREADSHEET_ID,
                body=request_body
            ).execute()

    except HttpError as err:
        print(f"An error occurred: {err}")
    
# Gets all valid values from the spreadsheet
# A valid value is one where column A is FALSE and column B is FALSE
# Returns a list of valid values after deleting the rows with TRUE in column A or B
def check_values():
    values = get_values()
    checked_values = []
    for value in values:
        if value[0] == "TRUE" and value[1] == "FALSE":
            checked_values.append(value)
    delete_rows_with_true()
    return checked_values
            
def get_length_values():
    new_not_approved = 0
    values = get_values()
    for value in values:
        if value[0] == "FALSE" and value[1] == "FALSE":
            new_not_approved += 1
    return new_not_approved

print(get_length_values())
    
