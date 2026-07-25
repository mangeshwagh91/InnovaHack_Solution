import { useState } from "react";
import Sidebar from "./Sidebar.jsx";
import Header from "./Header.jsx";
import NotificationDrawer from "../workspace/NotificationDrawer.jsx";

export default function AppLayout({ children, hideSidebar = false }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

  return (
    <div className="h-screen w-full flex flex-col font-sans bg-[#1a1a1a] text-[#f0ece4] overflow-hidden">
      <Header toggleSidebar={toggleSidebar} hideSidebarToggle={hideSidebar} />

      <div className="flex-1 flex relative h-full min-w-0 overflow-hidden">
        {!hideSidebar && <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />}

        <main className={`flex-1 w-full flex flex-col overflow-y-auto custom-scrollbar ${!hideSidebar ? "lg:pl-14" : ""}`}>
          {children}
        </main>
      </div>

      <NotificationDrawer />
    </div>
  );
}
