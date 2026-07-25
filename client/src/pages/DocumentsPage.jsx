import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Upload, FileText, CheckCircle, Clock, Trash2, ArrowRight, ShieldAlert } from "lucide-react";
import api from "../api/client.js";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import { useWorkspace } from "../context/WorkspaceContext.jsx";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState(() => {
    const cached = sessionStorage.getItem("dcpi_documents");
    return cached ? JSON.parse(cached) : [];
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const { currentProject } = useWorkspace();
  
  // Upload States
  const [file, setFile] = useState(null);
  const [docType, setDocType] = useState("specification"); // "specification" | "submittal" | "general"
  const [uploadStatus, setUploadStatus] = useState("");
  const [filter, setFilter] = useState("All");
  
  // Submittal Extra Fields
  const [vendorName, setVendorName] = useState("");
  const [poNumber, setPoNumber] = useState("");

  useEffect(() => {
    if (currentProject) {
      if (documents.length === 0) {
        fetchDocuments();
      } else {
        fetchDocuments(true); // background refresh
      }
    }
  }, [currentProject]);

  const fetchDocuments = async (background = false) => {
    if (!currentProject) return;
    if (!background) setLoading(true);
    if (!background) setError(null);
    try {
      const data = await api.getDocuments(currentProject.id);
      setDocuments(data.documents || []);
      sessionStorage.setItem("dcpi_documents", JSON.stringify(data.documents || []));
    } catch (err) {
      if (!background) setError(err.message || "Failed to load documents");
    } finally {
      if (!background) setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a file to upload");
      return;
    }
    
    setError(null);
    setUploadStatus("Uploading file...");
    const formData = new FormData();
    formData.append("file", file);
    if (currentProject) {
      formData.append("project_id", currentProject.id);
    }

    try {
      let result;
      if (docType === "specification") {
        result = await api.uploadSpecification(formData);
      } else if (docType === "submittal") {
        if (!vendorName || !poNumber) {
          setError("Vendor Name and PO Number are required for submittal uploads");
          setUploadStatus("");
          return;
        }
        formData.append("vendor_name", vendorName);
        formData.append("po_number", poNumber);
        result = await api.uploadSubmittal(formData);
      } else {
        // general upload
        formData.append("doc_type", "general");
        result = await api.uploadGeneral(formData);
      }
      
      if (result.status === "processing") {
        setUploadStatus("File uploaded. Background AI parsing in progress...");
        await api.pollUntilReady(result.document_id, (statusInfo) => {
          setUploadStatus(`Processing: ${statusInfo.queue_status || statusInfo.status}...`);
        });
      }

      setUploadStatus("File uploaded and ingested successfully!");
      setFile(null);
      setVendorName("");
      setPoNumber("");
      fetchDocuments();
    } catch (err) {
      setError(err.message || "Failed to upload document");
      setUploadStatus("");
    }
  };

  const handleDelete = async (docId) => {
    if (!confirm("Are you sure you want to delete this document? All associated records will be removed.")) return;
    setError(null);
    try {
      await api.deleteDocument(docId);
      fetchDocuments();
    } catch (err) {
      setError(err.message || "Failed to delete document");
    }
  };

  return (
    <div className="flex-1 w-full h-full relative bg-[#1a1a1a] overflow-hidden flex flex-col">
      <div className="flex-1 flex overflow-hidden relative z-10 w-full">
        
        {/* Left Panel: Sidebar */}
        <div className="w-[240px] flex-none bg-[#1a1a1a] border-r border-[#333330] flex flex-col overflow-hidden hidden lg:flex">
          {/* Sidebar Header */}
          <div className="h-12 border-b border-[#333330] bg-[#1a1a1a] flex items-center px-4 flex-shrink-0">
            <h1 className="text-[13px] font-bold text-white tracking-wide uppercase">Document Intel</h1>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#8a847b] mb-4 flex items-center gap-2">
              <Upload size={12} /> Upload Document
            </h2>

            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-[10px] font-bold text-[#8a847b] uppercase tracking-wider mb-1.5">Document Type</label>
                <select
                  value={docType}
                  onChange={(e) => {
                    setDocType(e.target.value);
                    setError(null);
                    setUploadStatus("");
                  }}
                  className="w-full bg-[#222222] border border-[#333330] rounded-md px-3 py-2 text-sm text-[#f0ece4] focus:outline-none focus:border-[#b08d6e] transition-colors"
                >
                  <option value="specification">Specification (PDF)</option>
                  <option value="submittal">Vendor Submittal (PDF)</option>
                  <option value="general">Delay Notice (PDF)</option>
                </select>
              </div>

              {docType === "submittal" && (
                <>
                  <div>
                    <label className="block text-[10px] font-bold text-[#8a847b] uppercase tracking-wider mb-1.5">Vendor Name</label>
                    <input
                      type="text"
                      value={vendorName}
                      onChange={(e) => setVendorName(e.target.value)}
                      placeholder="e.g. Vertiv"
                      className="w-full bg-[#222222] border border-[#333330] rounded-md px-3 py-2 text-sm text-[#f0ece4] focus:outline-none focus:border-[#b08d6e] transition-colors placeholder-[#8a847b]"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-[#8a847b] uppercase tracking-wider mb-1.5">PO Number</label>
                    <input
                      type="text"
                      value={poNumber}
                      onChange={(e) => setPoNumber(e.target.value)}
                      placeholder="e.g. PO-2026-001"
                      className="w-full bg-[#222222] border border-[#333330] rounded-md px-3 py-2 text-sm text-[#f0ece4] focus:outline-none focus:border-[#b08d6e] transition-colors placeholder-[#8a847b]"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="block text-[10px] font-bold text-[#8a847b] uppercase tracking-wider mb-1.5">Select PDF File</label>
                <div 
                  className={`relative border border-dashed rounded-lg bg-[#1a1a1a] transition-colors flex flex-col items-center justify-center p-6 text-center group cursor-pointer overflow-hidden ${file ? 'border-[#b08d6e]/50' : 'border-[#333330] hover:border-[#b08d6e]/40'}`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                      setFile(e.dataTransfer.files[0]);
                    }
                  }}
                >
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setFile(e.target.files[0])}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  
                  <div className="w-8 h-8 bg-[#222222] rounded-full flex items-center justify-center mb-2 group-hover:scale-110 transition-transform">
                    <Upload size={14} className={file ? "text-[#b08d6e]" : "text-[#8a847b]"} />
                  </div>
                  
                  {file ? (
                    <>
                      <span className="text-[11px] font-semibold text-[#b08d6e] truncate w-full">{file.name}</span>
                      <span className="text-[10px] text-[#8a847b] mt-1">Ready to upload</span>
                    </>
                  ) : (
                    <>
                      <span className="text-[11px] font-semibold text-[#8a847b]">Drag & Drop PDF</span>
                      <span className="text-[10px] text-[#8a847b] mt-1">or click to browse</span>
                    </>
                  )}
                </div>
              </div>

              <button
                type="submit"
                className="w-full bg-[#222222] hover:bg-[#333330] border border-[#333330] rounded-md p-2 flex items-center justify-center gap-2 text-sm font-semibold text-white transition-colors mt-4"
              >
                <span>Ingest Document</span>
                <ArrowRight size={14} />
              </button>
            </form>
          </div>
        </div>

        {/* Right Panel: Main Content */}
        <div className="flex-1 flex flex-col bg-[#1a1a1a] relative overflow-hidden">
          <div className="flex-1 overflow-y-auto custom-scrollbar p-6 lg:p-10">
            <div className="max-w-4xl mx-auto space-y-6">
              
              {/* Header inside Main Content */}
              <div>
                <h1 className="text-2xl font-bold text-[#f0ece4]">Project Documents</h1>
                <p className="text-[#8a847b] text-sm mt-1">Incorporate specifications, vendor submittals, and delay notices.</p>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="p-3 bg-red-950/30 border border-red-900 text-red-400 rounded-md text-xs font-semibold"
                >
                  {error}
                </motion.div>
              )}

              {uploadStatus && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="p-3 bg-[#222222] border border-[#333330] text-[#b08d6e] rounded-md text-xs font-semibold"
                >
                  {uploadStatus}
                </motion.div>
              )}

              {/* Filters */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[#333330] pb-4 gap-4">
                <h2 className="text-sm font-bold text-[#f0ece4] flex items-center gap-2">
                  <FileText size={16} className="text-[#b08d6e]" />
                  Ingested Documents ({documents.length})
                </h2>
                <div className="flex bg-[#1a1a1a] border border-[#333330] rounded-md p-1 overflow-x-auto">
                  {["All", "Specification", "Submittal", "General"].map((type) => (
                    <button
                      key={type}
                      onClick={() => setFilter(type)}
                      className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${filter === type ? 'bg-[#2a2a2a] text-white shadow-sm' : 'text-[#8a847b] hover:text-[#f0ece4]'}`}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </div>

              {/* Document List */}
              {loading ? (
                <div className="py-10 text-center"><LoadingSpinner message="Fetching document log..." /></div>
              ) : documents.length === 0 ? (
                <div className="text-center py-16 bg-[#1a1a1a] border border-[#333330] rounded-xl">
                  <FileText className="w-12 h-12 text-[#8a847b] mx-auto mb-4" />
                  <h3 className="text-[#f0ece4] font-bold text-sm">No Documents Ingested</h3>
                  <p className="text-[#8a847b] text-xs mt-1">Upload files using the panel on the left.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {documents.filter(doc => filter === "All" || doc.doc_type === filter.toLowerCase()).map(doc => (
                    <motion.div
                      key={doc.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="bg-[#1a1a1a] border border-[#333330] p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-[#333330] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-[#1a1a1a] rounded-lg border border-[#333330]">
                          <FileText size={18} className="text-[#b08d6e]" />
                        </div>
                        <div>
                          <h4 className="font-semibold text-sm text-[#f0ece4] truncate max-w-[200px] sm:max-w-md">{doc.filename}</h4>
                          <div className="flex items-center gap-3 mt-1">
                            <span className="text-[10px] font-bold text-[#8a847b] uppercase tracking-wider">{doc.doc_type}</span>
                            <span className="text-[10px] text-[#8a847b]">{doc.upload_ts?.slice(0, 10)}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border flex items-center gap-1 ${
                          doc.status === 'ready' 
                            ? 'bg-[#222222] border-[#333330] text-[#b08d6e]' 
                            : doc.status === 'processing'
                            ? 'bg-blue-950/30 border-blue-900 text-blue-400'
                            : 'bg-red-950/30 border-red-900 text-red-400'
                        }`}>
                          {doc.status === 'ready' ? <CheckCircle size={10} /> : <Clock size={10} />}
                          {doc.status}
                        </span>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="p-1.5 text-[#8a847b] hover:text-red-400 hover:bg-[#222222] rounded-md transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}

            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
