# CIBICS Software SOP (Standard Operating Procedure)

## 1. Purpose
This SOP explains how to use the CIBICS tracking software for daily operations, data upload, record updates, and monitoring.

## 2. Who Uses This Software
- `SUPER_ADMIN`
- `ASSIGNEE`
- `EMAIL_TEAM`

Each role sees different actions based on permission.

## 3. What the Software Does (Brief)
CIBICS is used to:
- Track customer/site records
- Assign records to users
- Capture customer contact details (name, mobile, email)
- Track progress through pipeline stages
- Upload new records through Excel (insert-only)
- Detect and skip duplicate rows during upload
- Monitor and acknowledge pending email alerts

## 4. Login & Access
1. Open the application URL in browser.
2. Login with your official credentials.
3. Use the left menu to navigate:
- `Dashboard`
- `Records`
- `Excel Upload` (SUPER_ADMIN)
- `Users` / `Profile`

## 5. Daily Workflow by Role

### A) SUPER_ADMIN
1. Open `Records` to monitor and manage all records.
2. Use filters/search for assignee, status, and alerts.
3. Click `Action` on any record to edit details or stage progress.
4. Use `Delete` when a record must be deactivated.
5. Open `Excel Upload` to upload new data.

### B) ASSIGNEE
1. Open `Records` and work only on assigned records.
2. Update:
- Customer Name
- Mobile No
- Client Email
- Notes
3. Save changes after each interaction.

### C) EMAIL_TEAM
1. Open `Records`.
2. Update relevant stage progress and notes.
3. Use `Ack` to acknowledge pending email alerts after handling.

## 6. Excel Upload SOP (SUPER_ADMIN)
Open `Excel Upload` from left menu.

### Step 1: Download Template
1. Click `Download Template`.
2. Use this format only (`Phoneme.xlsx` structure).

### Step 2: Choose File
1. Click `Choose File`.
2. Select `.xlsx` file.

### Step 3: Preview Duplicates
1. Click `Preview Duplicates`.
2. Review summary:
- Total rows
- Insertable rows
- Duplicate/skipped rows
3. Duplicate rows are highlighted.

### Step 4: Upload
1. Click `Upload (Insert Only)`.
2. System inserts only new rows.
3. Duplicate rows are skipped automatically.
4. Existing records are NOT modified by Excel upload.

## 7. Duplicate Detection Logic (Current)
Duplicates are checked using composite values of:
- `sl_no`
- `custodian_code`
- `unlo_code`
- `short_name`
- `custodian_organization`
- `state`
- `site_address`
- `pincode`
Plus `source_row` checks.

## 8. Record Management Rules
- Excel upload is insert-only.
- Duplicate rows are skipped with message.
- Existing records are not overwritten by upload.
- Only `SUPER_ADMIN` can delete records.
- Deleted records are soft-deleted (hidden from active list).

## 9. Alerts & Status Flow
- If client email is newly captured/changed, alert can become pending.
- `EMAIL_TEAM`/`SUPER_ADMIN` can acknowledge alerts.
- Status is derived from stage completion and data updates.

## 10. Troubleshooting (Quick)
- File rejected: ensure `.xlsx` format.
- Upload button disabled: first run `Preview Duplicates`.
- Duplicate count high: verify source file content and unique keys.
- Missing menu/action: check your role permission.

## 11. Data Quality Best Practices
- Always use latest template.
- Keep key fields consistent (codes, names, state spelling).
- Avoid blank/partial duplicates in master sheet.
- Validate preview before final upload.

## 12. Escalation
For login issues, permission issues, or unexpected errors, contact:
- System Admin / SUPER_ADMIN
- Technical support owner for CIBICS

---
Document: `SOP_CIBICS.md`
Version: `1.0`
Created on: `February 17, 2026`
