import os
import json
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from dotenv import load_dotenv
import re
import sys
import datetime
import calendar
import utils
import sheet_functions

load_dotenv('./config/.env')
github_token = os.getenv('GITHUB_TOKEN')
github_repo_owner = os.getenv('GITHUB_REPO_OWNER')
github_repo_name = os.getenv('GITHUB_REPO_NAME')
github_project_title = os.getenv('GITHUB_PROJECT_TITLE')

scopes = os.getenv('SCOPES').split(',') if os.getenv('SCOPES') else []
spreadsheet_id = os.getenv('SPREADSHEET_ID')
range_name = os.getenv('RANGE_NAME')

credentials_path = os.getenv('CREDENTIALS_PATH')

mod = "current"

predefined_status_values = ['In progress','In review','Todo','Backlog','Ready','Done','On Pause','Blocked', 'Client Action Needed','Testing']
role_values = {
    'Abdul Muhsin K': 'Backend Dev',
    'Albin Joseph' : 'Backend Dev',
    'Joyael Jose' : 'Backend Dev',
    'Sourav Rajeev' : 'Frontend Dev',
    'Jobin John' : 'Frontend Dev',
    'Vishnu Vijayan' : 'UI/UX Designer',
    'Abhirami' : 'QA',
}
assignee_names = {
    'albinJoseph1' : 'Albin Joseph',
    'jobinjohn4113112' : 'Jobin John',
    'abdul-yatnam':'Abdul Muhsin K',
    'brandadapt' : 'Brandadapt',
    'bincybabu3108' : 'Bincy Babu',
    'Jishnu-10' : 'Jishnu',
    'SouravRajeevK': 'Sourav Rajeev',
    'AthulyaPJ': 'Athulya P J',
    'Vishnuvijayan5': 'Vishnu Vijayan',
    'joyaeljose-yatnam': 'Joyael Jose',
    'AbhijithHaridas': 'Abhijith',
    'abhirami-kv': 'Abhirami'
}

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

def get_github_collaborators():
    """Get GitHub collaborators using the GitHub API"""
    url = f'https://api.github.com/repos/{github_repo_owner}/{github_repo_name}/collaborators'
    headers = {'Authorization': f'Bearer {github_token}'}
    response = requests.get(url, headers=headers)
    collaborators = response.json()
    collaborator_names = [get_github_user_full_name(collaborator['login']) for collaborator in collaborators]
    return collaborator_names

def get_github_issues():
    """Get all GitHub issues using the GitHub API with pagination"""
    issues = []
    page = 1
    per_page = 100  # Max allowed by GitHub API
    while True:
        url = f'https://api.github.com/repos/{github_repo_owner}/{github_repo_name}/issues?state=all&per_page={per_page}&page={page}'
        headers = {'Authorization': f'Bearer {github_token}'}
        response = requests.get(url, headers=headers)
        page_issues = response.json()
        if not page_issues or 'message' in page_issues:
            break  # Stop if no more issues or an error occurred
        issues.extend(page_issues)
        page += 1
    print("Number of Issues is:", len(issues))
    filtered_issues = [issue for issue in issues if issue['node_id'].startswith('I_')]
    print("Git API Response:", filtered_issues)
    return filtered_issues

def get_effective_closed_date(issue):
    """
    Returns the closed date of the issue if available,
    else returns the last date of the current year in ISO format.
    """
    if issue.get('closed_at'):
        return issue['closed_at']
    else:
        current_year = datetime.datetime.now().year
        return f"{current_year}-12-31T23:59:59Z"

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
    project_found = False
    if result is not None and 'projectItems' in result and result['projectItems'] is not None:
        for node in result['projectItems']['nodes']:
            project_title = node['project']['title']
            if project_title == github_project_title:
                project_found = True
                for field_value in node['fieldValues']['nodes']:
                    if 'name' in field_value:
                        if field_value['name'] in predefined_status_values:
                            project_status = field_value['name']
                            break
                if project_status:
                    break
    else:
        return "project_not_found"
    if not project_found:
        return "project_not_found"
    if project_status == 'Ready' or project_status == 'Todo':
        project_status = 'Pending'
    if project_status == 'In review':
        project_status = 'Review'
    if project_status == 'Done':
        project_status = 'Estimation Required'
    if project_status == None:
        return "No Status"
    project_status = project_status.title()
    return project_status

def update_google_sheet(service, issues, conclude):
    """Update Google Sheet with GitHub issues"""
    body = []
    counter = 0
    sheet_counter = 1
    to_merge=[]
    previous_issues_list = utils.get_previous_issues_list(service, spreadsheet_id, utils.get_sheet_name())
    print(previous_issues_list)
    issues = sorted(issues, key=lambda x: get_effective_closed_date(x))
    for issue in issues:
        issue_number = issue['number']
        project_status = get_issue_by_number(issue_number)
        issue['project_status'] = project_status
        if int(issue_number) in previous_issues_list:
            continue
        if conclude==True and issue['state'] != 'closed':
            continue
        if project_status == "Backlog":
            continue
        if project_status == "project_not_found":
            continue
        if mod == "new_month" and project_status == "Estimation Required":
            continue
        if project_status == "Estimation Required" and issue['state']=='open':
            project_status = "Pending"
        print("Project status : ", project_status)
        print("Assignees : ", issue['assignees'])
        assignees_full_names = []
        for assignee in issue['assignees']:
            assignee_full_name = assignee_names.get(assignee['login'],'not_found')
            if assignee_full_name == 'not_found':
                assignee_full_name = get_github_user_full_name(assignee['login']) if assignee else ''
            assignees_full_names.append(assignee_full_name)
        assignees_count = len(assignees_full_names)
        if assignees_count>1:
            merge={'startrowoffset':counter,'endrowoffset':assignees_count,'startcoloffset':0}
            to_merge.append(merge)
            merge={'startrowoffset':counter,'endrowoffset':assignees_count,'startcoloffset':3}
            to_merge.append(merge)
            merge={'startrowoffset':counter,'endrowoffset':assignees_count,'startcoloffset':4}
            to_merge.append(merge)
        
        if assignees_count == 0:
            role = "_" #It is a placeholder value for the field role which we are not using
            row = [
                sheet_counter,
                "",
                role,
                f"{issue['title']} #{issue['number']}",
                issue['html_url'],
                project_status
            ]
            body.append(row)
            counter+=1
        for assignee_name in assignees_full_names:
            role = role_values.get(assignee_name, "_")
            row = [
                sheet_counter,
                assignee_name,
                role,
                f"{issue['title']} #{issue['number']}",
                issue['html_url'],
                project_status
            ]
            body.append(row)
            counter+=1
        sheet_counter+=1
    
    match = re.match(r'(.*?)!([A-Z]+)(\d+):[A-Z]+', utils.get_range_name())
    if match:
        sheet_name, start_col_letter, start_row_str = match.groups()
        start_row_index = int(start_row_str)
        start_col_index = ord(start_col_letter.upper()) - ord('A')
    else:
        raise ValueError("Invalid range_name format")
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = next(
        (s['properties']['sheetId'] for s in sheet_metadata['sheets']
        if s['properties']['title'] == sheet_name),
        None
    )
    print("Sheet ID : ",sheet_id)
    sheet_functions.clear_range(service, sheet_id, start_row_index, start_row_index + 700, start_col_index, start_col_index + 7, spreadsheet_id)
    sheet_functions.unmerge_cells(service, sheet_id, spreadsheet_id)
    # body = sorted(body, key=lambda x: x[0])
    value_input_option = 'USER_ENTERED'
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=utils.get_range_name(),
        valueInputOption=value_input_option, body={'values': body}).execute()

    sheet_functions.merge_sheet_cells(sheet_id,start_row_index,start_col_index,to_merge,service, spreadsheet_id)
    print(f'{result.get("updatedCells")} cells updated.')
    output_issues_no = len(body)
    backlog_issues_no = 0
    no_project_issues_no = 0
    previous_issues_no = len(previous_issues_list)

    for issue in issues:
        if issue['state']=='closed':
            if issue['project_status'] == 'Backlog':
                backlog_issues_no+=1
                print("Backlog issue found , issue number : ",issue['number'])
            elif issue['project_status'] == 'project_not_found':
                no_project_issues_no+=1       
                print("No project issue found , issue number : ",issue['number'])
            print("Issue closed date : ", get_effective_closed_date(issue), "  Issue number : ", issue['number'])

    print("Output issues count : ", output_issues_no)
    print("Backlog issues count : ", backlog_issues_no)
    print("No project issues count : ", no_project_issues_no)
    print("Previous issues count : ", previous_issues_no)

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
    global mod
    month_end = False
    for arg in sys.argv:
        if arg == 'new_month' or arg == 'new_month_new_spreadsheet':
            if arg == 'new_month':
                update_google_sheet(service, issues, conclude=True)
            new_range_name = sheet_functions.process_new_month(service, spreadsheet_id)
            utils.update_env_variable('RANGE_NAME', new_range_name)
            mod = "new_month"
        if arg == 'month_end':
            update_google_sheet(service, issues, conclude=True)
            month_end = True
            mod = "month_end"
    if not month_end:
        update_google_sheet(service, issues,conclude=False)

if __name__ == '__main__':
    main()
