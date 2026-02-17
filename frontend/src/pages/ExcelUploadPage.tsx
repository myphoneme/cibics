import { useState } from 'react';

import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ShellLayout } from '../components/ShellLayout';
import { useToast } from '../components/ToastProvider';
import { getApiErrorMessage } from '../utils/errors';

interface ImportPreviewRow {
  source_row: number;
  sl_no: string | null;
  short_name: string | null;
  custodian_organization: string | null;
  state: string | null;
  custodian_code: string | null;
  unlo_code: string | null;
  duplicate: boolean;
  duplicate_reasons: string[];
}

interface ImportPreviewData {
  total_rows: number;
  duplicate_rows: number;
  insertable_rows: number;
  preview_rows: ImportPreviewRow[];
}

interface ImportUploadData {
  imported: number;
  created: number;
  updated: number;
  assignees_created: number;
  skipped_duplicates: number;
}

export function ExcelUploadPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<ImportPreviewData | null>(null);
  const [importBusy, setImportBusy] = useState(false);

  async function previewWorkbook() {
    if (!importFile) {
      toast.error('Please choose an Excel file first');
      return;
    }

    setImportBusy(true);
    try {
      const form = new FormData();
      form.append('file', importFile);
      const { data } = await api.post<ImportPreviewData>('/records/import/preview', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setImportPreview(data);
      toast.success('Preview ready. Duplicates are marked below.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to preview Excel file'));
    } finally {
      setImportBusy(false);
    }
  }

  async function uploadWorkbookInsertOnly() {
    if (!importFile) {
      toast.error('Please choose an Excel file first');
      return;
    }

    setImportBusy(true);
    try {
      const form = new FormData();
      form.append('file', importFile);
      const { data } = await api.post<ImportUploadData>('/records/import/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setImportPreview(null);
      toast.success(
        `Upload complete: ${data.created} inserted, ${data.skipped_duplicates} duplicates skipped, ${data.updated} updated`,
      );
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to upload Excel file'));
    } finally {
      setImportBusy(false);
    }
  }

  async function downloadTemplate() {
    try {
      const response = await api.get('/records/import/template', { responseType: 'blob' });
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'Phoneme.xlsx';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Template downloaded');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to download template'));
    }
  }

  return (
    <ShellLayout>
      <section className="panel">
        <h2>Excel Upload</h2>
        {user?.role !== 'SUPER_ADMIN' ? (
          <p className="error-box">Only SUPER_ADMIN can access Excel upload.</p>
        ) : (
          <details className="import-menu" open>
            <summary>Excel Upload Menu</summary>
            <div className="import-row">
              <input
                type="file"
                accept=".xlsx"
                onChange={(e) => {
                  setImportFile(e.target.files?.[0] || null);
                  setImportPreview(null);
                }}
              />
              <button className="btn btn-outline" type="button" onClick={downloadTemplate}>
                Download Template
              </button>
              <button className="btn btn-outline" type="button" disabled={importBusy || !importFile} onClick={previewWorkbook}>
                Preview Duplicates
              </button>
              <button
                className="btn btn-primary"
                type="button"
                disabled={importBusy || !importFile || !importPreview}
                onClick={uploadWorkbookInsertOnly}
              >
                Upload (Insert Only)
              </button>
            </div>
            {importPreview ? (
              <div className="import-preview-box">
                <p>
                  Total rows: {importPreview.total_rows} | Insertable: {importPreview.insertable_rows} | Duplicate/skipped:{' '}
                  {importPreview.duplicate_rows}
                </p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>Sl No</th>
                        <th>Short Name</th>
                        <th>Organization</th>
                        <th>State</th>
                        <th>Custodian Code</th>
                        <th>UNLO Code</th>
                        <th>Duplicate</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importPreview.preview_rows.map((row) => (
                        <tr key={row.source_row} className={row.duplicate ? 'row-duplicate' : ''}>
                          <td>{row.source_row}</td>
                          <td>{row.sl_no || '-'}</td>
                          <td>{row.short_name || '-'}</td>
                          <td>{row.custodian_organization || '-'}</td>
                          <td>{row.state || '-'}</td>
                          <td>{row.custodian_code || '-'}</td>
                          <td>{row.unlo_code || '-'}</td>
                          <td>{row.duplicate ? 'Yes' : 'No'}</td>
                          <td>{row.duplicate_reasons.length ? row.duplicate_reasons.join(', ') : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <small>Preview shows first {importPreview.preview_rows.length} rows only.</small>
              </div>
            ) : null}
            <p className="import-info-text">
              duplicate detection currently uses a composite of sl_no, custodian_code, unlo_code, short_name,
              custodian_organization, state, site_address, pincode plus source_row checks
            </p>
          </details>
        )}
      </section>
    </ShellLayout>
  );
}
