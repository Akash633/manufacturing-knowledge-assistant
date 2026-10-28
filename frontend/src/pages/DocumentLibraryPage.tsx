import React, { FormEvent, useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { api, ApiError } from '../services/api';
import { DocumentDetails, DocumentItem, SystemHealth } from '../types';

const PAGE_SIZE = 25;
const STATUSES = ['Approved', 'Draft', 'Pending Review', 'Withdrawn', 'Expired', 'Not Yet Effective'];

interface DocumentLibraryPageProps {
  machineModel: string;
  health: SystemHealth | null;
}

export const DocumentLibraryPage: React.FC<DocumentLibraryPageProps> = ({ machineModel, health }) => {
  const { can, status: authStatus } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetails | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [docNumber, setDocNumber] = useState('');
  const [title, setTitle] = useState('');
  const [revision, setRevision] = useState('Rev A');
  const [approvalStatus, setApprovalStatus] = useState('Draft');
  const [category, setCategory] = useState('Standard Operating Procedure');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [busyDocumentId, setBusyDocumentId] = useState<string | null>(null);

  const uploaderAllowed = can('document_uploader');
  const approverAllowed = can('document_approver');
  const maxFileSizeMb = health?.max_file_size_mb || 25;

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.getDocuments(statusFilter || undefined, machineModel, page * PAGE_SIZE, PAGE_SIZE, search)
      .then((response) => {
        if (!active) return;
        setDocuments(response.items);
        setTotal(response.total);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setDocuments([]);
        setTotal(0);
        setError(reason instanceof ApiError ? reason.message : 'The document registry could not be loaded.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [machineModel, page, search, statusFilter]);

  const handleUpload = async (event: FormEvent) => {
    event.preventDefault();
    setUploadError(null);
    setUploadMessage(null);
    if (!file || !docNumber.trim() || !title.trim()) {
      setUploadError('Select a document and complete the document number and title.');
      return;
    }
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      setUploadError('Only PDF and DOCX files are supported.');
      return;
    }
    if (file.size > maxFileSizeMb * 1024 * 1024) {
      setUploadError(`The selected file exceeds the ${maxFileSizeMb} MB upload limit.`);
      return;
    }
    if (approvalStatus !== 'Draft' && !approverAllowed) {
      setUploadError('Your verified identity does not have document_approver permission.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_number', docNumber);
    formData.append('title', title);
    formData.append('revision', revision);
    formData.append('approval_status', approvalStatus);
    formData.append('machine_model', machineModel);
    formData.append('section_category', category);

    setUploading(true);
    try {
      const uploaded = await api.uploadDocument(formData);
      setShowUploadModal(false);
      setFile(null);
      setDocNumber('');
      setTitle('');
      setApprovalStatus('Draft');
      setPage(0);
      setUploadMessage(`${uploaded.document_number} ${uploaded.revision} was uploaded as ${uploaded.approval_status}.`);
      await reloadDocuments();
    } catch (reason) {
      setUploadError(reason instanceof ApiError ? reason.message : 'The upload could not be completed.');
    } finally {
      setUploading(false);
    }
  };

  const reloadDocuments = async () => {
    try {
      const response = await api.getDocuments(
        statusFilter || undefined,
        machineModel,
        page * PAGE_SIZE,
        PAGE_SIZE,
        search,
      );
      setDocuments(response.items);
      setTotal(response.total);
      setError(null);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'The document registry could not be refreshed.');
    }
  };

  const viewDetails = async (id: string) => {
    setDetailLoading(true);
    setError(null);
    try {
      setSelectedDoc(await api.getDocumentDetails(id));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Document details could not be loaded.');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleStatusChange = async (doc: DocumentItem, nextStatus: string) => {
    setBusyDocumentId(doc.id);
    setError(null);
    try {
      await api.updateDocumentStatus(doc.id, nextStatus);
      await reloadDocuments();
      if (selectedDoc?.document.id === doc.id) await viewDetails(doc.id);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'The document status could not be changed.');
      await reloadDocuments();
    } finally {
      setBusyDocumentId(null);
    }
  };

  const handleDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Delete ${doc.document_number} ${doc.revision}? This action cannot be undone.`)) return;
    setBusyDocumentId(doc.id);
    setError(null);
    try {
      await api.deleteDocument(doc.id);
      if (selectedDoc?.document.id === doc.id) setSelectedDoc(null);
      await reloadDocuments();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'The document could not be deleted.');
    } finally {
      setBusyDocumentId(null);
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="page-container">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Controlled records</p>
          <h1>Document library</h1>
          <p className="page-description">Search and inspect revisions for {machineModel}. Authority depends on status, effective dates and supersession links.</p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setUploadError(null);
            setShowUploadModal(true);
          }}
          disabled={!uploaderAllowed}
          title={!uploaderAllowed ? 'A verified document_uploader role is required.' : undefined}
        >
          Upload document
        </button>
      </section>

      {!uploaderAllowed && (
        <div className="notice notice-neutral" role="status">
          Upload is disabled until a trusted OIDC identity with the <code>document_uploader</code> role is verified.
          {authStatus === 'unconfigured' && ' OIDC is not configured for this deployment.'}
        </div>
      )}
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {uploadMessage && <div className="notice notice-success" role="status">{uploadMessage}</div>}

      <section className="panel">
        <div className="library-toolbar">
          <label className="search-field">
            <span className="field-label">Search documents</span>
            <input
              type="search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(0);
              }}
              placeholder="Document number or title"
            />
          </label>
          <label className="control-inline">
            Approval status
            <select
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setPage(0);
              }}
            >
              <option value="">All statuses</option>
              {STATUSES.map((statusValue) => <option key={statusValue}>{statusValue}</option>)}
            </select>
          </label>
          <span className="result-count">{total.toLocaleString()} record(s)</span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th>
                <th>Revision</th>
                <th>Title</th>
                <th>Status</th>
                <th>Pages / chunks</th>
                <th>Type</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="table-state">Loading document records…</td></tr>
              ) : documents.length === 0 ? (
                <tr><td colSpan={8} className="table-state">No documents match the current filters.</td></tr>
              ) : documents.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <strong className="document-number">{doc.document_number}</strong>
                    {doc.is_synthetic_demo && <span className="source-tag">Synthetic</span>}
                  </td>
                  <td>{doc.revision}</td>
                  <td>{doc.title}</td>
                  <td><StatusBadge status={doc.approval_status} /></td>
                  <td>{doc.page_count} / {doc.chunk_count}</td>
                  <td>{doc.file_type.toUpperCase()}</td>
                  <td>{new Date(doc.updated_at).toLocaleDateString()}</td>
                  <td>
                    <div className="table-actions">
                      <button type="button" className="text-button" onClick={() => void viewDetails(doc.id)}>
                        Inspect
                      </button>
                      {approverAllowed && (
                        <select
                          aria-label={`Change status for ${doc.document_number} ${doc.revision}`}
                          value={doc.approval_status}
                          onChange={(event) => void handleStatusChange(doc, event.target.value)}
                          disabled={busyDocumentId === doc.id}
                        >
                          {[doc.approval_status, ...STATUSES.filter((value) => value !== doc.approval_status)].map((value) => (
                            <option key={value}>{value}</option>
                          ))}
                        </select>
                      )}
                      {can('admin') && (
                        <button
                          type="button"
                          className="text-button text-danger"
                          onClick={() => void handleDelete(doc)}
                          disabled={busyDocumentId === doc.id}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <span>Page {Math.min(page + 1, pageCount)} of {pageCount}</span>
          <div>
            <button type="button" className="btn btn-secondary" onClick={() => setPage((value) => Math.max(0, value - 1))} disabled={page === 0 || loading}>Previous</button>
            <button type="button" className="btn btn-secondary" onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))} disabled={page >= pageCount - 1 || loading}>Next</button>
          </div>
        </div>
      </section>

      {detailLoading && <div className="loading-state" role="status">Loading document evidence…</div>}
      {selectedDoc && (
        <section className="panel document-detail" aria-label="Document details">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Revision record</p>
              <h2>{selectedDoc.document.document_number} · {selectedDoc.document.revision}</h2>
              <p>{selectedDoc.document.title}</p>
            </div>
            <button type="button" className="btn btn-secondary" onClick={() => setSelectedDoc(null)}>Close details</button>
          </div>
          <div className="detail-grid">
            <Detail label="Approval status" value={selectedDoc.document.approval_status} />
            <Detail label="Authority" value={selectedDoc.authority_evaluation.is_authoritative ? 'Authoritative' : selectedDoc.authority_evaluation.reason} />
            <Detail label="Machine" value={selectedDoc.document.machine_model} />
            <Detail label="Effective date" value={selectedDoc.document.effective_date ? new Date(selectedDoc.document.effective_date).toLocaleDateString() : 'Not specified'} />
            <Detail label="Expiry date" value={selectedDoc.document.expiry_date ? new Date(selectedDoc.document.expiry_date).toLocaleDateString() : 'Not specified'} />
            <Detail label="Checksum" value={selectedDoc.document.checksum || 'Not available'} />
          </div>
          <h3 className="section-title">Extracted evidence ({selectedDoc.chunks.length} chunks)</h3>
          <div className="chunk-list">
            {selectedDoc.chunks.map((chunk) => (
              <article className="chunk-card" key={chunk.id}>
                <div className="citation-title">
                  <strong>Page {chunk.page_number} · {chunk.section_title || 'Section not specified'}</strong>
                  <span>{chunk.token_count} tokens</span>
                </div>
                <p>{chunk.content}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      {showUploadModal && (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !uploading) setShowUploadModal(false);
        }}>
          <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="upload-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Ingestion</p>
                <h2 id="upload-title">Upload a document</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setShowUploadModal(false)} disabled={uploading} aria-label="Close upload dialog">×</button>
            </div>
            <p className="modal-description">PDF or DOCX · maximum {maxFileSizeMb} MB · machine scope {machineModel}.</p>
            {uploadError && <div className="notice notice-error" role="alert">{uploadError}</div>}
            <form onSubmit={(event) => void handleUpload(event)} className="form-grid">
              <label className="form-field form-span">
                <span>Document file</span>
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                  required
                />
              </label>
              {file && <p className="file-selection form-span">{file.name} · {(file.size / (1024 * 1024)).toFixed(2)} MB</p>}
              <label className="form-field">
                <span>Document number</span>
                <input value={docNumber} onChange={(event) => setDocNumber(event.target.value)} required maxLength={64} />
              </label>
              <label className="form-field">
                <span>Revision</span>
                <input value={revision} onChange={(event) => setRevision(event.target.value)} required maxLength={32} />
              </label>
              <label className="form-field form-span">
                <span>Title</span>
                <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={255} />
              </label>
              <label className="form-field">
                <span>Initial status</span>
                <select value={approvalStatus} onChange={(event) => setApprovalStatus(event.target.value)}>
                  {approverAllowed
                    ? ['Draft', 'Pending Review', 'Approved'].map((value) => <option key={value}>{value}</option>)
                    : <option>Draft</option>}
                </select>
              </label>
              <label className="form-field">
                <span>Category</span>
                <select value={category} onChange={(event) => setCategory(event.target.value)}>
                  {['Standard Operating Procedure', 'Maintenance', 'Quality Alert', 'Safety Standard'].map((value) => <option key={value}>{value}</option>)}
                </select>
              </label>
              <div className="form-actions form-span">
                <button type="button" className="btn btn-secondary" onClick={() => setShowUploadModal(false)} disabled={uploading}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={uploading || !uploaderAllowed}>
                  {uploading ? 'Validating and indexing…' : 'Upload document'}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const tone = status === 'Approved' ? 'status-positive' :
    status === 'Superseded' || status === 'Withdrawn' || status === 'Expired' ? 'status-negative' :
      'status-warning';
  return <span className={`status-pill ${tone}`}>{status}</span>;
};

const Detail: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="detail-cell"><dt>{label}</dt><dd>{value}</dd></div>
);
