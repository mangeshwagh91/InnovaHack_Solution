import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Calendar, AlertTriangle, CheckCircle, Activity, ChevronDown, ChevronUp, Zap, Clock, Upload, FileSpreadsheet } from "lucide-react";
import api from "../api/client.js";
import SeverityBadge from "../components/SeverityBadge.jsx";
import ScheduleAITimeline from "../components/schedule/ScheduleAITimeline.jsx";
import { useWorkspace } from "../context/WorkspaceContext.jsx";

function AnimatedCounter({ value, suffix = "" }) {
  return <span>{value}{suffix}</span>;
}

export default function Schedule() {
  const [tasks, setTasks] = useState([]);
  const [delayData, setDelayData] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState(null);
  const [expandedTaskId, setExpandedTaskId] = useState(null);
  const [statusMsg, setStatusMsg] = useState("");
  const [scheduleFile, setScheduleFile] = useState(null);
  
  const { currentProject } = useWorkspace();

  const fileInputRef = useRef(null);

  useEffect(() => {
    if (currentProject) {
      loadTasks();
    } else {
      setTasks([]);
    }
  }, [currentProject]);

  async function loadTasks() {
    if (!currentProject) return;
    try {
      const data = await api.getScheduleTasks(currentProject.id);
      setTasks(data.tasks || []);
      try {
        const dc = await api.getDelayComparison();
        setDelayData(dc);
      } catch (_) {}
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleAnalyze() {
    if (!currentProject) return;
    try {
      setAnalyzing(true);
      setError(null);
      await api.analyzeSchedule(currentProject.id);
      await loadTasks();
      setStatusMsg("✓ Analysis complete");
      setTimeout(() => setStatusMsg(""), 3000);
    } catch (err) {
      setError(err.message);
      setStatusMsg("");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleImport(fileToUpload) {
    const file = fileToUpload || scheduleFile;
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    if (currentProject) formData.append("project_id", currentProject.id);

    formData.append("file", file);
    try {
      setImporting(true);
      setError(null);
      await api.importSchedule(formData);
      await loadTasks();
      setStatusMsg("✓ Schedule imported successfully");
      setTimeout(() => setStatusMsg(""), 3000);
      
      const savedSettings = localStorage.getItem('agentSettings');
      let autoRun = true;
      if (savedSettings) {
        try {
          const parsed = JSON.parse(savedSettings);
          autoRun = parsed.autoRunOnUpload;
        } catch (_) {}
      }
      
      if (autoRun) {
        handleAnalyze();
      }
    } catch (err) {
      setError(err.message);
      setStatusMsg("");
    } finally {
      setImporting(false);
      setScheduleFile(null);
    }
  }

  function getRiskLevel(score) {
    if (score >= 0.75) return "HIGH";
    if (score >= 0.5) return "MEDIUM";
    return "LOW";
  }

  const criticalTasksCount = tasks.filter(t => t.total_float_days === 0).length;
  const avgRisk = tasks.length ? Math.round((tasks.reduce((acc, t) => acc + t.risk_score, 0) / tasks.length) * 100) : 0;

  return (
    <div className="flex-1 w-full h-full relative bg-[#1a1a1a] overflow-hidden flex flex-col text-white">
      <div className="flex-1 flex overflow-hidden relative z-10 w-full">
        
        {/* ─── Left Sidebar: Upload & Analyze ──────────────────────────── */}
        <div className="w-[280px] flex-none bg-[#1a1a1a] border-r border-[#333330] flex flex-col overflow-hidden hidden lg:flex">
          {/* Sidebar Header */}
          <div className="h-12 border-b border-[#333330] bg-[#222222] flex items-center px-4 flex-shrink-0">
            <h1 className="text-[13px] font-bold text-white tracking-wide uppercase">Schedule Intel</h1>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar p-5 flex flex-col">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#8a847b] mb-4 flex items-center gap-2">
              <Upload size={12} /> Import Schedule
            </h2>

            {!scheduleFile ? (
              <div 
                className="w-full rounded-lg border border-[#333330] border-dashed flex flex-col items-center justify-center p-6 text-center cursor-pointer bg-[#222222] hover:bg-[#333330] hover:border-[#8a847b] transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                <input 
                  type="file" 
                  className="hidden" 
                  ref={fileInputRef} 
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setScheduleFile(e.target.files[0]);
                    }
                  }} 
                />
                <div className="w-10 h-10 rounded-lg bg-sky-500/10 text-sky-500 flex items-center justify-center mb-3">
                  <FileSpreadsheet size={20} />
                </div>
                <p className="text-xs font-semibold text-white mb-1">Click to browse files</p>
                <p className="text-[10px] text-[#8a847b]">MPP, P6, CSV formats</p>
              </div>
            ) : (
              <div className="w-full">
                <div className="p-3 rounded-lg border border-[#333330] bg-[#222222] flex items-center gap-3">
                  <div className="w-8 h-8 rounded-md bg-sky-500/10 text-sky-500 flex items-center justify-center shrink-0">
                    <FileSpreadsheet size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold text-white truncate mb-0.5">{scheduleFile.name}</p>
                    <p className="text-[10px] text-[#8a847b]">{(scheduleFile.size / 1024).toFixed(1)} KB</p>
                  </div>
                  <button onClick={() => setScheduleFile(null)} className="text-[#8a847b] hover:text-red-400 text-[10px] uppercase font-bold px-1 transition-colors">
                    Remove
                  </button>
                </div>
                
                <button
                  onClick={() => handleImport()}
                  disabled={importing}
                  className="mt-4 w-full bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  {importing ? (
                    <>
                      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />
                      Importing...
                    </>
                  ) : (
                    "Upload Schedule"
                  )}
                </button>
              </div>
            )}

            <div className="mt-auto pt-6">
              <motion.div 
                className={`transition-all duration-300 ${tasks.length === 0 ? "opacity-40 pointer-events-none" : ""}`}
              >
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing || tasks.length === 0}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg p-4 shadow-sm transition-colors flex flex-col items-center justify-center gap-2"
                >
                  <div className="w-8 h-8 bg-black/10 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Play fill="currentColor" size={14} className="ml-0.5" />
                  </div>
                  <h3 className="font-bold text-sm">Run AI Risk Analysis</h3>
                </button>
              </motion.div>
            </div>
          </div>
        </div>

        {/* ─── Main Canvas ────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-8 relative flex flex-col bg-[#1a1a1a]">
          
          <div className="max-w-6xl mx-auto w-full">
            {/* Header / KPIs */}
            <div className="mb-10">
              <h2 className="text-[22px] font-bold tracking-tight mb-2">Schedule Risk Intelligence</h2>
              <p className="text-[#8a847b] text-sm max-w-2xl mb-8">
                Upload project schedules and let AI identify critical paths, predict delays, and automatically recommend mitigation strategies before project impacts occur.
              </p>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Total Tasks", val: tasks.length || 0, icon: <Calendar size={16} />, color: "text-blue-400" },
                  { label: "Critical Path", val: criticalTasksCount, icon: <Zap size={16} />, color: "text-amber-500" },
                  { label: "Overall Risk", val: avgRisk, suffix: "%", icon: <AlertTriangle size={16} />, color: avgRisk > 50 ? "text-red-500" : "text-[#b08d6e]" },
                  { label: "AI Status", val: "Online", icon: <Activity size={16} />, color: "text-[#b08d6e]" }
                ].map((kpi, i) => (
                  <motion.div 
                    key={i} 
                    initial={{ opacity: 0, y: 10 }} 
                    animate={{ opacity: 1, y: 0 }} 
                    transition={{ delay: 0.05 * i }}
                    className="bg-[#222222] border border-[#333330] p-4 rounded-xl shadow-sm"
                  >
                    <div className={`mb-2 ${kpi.color}`}>{kpi.icon}</div>
                    <div className="text-2xl font-bold text-white"><AnimatedCounter value={kpi.val} suffix={kpi.suffix} /></div>
                    <div className="text-[10px] font-bold text-[#8a847b] uppercase tracking-widest mt-1">{kpi.label}</div>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Global Error/Status Toast */}
            <AnimatePresence>
              {(error || statusMsg) && !analyzing && !importing && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className={`mb-6 p-3 rounded-md border text-sm font-medium ${
                    error ? "bg-red-950/20 border-red-900/50 text-red-400" : "bg-sky-950/20 border-sky-900/50 text-sky-400"
                  }`}
                >
                  {error || statusMsg}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Results Dashboard */}
            <AnimatePresence mode="wait">
              {analyzing ? (
                <motion.div key="processing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <ScheduleAITimeline />
                </motion.div>
              ) : tasks.length > 0 ? (
                <motion.div key="results" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
                  
                  {/* Interactive Mock Timeline */}
                  <div className="bg-[#222222] border border-[#333330] rounded-xl p-6 shadow-sm overflow-hidden">
                    <div className="flex items-center justify-between mb-6">
                      <div>
                        <h2 className="text-base font-bold text-white">Critical Path Visualization</h2>
                        <p className="text-xs text-[#8a847b]">Interactive dependency graph and schedule float</p>
                      </div>
                      <div className="flex gap-4 text-xs font-semibold">
                        <span className="flex items-center gap-1 text-[#8a847b]"><div className="w-2.5 h-2.5 rounded-[3px] bg-[#333330]"></div> Float</span>
                        <span className="flex items-center gap-1 text-red-400"><div className="w-2.5 h-2.5 rounded-[3px] bg-red-500"></div> Critical</span>
                      </div>
                    </div>
                    
                    <div className="relative h-40 border-l border-b border-[#333330] mt-4 px-2 pt-2">
                      {tasks.slice(0, 4).map((task, idx) => {
                        const isCritical = task.total_float_days === 0;
                        const width = 20 + Math.random() * 30;
                        const left = idx * 15;
                        return (
                          <motion.div 
                            key={`mock-timeline-${task.id}`}
                            initial={{ width: 0 }}
                            animate={{ width: `${width}%` }}
                            transition={{ duration: 1, delay: idx * 0.2 }}
                            className={`h-5 rounded-md mb-3 relative flex items-center px-2 text-[9px] font-bold text-white truncate cursor-pointer hover:brightness-110 ${isCritical ? 'bg-red-500' : 'bg-[#333330]'}`}
                            style={{ marginLeft: `${left}%` }}
                          >
                            {task.task_code}
                            {idx < 3 && <div className="absolute top-full left-1/2 w-px h-3 bg-[#333330]" />}
                            {idx < 3 && <div className="absolute top-[28px] left-1/2 h-px bg-[#333330]" style={{ width: '15vw' }} />}
                          </motion.div>
                        );
                      })}
                      <div className="absolute inset-0 flex justify-between pointer-events-none opacity-20">
                        {[1,2,3,4,5].map(i => <div key={i} className="h-full w-px bg-[#333330]" />)}
                      </div>
                    </div>
                  </div>

                  {/* AI Recommendations & Task Table */}
                  <div className="bg-[#222222] border border-[#333330] rounded-xl overflow-hidden shadow-sm">
                    <div className="px-5 py-3 border-b border-[#333330] flex items-center justify-between bg-[#1a1a1a]">
                      <h3 className="font-semibold text-white text-sm">Detailed Risk Analysis</h3>
                      <span className="text-[10px] font-bold uppercase tracking-widest text-[#8a847b]">Priority Sorted</span>
                    </div>
                    
                    <div className="divide-y divide-[#333330] max-h-[600px] overflow-y-auto custom-scrollbar">
                      {[...tasks].sort((a,b) => b.risk_score - a.risk_score).map((task, idx) => {
                        const isExpanded = expandedTaskId === task.id;
                        const isCritical = task.total_float_days === 0;
                        
                        return (
                          <motion.div 
                            key={task.id}
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.05 * idx }}
                            className={`transition-colors ${isExpanded ? 'bg-[#333330]/30' : 'hover:bg-[#333330]/20'}`}
                          >
                            <div 
                              onClick={() => setExpandedTaskId(isExpanded ? null : task.id)}
                              className="px-5 py-4 flex items-center gap-4 cursor-pointer"
                            >
                              <div className={`w-1.5 h-1.5 rounded-full ${isCritical ? 'bg-red-500 animate-pulse' : 'bg-[#333330]'}`} />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="font-mono text-[10px] font-bold text-[#8a847b] bg-[#1a1a1a] border border-[#333330] px-1.5 rounded">{task.task_code}</span>
                                  <SeverityBadge severity={getRiskLevel(task.risk_score)} />
                                </div>
                                <h4 className="font-medium text-white truncate text-sm">{task.description}</h4>
                              </div>
                              
                              <div className="text-right mr-4 hidden md:block">
                                <p className="text-[9px] font-bold text-[#8a847b] uppercase tracking-wider">Float</p>
                                <p className={`font-mono font-bold text-xs ${isCritical ? 'text-red-500' : 'text-[#8a847b]'}`}>{task.total_float_days}d</p>
                              </div>
                              
                              <div className="text-right mr-4 hidden sm:block">
                                <p className="text-[9px] font-bold text-[#8a847b] uppercase tracking-wider">Delay Prob</p>
                                <p className="font-mono font-bold text-amber-500 text-xs">{(task.delay_probability * 100).toFixed(0)}%</p>
                              </div>

                              <button className="text-[#8a847b] hover:text-white">
                                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                              </button>
                            </div>

                            <AnimatePresence>
                              {isExpanded && (
                                <motion.div 
                                  initial={{ height: 0, opacity: 0 }}
                                  animate={{ height: 'auto', opacity: 1 }}
                                  exit={{ height: 0, opacity: 0 }}
                                  className="overflow-hidden bg-[#1a1a1a] border-t border-[#333330]"
                                >
                                  <div className="p-5">
                                    <div className="flex items-center gap-2 mb-4">
                                      <div className="w-6 h-6 rounded-md bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                                        <Zap size={14} />
                                      </div>
                                      <h5 className="font-bold text-white text-sm">AI Mitigation Strategy</h5>
                                    </div>
                                    
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
                                      <div className="bg-[#222222] p-3 rounded-lg border border-[#333330]">
                                        <span className="text-[9px] text-[#8a847b] font-bold uppercase tracking-wider block mb-1">Equipment Context</span>
                                        <span className="text-xs text-white">{task.equipment_description || "Standard civil/structural task"}</span>
                                      </div>
                                      <div className="bg-[#222222] p-3 rounded-lg border border-[#333330]">
                                        <span className="text-[9px] text-[#8a847b] font-bold uppercase tracking-wider block mb-1">Predecessors</span>
                                        <span className="text-xs font-mono text-indigo-400">
                                          {task.predecessor_ids_json && JSON.parse(task.predecessor_ids_json).length > 0 
                                            ? JSON.parse(task.predecessor_ids_json).join(", ") 
                                            : "None"}
                                        </span>
                                      </div>
                                      <div className="bg-[#222222] p-3 rounded-lg border border-[#333330] flex flex-col justify-center">
                                        <span className="text-[9px] text-[#8a847b] font-bold uppercase tracking-wider block mb-1">Timeline Impact</span>
                                        <span className="text-xs text-white flex items-center gap-1.5"><Clock size={12} className="text-[#8a847b]" /> {task.planned_start} to {task.planned_finish}</span>
                                      </div>
                                    </div>

                                    {task.mitigation_text ? (
                                      <div className="bg-indigo-950/20 border border-indigo-900/50 rounded-xl p-4">
                                        <p className="text-xs leading-relaxed text-indigo-200 whitespace-pre-wrap">{task.mitigation_text}</p>
                                        <div className="mt-4 flex items-center justify-end">
                                          <button className="bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] uppercase tracking-wider font-bold py-1.5 px-3 rounded-md transition-colors">
                                            Apply to Schedule
                                          </button>
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="text-center p-6 bg-[#222222] rounded-xl border border-[#333330] border-dashed">
                                        <AlertTriangle size={24} className="mx-auto text-amber-500/50 mb-2" />
                                        <p className="text-[#8a847b] text-xs font-medium">No AI mitigation has been generated for this task yet.</p>
                                      </div>
                                    )}
                                  </div>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </motion.div>
                        )
                      })}
                    </div>
                  </div>

                  {delayData && delayData.tasks && delayData.tasks.length > 0 && (
                    <div className="bg-[#222222] border border-[#333330] rounded-xl overflow-hidden shadow-sm">
                      <div className="px-5 py-3 border-b border-[#333330] bg-[#1a1a1a]">
                        <div className="flex items-center gap-2">
                          <Clock size={14} className="text-amber-500" />
                          <h3 className="font-semibold text-white text-sm">Delay Prediction vs Historical</h3>
                        </div>
                        <div className="flex gap-4 mt-1.5 text-[10px] text-[#8a847b]">
                          <span>Avg predicted: <strong className="text-amber-500">{delayData.avg_predicted_delay_days}d</strong></span>
                          <span>Avg historical: <strong className="text-white">{delayData.avg_historical_delay_days}d</strong></span>
                          <span>Exceeding historical: <strong className="text-red-500">{delayData.tasks_exceeding_historical}</strong></span>
                        </div>
                      </div>
                      <div className="divide-y divide-[#333330] max-h-64 overflow-y-auto custom-scrollbar">
                        {delayData.tasks.filter(t => t.predicted_delay_days > 0 || t.historical_avg_delay > 0).slice(0, 10).map((task) => {
                          const predicted = task.predicted_delay_days || 0;
                          const historical = task.historical_avg_delay || 0;
                          const maxVal = Math.max(predicted, historical, 1);
                          const isWorse = predicted > historical;
                          return (
                            <div key={task.id} className="px-5 py-3 flex items-center gap-4 hover:bg-[#333330]/20 transition-colors">
                              <div className="w-32 min-w-[8rem] truncate">
                                <span className="text-[10px] font-mono text-[#8a847b]">{task.task_code}</span>
                                <p className="text-xs text-white truncate font-medium">{task.description?.slice(0, 30)}</p>
                              </div>
                              <div className="flex-1 space-y-1.5">
                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] text-[#8a847b] uppercase tracking-wider w-16">Predicted</span>
                                  <div className="flex-1 h-2 bg-[#1a1a1a] rounded-full overflow-hidden border border-[#333330]">
                                    <motion.div
                                      initial={{ width: 0 }}
                                      animate={{ width: `${(predicted / maxVal) * 100}%` }}
                                      transition={{ duration: 0.8 }}
                                      className={`h-full rounded-full ${isWorse ? 'bg-red-500' : 'bg-amber-500'}`}
                                    />
                                  </div>
                                  <span className={`text-[10px] font-bold w-6 text-right ${isWorse ? 'text-red-500' : 'text-amber-500'}`}>{predicted}d</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] text-[#8a847b] uppercase tracking-wider w-16">Historical</span>
                                  <div className="flex-1 h-2 bg-[#1a1a1a] rounded-full overflow-hidden border border-[#333330]">
                                    <motion.div
                                      initial={{ width: 0 }}
                                      animate={{ width: `${(historical / maxVal) * 100}%` }}
                                      transition={{ duration: 0.8, delay: 0.1 }}
                                      className="h-full rounded-full bg-[#333330]"
                                    />
                                  </div>
                                  <span className="text-[10px] font-bold w-6 text-right text-[#8a847b]">{historical}d</span>
                                </div>
                              </div>
                              <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded-md border ${task.verdict === 'On Track' ? 'bg-[#b08d6e]/10 border-[#b08d6e]/30 text-[#b08d6e]' : task.verdict === 'At Risk' ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' : 'bg-red-500/10 border-red-500/30 text-red-500'}`}>
                                {task.verdict}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                </motion.div>
              ) : (
                <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full min-h-[400px] flex items-center justify-center bg-[#222222] border border-[#333330] rounded-xl border-dashed">
                  <div className="text-center">
                    <Calendar size={48} className="mx-auto mb-3 text-[#333330]" />
                    <p className="text-sm font-medium text-white">No Schedule Data</p>
                    <p className="text-xs text-[#8a847b] mt-1">Upload a schedule file on the left to begin analysis.</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

      </div>
    </div>
  );
}
