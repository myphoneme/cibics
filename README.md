# CIBICS Tracking Project

React + TypeScript frontend, FastAPI + PostgreSQL backend.

## What has been implemented

- Assignee creation from `PO STATUS` names in Excel (`PO Received` is treated as status, not assignee).
- Role-based access: `SUPER_ADMIN`, `ASSIGNEE`, `EMAIL_TEAM`.
- Dynamic stages (not fixed to 6 only):
  - Stage definitions table.
  - Per-record stage progress table.
  - Admin UI to add stages.
- Audit metadata fields on core tables:
  - `created_at`, `updated_at`, `is_active`, `updated_by`, `deleted_by`, `deleted_at`.
- Email alert recipient control:
  - `users.receive_alert` boolean (default `true` for all users).
- Import behavior: overwrite from Excel (source-of-truth re-import).
- Row highlight + alert when client email is captured/changed.
- Group-by assignee dashboard and mobile-friendly UI.
- Black/orange theme + dark/light mode toggle.

## Excel analysis (`Phoneme.xlsx`)

- Data rows: `755`
- Follow-up columns currently empty for all rows:
  - `Customer Name`, `Mobile No`, `Email id`
  - pipeline columns (`email sent to customer` ... `Po received`)
- `PO STATUS` distribution:
  - `PO Received`: `217`
  - `Krishan Kumar`: `234`
  - `Ashutosh Shrivastava`: `147`
  - `Nitin Chaudhary`: `60`
  - `Renuka`: `54`
  - `Dhruv`: `43`

## Database import status

Data has been imported into PostgreSQL:
- DB: `cibics`
- Host: `localhost`
- Port: `5432`
- User used for successful connection: `postgres`
- Password: `123456`

Imported result:
- `755` records inserted
- `5` assignee users created
- `6` default stage definitions created
- `4530` record-stage rows created (`755 * 6`)

## Runtime setup

### Backend

```powershell
pip install -r backend\requirements.txt
cd backend
python run.py
```

### Sync missing client emails from Excel (optional)

If your DB has fewer `client_email` values than the Excel sheet, run:

```powershell
# Use the backend venv/python so dependencies are available
backend\venv\Scripts\python.exe scripts\sync_emails_from_excel.py --excel Phoneme.xlsx

# If "Email id" column is empty, you can fill from "Custodian Email" instead
backend\venv\Scripts\python.exe scripts\sync_emails_from_excel.py --excel Phoneme.xlsx --header "Custodian Email"

# Preview without writing
backend\venv\Scripts\python.exe scripts\sync_emails_from_excel.py --excel Phoneme.xlsx --header "Custodian Email" --dry-run
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Default ports:
- Backend API: `8200`
- Frontend dev server: `3100`

## Important note for this environment

In this execution environment, package install was blocked by OS permissions. A fallback importer script was used:
- `scripts/import_phoneme_to_db.py`

Because auth dependencies were not installable here initially, a fallback importer script was used once. After dependency installation and re-import, users are now seeded with normal app hashing.

## Key files

- Backend models: `backend/app/models.py`
- Excel importer logic: `backend/app/importers/excel_importer.py`
- Records + stages API: `backend/app/routers/records.py`
- Dashboard API: `backend/app/routers/dashboard.py`
- User API (`receive_alert`): `backend/app/routers/users.py`
- Dynamic records UI: `frontend/src/pages/RecordsPage.tsx`
- Users UI (`receive_alert`): `frontend/src/pages/UsersPage.tsx`
