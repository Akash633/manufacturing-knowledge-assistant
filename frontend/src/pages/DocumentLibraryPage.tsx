import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { DocumentItem } from '../types';

export const DocumentLibraryPage: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [selectedDoc, setSelectedDoc] = useState<any | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);

  // Upload Form State
  const [file, setFile] = useState<File | null>(null);
  const [docNumber, setDocNumber] = useState('');
  const [title, setTitle] = useState('');
  const [revision, setRevision] = useState('Rev A');
  const [approvalStatus, setApprovalStatus] = useState('Approved');
  const [category, setCategory] = useState('Standard Operating Procedure');
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, [statusFilter]);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const res = await api.getDocuments(statusFilter || undefined);
      setDocuments(res.items || []);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !docNumber || !title) {
      alert('Please fill out all required fields and choose a PDF or DOCX file.');
      return;
    }

    try {
      setUploading(true);
      const formData = new FormData();
      formData.append('file', file);
      formData.append('document_number', docNumber);
      formData.append('title', title);
      formData.append('revision', revision);
      formData.append('approval_status', approvalStatus);
      formData.append('machine_model', 'DEMO-CNC-01');
      formData.append('section_category', category);

      await api.uploadDocument(formData);
      setShowUploadModal(false);
      setFile(null);
      setDocNumber('');
      setTitle('');
      await loadDocuments();
      alert('Document uploaded and indexed successfully!');
    } catch (err: any) {
      alert(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const viewDetails = async (id: string) => {
    try {
      const data = await api.getDocumentDetails(id);
      setSelectedDoc(data);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      await api.updateDocumentStatus(id, newStatus);
      await loadDocuments();
      if (selectedDoc && selectedDoc.document.id === id) {
        await viewDetails(id);
      }
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div className="page-container space-y-6">
      {/* Top Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>📚 Technical Document Library</span>
            <span className="badge badge-approved text-xs">Authority Controlled</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Browse and manage engineering SOPs, maintenance manuals, and quality alerts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field py-1.5 text-xs w-auto"
          >
            <option value="">All Statuses</option>
            <option value="Approved">Approved Only</option>
            <option value="Superseded">Superseded Only</option>
            <option value="Draft">Draft Only</option>
            <option value="Pending Review">Pending Review</option>
          </select>

          <button onClick={() => setShowUploadModal(true)} className="btn btn-primary text-xs">
            📤 Upload Document
          </button>
        </div>
      </div>

      {/* Documents Table */}
      <div className="card overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Doc Number</th>
              <th>Revision</th>
              <th>Title</th>
              <th>Status</th>
              <th>Pages / Chunks</th>
              <th>Format</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="text-center py-8 text-slate-400">Loading document registry...</td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-8 text-slate-400">No documents found matching criteria.</td>
              </tr>
            ) : (
              documents.map((doc) => (
                <tr key={doc.id} className="cursor-pointer hover:bg-slate-800/50">
                  <td className="font-mono font-bold text-cyan-400 text-xs">{doc.document_number}</td>
                  <td className="font-mono text-xs">{doc.revision}</td>
                  <td className="font-medium text-white text-xs">{doc.title}</td>
                  <td>
                    <span className={`badge ${
                      doc.approval_status === 'Approved' ? 'badge-approved' :
                      doc.approval_status === 'Superseded' ? 'badge-superseded' : 'badge-draft'
                    }`}>
                      {doc.approval_status}
                    </span>
                  </td>
                  <td className="font-mono text-xs text-slate-400">{doc.page_count} pgs / {doc.chunk_count} chks</td>
                  <td className="font-mono text-xs uppercase text-slate-400">{doc.file_type}</td>
                  <td className="text-xs text-slate-400 font-mono">
                    {new Date(doc.updated_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button onClick={() => viewDetails(doc.id)} className="btn btn-secondary py-1 px-2.5 text-xs">
                        Inspect
                      </button>
                      <select
                        value={doc.approval_status}
                        onChange={(e) => handleStatusChange(doc.id, e.target.value)}
                        className="bg-slate-900 border border-slate-700 text-xs rounded px-1.5 py-1 text-slate-300"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <option value="Approved">Approved</option>
                        <option value="Draft">Draft</option>
                        <option value="Pending Review">Pending Review</option>
                        <option value="Superseded">Superseded</option>
                        <option value="Withdrawn">Withdrawn</option>
                      </select>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal: Document Inspector Drawer */}
      {selectedDoc && (
        <div className="card border-cyan-500/50 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="font-bold text-white text-lg flex items-center gap-2">
                <span>{selectedDoc.document.document_number} ({selectedDoc.document.revision})</span>
                <span className="badge badge-approved text-xs">{selectedDoc.document.approval_status}</span>
              </h3>
              <p className="text-xs text-slate-400">{selectedDoc.document.title}</p>
            </div>
            <button onClick={() => setSelectedDoc(null)} className="btn btn-secondary text-xs">
              ✕ Close
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono bg-slate-950 p-3 rounded">
            <div><span className="text-slate-500">SHA256 CHECKSUM:</span> <div className="truncate text-cyan-300">{selectedDoc.document.checksum}</div></div>
            <div><span className="text-slate-500">AUTHORITY:</span> <div className="text-emerald-400">{selectedDoc.authority_evaluation?.is_authoritative ? 'AUTHORITATIVE' : 'NON-AUTHORITATIVE'}</div></div>
            <div><span className="text-slate-500">FILE TYPE:</span> <div className="text-white uppercase">{selectedDoc.document.file_type}</div></div>
            <div><span className="text-slate-500">PAGES / CHUNKS:</span> <div className="text-white">{selectedDoc.document.page_count} / {selectedDoc.chunks.length}</div></div>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
              Extracted Chunks & Page Evidence ({selectedDoc.chunks.length})
            </h4>
            <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
              {selectedDoc.chunks.map((chk: any) => (
                <div key={chk.id} className="p-3 bg-slate-900 border border-slate-800 rounded text-xs space-y-2">
                  <div className="flex justify-between items-center text-slate-400 font-mono">
                    <span className="text-cyan-400 font-bold">Chunk #{chk.chunk_index} | Page {chk.page_number}</span>
                    <span>[{chk.section_title}]</span>
                  </div>
                  <div className="text-slate-300 whitespace-pre-wrap">{chk.content}</div>
                  {chk.image_paths && chk.image_paths.length > 0 && (
                    <div className="pt-2 border-t border-slate-800 flex gap-2">
                      {chk.image_paths.map((imgUrl: string, idx: number) => (
                        <a key={idx} href={imgUrl} target="_blank" rel="noreferrer" className="text-xs text-cyan-400 underline">
                          📷 View Page Schematic #{idx + 1}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="card w-full max-w-lg space-y-4 border-slate-700">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Upload Manufacturing Document</h3>
              <button onClick={() => setShowUploadModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleUpload} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Document File (.pdf or .docx)*</label>
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="input-field py-1.5"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Document Number*</label>
                  <input
                    type="text"
                    value={docNumber}
                    onChange={(e) => setDocNumber(e.target.value)}
                    placeholder="e.g. SOP-CNC-002"
                    className="input-field"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Revision*</label>
                  <input
                    type="text"
                    value={revision}
                    onChange={(e) => setRevision(e.target.value)}
                    placeholder="Rev A"
                    className="input-field"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Document Title*</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Spindle Chuck Clamp Maintenance"
                  className="input-field"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Approval Status</label>
                  <select
                    value={approvalStatus}
                    onChange={(e) => setApprovalStatus(e.target.value)}
                    className="input-field"
                  >
                    <option value="Approved">Approved</option>
                    <option value="Draft">Draft</option>
                    <option value="Pending Review">Pending Review</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Category</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="input-field"
                  >
                    <option value="Standard Operating Procedure">Standard Operating Procedure</option>
                    <option value="Maintenance">Maintenance</option>
                    <option value="Quality Alert">Quality Alert</option>
                    <option value="Safety Standard">Safety Standard</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button type="button" onClick={() => setShowUploadModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={uploading} className="btn btn-primary">
                  {uploading ? 'Processing & Indexing...' : 'Upload & Parse'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
