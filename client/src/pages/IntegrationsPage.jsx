import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Database, 
  Cloud, 
  HardDrive, 
  Server, 
  Wifi, 
  CheckCircle2, 
  RefreshCw,
  Box,
  Map,
  Activity,
  Building,
  Globe,
  Upload,
  Search,
  Code2,
  Lock,
  SearchCode
} from "lucide-react";
import api from "../api/client.js";

const integrations = [
  {
    id: "sap",
    name: "SAP ERP",
    category: "Procurement & Cost",
    icon: <Database size={20} className="text-blue-400" />,
    description: "Live synchronization of purchase orders, vendor invoices, and actualized costs.",
    lastSync: "Not connected",
    tags: ["OFFICIAL"]
  },
  {
    id: "primavera",
    name: "Primavera P6",
    category: "Schedule & Critical Path",
    icon: <Activity size={20} className="text-[#b08d6e]" />,
    description: "Bi-directional sync of schedule logic, float calculations, and task dependencies.",
    lastSync: "Not connected",
    tags: ["OFFICIAL"]
  },
  {
    id: "forge",
    name: "Autodesk Forge",
    category: "BIM & 3D Models",
    icon: <Box size={20} className="text-rose-400" />,
    description: "Ingestion of 3D clash detection reports and spatial commissioning models.",
    lastSync: "Not connected",
    tags: ["ALPHA", "OFFICIAL"]
  },
  {
    id: "uptime",
    name: "Uptime Institute API",
    category: "Engineering Standards",
    icon: <Building size={20} className="text-purple-400" />,
    description: "Secure integration of paid Tier Classification standards for automated QA checklists.",
    lastSync: "Not connected",
    tags: ["OFFICIAL"]
  },
  {
    id: "tia",
    name: "TIA-942 Library",
    category: "Engineering Standards",
    icon: <Database size={20} className="text-amber-400" />,
    description: "Direct sync with official Telecommunications Industry Association standards documents.",
    lastSync: "Not connected",
    tags: ["OFFICIAL"]
  },
  {
    id: "bicsi",
    name: "BICSI 002",
    category: "Engineering Standards",
    icon: <Database size={20} className="text-yellow-400" />,
    description: "Data Center Design and Implementation Best Practices rulebook integration.",
    lastSync: "Not connected",
    tags: ["OFFICIAL"]
  },
  {
    id: "ashrae",
    name: "ASHRAE TC 9.9",
    category: "Engineering Standards",
    icon: <Database size={20} className="text-cyan-400" />,
    description: "Thermal guidelines for Data Processing Environments and cooling optimization.",
    lastSync: "Not connected",
    tags: ["OFFICIAL"]
  },
  {
    id: "iso_en",
    name: "ISO 50001 / EN 50600",
    category: "Engineering Standards",
    icon: <Database size={20} className="text-[#b08d6e]" />,
    description: "Energy management and data centre facilities infrastructures standards.",
    lastSync: "Not connected",
    tags: ["BETA", "OFFICIAL"]
  },
  {
    id: "nfpa",
    name: "NFPA 75 / 76",
    category: "Engineering Standards",
    icon: <Database size={20} className="text-red-400" />,
    description: "Fire protection of information technology equipment and telecommunications facilities.",
    lastSync: "Not connected",
    tags: ["OFFICIAL"]
  },
  {
    id: "iot",
    name: "Site IoT Sensors",
    category: "Live Conditions",
    icon: <Wifi size={20} className="text-[#b08d6e]" />,
    description: "Real-time telemetry for temperature, humidity, and generator power loads.",
    lastSync: "Not connected",
    tags: ["OFFICIAL"]
  }
];

export default function IntegrationsPage() {
  const [syncing, setSyncing] = useState({});
  const [connectedIds, setConnectedIds] = useState([]);
  const fileInputRef = useRef(null);
  const [activeUpload, setActiveUpload] = useState({ id: null, name: null });
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("All");

  const handleConnectClick = (integration) => {
    const isConnected = connectedIds.includes(integration.id) || integration.lastSync !== "Not connected";
    if (!isConnected) {
      setActiveUpload({ id: integration.id, name: integration.name });
      fileInputRef.current.click();
    } else {
      setSyncing(prev => ({ ...prev, [integration.id]: true }));
      setTimeout(() => {
        setSyncing(prev => ({ ...prev, [integration.id]: false }));
      }, Math.random() * 2000 + 1500);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !activeUpload.id) return;
    
    setSyncing(prev => ({ ...prev, [activeUpload.id]: true }));
    try {
      await api.uploadIntegrationDocument(file, activeUpload.name);
      setConnectedIds(prev => [...prev, activeUpload.id]);
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setSyncing(prev => ({ ...prev, [activeUpload.id]: false }));
      setActiveUpload({ id: null, name: null });
      e.target.value = null; // reset input
    }
  };

  const filteredIntegrations = integrations.filter(int => {
    const matchesSearch = int.name.toLowerCase().includes(searchQuery.toLowerCase()) || int.description.toLowerCase().includes(searchQuery.toLowerCase());
    if (activeTab === "All") return matchesSearch;
    if (activeTab === "Engineering Standards") return matchesSearch && int.category === "Engineering Standards";
    if (activeTab === "Live Data") return matchesSearch && (int.category === "Live Conditions" || int.category === "Supply Chain");
    return matchesSearch;
  });

  // Derived installed items
  const installedItems = integrations.filter(int => connectedIds.includes(int.id) || int.lastSync !== "Not connected");

  return (
    <div className="flex h-screen bg-[#1a1a1a] text-white overflow-hidden">
      
      {/* Hidden File Input */}
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={handleFileUpload} 
        accept="application/pdf" 
        className="hidden" 
      />

      {/* ─── Left Sidebar (Supabase Style) ─── */}
      <div className="w-[260px] flex-none bg-[#1a1a1a] border-r border-[#333330] overflow-y-auto z-10 flex flex-col custom-scrollbar pb-6 pt-6 px-4">
        <h1 className="text-xl font-bold text-white mb-8 tracking-tight px-2">Integrations</h1>
        
        <div className="mb-8">
          <div className="text-xs font-semibold text-[#8a847b] uppercase tracking-wider mb-2 px-2">Explore</div>
          <div className="space-y-0.5">
            <button 
              onClick={() => setActiveTab("All")}
              className={`w-full flex justify-between items-center px-3 py-1.5 rounded-md text-sm transition-colors ${activeTab === "All" ? "bg-[#222222] text-white font-medium" : "text-[#8a847b] hover:text-white"}`}
            >
              All
            </button>
            <button 
              onClick={() => setActiveTab("Engineering Standards")}
              className={`w-full flex justify-between items-center px-3 py-1.5 rounded-md text-sm transition-colors ${activeTab === "Engineering Standards" ? "bg-[#222222] text-white font-medium" : "text-[#8a847b] hover:text-white"}`}
            >
              Engineering Standards
            </button>
            <button 
              onClick={() => setActiveTab("Live Data")}
              className={`w-full flex justify-between items-center px-3 py-1.5 rounded-md text-sm transition-colors ${activeTab === "Live Data" ? "bg-[#222222] text-white font-medium" : "text-[#8a847b] hover:text-white"}`}
            >
              Live Data
            </button>
          </div>
        </div>

        <div>
          <div className="text-xs font-semibold text-[#8a847b] uppercase tracking-wider mb-2 px-2">Installed</div>
          <div className="space-y-1">
            {installedItems.length === 0 ? (
              <div className="text-xs text-[#8a847b] px-2 py-1">No integrations installed</div>
            ) : (
              installedItems.map(item => (
                <div key={item.id} className="flex items-center justify-between px-2 py-1.5 rounded-md group">
                  <div className="flex items-center gap-2">
                    <div className="p-1 bg-[#222222] border border-[#333330] rounded">
                      {item.icon}
                    </div>
                    <span className="text-sm text-[#d4d4d8] group-hover:text-white transition-colors">{item.name}</span>
                  </div>
                  {item.tags.includes("BETA") && (
                    <span className="text-[10px] font-bold text-amber-500 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded-full">BETA</span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ─── Main Content Area ─── */}
      <div className="flex-1 flex flex-col bg-[#1a1a1a] overflow-y-auto custom-scrollbar">
        
        {/* Header section */}
        <div className="px-10 pt-12 pb-8 max-w-7xl mx-auto w-full">
          <h2 className="text-2xl font-semibold text-white mb-2">Extend your platform</h2>
          <p className="text-[#8a847b] text-sm max-w-2xl mb-8">
            Extensions and wrappers that add functionality to your database and connect to external services.
          </p>

          <div className="relative mb-8 w-full max-w-sm">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8a847b]" />
            <input 
              type="text" 
              placeholder="Search integrations..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-[#222222] border border-[#333330] text-sm text-white rounded-md pl-10 pr-3 py-2 w-full focus:outline-none focus:border-[#333330] transition-colors"
            />
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredIntegrations.map((integration) => {
              const isConnected = connectedIds.includes(integration.id) || integration.lastSync !== "Not connected";
              const isSyncing = syncing[integration.id];
              const needsUpload = !isConnected;

              return (
                <div 
                  key={integration.id}
                  onClick={() => handleConnectClick(integration)}
                  className="bg-[#222222] border border-[#333330] rounded-xl p-5 hover:border-[#333330] transition-all cursor-pointer flex flex-col h-[200px] relative overflow-hidden group"
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="p-2 bg-[#333330] rounded-lg border border-[#333330]">
                      {integration.icon}
                    </div>
                    {isSyncing ? (
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-[#b08d6e]">
                        <RefreshCw size={14} className="animate-spin" />
                        <span>{needsUpload ? "Ingesting..." : "Syncing..."}</span>
                      </div>
                    ) : isConnected ? (
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-[#b08d6e]">
                        <CheckCircle2 size={14} />
                        <span>Installed</span>
                      </div>
                    ) : needsUpload ? (
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Upload size={14} />
                        <span>Upload PDF</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Server size={14} />
                        <span>Install</span>
                      </div>
                    )}
                  </div>

                  <h3 className="text-base font-semibold text-white mb-2">{integration.name}</h3>
                  <p className="text-sm text-[#8a847b] line-clamp-3 mb-4 flex-1">
                    {integration.description}
                  </p>

                  <div className="flex items-center gap-2 mt-auto">
                    {integration.tags.map(tag => (
                      <span 
                        key={tag} 
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${
                          tag === "BETA" 
                            ? "text-amber-500 bg-amber-500/10 border-amber-500/20" 
                            : tag === "ALPHA"
                              ? "text-rose-500 bg-rose-500/10 border-rose-500/20"
                              : "text-[#8a847b] bg-[#333330] border-[#333330]"
                        }`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      </div>
    </div>
  );
}
