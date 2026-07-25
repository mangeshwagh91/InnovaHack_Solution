import { createContext, useContext, useState, useEffect } from "react";
import api from "../api/client";

const WorkspaceContext = createContext();

export function WorkspaceProvider({ children }) {
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [unreadNotifications, setUnreadNotifications] = useState(3);
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(() => {
    const saved = localStorage.getItem("dcpi_current_project");
    return saved ? JSON.parse(saved) : null;
  });
  const [loadingProjects, setLoadingProjects] = useState(false);

  useEffect(() => {
    if (currentProject) {
      localStorage.setItem("dcpi_current_project", JSON.stringify(currentProject));
    }
  }, [currentProject]);

  useEffect(() => {
    fetchProjects();
  }, []);

  const toggleNotifications = () => {
    setIsNotificationsOpen(prev => !prev);
    if (!isNotificationsOpen) {
      setUnreadNotifications(0);
    }
  };

  const fetchProjects = async () => {
    setLoadingProjects(true);
    try {
      const data = await api.getProjects();
      setProjects(data);
      if (data.length > 0 && !currentProject) {
        // Set first project as default if none selected
        setCurrentProject(data[0]);
      }
    } catch (err) {
      console.error("Error fetching projects:", err);
    } finally {
      setLoadingProjects(false);
    }
  };

  return (
    <WorkspaceContext.Provider value={{ 
      isNotificationsOpen, 
      toggleNotifications,
      unreadNotifications,
      setUnreadNotifications,
      projects,
      setProjects,
      currentProject,
      setCurrentProject,
      fetchProjects,
      loadingProjects
    }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export const useWorkspace = () => useContext(WorkspaceContext);
