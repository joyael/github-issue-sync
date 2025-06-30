import os
import re
from dotenv import load_dotenv

def update_env_variable(variable_name, new_value):
    file_path = './config/.env'
    try:
        updated = False
        with open(file_path, 'r') as file:
            lines = file.readlines()

        updated_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith(f"{variable_name}="):
                updated_lines.append(f"{variable_name}={new_value}\n")
                updated = True
            else:
                updated_lines.append(line)

        if not updated:
            # Add new variable at the end if not found
            updated_lines.append(f"{variable_name}={new_value}\n")

        with open(file_path, 'w') as file:
            file.writelines(updated_lines)

        print(f".env file updated successfully: {file_path}")

    except Exception as e:
        print(f"Error updating .env file: {str(e)}")

    try:
        updated = False
        with open(file_path, 'r') as file:
            lines = file.readlines()

        updated_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith(f"{variable_name}="):
                updated_lines.append(f"{variable_name}='{new_value}'\n")
                updated = True
            else:
                updated_lines.append(line)

        if not updated:
            # Add new variable at the end if not found
            updated_lines.append(f"{variable_name}={new_value}\n")

        with open(file_path, 'w') as file:
            file.writelines(updated_lines)

        print(f".env file updated successfully: {file_path}")

    except Exception as e:
        print(f"Error updating .env file: {str(e)}")

def get_range_name(env_path='./config/.env'):
    load_dotenv(dotenv_path=env_path, override=True)
    return os.getenv('RANGE_NAME')

def get_sheet_name(env_path='./config/.env'):
    load_dotenv(dotenv_path=env_path, override=True)
    range_name = os.getenv('RANGE_NAME')
    return range_name.split('!')[0]

def get_previous_issues_list(service, spreadsheet_id, current_sheet_name):
    previous_issues_list = []
    
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get('sheets', [])
    
    for sheet in sheets:
        sheet_name = sheet['properties']['title']
        if sheet_name == current_sheet_name:
            continue
        
        # Define range for column E (index 4, i.e. column 'E')
        range_str = f"{sheet_name}!E5:E"
        
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_str
            ).execute()
            values = result.get('values', [])

            for row in values:
                if row:
                    cell_value = row[0]
                    match = re.search(r'#(\d+)', cell_value)
                    if match:
                        issue_number = int(match.group(1))
                        previous_issues_list.append(issue_number)
        except Exception as e:
            print(f"Error reading from sheet {sheet_name}: {e}")

    return previous_issues_list