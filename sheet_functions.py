import datetime
import calendar
import os
import utils
import sys
from googleapiclient.errors import HttpError

spreadsheet_id = os.getenv('SPREADSHEET_ID')

def process_new_month(service, spreadsheet_id):
    current_month = calendar.month_name[datetime.datetime.now().month]
    current_year = datetime.datetime.now().year
    new_sheet_name = f'{current_month}_{current_year}'
    source_sheet_name = utils.get_range_name().split('!')[0]
    duplicate_sheet(service, spreadsheet_id, source_sheet_name, new_sheet_name)
    new_range_name = new_sheet_name + '!' + utils.get_range_name().split('!')[1]
    return new_range_name

def duplicate_sheet(service, spreadsheet_id, source_sheet_name, new_sheet_name):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get('sheets', [])
    source_sheet_id = None
    for sheet in sheets:
        if sheet.get('properties', {}).get('title') == source_sheet_name:
            source_sheet_id = sheet.get('properties', {}).get('sheetId')
            break

    if source_sheet_id is None:
        raise ValueError(f"Source sheet '{source_sheet_name}' not found.")
    
    insert_sheet_index = len(sheets) 

    body = {
        'requests': [{
            'duplicateSheet': {
                'sourceSheetId': source_sheet_id,
                'insertSheetIndex': insert_sheet_index,
                'newSheetName': new_sheet_name
            }
        }]
    }

    try :    
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body=body).execute()
        return response
    except HttpError as error:
        if error.resp.status == 400 and 'duplicateSheet' in error._get_reason():
            print(f"This is not new month. Sheet '{new_sheet_name}' already exists.")
            sys.exit(1)
        else:
            raise

def merge_sheet_cells(sheet_id,start_row_index_,start_col_index,merge_data,service, spreadsheet_id):
    for merge in merge_data:
        print("Merge : ",merge)
    for merge in merge_data:
        startRowIndex = start_row_index_ + merge['startrowoffset'] - 1
        endRowIndex = startRowIndex + merge['endrowoffset']
        startColumnIndex = start_col_index + merge['startcoloffset']
        endColumnIndex = startColumnIndex + 1
        requests = [{
            "mergeCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": startRowIndex,
                    "endRowIndex": endRowIndex,
                    "startColumnIndex": startColumnIndex,
                    "endColumnIndex": endColumnIndex
                },
                "mergeType": "MERGE_ALL"
            }
        }]

        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()

def unmerge_cells(service, sheet_id, spreadsheet_id):
    batch_update_request = {
        "requests": [
            {
                "unmergeCells": {
                    "range": {
                        "sheetId": sheet_id
                    }
                }
            }
        ]
    }
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=batch_update_request
    ).execute()
    print("Unmerged all cells in the sheet.")

def clear_range(service, sheet_id, start_row_index, end_row_index, start_col_index, end_col_index, spreadsheet_id):
    num_rows = end_row_index - start_row_index + 1
    num_cols = end_col_index - start_col_index

    empty_rows = [
        {
            "values": [{"userEnteredValue": {"stringValue": ""}} for _ in range(num_cols)]
        }
        for _ in range(num_rows)
    ]

    batch_update_request = {
        "requests": [
            {
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row_index - 1,  # Convert to 0-based index
                        "endRowIndex": end_row_index,
                        "startColumnIndex": start_col_index,
                        "endColumnIndex": end_col_index
                    },
                    "rows": empty_rows,
                    "fields": "userEnteredValue"
                }
            }
        ]
    }

    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=batch_update_request
    ).execute()
    print("Cleared values in the specified range.")
