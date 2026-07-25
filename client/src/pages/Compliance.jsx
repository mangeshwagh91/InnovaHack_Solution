import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Play, ShieldAlert, CheckCircle, Activity, Box, ChevronDown, AlertTriangle } from "lucide-react";
import api from "../api/client.js";
import SeverityBadge from "../components/SeverityBadge.jsx";
import AIProcessingTimeline from "../components/compliance/AIProcessingTimeline.jsx";
import { useWorkspace } from "../context/WorkspaceContext.jsx";

function AnimatedCounter({ value, suffix = "" }) {
  return <span>{value}{suffix}</span>;
}

function DocSelect({ label, stepNumber, color, docs, value, onChange, placeholder, docsLoading }) {
  return (
    <div className="mb-6">
      <label className="flex items-center gap-2 text-[10px] font-bold text-[#8a847b] uppercase tracking-wider mb-2">
        <span className="w-4 h-4 rounded-full flex items-center justify-center text-white text-[9px]" style={{ backgroundColor: color }}>{stepNumber}</span>
        {label}
      </label>

      {docsLoading ? (
        <div className="h-9 bg-[#333330] rounded-md animate-pulse" />
      ) : docs.length === 0 ? (
        <div className="flex items-start gap-2 p-3 bg-amber-950/20 border border-amber-900/50 rounded-md text-amber-500 text-xs">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>No {label.toLowerCase()} found. <Link to="/documents" className="underline font-semibold block mt-1 hover:text-amber-400">Upload in Documents →</Link></span>
        </div>
      ) : (
        <div className="relative">
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-full appearance-none bg-[#222222] border border-[#333330] rounded-md px-3 py-2 text-sm text-[#f0ece4] focus:outline-none focus:border-[#b08d6e] transition-colors pr-8"
          >
            <option value="">{placeholder}</option>
            {docs.map((d) => (
              <option key={d.id || d.document_id} value={d.id || d.document_id}>
                {d.filename || d.name || d.id}
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8a847b] pointer-events-none" />
        </div>
      )}

      {value && (
        <div className="mt-2 flex items-center gap-1.5 text-[11px] text-[#b08d6e] font-medium">
          <CheckCircle size={12} /> Selected
        </div>
      )}
    </div>
  );
}

export default function Compliance() {
  const { currentProject } = useWorkspace();
  const [documents, setDocuments] = useState(() => {
    const cached = sessionStorage.getItem("dcpi_documents");
    return cached ? JSON.parse(cached) : [];
  });
  const [docsLoading, setDocsLoading] = useState(documents.length === 0);
  const [selectedSpecId, setSelectedSpecId] = useState("");
  const [selectedSubmId, setSelectedSubmId] = useState("");
  const [equipmentList, setEquipmentList] = useState([]);
  const [currentPoId, setCurrentPoId] = useState("");
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [runningCheck, setRunningCheck] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [selectedNcr, setSelectedNcr] = useState(null);
  const [status, setStatus] = useState("");

  const navigate = useNavigate();

  useEffect(() => {
    if (!currentProject) return;
    setDocsLoading(documents.length === 0);
    api.getDocuments(currentProject.id)
      .then((data) => {
        setDocuments(data.documents || []);
        sessionStorage.setItem("dcpi_documents", JSON.stringify(data.documents || []));
      })
      .catch(() => setDocuments([]))
      .finally(() => setDocsLoading(false));

    api.getEquipmentItems()
      .then((data) => setEquipmentList(data.equipment_items || []))
      .catch(() => {});

    api.getPurchaseOrders()
      .then((data) => setPurchaseOrders(data || []))
      .catch(() => {});
  }, [currentProject]);

  useEffect(() => {
    if (selectedSubmId && purchaseOrders.length > 0) {
      const po = purchaseOrders.find(p => p.document_id === selectedSubmId);
      if (po) {
        setCurrentPoId(po.id);
      }
    } else if (!selectedSubmId) {
      setCurrentPoId("");
    }
  }, [selectedSubmId, purchaseOrders]);


  useEffect(() => {
    const savedSettings = localStorage.getItem('agentSettings');
    let autoRun = true;
    if (savedSettings) {
      try {
        const parsed = JSON.parse(savedSettings);
        autoRun = parsed.autoRunOnUpload;
      } catch (_) {}
    }
    
    if (autoRun && selectedSpecId && selectedSubmId && currentPoId && !runningCheck && !results && !error) {
       handleRunCheck();
    }
  }, [selectedSpecId, selectedSubmId, currentPoId]);

  const specDocs = documents.filter(d => d.doc_type === "specification" || d.document_type === "specification");
  const submDocs = documents.filter(d => d.doc_type === "submittal" || d.document_type === "submittal");

  async function handleRunCheck() {
    if (!currentPoId) {
      setError("No purchase order available. Please upload a vendor submittal in Documents & Specs.");
      return;
    }
    try {
      setRunningCheck(true);
      setError(null);
      setSelectedNcr(null);
      setStatus("Running Spec Compliance Agent...");
      const data = await api.runComplianceCheck(currentPoId);
      setResults(data);
      setStatus(`✓ Check complete — ${data.summary?.total || 0} deviations found`);
    } catch (err) {
      setError(err.message);
      setStatus("");
    } finally {
      setRunningCheck(false);
    }
  }

  const step3Active = !!selectedSpecId && !!currentPoId;

  return (
    <div className="flex-1 w-full h-full relative bg-[#1a1a1a] overflow-hidden flex flex-col text-white">
      <div className="flex-1 flex overflow-hidden relative z-10 w-full">
        
        {/* ─── Left Sidebar: Pickers ────────────────────────────────────────────── */}
        <div className="w-[280px] flex-none bg-[#1a1a1a] border-r border-[#333330] flex flex-col overflow-hidden hidden lg:flex">
          {/* Sidebar Header */}
          <div className="h-12 border-b border-[#333330] bg-[#222222] flex items-center px-4 flex-shrink-0">
            <h1 className="text-[13px] font-bold text-white tracking-wide uppercase">Compliance Intel</h1>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar p-5 flex flex-col">
            <div className="mb-6 bg-blue-950/20 border border-blue-900/50 rounded-lg p-3 text-xs text-blue-300/80 font-medium leading-relaxed">
              Documents are pulled from your <Link to="/documents" className="underline font-bold text-blue-300">Documents</Link> library.
            </div>

            <DocSelect
              label="Specification"
              stepNumber="1"
              color="#0F3058"
              docs={specDocs}
              value={selectedSpecId}
              onChange={setSelectedSpecId}
              placeholder="Select specification"
              docsLoading={docsLoading}
            />

            <DocSelect
              label="Vendor Submittal"
              stepNumber="2"
              color="#8B5CF6"
              docs={submDocs}
              value={selectedSubmId}
              onChange={setSelectedSubmId}
              placeholder="Select vendor submittal"
              docsLoading={docsLoading}
            />

            <div className="mt-auto pt-6">
              <motion.div 
                className={`relative z-10 transition-all duration-300 ${!step3Active ? "opacity-40 pointer-events-none" : ""}`}
              >
                <button
                  onClick={handleRunCheck}
                  disabled={runningCheck || !step3Active}
                  className="w-full bg-[#b08d6e] hover:bg-[#b08d6e]/90 text-white rounded-lg p-4 shadow-sm transition-all flex flex-col items-center justify-center gap-2 relative overflow-hidden group"
                >
                  <div className="w-8 h-8 bg-black/10 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Play fill="currentColor" size={14} className="ml-0.5" />
                  </div>
                  <div className="text-center">
                    <h3 className="font-bold text-sm">Run AI Compliance</h3>
                  </div>
                </button>
              </motion.div>
            </div>
          </div>
        </div>

        {/* ─── Main Canvas ────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-8 relative flex flex-col bg-[#1a1a1a]">
          
          <div className="max-w-6xl mx-auto w-full">
            {/* Header / KPIs */}
            <div className="mb-8">
              <h2 className="text-[22px] font-bold tracking-tight mb-2">Compliance Intelligence</h2>
              <p className="text-[#8a847b] text-sm max-w-2xl mb-8">
                Compare project specifications with vendor submissions using AI to instantly identify deviations, ensure compliance and generate intelligent recommendations.
              </p>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Documents Processed", val: 124, icon: <FileText size={16} /> },
                  { label: "Compliance Accuracy", val: 98, suffix: "%", icon: <CheckCircle size={16} /> },
                  { label: "Critical Deviations", val: results?.summary?.critical || 3, icon: <ShieldAlert size={16} /> },
                  { label: "AI Status", val: "Online", icon: <Activity size={16} /> }
                ].map((kpi, i) => (
                  <motion.div 
                    key={i} 
                    initial={{ opacity: 0, y: 10 }} 
                    animate={{ opacity: 1, y: 0 }} 
                    transition={{ delay: 0.05 * i }}
                    className="bg-[#222222] border border-[#333330] p-4 rounded-xl shadow-sm"
                  >
                    <div className="text-[#b08d6e] mb-2">{kpi.icon}</div>
                    <div className="text-2xl font-bold text-white"><AnimatedCounter value={kpi.val} suffix={kpi.suffix} /></div>
                    <div className="text-[10px] font-bold text-[#8a847b] uppercase tracking-widest mt-1">{kpi.label}</div>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Error/Status Toast */}
            <AnimatePresence>
              {(error || status) && !runningCheck && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className={`mb-6 p-3 rounded-md border text-sm font-medium ${
                    error ? "bg-red-950/20 border-red-900/50 text-red-400" : "bg-[#b08d6e]/10 border-[#b08d6e]/30 text-[#b08d6e]"
                  }`}
                >
                  {error || status}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Results Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Center Panel: Results Dashboard */}
              <div className="lg:col-span-6 relative">
                <AnimatePresence mode="wait">
                  {runningCheck ? (
                    <motion.div key="processing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <AIProcessingTimeline />
                    </motion.div>
                  ) : results ? (
                    <motion.div key="results" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
                      
                      {/* Results Header Card */}
                      <div className="bg-[#222222] border border-[#333330] rounded-xl p-5 shadow-sm">
                        <div className="flex items-center justify-between mb-6">
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-[#1a1a1a] border border-[#333330] text-[#b08d6e] flex items-center justify-center font-bold text-lg">
                              {results.compliance_status === "COMPLIANT" ? "A+" : "C"}
                            </div>
                            <div>
                              <h2 className="text-base font-bold text-white">Compliance Report</h2>
                              <p className="text-xs text-[#8a847b]">PO: {results.po_number}</p>
                            </div>
                          </div>
                          <SeverityBadge severity={results.compliance_status === "COMPLIANT" ? "PASS" : "CRITICAL"} />
                        </div>

                        <div className="grid grid-cols-3 gap-3">
                          <div className="bg-[#1a1a1a] border border-red-900/30 rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-red-500">{results.summary?.critical || 0}</div>
                            <div className="text-[10px] font-bold uppercase tracking-wider text-red-400/80 mt-1">Critical</div>
                          </div>
                          <div className="bg-[#1a1a1a] border border-amber-900/30 rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-amber-500">{results.summary?.major || 0}</div>
                            <div className="text-[10px] font-bold uppercase tracking-wider text-amber-400/80 mt-1">Major</div>
                          </div>
                          <div className="bg-[#1a1a1a] border border-[#333330] rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-zinc-400">{results.summary?.minor || 0}</div>
                            <div className="text-[10px] font-bold uppercase tracking-wider text-[#8a847b] mt-1">Minor</div>
                          </div>
                        </div>
                      </div>

                      {/* Deviations List */}
                      {results.deviations && results.deviations.length > 0 ? (
                        <div className="space-y-3">
                          <h3 className="font-semibold text-white text-sm tracking-wide">Detected Deviations</h3>
                          {results.deviations.map((dev, idx) => (
                            <motion.div 
                              key={dev.id}
                              initial={{ opacity: 0, x: 10 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: 0.05 * idx }}
                              onClick={() => setSelectedNcr(dev.ncr_id ? dev : null)}
                              className={`bg-[#222222] border rounded-xl p-4 cursor-pointer transition-all hover:-translate-y-0.5 hover:bg-[#333330]/50 ${
                                selectedNcr?.id === dev.id ? "ring-1 ring-[#b08d6e] border-[#b08d6e] shadow-sm" : "border-[#333330]"
                              }`}
                            >
                              <div className="flex justify-between items-start mb-3">
                                <div className="font-mono text-[10px] font-bold bg-[#1a1a1a] px-2 py-1 rounded text-[#8a847b] border border-[#333330]">
                                  {dev.clause_number || "CLAUSE-UNK"}
                                </div>
                                <SeverityBadge severity={dev.severity} />
                              </div>
                              <h4 className="font-semibold text-white text-sm mb-2">{dev.attribute_name?.replace(/_/g, " ")}</h4>
                              <div className="grid grid-cols-2 gap-2 text-sm">
                                <div className="bg-[#1a1a1a] p-2 rounded-md border border-[#333330]">
                                  <span className="text-[9px] text-[#8a847b] font-bold uppercase block mb-1">Specified</span>
                                  <span className="text-zinc-300 font-medium text-xs">{dev.specified_value}</span>
                                </div>
                                <div className="bg-[#1a1a1a] p-2 rounded-md border border-red-900/20">
                                  <span className="text-[9px] text-red-500/80 font-bold uppercase block mb-1">Submitted</span>
                                  <span className="text-red-400 font-medium text-xs">{dev.submitted_value}</span>
                                </div>
                              </div>
                            </motion.div>
                          ))}
                        </div>
                      ) : (
                        <div className="bg-[#b08d6e]/10 border border-[#b08d6e]/20 rounded-xl p-6 text-center">
                          <CheckCircle className="w-12 h-12 text-[#b08d6e] mx-auto mb-3" />
                          <h3 className="text-lg font-bold text-[#b08d6e]">100% Compliant</h3>
                          <p className="text-[#b08d6e]/80 text-sm mt-1">No deviations found in this submission.</p>
                        </div>
                      )}

                    </motion.div>
                  ) : (
                    <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full min-h-[300px] flex items-center justify-center bg-[#222222] border border-[#333330] rounded-xl border-dashed">
                      <div className="text-center">
                        <Box size={32} className="mx-auto mb-3 text-[#333330]" />
                        <p className="text-sm font-medium text-white mb-1">Workspace Ready</p>
                        <p className="text-xs text-[#8a847b]">Select documents and run the agent.</p>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Right Panel: Intelligence Viewer */}
              <div className="lg:col-span-6">
                <div className="sticky top-0 bg-[#222222] rounded-xl overflow-hidden shadow-sm border border-[#333330] flex flex-col h-[600px]">
                  {/* Fake PDF Toolbar */}
                  <div className="bg-[#222222] px-4 py-2 flex items-center justify-between border-b border-[#333330]">
                    <div className="flex gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-[#333330]" />
                      <div className="w-2.5 h-2.5 rounded-full bg-[#333330]" />
                      <div className="w-2.5 h-2.5 rounded-full bg-[#333330]" />
                    </div>
                    <span className="text-[10px] font-mono text-[#8a847b]">AI Document Viewer</span>
                  </div>
                  
                  {/* Document Content */}
                  <div className="flex-1 p-5 relative overflow-hidden bg-[#1a1a1a]">
                    {!selectedNcr ? (
                      <div className="h-full flex flex-col items-center justify-center text-[#333330] text-center px-4">
                        <FileText size={32} className="mb-3 opacity-40" />
                        <p className="text-xs text-[#8a847b]">Select a deviation to view AI insights and source citations.</p>
                      </div>
                    ) : (
                      <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="h-full flex flex-col">
                        {/* Mocked PDF text showing highlight */}
                        <div className="bg-[#222222] rounded-lg shadow-sm p-4 text-[11px] leading-relaxed text-[#8a847b] font-serif relative overflow-hidden h-40 mb-4 border border-[#333330]">
                          Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
                          <br/><br/>
                          <span className="bg-[#b08d6e]/20 text-white font-bold px-1 rounded relative inline-block border border-[#b08d6e]/50">
                            {selectedNcr.clause_number}: {selectedNcr.specified_value}
                            <motion.span animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 2, repeat: Infinity }} className="absolute -inset-0.5 border border-[#b08d6e] rounded pointer-events-none" />
                          </span>
                          <br/><br/>
                          Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident.
                        </div>

                        {/* AI Insights Panel */}
                        <div className="flex-1 bg-[#222222] border border-[#333330] rounded-xl p-4 text-white flex flex-col">
                          <div className="flex items-center gap-2 mb-3">
                            <div className="w-2 h-2 rounded-full bg-[#b08d6e] animate-pulse" />
                            <h4 className="font-bold text-sm">AI Insights</h4>
                          </div>
                          
                          <div className="flex-1 space-y-4 overflow-y-auto pr-2 custom-scrollbar text-xs">
                            <div>
                              <span className="text-[#8a847b] text-[10px] font-bold uppercase tracking-wider block mb-1">Deviation Rationale</span>
                              <p className="text-zinc-200 leading-relaxed">{selectedNcr.justification}</p>
                            </div>
                            
                            <div className="bg-[#b08d6e]/10 border border-[#b08d6e]/30 p-3 rounded-lg">
                              <span className="text-[#b08d6e] text-[10px] font-bold uppercase tracking-wider block mb-1">Recommendation</span>
                              <p className="text-white leading-relaxed">{selectedNcr.recommended_action}</p>
                            </div>

                            <div className="flex items-center justify-between bg-[#1a1a1a] p-3 rounded-lg border border-[#333330]">
                              <span className="text-[#8a847b]">AI Confidence</span>
                              <span className="font-bold text-[#b08d6e]">{(selectedNcr.w_conform * 100).toFixed(1)}%</span>
                            </div>
                          </div>
                          
                          <button
                            onClick={() => navigate(`/ncr/${selectedNcr.ncr_id}`)}
                            className="w-full mt-4 bg-white text-black hover:bg-zinc-200 text-sm font-semibold py-2 rounded-lg transition-colors shadow-sm"
                          >
                            Open Full NCR
                          </button>
                        </div>
                      </motion.div>
                    )}
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
