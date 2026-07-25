import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Compliance from "./pages/Compliance.jsx";
import NCRDetail from "./pages/NCRDetail.jsx";
import Schedule from "./pages/Schedule.jsx";
import RFIChat from "./pages/RFIChat.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import BidsAndContracts from "./pages/TendersAndContracts.jsx";
import DocumentsPage from "./pages/DocumentsPage.jsx";
import VendorDashboard from "./pages/VendorDashboard.jsx";
import CommissioningPage from "./pages/CommissioningPage.jsx";
import VendorBids from "./pages/VendorTenders.jsx";
import VendorProfile from "./pages/VendorProfile.jsx";
import PageTransition from "./components/PageTransition.jsx";
import DesignPage from "./pages/DesignPage.jsx";
import NewProject from "./pages/NewProject.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import ProjectsPage from "./pages/ProjectsPage.jsx";
import SupplyChainPage from "./pages/SupplyChainPage.jsx";
import IntegrationsPage from "./pages/IntegrationsPage.jsx";
import TeamPage from "./pages/TeamPage.jsx";

// Auth and Workspace Layout
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import { WorkspaceProvider } from "./context/WorkspaceContext.jsx";
import LoginScreen from "./components/auth/LoginScreen.jsx";

// Animated routes — must be inside BrowserRouter
function AnimatedRoutes() {
  const location = useLocation();
  const { user } = useAuth();

  if (user?.type === "vendor") {
    return (
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<PageTransition><VendorDashboard /></PageTransition>} />
          <Route path="/vendor/tenders" element={<PageTransition><VendorBids /></PageTransition>} />
          <Route path="/vendor/profile" element={<PageTransition><VendorProfile /></PageTransition>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AnimatePresence>
    );
  }

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<PageTransition><ProjectsPage /></PageTransition>} />
        <Route path="/dashboard" element={<PageTransition><Dashboard /></PageTransition>} />
        <Route path="/integrations" element={<PageTransition><IntegrationsPage /></PageTransition>} />
        <Route path="/compliance" element={<PageTransition><Compliance /></PageTransition>} />
        <Route path="/design" element={<PageTransition><DesignPage /></PageTransition>} />
        <Route path="/ncr/:ncrId" element={<PageTransition><NCRDetail /></PageTransition>} />
        <Route path="/schedule" element={<PageTransition><Schedule /></PageTransition>} />
        <Route path="/rfi" element={<PageTransition><RFIChat /></PageTransition>} />
        <Route path="/commissioning" element={<PageTransition><CommissioningPage /></PageTransition>} />
        <Route path="/settings" element={<PageTransition><SettingsPage /></PageTransition>} />
        <Route path="/tenders" element={<PageTransition><BidsAndContracts /></PageTransition>} />
        <Route path="/supply-chain" element={<PageTransition><SupplyChainPage /></PageTransition>} />
        <Route path="/documents" element={<PageTransition><DocumentsPage /></PageTransition>} />
        <Route path="/projects/new" element={<PageTransition><NewProject /></PageTransition>} />
        <Route path="/team" element={<PageTransition><TeamPage /></PageTransition>} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </AnimatePresence>
  );
}

// Inner Application (Handles Auth Routing)
function ApplicationCore() {
  const { user } = useAuth();
  const location = useLocation();

  const isPublicPage = (location.pathname === "/" && !user) || location.pathname === "/login" || location.pathname === "/signup";
  const isFullscreen = location.pathname === "/projects/new";

  if (isPublicPage) {
    return (
      <motion.div
        key="public-workspace"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="min-h-screen"
      >
        <Routes>
          <Route path="/" element={<PageTransition><LandingPage /></PageTransition>} />
          <Route path="/login" element={<Navigate to="/projects" replace />} />
          <Route path="/signup" element={<Navigate to="/projects" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </motion.div>
    );
  }

  return (
    <motion.div
      key="workspace"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 1.0, ease: [0.16, 1, 0.3, 1] }}
      className="h-screen w-full overflow-hidden"
    >
      <AppLayout hideSidebar={isFullscreen}>
        <AnimatedRoutes />
      </AppLayout>
    </motion.div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <WorkspaceProvider>
        <BrowserRouter>
          <ApplicationCore />
        </BrowserRouter>
      </WorkspaceProvider>
    </AuthProvider>
  );
}
