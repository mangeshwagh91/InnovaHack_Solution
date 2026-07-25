import { useState } from "react";
import { Triangle, Search, HelpCircle, Lightbulb, Menu } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import ProfileDropdown from "../workspace/ProfileDropdown.jsx";

export default function Header({ toggleSidebar, hideSidebarToggle }) {
  const [searchFocused, setSearchFocused] = useState(false);
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-30 h-12 bg-[#1a1a1a] border-b border-[#333330] flex items-center justify-between pr-4 pl-4 lg:pl-0 lg:pr-6">
      {/* Left: Org Name & Badge */}
      <div className="flex items-center flex-1 min-w-0">
        {!hideSidebarToggle && (
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded-md text-[#8a847b] hover:text-white hover:bg-[#222222] lg:hidden transition-colors mr-2"
          >
            <Menu size={18} />
          </button>
        )}
        <button 
          onClick={() => { logout(); navigate("/"); }} 
          className="flex items-center bg-transparent border-none cursor-pointer p-0"
        >
          <div className="hidden lg:flex w-14 items-center justify-center shrink-0">
            <Triangle size={18} className="fill-current text-white mt-0.5" />
          </div>
          <div className="lg:hidden flex items-center justify-center shrink-0 mr-2">
            <Triangle size={18} className="fill-current text-white mt-0.5" />
          </div>
          <span className="text-white font-medium text-[15px] tracking-tight hover:text-[#f0ece4] transition-colors">
            EPC Company's Org
          </span>
        </button>
      </div>

      {/* Right: Controls & Profile */}
      <div className="flex items-center gap-4">
        <a href="#" className="hidden md:block text-[13px] font-medium text-[#8a847b] hover:text-white transition-colors">
          Feedback
        </a>
        
        {/* Search */}
        <div
          className={`hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md w-56 transition-all duration-200 ${
            searchFocused
              ? "bg-[#1a1a1a] border border-[#8a847b] ring-1 ring-[#8a847b]"
              : "bg-[#1a1a1a] border border-[#333330] hover:border-[#8a847b]"
          }`}
        >
          <Search size={14} className="text-[#8a847b] shrink-0" />
          <input
            type="text"
            placeholder="Search..."
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            className="bg-transparent border-none outline-none text-[13px] text-white w-full placeholder:text-[#8a847b]"
          />
          <span className="text-[10px] text-[#8a847b] font-mono hidden lg:inline shrink-0 border border-[#333330] rounded px-1 py-0.5 bg-[#222222]">
            Ctrl K
          </span>
        </div>

        <div className="flex items-center gap-2 text-[#8a847b]">
          <button className="p-1.5 rounded-md hover:text-white hover:bg-[#222222] transition-colors">
            <HelpCircle size={18} />
          </button>
          <button className="p-1.5 rounded-md hover:text-white hover:bg-[#222222] transition-colors">
            <Lightbulb size={18} />
          </button>
        </div>

        <div className="pl-1">
          <ProfileDropdown />
        </div>
      </div>
    </header>
  );
}
