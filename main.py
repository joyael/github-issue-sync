import os
import json
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from dotenv import load_dotenv

load_dotenv('./configuration/.env')
github_token = os.getenv('GITHUB_TOKEN')
github_repo_owner = os.getenv('GITHUB_REPO_OWNER')
github_repo_name = os.getenv('GITHUB_REPO_NAME')

scopes = os.getenv('SCOPES')
spreadsheet_id = os.getenv('SPREADSHEET_ID')
range_name = os.getenv('RANGE_NAME')

credentials_path = os.getenv('CREDENTIALS_PATH')

def get_github_user_full_name(username):
    url = f"https://api.github.com/users/{username}"
    response = requests.get(url)
    if response.status_code == 200:
        user_data = response.json()
        return user_data.get("name")
    else:
        return username

# Issue fields to update in Google Sheets
ISSUE_FIELDS = ['number', 'assignee', 'title', 'html_url']

def get_github_issues():
    """Get GitHub issues using the GitHub API"""
    url = f'https://api.github.com/repos/{github_repo_owner}/{github_repo_name}/issues'
    headers = {'Authorization': f'Bearer {github_token}'}
    response = requests.get(url, headers=headers)
    print("Git API Response : " , response.json())
    return response.json()

def update_google_sheet(service, issues):
    """Update Google Sheet with GitHub issues"""
    body = []
    counter = 1
    for issue in issues:
        assignee_full_name = get_github_user_full_name(issue['assignee']['login']) if issue['assignee'] else ''
        label_with_zero = next((label['name'] for label in issue['labels'] if '0' in label['name']), '')
        role = "_"
        row = [
            counter,
            assignee_full_name,
            role,
            f"{issue['title']} #{issue['number']}",
            issue['html_url'],
            label_with_zero
        ]
        body.append(row)
        counter+=1
    value_input_option = 'USER_ENTERED'
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption=value_input_option, body={'values': body}).execute()
    print(f'{result.get("updatedCells")} cells updated.')

def main():
    """Main function"""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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