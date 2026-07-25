import { useState, useRef, useEffect, Suspense } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Grid, Environment, Html } from "@react-three/drei";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Upload, Box, Cpu, Server, Map as MapIcon, Loader2, CheckCircle2,
  Database, Table2, FunctionSquare, Zap, List, Puzzle, Hash, BookOpen,
  Shield, Users, Settings, Copy, HardDrive, ArrowRightLeft, Search, Plus,
  LayoutTemplate, BrickWall, DoorClosed, Fan, Zap as ZapIcon, LayoutGrid, PaintBucket, Camera
} from "lucide-react";

// ─── 3D Component: Wall ──────────────────────────────────────────────────────
function Wall({ position, size, id, onClick }) {
  const [hovered, setHovered] = useState(false);
  return (
    <mesh 
      position={position} 
      onPointerOver={(e) => (e.stopPropagation(), setHovered(true))}
      onPointerOut={() => setHovered(false)}
      onClick={(e) => {
        e.stopPropagation();
        if (onClick) onClick(id, "wall");
      }}
    >
      <boxGeometry args={size} />
      <meshStandardMaterial 
        color={hovered ? "#b08d6e" : "#1e293b"} 
        transparent 
        opacity={hovered ? 0.9 : 0.8}
        metalness={0.2}
        roughness={0.8}
      />
    </mesh>
  );
}

// ─── 3D Component: Object (Rack/HVAC) ────────────────────────────────────────
function InfrastructureObject({ position, size, type, id, onClick }) {
  const [hovered, setHovered] = useState(false);
  
  const getColor = () => {
    if (type === "rack") return "#0F3058"; // Blue
    if (type === "pdu") return "#F2AF48"; // Yellow
    if (type === "hvac") return "#b08d6e"; // Primary Brand
    return "#64748b";
  };

  return (
    <mesh 
      position={position}
      onPointerOver={(e) => (e.stopPropagation(), setHovered(true))}
      onPointerOut={() => setHovered(false)}
      onClick={(e) => {
        e.stopPropagation();
        if (onClick) onClick(id, type);
      }}
    >
      <boxGeometry args={size} />
      <meshStandardMaterial 
        color={hovered ? "#f0ece4" : getColor()} 
        metalness={0.8} 
        roughness={0.2} 
      />
      {hovered && (
        <Html position={[0, size[1] / 2 + 0.5, 0]} center>
          <div className="bg-[#1a1a1a]/80 backdrop-blur-md text-white text-[10px] font-bold px-2 py-1 rounded-md border border-[#333330] shadow-xl whitespace-nowrap">
            {type.toUpperCase()} - {id}
          </div>
        </Html>
      )}
    </mesh>
  );
}

// ─── Sidebar Item Component ──────────────────────────────────────────────────
function SidebarItem({ icon: Icon, label, active }) {
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 text-[13px] rounded-md cursor-pointer transition-colors ${active ? 'bg-[#333330] text-white font-medium' : 'text-[#8a847b] hover:text-white hover:bg-[#333330]/50'}`}>
      <Icon size={14} className={active ? "text-[#b08d6e]" : "text-[#8a847b]"} />
      <span>{label}</span>
    </div>
  );
}

function SidebarSection({ title, children }) {
  return (
    <div className="mb-6">
      <div className="text-[10px] text-[#8a847b] uppercase tracking-widest font-bold mb-2 px-3">
        {title}
      </div>
      <div className="space-y-0.5">
        {children}
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────
export default function DesignPage() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [hasProcessed, setHasProcessed] = useState(false);
  const [sceneData, setSceneData] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  
  const fileInputRef = useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsProcessing(true);
    setHasProcessed(false);
    
    // In a real app, this sends FormData to the backend.
    // For this hackathon MVP, we hit the simulated FastAPI route.
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const response = await fetch("http://localhost:8000/api/design/convert", {
        method: "POST",
        body: formData,
      });
      
      const result = await response.json();
      
      if (result.status === "success") {
        setSceneData(result.data);
        setHasProcessed(true);
      }
    } catch (error) {
      console.error("Failed to process 2D file:", error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleItemClick = (id, type) => {
    setSelectedItem({ id, type });
  };

  return (
    <div className="flex-1 w-full h-full relative bg-[#1a1a1a] overflow-hidden flex flex-col">
      
      {/* ─── Top Header (Like Supabase Top Nav) ─── */}
      <div className="flex-none h-12 border-b border-[#333330] bg-[#222222] flex items-center justify-between px-4 z-20">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-[#8a847b]">
            <MapIcon size={16} className="text-[#b08d6e]" />
            <span className="text-white font-semibold">DC Project Org</span>
            <span className="text-[#333330]">/</span>
            <span className="text-white">AI Digital Twin Engine</span>
            <span className="text-[#333330]">/</span>
            <span className="px-2 py-0.5 rounded-full bg-[#b08d6e]/10 text-[#b08d6e] text-[10px] font-bold border border-[#b08d6e]/20">PRODUCTION</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8a847b]" />
            <input 
              type="text" 
              placeholder="Search components..." 
              className="bg-[#222222] border border-[#333330] text-sm text-white rounded-md pl-8 pr-3 py-1.5 focus:outline-none focus:border-[#333330] w-48 transition-colors"
            />
          </div>
          
          {hasProcessed && (
            <div className="flex items-center gap-2 text-[11px] font-bold text-[#b08d6e] bg-[#b08d6e]/10 px-3 py-1.5 rounded-md border border-[#b08d6e]/20">
              <CheckCircle2 size={14} />
              <span>Model Synced</span>
            </div>
          )}
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isProcessing}
            className="flex items-center gap-2 bg-[#8c6f55] hover:bg-[#b08d6e] text-white px-3 py-1.5 rounded-md text-sm font-semibold transition-colors disabled:opacity-50"
          >
            {isProcessing ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
            <span>Upload Plan</span>
          </button>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            accept=".jpg,.jpeg,.png,.pdf,.dxf"
            className="hidden" 
          />
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* ─── Left Sidebar (Editing Tools) ─── */}
        <div className="w-[240px] flex-none bg-[#1a1a1a] border-r border-[#333330] overflow-y-auto z-10 flex flex-col py-4 custom-scrollbar">
          <div className="px-4 mb-6">
            <h2 className="text-base font-semibold text-white">Design Tools</h2>
          </div>

          <SidebarSection title="Layout Management">
            <SidebarItem icon={LayoutTemplate} label="3D Visualizer" active={true} />
            <SidebarItem icon={BrickWall} label="Walls & Partitions" />
            <SidebarItem icon={DoorClosed} label="Doors & Windows" />
          </SidebarSection>

          <SidebarSection title="Infrastructure">
            <SidebarItem icon={Server} label="Server Racks" />
            <SidebarItem icon={Fan} label="HVAC Systems" />
            <SidebarItem icon={ZapIcon} label="Power Distribution" />
            <SidebarItem icon={LayoutGrid} label="Cable Trays" />
          </SidebarSection>

          <SidebarSection title="Configuration">
            <SidebarItem icon={PaintBucket} label="Materials & Textures" />
            <SidebarItem icon={Settings} label="Environment Settings" />
            <SidebarItem icon={Camera} label="Cameras & Views" />
          </SidebarSection>

          <SidebarSection title="Platform">
            <SidebarItem icon={Copy} label="Snapshots" />
            <SidebarItem icon={HardDrive} label="Export Models" />
            <SidebarItem icon={ArrowRightLeft} label="Migrations" />
          </SidebarSection>
        </div>

        {/* ─── Main Dotted Canvas Area ─── */}
        <div 
          className="flex-1 relative bg-[#1a1a1a]"
          style={{ 
            backgroundImage: 'radial-gradient(#27272a 1px, transparent 1px)', 
            backgroundSize: '24px 24px' 
          }}
        >
          {/* Empty State */}
          <AnimatePresence>
            {!hasProcessed && !isProcessing && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 z-10 flex flex-col items-center justify-center"
              >
                <div className="w-24 h-24 rounded-2xl bg-[#222222] border border-[#333330] flex items-center justify-center mb-6 shadow-2xl">
                  <Box size={40} className="text-[#8a847b]" />
                </div>
                <h2 className="text-xl font-bold text-white mb-2">Initialize Digital Twin</h2>
                <p className="text-sm text-[#8a847b] max-w-sm text-center mb-6">
                  Upload a 2D floor plan or CAD file. The AI engine will automatically extract topology and generate an editable 3D environment.
                </p>
                <button 
                  onClick={() => fileInputRef.current?.click()}
                  className="bg-[#222222] hover:bg-[#333330] border border-[#333330] text-white px-6 py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center gap-2"
                >
                  <Plus size={16} />
                  <span>New Layout</span>
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Processing State */}
          <AnimatePresence>
            {isProcessing && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-[#1a1a1a]/80 backdrop-blur-sm"
              >
                <div className="relative">
                  <div className="w-16 h-16 border-4 border-[#333330] border-t-emerald-500 rounded-full animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Cpu size={20} className="text-[#b08d6e] animate-pulse" />
                  </div>
                </div>
                <h2 className="text-sm font-bold text-[#b08d6e] mt-6 tracking-widest uppercase">Analyzing Topology</h2>
                <p className="text-xs text-[#8a847b] mt-2">Running computer vision segmentation...</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* 3D Canvas */}
          {hasProcessed && sceneData && (
            <div className="absolute inset-0 z-0">
              <Canvas camera={{ position: [10, 10, 10], fov: 45 }}>
                {/* Background color is transparent so the dotted pattern shows through the Canvas */}
                <ambientLight intensity={0.6} />
                <directionalLight position={[10, 20, 10]} intensity={1.5} castShadow />
                <directionalLight position={[-10, 10, -10]} intensity={0.5} color="#0F3058" />
                
                <Suspense fallback={null}>
                  <group position={[0, -1.5, 0]}>
                    {/* Floor (Optional: make it semi-transparent or slightly dark to differentiate from the void) */}
                    <mesh position={[0, -0.1, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                      <planeGeometry args={sceneData.roomSize || [15, 15]} />
                      <meshStandardMaterial color="#111113" roughness={0.4} metalness={0.1} opacity={0.8} transparent />
                    </mesh>

                    {/* Grid Helper - enhanced to match the technical look */}
                    <Grid 
                      renderOrder={-1} 
                      position={[0, 0, 0]} 
                      infiniteGrid 
                      fadeDistance={40} 
                      cellColor="#333330" 
                      sectionColor="#52525b" 
                    />

                    {/* Render Walls */}
                    {sceneData.walls?.map((wall) => (
                      <Wall 
                        key={wall.id} 
                        id={wall.id}
                        position={wall.position} 
                        size={wall.size} 
                        onClick={handleItemClick}
                      />
                    ))}

                    {/* Render Objects */}
                    {sceneData.objects?.map((obj) => (
                      <InfrastructureObject 
                        key={obj.id} 
                        id={obj.id}
                        type={obj.type}
                        position={obj.position} 
                        size={obj.size} 
                        onClick={handleItemClick}
                      />
                    ))}
                  </group>
                  <Environment preset="city" />
                </Suspense>
                <OrbitControls makeDefault autoRotate autoRotateSpeed={0.3} maxPolarAngle={Math.PI / 2 - 0.05} />
              </Canvas>
            </div>
          )}

          {/* Floating Canvas Controls (Bottom Right) */}
          {hasProcessed && sceneData && (
            <div className="absolute bottom-6 right-6 z-20 flex bg-[#222222] border border-[#333330] rounded-lg shadow-xl p-1">
               <button className="p-2 text-[#8a847b] hover:text-white hover:bg-[#333330] rounded-md transition-colors" title="Zoom In">
                 <Plus size={16} />
               </button>
               <div className="w-px bg-[#333330] mx-1 my-1"></div>
               <button className="p-2 text-[#8a847b] hover:text-white hover:bg-[#333330] rounded-md transition-colors" title="Zoom Out">
                 <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/></svg>
               </button>
               <div className="w-px bg-[#333330] mx-1 my-1"></div>
               <button className="p-2 text-[#b08d6e] hover:text-[#b08d6e] hover:bg-[#333330] rounded-md transition-colors" title="Auto Rotate">
                 <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
               </button>
            </div>
          )}
        </div>

        {/* ─── Right Inspector Panel (Slide in when object selected) ─── */}
        <AnimatePresence>
          {selectedItem && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 280 }}
              exit={{ opacity: 0, width: 0 }}
              className="flex-none bg-[#222222] border-l border-[#333330] z-20 overflow-hidden shadow-[-8px_0_24px_rgba(0,0,0,0.5)]"
            >
              <div className="w-[280px] h-full flex flex-col">
                <div className="p-4 border-b border-[#333330] flex items-center justify-between bg-[#222222]">
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <Server size={14} className="text-[#b08d6e]" />
                    Properties
                  </h3>
                  <button 
                    onClick={() => setSelectedItem(null)}
                    className="text-[#8a847b] hover:text-white transition-colors p-1 hover:bg-[#333330] rounded"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
                  </button>
                </div>
                
                <div className="p-4 space-y-4 overflow-y-auto custom-scrollbar flex-1">
                  <div className="space-y-1">
                    <span className="text-[10px] text-[#8a847b] font-bold uppercase tracking-widest block">Object ID</span>
                    <div className="bg-[#222222] border border-[#333330] rounded-md p-2 flex justify-between items-center group">
                      <span className="text-sm text-[#f0ece4] font-mono">{selectedItem.id}</span>
                      <button className="text-[#8a847b] opacity-0 group-hover:opacity-100 hover:text-white transition-all">
                         <Copy size={12} />
                      </button>
                    </div>
                  </div>
                  
                  <div className="space-y-1">
                    <span className="text-[10px] text-[#8a847b] font-bold uppercase tracking-widest block">Classification</span>
                    <div className="bg-[#222222] border border-[#333330] rounded-md p-2">
                      <span className="text-sm text-[#b08d6e] font-semibold capitalize">{selectedItem.type}</span>
                    </div>
                  </div>
                  
                  <div className="pt-4 border-t border-[#333330] space-y-2">
                    <button className="w-full bg-[#222222] hover:bg-[#333330] border border-[#333330] text-white py-2 rounded-md text-xs font-semibold transition-all">
                      Edit Dimensions
                    </button>
                    <button className="w-full bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 py-2 rounded-md text-xs font-semibold transition-all">
                      Delete Object
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  );
}

