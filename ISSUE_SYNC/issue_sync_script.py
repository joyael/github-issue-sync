import os
import json
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# GitHub API credentials
GITHUB_TOKEN = 'your_github_token'
GITHUB_REPO_OWNER = 'your_github_username'
GITHUB_REPO_NAME = 'your_github_repo_name'

# Google Sheets API credentials
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = 'your_spreadsheet_id'
RANGE_NAME = 'Sheet1!A1:G'  # Update this to your sheet range

# Issue fields to update in Google Sheets
ISSUE_FIELDS = ['number', 'title', 'body', 'labels', 'state', 'created_at', 'updated_at']

def get_github_issues():
    """Get GitHub issues using the GitHub API"""
    url = f'https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/issues'
    headers = {'Authorization': f'Bearer {GITHUB_TOKEN}'}
    response = requests.get(url, headers=headers)
    return response.json()

def update_google_sheet(service, issues):
    """Update Google Sheet with GitHub issues"""
    body = []
    for issue in issues:
        row = []
        for field in ISSUE_FIELDS:
            if field == 'labels':
                row.append(', '.join([label['name'] for label in issue[field]]))
            else:
                row.append(issue[field])
        body.append(row)
    value_input_option = 'USER_ENTERED'
    result = service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
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
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('sheets', 'v4', credentials=creds)
    issues = get_github_issues()
    update_google_sheet(service, issues)

if __name__ == '__main__':
    main()
