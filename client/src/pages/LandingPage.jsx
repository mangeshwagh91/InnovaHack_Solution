import { useRef, useEffect, useState } from "react";
import {
  motion,
  AnimatePresence,
  useScroll,
  useTransform,
  useSpring,
  useInView,
  animate,
} from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight, ShieldCheck, FileText,
  Mail, Truck, AlertTriangle, LayoutGrid, Layers,
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

/* ═══════════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ═══════════════════════════════════════════════════════════════════ */
const C = {
  bg:      "#1a1a1a",
  surface: "#222222",
  elevated:"#2a2a2a",
  bronze:  "#b08d6e",
  ivory:   "#f0ece4",
  muted:   "#8a847b",
  dim:     "#4a4640",
  border:  "#333330",
};

/* ═══════════════════════════════════════════════════════════════════
   REUSABLE COMPONENTS
   ═══════════════════════════════════════════════════════════════════ */

// Animated counter
function Counter({ to, suffix = "", delay = 0, duration = 1.8 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!inView) return;
    const t = setTimeout(() => {
      const controls = animate(0, to, {
        duration,
        ease: [0.16, 1, 0.3, 1],
        onUpdate: (v) => setVal(Math.round(v)),
      });
      return () => controls.stop();
    }, delay * 1000);
    return () => clearTimeout(t);
  }, [inView, to, delay, duration]);
  return <span ref={ref}>{val}{suffix}</span>;
}

// MacOS-style window chrome
function MacWindow({ children, title = "dataforge-workspace" }) {
  return (
    <div className="w-full rounded-xl overflow-hidden" style={{ backgroundColor: C.bg, border: `1px solid ${C.border}`, boxShadow: "0 25px 60px rgba(0,0,0,0.7)" }}>
      <div className="flex items-center justify-between px-4 py-3 select-none" style={{ backgroundColor: C.bg, borderBottom: `1px solid ${C.border}` }}>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f56]" />
          <div className="w-2.5 h-2.5 rounded-full bg-[#F2AF48]" />
          <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: C.bronze }} />
        </div>
        <span className="text-[11px] font-mono font-semibold tracking-wider" style={{ color: C.muted }}>{title}</span>
        <div className="w-12" />
      </div>
      <div className="p-6 relative" style={{ backgroundColor: C.surface }}>
        {children}
      </div>
    </div>
  );
}

// Scroll-drawing vertical timeline
function ScrollTimeline({ steps }) {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start 0.7", "end 0.3"],
  });
  const lineHeight = useSpring(useTransform(scrollYProgress, [0, 1], ["0%", "100%"]), {
    stiffness: 60, damping: 20,
  });

  return (
    <div ref={containerRef} style={{ position: "relative", padding: "0 24px" }}>
      {/* Track */}
      <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, backgroundColor: C.border, transform: "translateX(-50%)", opacity: 0.4 }} />
      {/* Animated bronze fill */}
      <motion.div style={{ position: "absolute", left: "50%", top: 0, width: 2, backgroundColor: C.bronze, transform: "translateX(-50%)", height: lineHeight, boxShadow: `0 0 12px ${C.bronze}44` }} />
      {/* Nodes */}
      <div style={{ display: "flex", flexDirection: "column", gap: 80, position: "relative" }}>
        {steps.map((step, i) => (
          <TimelineNode key={i} step={step} index={i} />
        ))}
      </div>
    </div>
  );
}

function TimelineNode({ step, index }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const isLeft = index % 2 === 0;

  return (
    <div ref={ref} style={{ display: "flex", alignItems: "center", gap: 32, flexDirection: isLeft ? "row" : "row-reverse", maxWidth: 800, margin: "0 auto", width: "100%" }}>
      <motion.div
        initial={{ opacity: 0, x: isLeft ? -50 : 50, filter: "blur(6px)" }}
        animate={inView ? { opacity: 1, x: 0, filter: "blur(0px)" } : {}}
        transition={{ duration: 0.8, ease: [0.25, 0.46, 0.45, 0.94] }}
        style={{ flex: 1, textAlign: isLeft ? "right" : "left", padding: "20px 24px", backgroundColor: `${C.surface}cc`, borderRadius: 8, border: `1px solid ${C.border}44`, backdropFilter: "blur(8px)" }}
      >
        <p style={{ color: C.ivory, fontSize: 15, fontWeight: 500, lineHeight: 1.5, margin: 0 }}>{step.label}</p>
        <p style={{ color: C.muted, fontSize: 12, lineHeight: 1.5, margin: "6px 0 0 0" }}>{step.detail}</p>
      </motion.div>

      <motion.div
        initial={{ scale: 0 }}
        animate={inView ? { scale: 1 } : {}}
        transition={{ duration: 0.4, delay: 0.2, type: "spring", stiffness: 200 }}
        style={{ width: 14, height: 14, borderRadius: "50%", border: `2px solid ${C.bronze}`, backgroundColor: C.bg, flexShrink: 0, boxShadow: inView ? `0 0 14px ${C.bronze}44` : "none" }}
      />

      <motion.div
        initial={{ opacity: 0, x: isLeft ? 30 : -30 }}
        animate={inView ? { opacity: 1, x: 0 } : {}}
        transition={{ duration: 0.6, delay: 0.3 }}
        style={{ flex: 1, textAlign: isLeft ? "left" : "right" }}
      >
        {step.agent && (
          <span style={{ display: "inline-block", fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: C.bronze, padding: "5px 12px", border: `1px solid ${C.bronze}44`, borderRadius: 16 }}>
            {step.agent}
          </span>
        )}
      </motion.div>
    </div>
  );
}

// Differentiator statement with drawing underline
function Statement({ text, index = 0 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.8, delay: index * 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
      style={{ maxWidth: 600, margin: "0 auto", padding: "40px 0" }}
    >
      <p style={{ color: C.ivory, fontSize: "clamp(17px, 2.5vw, 20px)", fontWeight: 400, lineHeight: 1.6, letterSpacing: "0.01em", margin: 0 }}>
        {text}
      </p>
      <motion.div
        initial={{ scaleX: 0 }}
        animate={inView ? { scaleX: 1 } : {}}
        transition={{ duration: 0.8, delay: index * 0.15 + 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
        style={{ height: 1, backgroundColor: C.bronze, marginTop: 24, transformOrigin: "left" }}
      />
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   MAIN LANDING PAGE
   ═══════════════════════════════════════════════════════════════════ */
export default function LandingPage() {
  const navigate = useNavigate();
  const { loginAsTeam, loginAsVendorDemo } = useAuth();
  const [activeTab, setActiveTab] = useState("bidding");
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 80, damping: 25 });

  // Interactive Simulation States
  const [selectedBid, setSelectedBid] = useState("Delta");
  const [ncrResult, setNcrResult] = useState(null);
  const [ncrLoading, setNcrLoading] = useState(false);
  const [emailSubject, setEmailSubject] = useState("");
  const [emailStatus, setEmailStatus] = useState("idle");
  const [truckDelay, setTruckDelay] = useState(false);

  const tabs = [
    { id: "bidding", label: "Vendor Bidding", icon: <Layers size={14} /> },
    { id: "compliance", label: "Compliance Scan", icon: <ShieldCheck size={14} /> },
    { id: "email", label: "Email Ingestion", icon: <Mail size={14} /> },
    { id: "logistics", label: "GPS Telemetry", icon: <Truck size={14} /> },
  ];

  const timelineSteps = [
    { label: "Vendors submit tenders to the platform", detail: "AI scores across price, compliance, lead time, and quality — recommends the best vendor.", agent: "Procurement Agent" },
    { label: "Engineers upload 1000+ page specifications", detail: "AI extracts every clause, vectorizes it, and builds a searchable knowledge graph.", agent: "Orchestrator Agent" },
    { label: "Vendor submittals checked against specs", detail: "Catches deviations instantly. Auto-generates full NCRs with clause references.", agent: "Compliance Agent" },
    { label: "Schedule risks predicted across 500+ tasks", detail: "Cross-references float erosion, NCR severity, and procurement delays.", agent: "Schedule Agent" },
    { label: "GPS tracks equipment shipments in real-time", detail: "Detects delays, links them to the critical path, suggests alternatives with cost impact.", agent: "Supply Chain Agent" },
    { label: "Field engineers ask questions on-site", detail: "Instant answers with exact page citations. No more 2-4 week wait.", agent: "Knowledge Agent" },
    { label: "Commissioning tests validated against specs", detail: "AI generates equipment-specific checklists from actual project specs.", agent: "Commissioning Agent" },
  ];

  return (
    <div style={{ backgroundColor: C.bg, color: C.ivory, fontFamily: "'Inter', 'Helvetica Neue', sans-serif", overflowX: "hidden", position: "relative" }}>

      {/* ─── Scroll progress bar ─── */}
      <motion.div style={{ position: "fixed", top: 0, left: 0, right: 0, height: 2, backgroundColor: C.bronze, scaleX, transformOrigin: "left", zIndex: 100 }} />

      {/* Grain texture */}
      <div style={{ position: "fixed", inset: 0, backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E")`, pointerEvents: "none", zIndex: 1 }} />

      {/* ─── Sticky Nav ─── */}
      <nav style={{ position: "fixed", top: 2, left: 0, right: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 32px", backgroundColor: `${C.bg}dd`, backdropFilter: "blur(12px)", borderBottom: `1px solid ${C.border}66` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, borderRadius: 6, backgroundColor: C.bronze, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <LayoutGrid size={14} color={C.bg} strokeWidth={2.5} />
          </div>
          <div>
            <span style={{ fontWeight: 700, fontSize: 15, color: C.ivory, letterSpacing: "-0.02em", display: "block", lineHeight: 1 }}>DataForge</span>
            <span style={{ fontSize: 9, color: C.muted, letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600 }}>AI Platform</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <button onClick={() => navigate("/projects")} style={{ fontSize: 12, fontWeight: 600, color: C.muted, background: "none", border: "none", cursor: "pointer" }}>Sign In</button>
          <button onClick={() => navigate("/projects")} style={{ fontSize: 12, fontWeight: 700, color: C.bg, background: C.bronze, border: "none", padding: "8px 18px", borderRadius: 6, cursor: "pointer" }}>Start Free</button>
        </div>
      </nav>


      {/* ════════════════ HERO ════════════════ */}
      <section style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 24px", position: "relative", zIndex: 2 }}>

        {/* Subtle blueprint grid behind everything */}
        <div style={{ position: "absolute", inset: 0, backgroundImage: `linear-gradient(to right, ${C.border}08 1px, transparent 1px), linear-gradient(to bottom, ${C.border}08 1px, transparent 1px)`, backgroundSize: "64px 64px", pointerEvents: "none" }} />

        <div style={{ textAlign: "center", position: "relative" }}>

          {/* ── Title with animated gradient sweep ── */}
          <div style={{ overflow: "hidden", position: "relative" }}>
            <motion.h1
              initial={{ y: "100%" }}
              animate={{ y: "0%" }}
              transition={{ duration: 1, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
              style={{ fontSize: "clamp(60px, 13vw, 160px)", fontWeight: 200, letterSpacing: "-0.05em", margin: 0, paddingBottom: "0.15em", marginBottom: "-0.15em", lineHeight: 0.9, position: "relative", color: "transparent" }}
            >
              {/* Base text layer (dim) */}
              <span style={{ backgroundImage: `linear-gradient(180deg, ${C.ivory}33 0%, ${C.ivory}15 100%)`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                DataForge
              </span>

              {/* Sweeping highlight layer */}
              <motion.span
                animate={{ backgroundPosition: ["-200% center", "200% center"] }}
                transition={{ repeat: Infinity, duration: 6, ease: "linear" }}
                style={{
                  position: "absolute", inset: 0,
                  backgroundImage: `linear-gradient(90deg, transparent 0%, ${C.ivory} 45%, ${C.bronze} 50%, ${C.ivory} 55%, transparent 100%)`,
                  backgroundSize: "200% 100%",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  fontSize: "inherit", fontWeight: "inherit", letterSpacing: "inherit", lineHeight: "inherit",
                }}
              >
                DataForge
              </motion.span>
            </motion.h1>
          </div>

          {/* ── Forge line — a horizontal line that heats up ── */}
          <div style={{ position: "relative", width: 200, margin: "24px auto", height: 1 }}>
            <div style={{ position: "absolute", inset: 0, backgroundColor: `${C.border}44` }} />
            <motion.div
              animate={{ left: ["-30%", "100%"] }}
              transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
              style={{ position: "absolute", top: -1, width: "30%", height: 3, borderRadius: 2, background: `linear-gradient(90deg, transparent, ${C.bronze}, transparent)` }}
            />
          </div>

          {/* ── Subtitle ── */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1.2, delay: 1 }}
            style={{ fontSize: "clamp(14px, 2vw, 17px)", color: C.muted, fontWeight: 400, margin: 0, lineHeight: 1.6, letterSpacing: "0.01em" }}
          >
            AI-Powered EPC Intelligence for Data Centres
          </motion.p>

          {/* ── Live agent status strip ── */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 1.6 }}
            style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "clamp(12px, 2.5vw, 24px)", marginTop: 32, flexWrap: "wrap" }}
          >
            {[
              { name: "Procurement", delay: 0 },
              { name: "Compliance", delay: 0.8 },
              { name: "Schedule", delay: 1.6 },
              { name: "Supply Chain", delay: 2.4 },
              { name: "Knowledge", delay: 0.4 },
              { name: "Commissioning", delay: 1.2 },
              { name: "Report", delay: 2.0 },
            ].map((agent) => (
              <div key={agent.name} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <motion.div
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ repeat: Infinity, duration: 3, delay: agent.delay, ease: "easeInOut" }}
                  style={{ width: 5, height: 5, borderRadius: "50%", backgroundColor: C.bronze }}
                />
                <span style={{ fontSize: 10, fontWeight: 500, color: C.dim, letterSpacing: "0.04em", textTransform: "uppercase" }}>{agent.name}</span>
              </div>
            ))}
          </motion.div>

          {/* ── CTA Buttons ── */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 2.2 }}
            style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap", marginTop: 44 }}
          >
            <motion.button
              onClick={() => {
                loginAsTeam();
                navigate("/projects");
              }}
              whileHover={{ scale: 1.05 }}
              style={{ padding: "13px 32px", backgroundColor: C.bronze, color: C.bg, border: "none", borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: "pointer", letterSpacing: "0.03em", transition: "opacity 0.3s" }}
              onMouseEnter={e => e.target.style.opacity = "0.85"}
              onMouseLeave={e => e.target.style.opacity = "1"}
            >
              Enter Platform
            </motion.button>
            <motion.button
              onClick={() => {
                loginAsVendorDemo();
                navigate("/");
              }}
              whileHover={{ scale: 1.05 }}
              style={{ padding: "13px 32px", backgroundColor: C.surface, color: C.ivory, border: `1px solid ${C.border}`, borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: "pointer", letterSpacing: "0.03em", transition: "border-color 0.3s" }}
              onMouseEnter={e => { e.target.style.borderColor = C.bronze; }}
              onMouseLeave={e => { e.target.style.borderColor = C.border; }}
            >
              Vendor Portal
            </motion.button>
          </motion.div>
        </div>

      </section>


      {/* ════════════════ STATS BAR ════════════════ */}
      <section style={{ padding: "48px 24px", borderTop: `1px solid ${C.border}33`, borderBottom: `1px solid ${C.border}33`, position: "relative", zIndex: 2 }}>
        <div style={{ display: "flex", justifyContent: "center", gap: "clamp(32px, 6vw, 72px)", flexWrap: "wrap", maxWidth: 800, margin: "0 auto" }}>
          {[
            { value: 7, suffix: "", label: "AI Agents" },
            { value: 120, suffix: "+", label: "Hours Saved / Week" },
            { value: 14, suffix: "", label: "Days Risk Flagged Early" },
            { value: 98, suffix: "%", label: "Compliance Accuracy" },
          ].map((stat, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.1 }} style={{ textAlign: "center" }}>
              <p style={{ fontSize: "clamp(26px, 4vw, 38px)", fontWeight: 300, color: C.bronze, margin: 0, letterSpacing: "-0.02em" }}>
                <Counter to={stat.value} suffix={stat.suffix} delay={i * 0.1} />
              </p>
              <p style={{ fontSize: 10, color: C.muted, letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600, marginTop: 6 }}>{stat.label}</p>
            </motion.div>
          ))}
        </div>
      </section>


      {/* ════════════════ SCENE 2: THE FLOW (SCROLL TIMELINE) ════════════════ */}
      <section style={{ padding: "100px 24px", maxWidth: 900, margin: "0 auto", position: "relative", zIndex: 2 }}>
        <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ duration: 0.8 }} style={{ textAlign: "center", marginBottom: 72 }}>
          <p style={{ fontSize: 11, color: C.bronze, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 12 }}>How it works</p>
          <h2 style={{ fontSize: "clamp(24px, 4vw, 36px)", fontWeight: 300, color: C.ivory, letterSpacing: "-0.02em", margin: 0 }}>
            One continuous flow, zero manual handoffs.
          </h2>
        </motion.div>
        <ScrollTimeline steps={timelineSteps} />
      </section>


      {/* ════════════════ INTERACTIVE SANDBOX ════════════════ */}
      <section id="playground" style={{ scrollMarginTop: 80, padding: "80px 24px", maxWidth: 1100, margin: "0 auto", position: "relative", zIndex: 2 }}>
        <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ duration: 0.6 }} style={{ marginBottom: 40 }}>
          <p style={{ fontSize: 11, color: C.bronze, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 8 }}>Try it yourself</p>
          <h2 style={{ fontSize: "clamp(22px, 3vw, 30px)", fontWeight: 800, color: C.ivory, letterSpacing: "-0.02em", margin: 0 }}>Interactive Sandbox Demo</h2>
          <p style={{ fontSize: 13, color: C.muted, marginTop: 8, maxWidth: 500 }}>Toggle controls below to simulate core platform workflows.</p>
        </motion.div>

        <div style={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 16, padding: "clamp(20px, 3vw, 32px)", position: "relative" }}>
          {/* Tab bar */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, paddingBottom: 20, marginBottom: 28, borderBottom: `1px solid ${C.border}` }}>
            {tabs.map(t => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "9px 18px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none",
                  backgroundColor: activeTab === t.id ? C.bronze : "transparent",
                  color: activeTab === t.id ? C.bg : C.muted,
                  transition: "all 0.2s",
                }}
              >
                {t.icon}{t.label}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: 32, flexWrap: "wrap", alignItems: "stretch" }}>
            {/* Left: Controls */}
            <div style={{ flex: "1 1 300px", minWidth: 260, display: "flex", flexDirection: "column", justifyContent: "center" }}>
              <AnimatePresence mode="wait">
                {activeTab === "bidding" && (
                  <motion.div key="bid" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    <h3 style={{ fontSize: 17, fontWeight: 700, color: C.ivory, margin: 0 }}>Analyze vendor tenders</h3>
                    <p style={{ fontSize: 12, color: C.muted, lineHeight: 1.6 }}>Select a vendor to see AI-scored match against project specifications.</p>
                    <div style={{ display: "flex", gap: 8 }}>
                      {["Delta", "Schneider", "Eaton"].map(brand => (
                        <button key={brand} onClick={() => setSelectedBid(brand)} style={{ flex: 1, padding: "10px 0", borderRadius: 8, fontSize: 12, cursor: "pointer", fontWeight: selectedBid === brand ? 700 : 500, border: `1px solid ${selectedBid === brand ? C.bronze : C.border}`, backgroundColor: selectedBid === brand ? `${C.bronze}15` : "transparent", color: selectedBid === brand ? C.ivory : C.muted, transition: "all 0.2s" }}>
                          {brand}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}

                {activeTab === "compliance" && (
                  <motion.div key="comp" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    <h3 style={{ fontSize: 17, fontWeight: 700, color: C.ivory, margin: 0 }}>Scan TIA-942 Guidelines</h3>
                    <p style={{ fontSize: 12, color: C.muted, lineHeight: 1.6 }}>Cross-reference clearances against Tier regulations to isolate violations.</p>
                    <button onClick={() => { setNcrLoading(true); setTimeout(() => { setNcrResult({ details: "Aisle containment space is 1.05m. Annex G requires min 1.2m clearance." }); setNcrLoading(false); }, 1000); }} disabled={ncrLoading} style={{ padding: "10px 20px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none", backgroundColor: C.bronze, color: C.bg, opacity: ncrLoading ? 0.5 : 1, transition: "opacity 0.2s" }}>
                      {ncrLoading ? "Running Sweep..." : "Initiate Audit Run"}
                    </button>
                  </motion.div>
                )}

                {activeTab === "email" && (
                  <motion.div key="email" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    <h3 style={{ fontSize: 17, fontWeight: 700, color: C.ivory, margin: 0 }}>Ingest FWD blueprints</h3>
                    <p style={{ fontSize: 12, color: C.muted, lineHeight: 1.6 }}>Forward specs from site email attachments into the parsing workspace.</p>
                    <input type="text" value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} placeholder="e.g., Delta UPS specification logs" style={{ padding: "10px 14px", borderRadius: 8, fontSize: 12, border: `1px solid ${C.border}`, backgroundColor: C.bg, color: C.ivory, outline: "none" }} />
                    <button onClick={() => { if (!emailSubject) return; setEmailStatus("sending"); setTimeout(() => setEmailStatus("parsed"), 1200); }} disabled={emailStatus === "sending" || !emailSubject} style={{ padding: "10px 20px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none", backgroundColor: C.bronze, color: C.bg, opacity: (emailStatus === "sending" || !emailSubject) ? 0.5 : 1 }}>
                      {emailStatus === "sending" ? "Processing..." : "Send FWD email"}
                    </button>
                  </motion.div>
                )}

                {activeTab === "logistics" && (
                  <motion.div key="log" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    <h3 style={{ fontSize: 17, fontWeight: 700, color: C.ivory, margin: 0 }}>Logistics Delay Flagging</h3>
                    <p style={{ fontSize: 12, color: C.muted, lineHeight: 1.6 }}>Simulate route bottlenecks to verify dynamic recalculations.</p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button onClick={() => setTruckDelay(false)} style={{ flex: 1, padding: "10px 0", borderRadius: 8, fontSize: 12, cursor: "pointer", border: `1px solid ${!truckDelay ? C.bronze : C.border}`, backgroundColor: !truckDelay ? `${C.bronze}15` : "transparent", color: !truckDelay ? C.ivory : C.muted, fontWeight: !truckDelay ? 700 : 500 }}>Clear Route</button>
                      <button onClick={() => setTruckDelay(true)} style={{ flex: 1, padding: "10px 0", borderRadius: 8, fontSize: 12, cursor: "pointer", border: `1px solid ${truckDelay ? "#c4655a" : C.border}`, backgroundColor: truckDelay ? "#c4655a15" : "transparent", color: truckDelay ? "#c4655a" : C.muted, fontWeight: truckDelay ? 700 : 500 }}>Trigger Traffic</button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Right: Console */}
            <div style={{ flex: "1 1 380px", minWidth: 300 }}>
              <MacWindow title="dataforge-terminal">
                <div style={{ minHeight: 200, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                  <AnimatePresence mode="wait">
                    {activeTab === "bidding" && (
                      <motion.div key={`bid-${selectedBid}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ fontFamily: "monospace", fontSize: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: `1px solid ${C.border}` }}>
                          <span style={{ fontSize: 10, fontWeight: 700, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em" }}>Tender Analysis</span>
                          <span style={{ fontSize: 10, fontWeight: 700, color: selectedBid === "Delta" ? C.bronze : C.muted }}>{selectedBid} Systems</span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                          <div>
                            <div style={{ color: C.ivory, fontWeight: 700 }}>{selectedBid === "Delta" ? "Delta MOD-500" : selectedBid === "Schneider" ? "Galaxy PX" : "Eaton Power-9"}</div>
                            <span style={{ color: C.muted, fontSize: 10 }}>Category: UPS Module</span>
                          </div>
                          <span style={{ fontSize: 10, fontWeight: 700, color: selectedBid === "Delta" ? C.bronze : C.muted }}>{selectedBid === "Delta" ? "98% Match" : selectedBid === "Schneider" ? "84% Match" : "79% Match"}</span>
                        </div>
                        <div style={{ padding: 12, backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", color: C.muted, marginBottom: 4 }}><span>Efficiency</span><span>{selectedBid === "Delta" ? "96.5%" : "94.8%"}</span></div>
                          <div style={{ display: "flex", justifyContent: "space-between", color: C.muted }}><span>Lead Time</span><span>{selectedBid === "Delta" ? "4 Weeks" : "8 Weeks"}</span></div>
                        </div>
                        <div style={{ color: C.muted, fontSize: 11 }}>{selectedBid === "Delta" ? "✓ Verified compliance parameters." : "⚠ Width exceeds clearance space."}</div>
                      </motion.div>
                    )}

                    {activeTab === "compliance" && (
                      <motion.div key="comp-r" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ fontFamily: "monospace", fontSize: 12 }}>
                        {!ncrResult && !ncrLoading && <div style={{ textAlign: "center", color: C.muted, padding: "32px 0" }}>&lt; Sweep Idle &gt;</div>}
                        {ncrLoading && (
                          <div>
                            <div style={{ color: C.ivory, marginBottom: 8 }}>Analyzing clearances...</div>
                            <div style={{ height: 2, backgroundColor: C.bg, borderRadius: 4, overflow: "hidden" }}>
                              <motion.div initial={{ width: 0 }} animate={{ width: "100%" }} transition={{ duration: 1 }} style={{ height: "100%", backgroundColor: C.bronze }} />
                            </div>
                          </div>
                        )}
                        {ncrResult && !ncrLoading && (
                          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                            <div style={{ color: "#c4655a", fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}>
                              <AlertTriangle size={14} /> Deviation isolated
                            </div>
                            <div style={{ padding: 12, backgroundColor: "#2a201e", border: "1px solid #c4655a33", color: "#c4655a", borderRadius: 8, fontSize: 11 }}>{ncrResult.details}</div>
                          </div>
                        )}
                      </motion.div>
                    )}

                    {activeTab === "email" && (
                      <motion.div key="email-r" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ fontFamily: "monospace", fontSize: 12 }}>
                        {emailStatus === "idle" && <div style={{ textAlign: "center", color: C.muted, padding: "32px 0" }}>&lt; Awaiting forwarding trigger &gt;</div>}
                        {emailStatus === "sending" && <div style={{ color: C.ivory }}>Connecting SMTP & parsing attachment payload...</div>}
                        {emailStatus === "parsed" && (
                          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: 12, backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8 }}>
                              <FileText size={16} color={C.muted} />
                              <div>
                                <div style={{ color: C.ivory, fontWeight: 700, fontSize: 11 }}>{emailSubject}</div>
                                <div style={{ fontSize: 10, color: C.muted }}>Payload: spec_sheet.pdf</div>
                              </div>
                            </div>
                            <div style={{ color: C.bronze, fontWeight: 700 }}>✓ PDF processed. Specs added to workspace.</div>
                          </div>
                        )}
                      </motion.div>
                    )}

                    {activeTab === "logistics" && (
                      <motion.div key={`log-${truckDelay}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ fontFamily: "monospace", fontSize: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                        <div style={{ height: 56, backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, position: "relative", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <div style={{ position: "absolute", width: "80%", height: 2, backgroundColor: C.border, borderRadius: 4, overflow: "hidden" }}>
                            <div style={{ height: "100%", width: "60%", backgroundColor: truckDelay ? "#c4655a" : C.bronze }} />
                          </div>
                          <div style={{ position: "absolute", left: "60%", marginLeft: -10, width: 20, height: 20, borderRadius: "50%", border: `1.5px solid ${truckDelay ? "#c4655a" : C.bronze}`, backgroundColor: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Truck size={9} color={truckDelay ? "#c4655a" : C.bronze} />
                          </div>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                          <span style={{ color: C.muted }}>UPS Carrier: Trk-9912</span>
                          <span style={{ fontWeight: 700, color: truckDelay ? "#c4655a" : C.bronze }}>{truckDelay ? "Incident Detected" : "Clear Route"}</span>
                        </div>
                        {truckDelay && <div style={{ padding: 10, backgroundColor: "#2a201e", border: "1px solid #c4655a33", color: "#c4655a", borderRadius: 8, fontSize: 11 }}>Alert: weather issue on Route 40. Arrival time: +4h.</div>}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </MacWindow>
            </div>
          </div>
        </div>
      </section>


      {/* ════════════════ SCENE 3: THE DIFFERENTIATOR ════════════════ */}
      <section style={{ padding: "100px 24px", maxWidth: 700, margin: "0 auto", position: "relative", zIndex: 2 }}>
        <motion.p initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ duration: 0.8 }} style={{ textAlign: "center", fontSize: 11, color: C.bronze, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 48 }}>
          What makes this different
        </motion.p>
        <Statement text="NCRs auto-generated with exact spec clause references — not flagged, written." index={0} />
        <Statement text="RFIs answered in seconds with page citations — not weeks." index={1} />
        <Statement text="Shipping delays linked directly to the critical path — not siloed." index={2} />
      </section>





      {/* ─── Footer ─── */}
      <footer style={{ borderTop: `1px solid ${C.border}33`, padding: "28px 24px", textAlign: "center" }}>
        <p style={{ fontSize: 10, color: C.dim, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>© 2026 DataForge AI — All rights reserved.</p>
      </footer>
    </div>
  );
}
