# google sheets

import logging
import json
import datetime
import httplib2
import googleapiclient.discovery
from google.oauth2 import service_account

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import user_passes_test

from dojo.models import (
    Finding,
    System_Settings,
    Test,
    Dojo_User,
    Note_Type,
    NoteHistory,
    Notes,
    Sonarqube_Issue,
)
from dojo.forms import GoogleSheetFieldsForm
from dojo.utils import add_breadcrumb, Product_Tab

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_superuser)
def configure_google_sheets(request):
    fields = Finding._meta.fields
    system_settings = get_object_or_404(System_Settings, id=1)
    revoke_access = False
    if system_settings.credentials:
        revoke_access = True
        column_details = json.loads(system_settings.column_widths.replace("'", '"'))
        initial = {}
        for field in fields:
            initial[field.name] = column_details[field.name][0]
            if column_details[field.name][1] == 0:
                initial["Protect " + field.name] = False
            else:
                initial["Protect " + field.name] = True
        initial["drive_folder_ID"] = system_settings.drive_folder_ID
        initial["email_address"] = system_settings.email_address
        initial["enable_service"] = system_settings.enable_google_sheets
        form = GoogleSheetFieldsForm(
            all_fields=fields, initial=initial, credentials_required=False
        )
    else:
        form = GoogleSheetFieldsForm(all_fields=fields, credentials_required=True)
    if request.method == "POST":
        if system_settings.credentials:
            form = GoogleSheetFieldsForm(
                request.POST,
                request.FILES,
                all_fields=fields,
                credentials_required=False,
            )
        else:
            form = GoogleSheetFieldsForm(
                request.POST,
                request.FILES,
                all_fields=fields,
                credentials_required=True,
            )

        if request.POST.get("revoke"):
            system_settings.column_widths = ""
            system_settings.credentials = ""
            system_settings.drive_folder_ID = ""
            system_settings.email_address = ""
            system_settings.enable_google_sheets = False
            system_settings.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Access revoked",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("dashboard"))

        if request.POST.get("update"):
            if form.is_valid():
                # Create a dictionary object from the uploaded credentials file
                if len(request.FILES) != 0:
                    cred_file = request.FILES["cred_file"]
                    cred_byte = (
                        cred_file.read()
                    )  # read data from the temporary uploaded file
                    cred_str = cred_byte.decode(
                        "utf8"
                    )  # convert bytes object to string
                    initial = True
                else:
                    cred_str = system_settings.credentials
                    initial = False

                # Get the drive folder ID
                drive_folder_ID = form.cleaned_data["drive_folder_ID"]
                validate_inputs = validate_drive_authentication(
                    request, cred_str, drive_folder_ID
                )

                if validate_inputs:
                    # Create a dictionary of column names and widths
                    column_widths = {}
                    for i in fields:
                        column_widths[i.name] = []
                        column_widths[i.name].append(form.cleaned_data[i.name])
                        if form.cleaned_data["Protect " + i.name]:
                            column_widths[i.name].append(1)
                        else:
                            column_widths[i.name].append(0)

                    system_settings.column_widths = column_widths
                    system_settings.credentials = cred_str
                    system_settings.drive_folder_ID = drive_folder_ID
                    system_settings.email_address = form.cleaned_data["email_address"]
                    system_settings.enable_google_sheets = form.cleaned_data[
                        "enable_service"
                    ]
                    system_settings.save()
                    if initial:
                        messages.add_message(
                            request,
                            messages.SUCCESS,
                            "Google Drive configuration saved successfully.",
                            extra_tags="alert-success",
                        )
                    else:
                        messages.add_message(
                            request,
                            messages.SUCCESS,
                            "Google Drive configuration updated successfully.",
                            extra_tags="alert-success",
                        )
                    return HttpResponseRedirect(reverse("dashboard"))
                else:
                    system_settings.enable_google_sheets = False
                    system_settings.save()
    add_breadcrumb(
        title="Google Sheet Sync Configuration", top_level=True, request=request
    )
    return render(
        request,
        "dojo/google_sheet_configuration.html",
        {
            "name": "Google Sheet Sync Configuration",
            "metric": False,
            "form": form,
            "revoke_access": revoke_access,
        },
    )


def validate_drive_authentication(request, cred_str, drive_folder_ID):
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    service_account_info = json.loads(cred_str)
    try:
        # Validate the uploaded credentials file
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
    except ValueError:
        messages.add_message(
            request,
            messages.ERROR,
            "Invalid credentials file.",
            extra_tags="alert-danger",
        )
        return False
    else:
        sheets_service = googleapiclient.discovery.build(
            "sheets", "v4", credentials=credentials, cache_discovery=False
        )
        drive_service = googleapiclient.discovery.build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )
        spreadsheet = {"properties": {"title": "Test spreadsheet"}}
        try:
            # Check the sheets API is enabled or not
            spreadsheet = (
                sheets_service.spreadsheets()
                .create(body=spreadsheet, fields="spreadsheetId")
                .execute()
            )
        except googleapiclient.errors.HttpError:
            messages.add_message(
                request,
                messages.ERROR,
                "Enable the Google Sheets API from the Google Developer Console.",
                extra_tags="alert-danger",
            )
            return False
        else:
            spreadsheetId = spreadsheet.get("spreadsheetId")
            try:
                # Check the drive API is enabled or not
                file = (
                    drive_service.files()
                    .get(fileId=spreadsheetId, fields="parents")
                    .execute()
                )  # Retrieve the existing parents to remove
            except googleapiclient.errors.HttpError:
                messages.add_message(
                    request,
                    messages.ERROR,
                    "Enable the Google Drive API from the Google Developer Console.",
                    extra_tags="alert-danger",
                )
                return False
            else:
                previous_parents = ",".join(file.get("parents"))
                folder_id = drive_folder_ID
                try:
                    # Validate the drive folder id and it's permissions
                    file = (
                        drive_service.files()
                        .update(
                            fileId=spreadsheetId,  # Move the file to the new folder
                            addParents=folder_id,
                            removeParents=previous_parents,
                            fields="id, parents",
                        )
                        .execute()
                    )
                except googleapiclient.errors.HttpError as error:
                    if error.resp.status == 403:
                        messages.add_message(
                            request,
                            messages.ERROR,
                            "Unable to write to the given Google Drive folder",
                            extra_tags="alert-danger",
                        )
                    if error.resp.status == 404:
                        messages.add_message(
                            request,
                            messages.ERROR,
                            "Invalid Google Drive folder ID",
                            extra_tags="alert-danger",
                        )
                    return False
                else:
                    drive_service.files().delete(
                        fileId=spreadsheetId
                    ).execute()  # Delete 'test spreadsheet'
                    return True


@user_passes_test(lambda u: u.is_staff)
def export_to_sheet(request, tid):
    system_settings = get_object_or_404(System_Settings, id=1)
    google_sheets_enabled = system_settings.enable_google_sheets
    if google_sheets_enabled is False:
        raise PermissionDenied
    test = Test.objects.get(id=tid)
    spreadsheet_name = (
        test.engagement.product.name + "-" + test.engagement.name + "-" + str(test.id)
    )
    service_account_info = json.loads(system_settings.credentials)
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    try:
        drive_service = googleapiclient.discovery.build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )
        folder_id = system_settings.drive_folder_ID
        files = (
            drive_service.files()
            .list(
                q="mimeType='application/vnd.google-apps.spreadsheet' and parents in '%s' and name='%s'"
                % (folder_id, spreadsheet_name),
                spaces="drive",
                pageSize=10,
                fields="files(id, name)",
            )
            .execute()
        )
        spreadsheets = files.get("files")
        if len(spreadsheets) == 1:
            spreadsheetId = spreadsheets[0].get("id")
            sync = sync_findings(request, tid, spreadsheetId)
            errors = sync["errors"]
            sheet_title = sync["sheet_title"]
            if len(errors) > 0:
                product_tab = Product_Tab(
                    test.engagement.product.id,
                    title="Syncing Errors",
                    tab="engagements",
                )
                product_tab.setEngagement(test.engagement)
                spreadsheet_url = (
                    "https://docs.google.com/spreadsheets/d/" + spreadsheetId
                )
                return render(
                    request,
                    "dojo/syncing_errors.html",
                    {
                        "test": test,
                        "errors": errors,
                        "name": "Google Drive Sync Errors",
                        "product_tab": product_tab,
                        "sheet_title": sheet_title,
                        "spreadsheet_name": spreadsheet_name,
                        "spreadsheet_url": spreadsheet_url,
                    },
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Synched Google Sheet with database.",
                    extra_tags="alert-success",
                )
                return HttpResponseRedirect(reverse("view_test", args=(tid,)))
        elif len(spreadsheets) == 0:
            create_googlesheet(request, tid)
            messages.add_message(
                request,
                messages.SUCCESS,
                "Successfully exported finding details to Google Sheet.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("view_test", args=(tid,)))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "More than one Google Sheet exists for this test. Please contact your system admin to solve the issue.",
                extra_tags="alert-danger",
            )
            return HttpResponseRedirect(reverse("view_test", args=(tid,)))
    except httplib2.ServerNotFoundError:
        error_message = "Unable to reach the Google Sheet API."
        return render(
            request, "google_sheet_error.html", {"error_message": error_message}
        )
    except googleapiclient.errors.HttpError as error:
        error_message = "There is a problem with the Google Sheets Sync Configuration. Contact your system admin to solve the issue."
        return render(
            request, "google_sheet_error.html", {"error_message": error_message}
        )
    except Exception as e:
        error_message = e
        return render(
            request, "google_sheet_error.html", {"error_message": error_message}
        )


def create_googlesheet(request, tid):
    user_email = request.user.email
    if not user_email:
        raise Exception("User must have an email address to use this feature.")
    test = Test.objects.get(id=tid)
    system_settings = get_object_or_404(System_Settings, id=1)
    service_account_info = json.loads(system_settings.credentials)
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    sheets_service = googleapiclient.discovery.build(
        "sheets", "v4", credentials=credentials, cache_discovery=False
    )
    drive_service = googleapiclient.discovery.build(
        "drive", "v3", credentials=credentials, cache_discovery=False
    )
    # Create a new spreadsheet
    spreadsheet_name = (
        test.engagement.product.name + "-" + test.engagement.name + "-" + str(test.id)
    )
    spreadsheet = {"properties": {"title": spreadsheet_name}}
    spreadsheet = (
        sheets_service.spreadsheets()
        .create(body=spreadsheet, fields="spreadsheetId")
        .execute()
    )
    spreadsheetId = spreadsheet.get("spreadsheetId")
    folder_id = system_settings.drive_folder_ID

    # Move the spreadsheet inside the drive folder
    file = drive_service.files().get(fileId=spreadsheetId, fields="parents").execute()
    previous_parents = ",".join(file.get("parents"))
    file = (
        drive_service.files()
        .update(
            fileId=spreadsheetId,
            addParents=folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        )
        .execute()
    )
    # Share created Spreadsheet with current user
    drive_service.permissions().create(
        body={"type": "user", "role": "writer", "emailAddress": user_email},
        fileId=spreadsheetId,
    ).execute()
    populate_sheet(tid, spreadsheetId)


def sync_findings(request, tid, spreadsheetId):
    test = Test.objects.get(id=tid)
    system_settings = get_object_or_404(System_Settings, id=1)
    service_account_info = json.loads(system_settings.credentials)
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    sheets_service = googleapiclient.discovery.build(
        "sheets", "v4", credentials=credentials, cache_discovery=False
    )
    res = {}
    spreadsheet = (
        sheets_service.spreadsheets().get(spreadsheetId=spreadsheetId).execute()
    )
    sheet_names = []
    for sheet in spreadsheet["sheets"]:
        date = sheet["properties"]["title"]
        try:
            date = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
            sheet_names.append(date)
        except:
            pass
    try:
        sheet_title = str(max(sheet_names))
    except:
        raise Exception(
            "Existing Google Spreadsheet has errors. Delete the speadsheet and export again."
        )
    res["sheet_title"] = sheet_title

    result = (
        sheets_service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheetId, range=sheet_title)
        .execute()
    )
    rows = result.get("values", [])
    header_raw = rows[0]
    findings_sheet = rows[1:]
    findings_db = Finding.objects.filter(test=test).order_by("numerical_severity")
    column_details = json.loads(system_settings.column_widths.replace("'", '"'))
    active_note_types = Note_Type.objects.filter(is_active=True)
    note_type_activation = len(active_note_types)

    errors = []
    index_of_active = header_raw.index("active")
    index_of_verified = header_raw.index("verified")
    index_of_duplicate = header_raw.index("duplicate")
    index_of_false_p = header_raw.index("false_p")
    index_of_id = header_raw.index("id")

    for finding_sheet in findings_sheet:
        finding_id = finding_sheet[index_of_id]
        active = finding_sheet[index_of_active]
        verified = finding_sheet[index_of_verified]
        duplicate = finding_sheet[index_of_duplicate]
        false_p = finding_sheet[index_of_false_p]

        if (
            active == "TRUE" or verified == "TRUE"
        ) and duplicate == "TRUE":  # Check update finding conditions
            error = "Duplicate findings cannot be verified or active"
            errors.append(
                {
                    "finding_id": finding_id,
                    "column_names": "active, verified, duplicate",
                    "error": error,
                }
            )
        elif false_p == "TRUE" and verified == "TRUE":
            error = "False positive findings cannot be verified."
            errors.append(
                {
                    "finding_id": finding_id,
                    "column_names": "false_p, verified",
                    "error": error,
                }
            )
        else:
            try:
                finding_db = findings_db.get(id=finding_id)  # Update finding attributes
            except:
                if finding_id is None:
                    finding_id = "Null"
                error = "Finding does not belong to the Test"
                errors.append(
                    {"finding_id": finding_id, "column_names": "id", "error": error}
                )
            else:
                finding_notes = finding_db.notes.all()
                for column_name in header_raw:
                    if column_name in column_details:
                        if int(column_details[column_name][1]) == 0:
                            index_of_column = header_raw.index(column_name)
                            if finding_sheet[index_of_column] == "TRUE":
                                setattr(finding_db, column_name, True)
                            elif finding_sheet[index_of_column] == "FALSE":
                                setattr(finding_db, column_name, False)
                            else:
                                setattr(
                                    finding_db,
                                    column_name,
                                    finding_sheet[index_of_column],
                                )
                    elif (
                        column_name[:6] == "[note]" and column_name[-3:] == "_id"
                    ):  # Updating notes
                        note_column_name = column_name[:-3]
                        try:
                            index_of_note_column = header_raw.index(note_column_name)
                        except ValueError:
                            pass
                        else:
                            index_of_id_column = header_raw.index(column_name)
                            note_id = finding_sheet[index_of_id_column]
                            note_entry = finding_sheet[index_of_note_column].rstrip()
                            if note_entry != "":
                                if note_id != "":  # If the note is an existing one
                                    note_db = finding_notes.get(id=note_id)
                                    if note_entry != note_db.entry.rstrip():
                                        note_db.entry = note_entry
                                        note_db.edited = True
                                        note_db.editor = request.user
                                        note_db.edit_time = timezone.now()
                                        history = NoteHistory(
                                            data=note_db.entry,
                                            time=note_db.edit_time,
                                            current_editor=note_db.editor,
                                        )
                                        history.save()
                                        note_db.history.add(history)
                                        note_db.save()
                                else:  # If the note is a newly added one
                                    if note_type_activation:
                                        if note_column_name[7:12] == "Note_":
                                            error = "Can not add new notes without a note-type. Add your note under the correct note-type column"
                                            errors.append(
                                                {
                                                    "finding_id": finding_id,
                                                    "column_names": note_column_name,
                                                    "error": error,
                                                }
                                            )
                                        else:
                                            note_type_name = note_column_name[7:][:-2]
                                            try:
                                                note_type = active_note_types.get(
                                                    name=note_type_name
                                                )
                                            except:
                                                try:
                                                    note_type = Note_Type.objects.get(
                                                        name=note_type_name
                                                    )
                                                except:
                                                    pass
                                                else:
                                                    error = (
                                                        '"'
                                                        + note_type_name
                                                        + '" Note-type is disabled. Cannot add new notes of "'
                                                        + note_type_name
                                                        + '" type'
                                                    )
                                                    errors.append(
                                                        {
                                                            "finding_id": finding_id,
                                                            "column_names": note_column_name,
                                                            "error": error,
                                                        }
                                                    )
                                            else:
                                                new_note = Notes(
                                                    note_type=note_type,
                                                    entry=note_entry,
                                                    date=timezone.now(),
                                                    author=request.user,
                                                )
                                                new_note.save()
                                                history = NoteHistory(
                                                    data=new_note.entry,
                                                    time=new_note.date,
                                                    current_editor=new_note.author,
                                                    note_type=new_note.note_type,
                                                )
                                                history.save()
                                                new_note.history.add(history)
                                                finding_db.notes.add(new_note)
                                    else:
                                        if note_column_name[7:12] == "Note_":
                                            new_note = Notes(
                                                entry=note_entry,
                                                date=timezone.now(),
                                                author=request.user,
                                            )
                                            new_note.save()
                                            history = NoteHistory(
                                                data=new_note.entry,
                                                time=new_note.date,
                                                current_editor=new_note.author,
                                            )
                                            history.save()
                                            new_note.history.add(history)
                                            finding_db.notes.add(new_note)
                                        else:
                                            error_location = (
                                                finding_id + " " + note_column_name
                                            )
                                            error = "Note-types are not enabled. Notes cannot have a note-type."
                                            errors.append(
                                                {
                                                    "finding_id": finding_id,
                                                    "column_names": note_column_name,
                                                    "error": error,
                                                }
                                            )
                finding_db.save()
    res["errors"] = errors
    populate_sheet(tid, spreadsheetId)
    return res


def populate_sheet(tid, spreadsheetId):
    system_settings = get_object_or_404(System_Settings, id=1)
    service_account_info = json.loads(system_settings.credentials)
    service_account_email = service_account_info["client_email"]
    email_address = system_settings.email_address
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    sheets_service = googleapiclient.discovery.build(
        "sheets", "v4", credentials=credentials, cache_discovery=False
    )
    findings_list = get_findings_list(tid)
    row_count = len(findings_list)
    column_count = len(findings_list[0])

    # Create new sheet in the spreadsheet
    now = datetime.datetime.now()
    sheet_title = now.strftime("%Y-%m-%d %H:%M:%S")
    new_sheet = {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "title": sheet_title,
                        "gridProperties": {
                            "rowCount": row_count,
                            "columnCount": column_count,
                        },
                    }
                }
            }
        ]
    }
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheetId, body=new_sheet
    ).execute()

    # Move new sheet to the left most corner
    spreadsheet = (
        sheets_service.spreadsheets().get(spreadsheetId=spreadsheetId).execute()
    )
    for sheet in spreadsheet["sheets"]:
        if sheet["properties"]["title"] == sheet_title:
            sheet_id = sheet["properties"]["sheetId"]
            break
    reqs = {
        "requests": [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "index": 0},
                    "fields": "index",
                }
            }
        ]
    }
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheetId, body=reqs
    ).execute()

    # Update created sheet with finding details
    result = (
        sheets_service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheetId,
            range=sheet_title,
            valueInputOption="RAW",
            body={"values": findings_list},
        )
        .execute()
    )

    # Format the header row
    body = {
        "requests": [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0},
                            "horizontalAlignment": "CENTER",
                            "textFormat": {
                                "foregroundColor": {
                                    "red": 1.0,
                                    "green": 1.0,
                                    "blue": 1.0,
                                },
                                "fontSize": 12,
                                "bold": True,
                            },
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "addProtectedRange": {
                    "protectedRange": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": column_count,
                        },
                        "editors": {"users": [service_account_email, email_address]},
                        # "description": "Protecting total row",
                        "warningOnly": False,
                    }
                }
            },
        ]
    }
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheetId, body=body
    ).execute()

    # Format columns with input field widths and protect columns
    range = sheet_title + "!1:1"
    result = (
        sheets_service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheetId, range=range)
        .execute()
    )
    rows = result.get("values", [])
    header_raw = rows[0]
    fields = Finding._meta.fields
    column_details = json.loads(system_settings.column_widths.replace("'", '"'))
    body = {}
    body["requests"] = []
    for column_name in header_raw:
        index_of_column = header_raw.index(column_name)
        if column_name in column_details:
            # If column width is 0 hide column
            if int(column_details[column_name][0]) == 0:
                body["requests"].append(
                    {
                        "updateDimensionProperties": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "COLUMNS",
                                "startIndex": index_of_column,
                                "endIndex": index_of_column + 1,
                            },
                            "properties": {
                                "hiddenByUser": True,
                            },
                            "fields": "hiddenByUser",
                        }
                    }
                )
            else:
                # If column width is not 0 adjust column to given width
                body["requests"].append(
                    {
                        "updateDimensionProperties": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "COLUMNS",
                                "startIndex": index_of_column,
                                "endIndex": index_of_column + 1,
                            },
                            "properties": {"pixelSize": column_details[column_name][0]},
                            "fields": "pixelSize",
                        }
                    }
                )
            # If protect column is true, protect in sheet
            if column_details[column_name][1] == 1:
                body["requests"].append(
                    {
                        "addProtectedRange": {
                            "protectedRange": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": 1,
                                    "endRowIndex": row_count,
                                    "startColumnIndex": index_of_column,
                                    "endColumnIndex": index_of_column + 1,
                                },
                                "editors": {
                                    "users": [service_account_email, email_address]
                                },
                                "warningOnly": False,
                            }
                        }
                    }
                )
            # Format boolean fields in the google sheet
            if (fields[index_of_column].get_internal_type()) == "BooleanField":
                body["requests"].append(
                    {
                        "setDataValidation": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "endRowIndex": row_count,
                                "startColumnIndex": index_of_column,
                                "endColumnIndex": index_of_column + 1,
                            },
                            "rule": {
                                "condition": {
                                    "type": "BOOLEAN",
                                },
                                "inputMessage": "Value must be BOOLEAN",
                                "strict": True,
                            },
                        }
                    }
                )
            # Format integer fields in the google sheet
            elif (fields[index_of_column].get_internal_type()) == "IntegerField":
                body["requests"].append(
                    {
                        "setDataValidation": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "endRowIndex": row_count,
                                "startColumnIndex": index_of_column,
                                "endColumnIndex": index_of_column + 1,
                            },
                            "rule": {
                                "condition": {
                                    "type": "NUMBER_GREATER",
                                    "values": [{"userEnteredValue": "-1"}],
                                },
                                "inputMessage": "Value must be an integer",
                                "strict": True,
                            },
                        }
                    }
                )
            # Format date fields in the google sheet
            elif (fields[index_of_column].get_internal_type()) == "DateField":
                body["requests"].append(
                    {
                        "setDataValidation": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "endRowIndex": row_count,
                                "startColumnIndex": index_of_column,
                                "endColumnIndex": index_of_column + 1,
                            },
                            "rule": {
                                "condition": {
                                    "type": "DATE_IS_VALID",
                                },
                                "inputMessage": "Value must be a valid date",
                                "strict": True,
                            },
                        }
                    }
                )
            # Make severity column a dropdown
            elif column_name == "severity":
                body["requests"].append(
                    {
                        "setDataValidation": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "endRowIndex": row_count,
                                "startColumnIndex": index_of_column,
                                "endColumnIndex": index_of_column + 1,
                            },
                            "rule": {
                                "condition": {
                                    "type": "ONE_OF_LIST",
                                    "values": [
                                        {"userEnteredValue": "Info"},
                                        {"userEnteredValue": "Low"},
                                        {"userEnteredValue": "Medium"},
                                        {"userEnteredValue": "High"},
                                        {"userEnteredValue": "Critical"},
                                    ],
                                },
                                "inputMessage": "Value must be an one of list",
                                "strict": True,
                            },
                        }
                    }
                )
        # Hide and protect note id columns and last column
        elif (
            column_name[:6] == "[note]" and column_name[-3:] == "_id"
        ) or column_name == "Last column":
            body["requests"].append(
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": index_of_column,
                            "endIndex": index_of_column + 1,
                        },
                        "properties": {
                            "hiddenByUser": True,
                        },
                        "fields": "hiddenByUser",
                    }
                }
            )
            body["requests"].append(
                {
                    "addProtectedRange": {
                        "protectedRange": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "endRowIndex": row_count,
                                "startColumnIndex": index_of_column,
                                "endColumnIndex": index_of_column + 1,
                            },
                            "editors": {
                                "users": [service_account_email, email_address]
                            },
                            "warningOnly": False,
                        }
                    }
                }
            )
        elif column_name[:6] == "[note]" or column_name[:11] == "[duplicate]":
            body["requests"].append(
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": index_of_column,
                            "endIndex": index_of_column + 1,
                        }
                    }
                }
            )
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheetId, body=body
    ).execute()


def get_findings_list(tid):
    test = Test.objects.get(id=tid)
    system_settings = get_object_or_404(System_Settings, id=1)
    findings = Finding.objects.filter(test=test).order_by("numerical_severity")
    active_note_types = Note_Type.objects.filter(is_active=True).order_by("id")
    note_type_activation = active_note_types.count()

    # Create the header row
    fields = Finding._meta.fields
    findings_list = []
    headings = []
    for i in fields:
        headings.append(i.name)
    findings_list.append(headings)

    # Create finding rows
    for finding in findings:
        finding_details = []
        for field in fields:
            value = getattr(finding, field.name)
            if (
                type(value) == datetime.date
                or type(value) == Test
                or type(value) == datetime.datetime
            ):
                var = str(value)
            elif type(value) == User or type(value) == Dojo_User:
                var = value.username
            elif type(value) == Finding:
                var = value.id
            elif type(value) == Sonarqube_Issue:
                var = value.key
            else:
                var = value
            finding_details.append(var)
        findings_list.append(finding_details)

    # Add notes into the findings_list
    if note_type_activation:
        for note_type in active_note_types:
            max_note_count = 1
            if note_type.is_single:
                findings_list[0].append("[note] " + note_type.name + "_1_id")
                findings_list[0].append("[note] " + note_type.name + "_1")
            else:
                for finding in findings:
                    note_count = finding.notes.filter(note_type=note_type).count()
                    if max_note_count < note_count:
                        max_note_count = note_count
                for n in range(max_note_count):
                    findings_list[0].append(
                        "[note] " + note_type.name + "_" + str(n + 1) + "_id"
                    )
                    findings_list[0].append(
                        "[note] " + note_type.name + "_" + str(n + 1)
                    )
            for f in range(findings.count()):
                finding = findings[f]
                notes = finding.notes.filter(note_type=note_type).order_by("id")
                for note in notes:
                    findings_list[f + 1].append(note.id)
                    findings_list[f + 1].append(note.entry)
                missing_notes_count = max_note_count - notes.count()
                for i in range(missing_notes_count):
                    findings_list[f + 1].append("")
                    findings_list[f + 1].append("")
        max_note_count = 0
        for finding in findings:
            note_count = finding.notes.exclude(note_type__in=active_note_types).count()
            if max_note_count < note_count:
                max_note_count = note_count
        if max_note_count > 0:
            for i in range(max_note_count):
                findings_list[0].append("[note] " + "Note_" + str(i + 1) + "_id")
                findings_list[0].append("[note] " + "Note_" + str(i + 1))
            for f in range(findings.count()):
                finding = findings[f]
                notes = finding.notes.exclude(note_type__in=active_note_types).order_by(
                    "id"
                )
                for note in notes:
                    findings_list[f + 1].append(note.id)
                    findings_list[f + 1].append(note.entry)
                missing_notes_count = max_note_count - notes.count()
                for i in range(missing_notes_count):
                    findings_list[f + 1].append("")
                    findings_list[f + 1].append("")
    else:
        max_note_count = 1
        for finding in findings:
            note_count = len(finding.notes.all())
            if note_count > max_note_count:
                max_note_count = note_count
        for i in range(max_note_count):
            findings_list[0].append("[note] " + "Note_" + str(i + 1) + "_id")
            findings_list[0].append("[note] " + "Note_" + str(i + 1))
        for f in range(findings.count()):
            finding = findings[f]
            notes = finding.notes.all().order_by("id")
            for note in notes:
                findings_list[f + 1].append(note.id)
                findings_list[f + 1].append(note.entry)
            missing_notes_count = max_note_count - notes.count()
            for i in range(missing_notes_count):
                findings_list[f + 1].append("")
                findings_list[f + 1].append("")

    if system_settings.enable_deduplication:
        if note_type_activation:
            for note_type in active_note_types:
                findings_list[0].append("[duplicate] " + note_type.name)
            for f in range(findings.count()):
                original_finding = findings[f].duplicate_finding
                for note_type in active_note_types:
                    try:
                        note = original_finding.notes.filter(
                            note_type=note_type
                        ).latest("date")
                        findings_list[f + 1].append(note.entry)
                    except:
                        findings_list[f + 1].append("")
        else:
            findings_list[0].append("[duplicate] note")
            for f in range(findings.count()):
                original_finding = findings[f].duplicate_finding
                try:
                    note = original_finding.notes.latest("date")
                    findings_list[f + 1].append(note.entry)
                except:
                    findings_list[f + 1].append("")

    findings_list[0].append("Last column")
    for f in range(findings.count()):
        findings_list[f + 1].append("-")
    return findings_list
