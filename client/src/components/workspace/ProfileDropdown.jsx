import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { ActivitySquare, Bell, Settings, LogOut, ChevronDown } from "lucide-react";
import { useAuth } from "../../context/AuthContext.jsx";
import { useWorkspace } from "../../context/WorkspaceContext.jsx";

export default function ProfileDropdown() {
  const { logout, user } = useAuth();
  const { toggleNotifications } = useWorkspace();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const name = user?.name || "EPC Project Team";
  const userTypeLabel = user?.type === "vendor" ? "Vendor Workspace" : "EPC Team Workspace";
  const initials = name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();

  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 pl-1 pr-2 py-1 rounded-xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors"
      >
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white text-[11px] font-bold">
          {initials}
        </div>
        <ChevronDown
          size={12}
          className={`text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ duration: 0.13, ease: "easeOut" }}
            className="absolute right-0 top-11 w-60 bg-white border border-slate-200 rounded-2xl shadow-xl z-50 overflow-hidden"
          >
            {/* User info */}
            <div className="p-3 flex items-center gap-3 border-b border-slate-100 bg-slate-50">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {initials}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-bold text-slate-800 truncate">{name}</p>
                <p className="text-[11px] text-slate-400 truncate">{userTypeLabel}</p>
              </div>
            </div>

            {/* Menu */}
            <div className="p-1.5 space-y-0.5">
              <Link
                to="/activity"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-colors"
              >
                <ActivitySquare size={15} className="text-slate-400" /> Activity Center
              </Link>
              <button
                onClick={() => { setOpen(false); toggleNotifications(); }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-colors"
              >
                <Bell size={15} className="text-slate-400" /> Notifications
              </button>
              <Link
                to="/settings"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-colors"
              >
                <Settings size={15} className="text-slate-400" /> Settings
              </Link>
            </div>

            {/* Logout */}
            <div className="p-1.5 border-t border-slate-100">
              <button
                onClick={logout}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-rose-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
              >
                <LogOut size={15} /> Log out
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
