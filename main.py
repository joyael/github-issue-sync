import os
import json
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from dotenv import load_dotenv
import re

load_dotenv('./config/.env')
github_token = os.getenv('GITHUB_TOKEN')
github_repo_owner = os.getenv('GITHUB_REPO_OWNER')
github_repo_name = os.getenv('GITHUB_REPO_NAME')

scopes = os.getenv('SCOPES').split(',') if os.getenv('SCOPES') else []
spreadsheet_id = os.getenv('SPREADSHEET_ID')
range_name = os.getenv('RANGE_NAME')

credentials_path = os.getenv('CREDENTIALS_PATH')

def get_github_user_full_name(username):
    url = f"https://api.github.com/users/{username}"
    headers = {
        'Authorization': f'Bearer {github_token}',
        'Accept': 'application/vnd.github+json'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        user_data = response.json()
        return user_data.get("name") or username
    else:
        print(f"Failed to fetch user {username}: {response.status_code} - {response.text}")
        return username

# Issue fields to update in Google Sheets
ISSUE_FIELDS = ['number', 'assignee', 'title', 'html_url']

def get_github_collaborators():
    """Get GitHub collaborators using the GitHub API"""
    url = f'https://api.github.com/repos/{github_repo_owner}/{github_repo_name}/collaborators'
    headers = {'Authorization': f'Bearer {github_token}'}
    response = requests.get(url, headers=headers)
    collaborators = response.json()
    collaborator_names = [get_github_user_full_name(collaborator['login']) for collaborator in collaborators]
    return collaborator_names

def get_github_issues():
    """Get GitHub issues using the GitHub API"""
    url = f'https://api.github.com/repos/{github_repo_owner}/{github_repo_name}/issues?state=all'
    headers = {'Authorization': f'Bearer {github_token}'}
    response = requests.get(url, headers=headers)
    issues = response.json()
    filtered_issues = [issue for issue in issues if issue['node_id'].startswith('I_')]
    print("Git API Response : " , response.json())
    return filtered_issues


graphql_url = 'https://api.github.com/graphql'
headers = {
        'Authorization': f'Bearer {github_token}',
        'Content-Type': 'application/json'
}

def get_issue_by_number(issue_number):
    query = f"""
    {{
      repository(owner: "{github_repo_owner}", name: "{github_repo_name}") {{
        issue(number: {issue_number}) {{
          number
          title
          url
          projectItems(first: 5) {{
            nodes {{
              project {{ title }}
              fieldValues(first: 10) {{
                nodes {{
                  ... on ProjectV2ItemFieldSingleSelectValue {{
                    name
                    field {{
                      ... on ProjectV2Field {{
                        name
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    response = requests.post(graphql_url, json={'query': query}, headers=headers)
    result = response.json()['data']['repository']['issue']
    project_status = None
    
    if result is not None and 'projectItems' in result and result['projectItems'] is not None:
        for node in result['projectItems']['nodes']:
            for field_value in node['fieldValues']['nodes']:
                if 'name' in field_value:
                    project_status = field_value['name']
                    break
            if project_status:
                break
    else:
        return "undefined"
    if project_status == 'Ready':
        project_status = 'Pending'
    if project_status == 'In Review':
        project_status = 'Review'
    if project_status == 'Done':
        project_status = 'Estimation Required'
    project_status = project_status.title()
    return project_status



def set_data_validation_assignees(sheet_id,start_row_index_,start_col_index,issues_count,body,service):
    # Only proceed if sheet_id is found
    if sheet_id is not None:
        # Calculate the range for data validation
        start_row_index = start_row_index_ - 1 # (0-based)
        end_row_index = start_row_index + issues_count
        start_column_index = start_col_index + 1 
        end_column_index = start_column_index + 1

        # Extract assignee names from each issue (column 2, index 1)
        collaborators = get_github_collaborators()

        # Prepare data validation values
        validation_values = [{'userEnteredValue': name} for name in collaborators]

        # Prepare the request for data validation
        request = {
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row_index,
                    "endRowIndex": end_row_index,
                    "startColumnIndex": start_column_index,
                    "endColumnIndex": end_column_index
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": validation_values
                    },
                    "showCustomUi": True,
                    "strict": False
                }
            }
        }

        # Send the request
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [request]}
        ).execute()
        print('Data validation set for the range.')
    else:
        print("Sheet ID not found.")

def set_data_validation_statuses(sheet_id,start_row_index_,start_col_index,issues_count,body,service):
    # Only proceed if sheet_id is found
    if sheet_id is not None:
        # Calculate the range for data validation
        start_row_index = start_row_index_ - 1 # (0-based)
        end_row_index = start_row_index + issues_count
        start_column_index = start_col_index + 5
        end_column_index = start_column_index + 1

        status_options = set(row[5] for row in body)

        # Prepare data validation values
        validation_values = [{'userEnteredValue': name} for name in status_options]

        # Prepare the request for data validation
        request = {
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row_index,
                    "endRowIndex": end_row_index,
                    "startColumnIndex": start_column_index,
                    "endColumnIndex": end_column_index
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": validation_values
                    },
                    "showCustomUi": True,
                    "strict": False
                }
            }
        }

        # Send the request
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [request]}
        ).execute()
        print('Data validation set for the range.')
    else:
        print("Sheet ID not found.")


def update_google_sheet(service, issues):
    """Update Google Sheet with GitHub issues"""
    body = []
    counter = 1
    for issue in issues:
        issue_number = issue['number']
        project_status = get_issue_by_number(issue_number)
        if project_status == "Backlog":
            continue
        print("Project status : ", project_status)
        print("Assignees : ", issue['assignees'])
        assignees_full_names = []
        for assignee in issue['assignees']:
            assignee_full_name = get_github_user_full_name(assignee['login']) if assignee else ''
            assignees_full_names.append(assignee_full_name)
        assignee_dropdown_values = assignees_full_names  # list of names
        assignee_cell_value = ", ".join(assignee_dropdown_values)  # display in cell

        role = "_" #It is a placeholder value for the field role which we are not using
        row = [
            counter,
            assignee_cell_value,
            role,
            f"{issue['title']} #{issue['number']}",
            issue['html_url'],
            project_status
        ]
        body.append(row)
        counter+=1
    value_input_option = 'USER_ENTERED'
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption=value_input_option, body={'values': body}).execute()
    
    # Extract sheet name and starting row number from range_name like 'Sheet12!B5:G'
    match = re.match(r'(.*?)!([A-Z]+)(\d+):[A-Z]+', range_name)
    if match:
        sheet_name, start_col_letter, start_row_str = match.groups()
        start_row_index = int(start_row_str)
        start_col_index = ord(start_col_letter.upper()) - ord('A')
    else:
        raise ValueError("Invalid range_name format")

    # Get sheetId using sheet name
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = next(
        (s['properties']['sheetId'] for s in sheet_metadata['sheets']
        if s['properties']['title'] == sheet_name),
        None
    )
    issues_count=len(body)
    set_data_validation_assignees(sheet_id,start_row_index,start_col_index,issues_count,body,service)
    set_data_validation_statuses(sheet_id,start_row_index,start_col_index,issues_count,body,service)
    print(f'{result.get("updatedCells")} cells updated.')

def main():
    """Main function"""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Refresh failed: {e}. Re-running authentication flow.")
                creds = None  # force new login below
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, scopes)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('sheets', 'v4', credentials=creds)
    issues = get_github_issues()
    update_google_sheet(service, issues)

if __name__ == '__main__':
    main()