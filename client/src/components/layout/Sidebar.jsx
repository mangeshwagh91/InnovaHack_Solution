import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  BarChart3,
  FileText,
  HelpCircle,
  AlertCircle,
  ActivitySquare,
  Landmark,
  LayoutGrid,
  CreditCard,
  Settings,
  Truck,
  Triangle,
  LogOut,
  CheckSquare
} from "lucide-react";
import { useAuth } from "../../context/AuthContext.jsx";
import { useWorkspace } from "../../context/WorkspaceContext.jsx";

export default function Sidebar({ isOpen, setIsOpen }) {
  const location = useLocation();
  const { user } = useAuth();
  const isVendor = user?.type === "vendor";
  const isGlobalPage = ["/projects", "/integrations", "/settings", "/team"].includes(location.pathname);
  const [isHovered, setIsHovered] = useState(false);
  const isExpanded = isOpen || isHovered;

  const globalLinks = [
    { name: "Projects", path: "/projects", icon: <LayoutGrid size={18} /> },
    { name: "Team", path: "/team", icon: <FileText size={18} /> },
    { name: "Integrations", path: "/integrations", icon: <BarChart3 size={18} /> },
    { name: "Usage", path: "#", icon: <ActivitySquare size={18} /> },
    { name: "Billing", path: "#", icon: <Landmark size={18} /> },
  ];

  const teamLinks = [
    { name: "Dashboard", path: "/dashboard", icon: <BarChart3 size={18} /> },
    { name: "Documents", path: "/documents", icon: <FileText size={18} /> },
    { name: "RFI Copilot", path: "/rfi", icon: <HelpCircle size={18} /> },
    { name: "Compliance", path: "/compliance", icon: <AlertCircle size={18} /> },
    { name: "Schedule", path: "/schedule", icon: <ActivitySquare size={18} /> },
    { name: "Commissioning", path: "/commissioning", icon: <CheckSquare size={18} /> },
    { name: "Design", path: "/design", icon: <LayoutGrid size={18} /> },
    { name: "Tenders", path: "/tenders", icon: <Landmark size={18} /> },
    { name: "Logistics", path: "/supply-chain", icon: <Truck size={18} /> },
  ];

  const vendorLinks = [
    { name: "Open Projects", path: "/", icon: <BarChart3 size={18} /> },
    { name: "My Tenders", path: "/vendor/tenders", icon: <Landmark size={18} /> },
    { name: "Vendor Profile", path: "/vendor/profile", icon: <FileText size={18} /> },
  ];

  const links = isGlobalPage ? globalLinks : isVendor ? vendorLinks : teamLinks;

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Expandable Sidebar */}
      <aside
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={`fixed lg:absolute top-0 left-0 h-full bg-[#1a1a1a] border-r border-[#333330] z-40 flex flex-col py-4 transition-all duration-250 ease-[cubic-bezier(0.4,0,0.2,1)] lg:translate-x-0 overflow-hidden shrink-0 ${isOpen ? "translate-x-0" : "-translate-x-full"
          } ${isExpanded ? "w-64 shadow-[4px_0_24px_rgba(0,0,0,0.5)]" : "w-14"} px-2`}
      >

        {/* Nav Icons */}
        <div className="flex-1 flex flex-col gap-0.5 w-full">
          {links.map((link) => {
            const isActive = location.pathname === link.path;
            return (
              <Link
                key={link.name}
                to={link.path}
                onClick={() => setIsOpen(false)}
                title={!isExpanded ? link.name : ""}
                className={`relative flex items-center rounded-md transition-colors group w-full h-9 overflow-hidden ${isActive
                    ? "text-white bg-[#2a2a2a]"
                    : "text-[#8a847b] hover:text-white hover:bg-[#222222]"
                  }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="sidebarActive"
                    className="absolute left-[-12px] top-1/2 -translate-y-1/2 w-[2px] h-5 bg-white rounded-r-full"
                    initial={false}
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  />
                )}
                <div className="w-10 h-9 flex items-center justify-center shrink-0">
                  {link.icon}
                </div>
                <span className={`ml-1 text-[13px] font-medium whitespace-nowrap transition-opacity duration-250 ${isExpanded ? "opacity-100 " : "opacity-0"}`}>
                  {link.name}
                </span>
              </Link>
            );
          })}
        </div>

        {/* Bottom Profile / Settings */}
        <div className="mt-auto flex flex-col gap-0.5 w-full">
          <button title={!isExpanded ? "Settings" : ""} className={`flex items-center rounded-md text-[#8a847b] hover:text-white hover:bg-[#222222] transition-colors w-full h-9 overflow-hidden`}>
            <div className="w-10 h-9 flex items-center justify-center shrink-0">
              <Settings size={18} />
            </div>
            <span className={`ml-1 text-[13px] font-medium whitespace-nowrap transition-opacity duration-250 ${isExpanded ? "opacity-100 " : "opacity-0"}`}>
              Settings
            </span>
          </button>
          <button title={!isExpanded ? "Profile" : ""} className={`flex items-center rounded-md text-[#8a847b] hover:text-white hover:bg-[#222222] transition-colors w-full h-9 overflow-hidden`}>
            <div className="w-10 h-9 flex items-center justify-center shrink-0">
              <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-[#b08d6e] to-teal-500" />
            </div>
            <span className={`ml-1 text-[13px] font-medium whitespace-nowrap transition-opacity duration-250 ${isExpanded ? "opacity-100 " : "opacity-0"}`}>
              Profile
            </span>
          </button>
        </div>
      </aside>
    </>
  );
}
