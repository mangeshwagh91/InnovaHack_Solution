import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Truck, AlertTriangle, CheckCircle2, Activity, Zap,
  RefreshCw, Info, ExternalLink, Plus, ChevronDown, Clock,
  Filter, SlidersHorizontal
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import icon from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";

// Fix leaflet default icon
let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [18, 30],
  iconAnchor: [9, 30],
  popupAnchor: [1, -28],
});
L.Marker.prototype.options.icon = DefaultIcon;

function riskColor(level) {
  if (level === "CRITICAL") return "#E24B4A";
  if (level === "HIGH") return "#E24B4A";
  if (level === "MEDIUM") return "#F2AF48";
  return "#22c55e";
}

export default function SupplyChainPage() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(null);
  const [selected, setSelected] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [riskFilter, setRiskFilter] = useState("All");

  const fetchShipments = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const res = await fetch("http://localhost:8000/api/supply-chain/shipments");
      const data = await res.json();
      const list = data.shipments || [];
      setShipments(list);
      if (!selected && list.length > 0) setSelected(list[0].id);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchShipments();
    const interval = setInterval(fetchShipments, 30000);
    return () => clearInterval(interval);
  }, []);

  const analyzeRisk = async (id) => {
    setAnalyzing(id);
    try {
      await fetch(`http://localhost:8000/api/supply-chain/shipments/${id}/analyze`, { method: "POST" });
      await fetchShipments();
    } catch (e) {
      console.error(e);
    } finally {
      setAnalyzing(null);
    }
  };

  const selectedShipment = shipments.find(s => s.id === selected);
  const criticalCount = shipments.filter(s => s.risk_level === "CRITICAL" || s.risk_level === "HIGH").length;
  const filteredMapShipments = riskFilter === "All"
    ? shipments
    : shipments.filter(s => s.risk_level === riskFilter);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-[#1a1a1a] flex items-center justify-center z-50">
        <div className="flex flex-col items-center gap-3">
          <Activity className="animate-spin text-[#b08d6e]" size={24} />
          <p className="text-[#8a847b] text-xs font-medium">Loading shipments...</p>
        </div>
      </div>
    );
  }

  return (
    // The parent <main> no longer has padding, so we just use flex-1
    <div className="flex-1 flex flex-row w-full h-full overflow-hidden">

      {/* ─── LEFT INNER SIDEBAR ──────────────────────────── */}
      <aside className="w-[240px] flex-shrink-0 border-r border-[#222222] bg-[#1a1a1a] flex flex-col overflow-hidden">

        {/* Title */}
        <div className="px-4 pt-5 pb-4">
          <h2 className="text-[13px] font-semibold text-white">Supply Chain</h2>
        </div>

        {/* Nav sections */}
        <nav className="flex-1 overflow-y-auto px-2 space-y-4 pb-4">

          {/* GENERAL */}
          <div>
            <div className="px-2 mb-1 text-[10px] font-semibold text-[#8a847b] uppercase tracking-widest">General</div>
            <button
              onClick={() => setRiskFilter("All")}
              className={`w-full text-left px-2 py-1.5 rounded text-[13px] transition-colors ${
                riskFilter === "All"
                  ? "bg-[#222222] text-white font-semibold"
                  : "text-[#8a847b] hover:text-white"
              }`}
            >
              All Shipments
            </button>
          </div>

          {/* RISK LEVELS */}
          <div>
            <div className="px-2 mb-1 text-[10px] font-semibold text-[#8a847b] uppercase tracking-widest">Risk Levels</div>
            {[
              { label: "Critical", value: "CRITICAL", dot: "bg-red-500" },
              { label: "High Risk", value: "HIGH", dot: "bg-red-400" },
              { label: "Medium", value: "MEDIUM", dot: "bg-amber-400" },
              { label: "On Track", value: "LOW", dot: "bg-[#b08d6e]" },
            ].map(item => (
              <button
                key={item.value}
                onClick={() => setRiskFilter(item.value)}
                className={`w-full text-left px-2 py-1.5 rounded text-[13px] transition-colors flex items-center gap-2 ${
                  riskFilter === item.value
                    ? "bg-[#222222] text-white font-semibold"
                    : "text-[#8a847b] hover:text-white"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${item.dot}`} />
                {item.label}
              </button>
            ))}
          </div>

          {/* SHIPMENTS */}
          <div>
            <div className="px-2 mb-1 text-[10px] font-semibold text-[#8a847b] uppercase tracking-widest">Shipments</div>
            {shipments.map(s => {
              const dotCls =
                s.risk_level === "CRITICAL" || s.risk_level === "HIGH" ? "bg-red-500" :
                s.risk_level === "MEDIUM" ? "bg-amber-400" : "bg-[#b08d6e]";
              return (
                <button
                  key={s.id}
                  onClick={() => setSelected(s.id)}
                  className={`w-full text-left px-2 py-1.5 rounded text-[13px] transition-colors flex items-center gap-2 ${
                    selected === s.id
                      ? "bg-[#222222] text-white font-semibold"
                      : "text-[#8a847b] hover:text-white"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotCls}`} />
                  <span className="truncate">{s.carrier_name}</span>
                </button>
              );
            })}
          </div>

          {/* CUSTOM SECTION (mirrors Supabase "Custom Reports" card) */}
          <div>
            <div className="px-2 mb-2 text-[10px] font-semibold text-[#8a847b] uppercase tracking-widest">AI Analysis</div>
            <div className="mx-1 rounded-lg border border-[#222222] bg-[#222222] p-3 text-center">
              {criticalCount === 0 ? (
                <>
                  <p className="text-[11px] text-white font-semibold mb-0.5">No risks detected</p>
                  <p className="text-[10px] text-[#8a847b] leading-relaxed">All shipments are on track.</p>
                </>
              ) : (
                <>
                  <p className="text-[11px] text-white font-semibold mb-0.5">{criticalCount} at-risk shipments</p>
                  <p className="text-[10px] text-[#8a847b] leading-relaxed">Run AI models to get alternatives.</p>
                </>
              )}
              <button
                onClick={() => fetchShipments(true)}
                className="mt-2 w-full flex items-center justify-center gap-1 text-[11px] font-semibold text-[#8a847b] hover:text-white bg-[#222222] hover:bg-[#333330] rounded px-2 py-1.5 transition-colors"
              >
                <RefreshCw size={10} className={refreshing ? "animate-spin" : ""} />
                Refresh Data
              </button>
            </div>
          </div>

        </nav>
      </aside>

      {/* ─── MAIN CONTENT AREA ───────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden bg-[#1a1a1a]">

        {/* Page Heading */}
        <div className="px-6 pt-5 pb-3 flex-shrink-0">
          <h1 className="text-[22px] font-semibold text-white tracking-tight">Live Transit Map</h1>
        </div>

        {/* Toolbar Row (filters bar) */}
        <div className="px-6 pb-3 flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => fetchShipments(true)}
            className="p-1.5 rounded text-[#8a847b] hover:text-white hover:bg-[#222222] transition-colors"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin text-[#b08d6e]" : ""} />
          </button>
          <button className="flex items-center gap-1.5 text-[12px] text-[#8a847b] bg-[#222222] border border-[#222222] rounded px-3 py-1.5 hover:border-[#333330] transition-colors">
            <Clock size={12} />
            Last 30 minutes
            <ChevronDown size={11} className="text-[#8a847b]" />
          </button>
          <button className="flex items-center gap-1.5 text-[12px] text-[#8a847b] bg-[#222222] border border-[#222222] rounded px-3 py-1.5 hover:border-[#333330] transition-colors">
            {riskFilter === "All" ? "All Risk Levels" : riskFilter}
            <ChevronDown size={11} className="text-[#8a847b]" />
          </button>
          <button className="flex items-center gap-1.5 text-[12px] text-[#8a847b] bg-[#222222] border border-[#222222] rounded px-3 py-1.5 hover:border-[#333330] transition-colors">
            <Plus size={11} />
            Add filter
          </button>
          <div className="flex-1" />
          <button className="flex items-center gap-1.5 text-[12px] text-[#8a847b] bg-[#222222] border border-[#222222] rounded px-3 py-1.5 hover:border-[#333330] transition-colors">
            <ExternalLink size={12} />
            Export
          </button>
        </div>

        {/* Map Container Panel */}
        <div className="mx-6 mb-3 rounded-lg border border-[#222222] overflow-hidden flex flex-col flex-1 min-h-0">
          {/* Panel Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#222222] flex-shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold text-white">Shipments by Geography</span>
              <Info size={13} className="text-[#8a847b]" />
            </div>
            <button className="p-1 text-[#8a847b] hover:text-white transition-colors rounded hover:bg-[#222222]">
              <ExternalLink size={13} />
            </button>
          </div>

          {/* Map */}
          <div className="flex-1 relative" style={{ minHeight: 0 }}>
            <MapContainer
              center={[20, 10]}
              zoom={2}
              style={{ height: "100%", width: "100%", background: "#1a1a1a" }}
              zoomControl={false}
              attributionControl={false}
            >
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
              />
              {filteredMapShipments.map(s => {
                const color = riskColor(s.risk_level);
                const isSelected = s.id === selected;
                return (
                  <React.Fragment key={s.id}>
                    <Polyline
                      positions={[[s.origin_lat, s.origin_lng], [s.dest_lat, s.dest_lng]]}
                      pathOptions={{
                        color,
                        weight: isSelected ? 2 : 1.2,
                        dashArray: "5, 10",
                        opacity: isSelected ? 0.8 : 0.35,
                      }}
                    />
                    <Circle
                      center={[s.current_lat, s.current_lng]}
                      radius={isSelected ? 180000 : 100000}
                      pathOptions={{
                        color,
                        fillColor: color,
                        fillOpacity: isSelected ? 0.5 : 0.3,
                        weight: 0,
                      }}
                      eventHandlers={{ click: () => setSelected(s.id) }}
                    >
                      <Popup>
                        <div style={{ fontFamily: "sans-serif", fontSize: 12 }}>
                          <div style={{ fontWeight: 700, marginBottom: 2 }}>{s.carrier_name}</div>
                          <div style={{ color: "#8a847b", fontSize: 10 }}>{s.tracking_number}</div>
                          <div style={{ color, fontWeight: 700, fontSize: 10, marginTop: 4 }}>{s.risk_level}</div>
                        </div>
                      </Popup>
                    </Circle>
                  </React.Fragment>
                );
              })}
            </MapContainer>
          </div>
        </div>

        {/* Bottom: Selected Shipment Detail Panel */}
        <AnimatePresence>
          {selectedShipment && (
            <motion.div
              key={selectedShipment.id}
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="mx-6 mb-4 rounded-lg border border-[#222222] bg-[#222222] flex-shrink-0 overflow-hidden"
            >
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#222222]">
                <span className="text-[12px] font-semibold text-white flex items-center gap-2">
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ background: riskColor(selectedShipment.risk_level) }}
                  />
                  {selectedShipment.carrier_name}
                  <span className="text-[10px] font-mono text-[#8a847b]">{selectedShipment.tracking_number}</span>
                </span>
                <span
                  className="text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded"
                  style={{
                    color: riskColor(selectedShipment.risk_level),
                    background: riskColor(selectedShipment.risk_level) + "15",
                    border: `1px solid ${riskColor(selectedShipment.risk_level)}30`,
                  }}
                >
                  {selectedShipment.risk_level}
                </span>
              </div>
              <div className="px-4 py-3 flex items-center gap-10">
                <div>
                  <div className="text-[9px] text-[#8a847b] uppercase tracking-widest mb-0.5">Est. Arrival</div>
                  <div className="text-[12px] text-white font-semibold">
                    {new Date(selectedShipment.estimated_arrival).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-[#8a847b] uppercase tracking-widest mb-0.5">Required By</div>
                  <div className="text-[12px] font-semibold"
                    style={{ color: (selectedShipment.risk_level === "HIGH" || selectedShipment.risk_level === "CRITICAL") ? "#E24B4A" : "#f0ece4" }}
                  >
                    {new Date(selectedShipment.required_delivery).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-[#8a847b] uppercase tracking-widest mb-0.5">Status</div>
                  <div className="text-[12px] text-[#8a847b] font-semibold capitalize">{selectedShipment.status}</div>
                </div>
                <div className="flex-1" />
                {(selectedShipment.risk_level === "HIGH" || selectedShipment.risk_level === "CRITICAL") && (
                  !selectedShipment.ai_alternatives?.alternatives?.length ? (
                    <button
                      onClick={() => analyzeRisk(selectedShipment.id)}
                      disabled={analyzing === selectedShipment.id}
                      className="flex items-center gap-1.5 text-[11px] font-semibold text-[#8a847b] hover:text-white bg-[#222222] hover:bg-[#333330] border border-[#333330] rounded px-3 py-1.5 transition-all disabled:opacity-50"
                    >
                      {analyzing === selectedShipment.id
                        ? <><Activity size={11} className="animate-spin" /> Analyzing…</>
                        : <><Zap size={11} /> Run AI Risk Model</>}
                    </button>
                  ) : (
                    <div className="text-[11px] text-red-400 bg-red-500/5 border border-red-500/10 rounded px-3 py-2 max-w-xs">
                      <span className="font-bold text-[10px] uppercase tracking-widest block mb-0.5 text-red-500">AI Assessment</span>
                      {selectedShipment.ai_alternatives.risk_assessment}
                    </div>
                  )
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  );
}
