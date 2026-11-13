import json, os, mimetypes
from pathlib import Path
import streamlit as st

def google_configured():
    try:
        return bool(st.secrets.get("gcp_service_account")) and bool(st.secrets.get("google",{}).get("spreadsheet_id"))
    except Exception:
        return False

def _credentials():
    from google.oauth2.service_account import Credentials
    info=dict(st.secrets["gcp_service_account"])
    scopes=[
      "https://www.googleapis.com/auth/drive",
      "https://www.googleapis.com/auth/spreadsheets"
    ]
    return Credentials.from_service_account_info(info,scopes=scopes)

def upload_folder_to_drive(folder, job_id):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds=_credentials()
    drive=build("drive","v3",credentials=creds,cache_discovery=False)
    parent=st.secrets.get("google",{}).get("drive_folder_id","")
    meta={"name":job_id,"mimeType":"application/vnd.google-apps.folder"}
    if parent: meta["parents"]=[parent]
    folder_obj=drive.files().create(body=meta,fields="id,webViewLink").execute()
    folder_id=folder_obj["id"]
    for path in Path(folder).glob("*"):
        if not path.is_file() or path.name.startswith("reference_"): continue
        mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        media=MediaFileUpload(str(path),mimetype=mime,resumable=True)
        drive.files().create(
            body={"name":path.name,"parents":[folder_id]},
            media_body=media,fields="id"
        ).execute()
    return f"https://drive.google.com/drive/folders/{folder_id}"

def save_job_to_google(manifest, drive_url=""):
    import gspread
    creds=_credentials()
    gc=gspread.authorize(creds)
    sh=gc.open_by_key(st.secrets["google"]["spreadsheet_id"])
    try:
        ws=sh.worksheet("Production")
    except Exception:
        ws=sh.add_worksheet(title="Production",rows=1000,cols=12)
        ws.append_row(["job_id","product_name","market","created_at","slides","engine","drive_url","status"])
    row=[
      manifest.get("job_id",""),
      manifest.get("product",{}).get("product_name",""),
      manifest.get("product",{}).get("market",""),
      manifest.get("created_at",""),
      len(manifest.get("slides",[])),
      manifest.get("engine",""),
      drive_url,
      "Généré - à vérifier"
    ]
    ws.append_row(row,value_input_option="USER_ENTERED")
