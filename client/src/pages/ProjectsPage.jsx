import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Search, Plus, LayoutGrid, List, MoreVertical, Play, Pause, Trash2 } from "lucide-react";
import { useWorkspace } from "../context/WorkspaceContext.jsx";
import api from "../api/client.js";

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

export default function ProjectsPage() {
  const { projects, fetchProjects, setCurrentProject, loadingProjects } = useWorkspace();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("name");
  const [isGridView, setIsGridView] = useState(true);
  const [menuOpen, setMenuOpen] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    fetchProjects();

    const handleClickOutside = () => setMenuOpen(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const handleToggleStatus = async (e, project) => {
    e.stopPropagation();
    const nextStatus = project.status === "paused" ? "active" : "paused";
    try {
      await api.updateProjectStatus(project.id, nextStatus);
      fetchProjects();
    } catch (err) {
      console.error("Failed to update project status:", err);
    }
  };

  const handleDeleteProject = async (e, projectId) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this project? This will permanently delete all associated documents, tasks, NCRs, and purchase orders.")) {
      setMenuOpen(null);
      return;
    }
    setDeletingId(projectId);
    try {
      await api.deleteProject(projectId);
      await fetchProjects();
    } catch (err) {
      console.error("Failed to delete project:", err);
      alert("Failed to delete project.");
    } finally {
      setDeletingId(null);
      setMenuOpen(null);
    }
  };

  const filteredProjects = projects
    .filter((project) => {
      const matchesSearch = project.name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = statusFilter === "all" || project.status === statusFilter;
      return matchesSearch && matchesStatus;
    })
    .sort((a, b) => {
      if (sortBy === "name") {
        return a.name.localeCompare(b.name);
      } else if (sortBy === "newest") {
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
      }
      return 0;
    });

  const handleProjectSelect = (project) => {
    setCurrentProject(project);
    navigate("/dashboard");
  };

  return (
    <div style={{ backgroundColor: C.bg, color: C.ivory, fontFamily: "'Inter', 'Helvetica Neue', sans-serif", position: "relative" }} className="flex flex-col min-h-screen">
      {/* Grain texture */}
      <div style={{ position: "fixed", inset: 0, backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E")`, pointerEvents: "none", zIndex: 1 }} />

      <div className="flex-1 p-10 max-w-6xl mx-auto w-full pt-16 relative z-10">
        <h1 style={{ color: C.ivory }} className="text-[22px] font-bold tracking-tight mb-8">Projects</h1>

      {/* ─── Toolbar: Search, Filters & Views ─── */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between mb-6">
        <div className="flex flex-1 w-full gap-3 items-center flex-wrap sm:flex-nowrap">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: C.dim }} size={15} />
            <input
              type="text"
              placeholder="Search for a project"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ backgroundColor: C.surface, borderColor: C.border, color: C.ivory }}
              className="w-full border rounded-md pl-9 pr-4 py-1.5 text-sm focus:outline-none transition-all placeholder-opacity-50"
            />
          </div>

          {/* Status Selector */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ backgroundColor: C.surface, borderColor: C.border, color: C.muted }}
            className="border rounded-md px-3 py-1.5 text-sm font-medium focus:outline-none cursor-pointer"
          >
            <option value="all">Status</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
          </select>

          {/* Sort Selector */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            style={{ backgroundColor: C.surface, borderColor: C.border, color: C.muted }}
            className="border rounded-md px-3 py-1.5 text-sm font-medium focus:outline-none cursor-pointer"
          >
            <option value="name">Sorted by name</option>
            <option value="newest">Sorted by newest</option>
          </select>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          {/* View toggles */}
          <div style={{ backgroundColor: C.surface, borderColor: C.border }} className="border p-0.5 rounded-md flex items-center shrink-0">
            <button
              onClick={() => setIsGridView(true)}
              style={{ backgroundColor: isGridView ? C.border : "transparent", color: isGridView ? C.ivory : C.dim }}
              className="p-1.5 rounded-[4px] transition-colors hover:text-opacity-80"
            >
              <LayoutGrid size={14} />
            </button>
            <button
              onClick={() => setIsGridView(false)}
              style={{ backgroundColor: !isGridView ? C.border : "transparent", color: !isGridView ? C.ivory : C.dim }}
              className="p-1.5 rounded-[4px] transition-colors hover:text-opacity-80"
            >
              <List size={14} />
            </button>
          </div>

          {/* Create Project Button */}
          <button
            onClick={() => navigate("/projects/new")}
            style={{ backgroundColor: C.bronze, color: "#ffffff" }}
            className="px-4 py-1.5 rounded-md text-[13px] font-semibold transition-colors flex items-center gap-1.5 whitespace-nowrap hover:opacity-90"
          >
            <Plus size={14} className="stroke-[3px]" /> New project
          </button>
        </div>
      </div>

      {/* ─── Project Grid ─── */}
      {loadingProjects ? (
        <div className="flex flex-col items-center justify-center py-20" style={{ color: C.dim }}>
          <div style={{ borderTopColor: "transparent", borderColor: C.bronze }} className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filteredProjects.length === 0 ? (
        <div style={{ borderColor: C.border }} className="border rounded-xl p-12 text-center">
          <p style={{ color: C.dim }} className="text-sm">No projects found.</p>
        </div>
      ) : isGridView ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredProjects.map((project, idx) => (
            <motion.div
              key={project.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * idx }}
              onClick={() => handleProjectSelect(project)}
              style={{ backgroundColor: C.surface, borderColor: C.border }}
              className="border rounded-xl p-5 transition-colors cursor-pointer flex flex-col justify-between h-[160px] group hover:border-[#c9a052]"
            >
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <h3 style={{ color: C.ivory }} className="font-semibold text-base leading-tight">
                    {project.name}
                  </h3>
                  <div style={{ color: C.dim }} className="text-[13px] font-mono">
                    {project.location || "AWS | ap-southeast-1"}
                  </div>
                </div>
                
                <div className="relative">
                  <button
                    onClick={(e) => { 
                      e.stopPropagation(); 
                      setMenuOpen(menuOpen === project.id ? null : project.id);
                    }}
                    style={{ color: C.dim }}
                    className="p-1 rounded-md transition-colors hover:text-white"
                  >
                    <MoreVertical size={16} />
                  </button>
                  
                  {menuOpen === project.id && (
                    <div 
                      style={{ backgroundColor: C.surface, borderColor: C.border }}
                      className="absolute right-0 top-full mt-1 w-40 rounded-lg border shadow-xl z-50 overflow-hidden"
                    >
                      <button
                        onClick={(e) => handleDeleteProject(e, project.id)}
                        disabled={deletingId === project.id}
                        className="w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                      >
                        <Trash2 size={14} />
                        {deletingId === project.id ? "Deleting..." : "Delete Project"}
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-3">
                 <span style={{ color: C.muted, backgroundColor: C.border }} className="inline-flex items-center text-[10px] font-bold rounded px-1.5 py-0.5 uppercase tracking-wider">
                    {project.size_mw ? `${project.size_mw} MW` : "NANO"}
                 </span>
              </div>

              <div style={{ borderColor: C.border }} className="flex items-center justify-between mt-auto pt-4 border-t">
                <div 
                  onClick={(e) => handleToggleStatus(e, project)}
                  style={{ color: C.dim }}
                  className="flex items-center gap-2 group/status hover:text-white transition-colors"
                >
                  <div style={{ 
                      borderColor: project.status === "paused" ? C.border : C.bronze,
                      backgroundColor: project.status === "paused" ? "transparent" : C.bronze,
                      color: project.status === "paused" ? C.dim : C.bg 
                    }} className="w-4 h-4 rounded-full flex items-center justify-center border transition-colors">
                    {project.status === "paused" ? <Pause size={8} className="fill-current" /> : <Play size={8} className="fill-current" />}
                  </div>
                  <span className="text-[13px]">
                    Project is {project.status || "paused"}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      ) : (
        <div style={{ borderColor: C.border }} className="border rounded-xl overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr style={{ backgroundColor: C.surface, borderColor: C.border, color: C.dim }} className="border-b text-[13px]">
                <th className="px-6 py-3 font-normal">Project Name</th>
                <th className="px-6 py-3 font-normal">Region</th>
                <th className="px-6 py-3 font-normal">Status</th>
                <th className="px-6 py-3 font-normal"></th>
              </tr>
            </thead>
            <tbody style={{ borderColor: C.border }} className="divide-y">
              {filteredProjects.map((project) => (
                <tr
                  key={project.id}
                  onClick={() => handleProjectSelect(project)}
                  style={{ transition: "background-color 0.2s" }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = `${C.border}88`}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
                  className="cursor-pointer group"
                >
                  <td className="px-6 py-4">
                    <span style={{ color: C.ivory }} className="font-semibold">
                      {project.name}
                    </span>
                  </td>
                  <td style={{ color: C.dim }} className="px-6 py-4 text-[13px] font-mono">
                    {project.location || "AWS | ap-southeast-1"}
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={(e) => handleToggleStatus(e, project)}
                      style={{ color: C.dim }}
                      className="inline-flex items-center gap-2 text-[13px] hover:text-white"
                    >
                      <div style={{ 
                          borderColor: project.status === "paused" ? C.border : C.bronze,
                          backgroundColor: project.status === "paused" ? "transparent" : C.bronze,
                          color: project.status === "paused" ? C.dim : C.bg 
                        }} className="w-4 h-4 rounded-full flex items-center justify-center border">
                         {project.status === "paused" ? <Pause size={8} className="fill-current" /> : <Play size={8} className="fill-current" />}
                      </div>
                      Project is {project.status || "paused"}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="relative inline-block text-left">
                      <button
                        onClick={(e) => { 
                          e.stopPropagation(); 
                          setMenuOpen(menuOpen === project.id ? null : project.id);
                        }}
                        style={{ color: C.dim }}
                        className="p-1.5 rounded-md hover:bg-[#333330] transition-colors"
                      >
                        <MoreVertical size={16} />
                      </button>
                      
                      {menuOpen === project.id && (
                        <div 
                          style={{ backgroundColor: C.surface, borderColor: C.border }}
                          className="absolute right-0 top-full mt-1 w-40 rounded-lg border shadow-xl z-50 overflow-hidden"
                        >
                          <button
                            onClick={(e) => handleDeleteProject(e, project.id)}
                            disabled={deletingId === project.id}
                            className="w-full text-left px-4 py-2 text-sm flex items-center gap-2 text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                          >
                            <Trash2 size={14} />
                            {deletingId === project.id ? "Deleting..." : "Delete Project"}
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </div>
    </div>
  );
}
