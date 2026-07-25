import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Upload, X, Building2, MapPin, Calendar, DollarSign, Users, Shield, Zap } from "lucide-react";
import ComplianceBackground from "../components/compliance/ComplianceBackground.jsx";
import api from "../api/client.js";

export default function NewProject() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [imagePreview, setImagePreview] = useState(null);
  
  const [formData, setFormData] = useState({
    name: "",
    capacity: "",
    capacityUnit: "MW",
    goLiveDate: "",
    totalBudget: "",
    equipmentBudget: "",
    location: "",
    tier: "Tier III",
    description: "",
    pm: ""
  });

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result);
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.createProject({
        name: formData.name,
        size_mw: parseFloat(formData.capacity) || 0.0,
        deadline: formData.goLiveDate,
        budget: parseFloat(formData.totalBudget) || 0.0,
        location: formData.location || "",
        capacity_unit: formData.capacityUnit,
        equipment_budget: parseFloat(formData.equipmentBudget) || 0.0,
        tier: formData.tier,
        description: formData.description || "",
        pm: formData.pm || ""
      });
      navigate("/projects");
    } catch (err) {
      alert("Failed to initialize project: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative pb-24 text-slate-800">
      <ComplianceBackground />
      
      <div className="max-w-4xl mx-auto pt-8 relative z-10 px-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Create New Project</h1>
          <p className="text-slate-500 mt-2">Initialize a new Data Centre project and orchestrate your AI agents.</p>
        </motion.div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-8">
          
          {/* Image Upload Area */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ delay: 0.1 }}
            className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm"
          >
            <h2 className="text-lg font-bold text-slate-800 mb-4">Project Image</h2>
            <div className="relative border-2 border-dashed border-slate-300 hover:border-[#b08d6e]/50 rounded-2xl bg-slate-50/50 transition-colors group h-48 overflow-hidden flex flex-col items-center justify-center">
              {imagePreview ? (
                <>
                  <img src={imagePreview} alt="Preview" className="absolute inset-0 w-full h-full object-cover opacity-80" />
                  <button 
                    type="button"
                    onClick={(e) => { e.preventDefault(); setImagePreview(null); }}
                    className="absolute top-4 right-4 p-2 bg-slate-900/85 hover:bg-red-500 text-white rounded-full transition-colors z-10"
                  >
                    <X size={16} />
                  </button>
                </>
              ) : (
                <div className="flex flex-col items-center pointer-events-none">
                  <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                    <Upload size={20} className="text-[#b08d6e]" />
                  </div>
                  <span className="text-sm font-semibold text-slate-650">Upload Data Centre Rendering</span>
                  <span className="text-xs text-slate-400 mt-1">PNG, JPG up to 10MB</span>
                </div>
              )}
              <input 
                type="file" 
                accept="image/*" 
                onChange={handleImageChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
            </div>
          </motion.div>

          {/* Core Details */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ delay: 0.2 }}
            className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm"
          >
            <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
              <Building2 size={18} className="text-blue-500" />
              Core Project Details
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="md:col-span-2">
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Project Name <span className="text-red-500">*</span></label>
                <input 
                  required
                  type="text" 
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  placeholder="e.g. London Hyperscale Phase 2"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-[#b08d6e]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Capacity <span className="text-red-500">*</span></label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Zap size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input 
                      required
                      type="number" 
                      value={formData.capacity}
                      onChange={(e) => setFormData({...formData, capacity: e.target.value})}
                      placeholder="Capacity"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-[#b08d6e]"
                    />
                  </div>
                  <select 
                    value={formData.capacityUnit}
                    onChange={(e) => setFormData({...formData, capacityUnit: e.target.value})}
                    className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-850 focus:outline-none focus:border-[#b08d6e] w-24"
                  >
                    <option value="MW">MW</option>
                    <option value="kW">kW</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Target Go-Live Date <span className="text-red-500">*</span></label>
                <div className="relative">
                  <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input 
                    required
                    type="date" 
                    value={formData.goLiveDate}
                    onChange={(e) => setFormData({...formData, goLiveDate: e.target.value})}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-[#b08d6e] [color-scheme:light]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Total Project Budget <span className="text-red-500">*</span></label>
                <div className="relative">
                  <DollarSign size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input 
                    required
                    type="number" 
                    value={formData.totalBudget}
                    onChange={(e) => setFormData({...formData, totalBudget: e.target.value})}
                    placeholder="Total Budget"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-[#b08d6e]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Equipment Budget <span className="text-red-500">*</span></label>
                <div className="relative">
                  <DollarSign size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input 
                    required
                    type="number" 
                    value={formData.equipmentBudget}
                    onChange={(e) => setFormData({...formData, equipmentBudget: e.target.value})}
                    placeholder="Equipment Budget"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-[#b08d6e]"
                  />
                </div>
              </div>
            </div>
          </motion.div>

          {/* Optional Details */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ delay: 0.3 }}
            className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm"
          >
            <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
              <Shield size={18} className="text-indigo-500" />
              Additional Settings
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Project Location</label>
                <div className="relative">
                  <MapPin size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input 
                    type="text" 
                    value={formData.location}
                    onChange={(e) => setFormData({...formData, location: e.target.value})}
                    placeholder="City, Country"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-[#b08d6e]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Tier Certification Target</label>
                <select 
                  value={formData.tier}
                  onChange={(e) => setFormData({...formData, tier: e.target.value})}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-850 focus:outline-none focus:border-[#b08d6e]"
                >
                  <option value="Tier I">Tier I</option>
                  <option value="Tier II">Tier II</option>
                  <option value="Tier III">Tier III</option>
                  <option value="Tier IV">Tier IV</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Assigned PM</label>
                <div className="relative">
                  <Users size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input 
                    type="text" 
                    value={formData.pm}
                    onChange={(e) => setFormData({...formData, pm: e.target.value})}
                    placeholder="Project Manager Name"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-[#b08d6e]"
                  />
                </div>
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wider">Description</label>
                <textarea 
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  placeholder="Brief scope of the project..."
                  rows={4}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-[#b08d6e] resize-none"
                />
              </div>
            </div>
          </motion.div>

          <div className="flex justify-end gap-4">
            <button 
              type="button"
              onClick={() => navigate("/")}
              className="px-6 py-3 rounded-xl font-bold text-slate-500 hover:text-slate-800 bg-slate-100 border border-slate-200 hover:bg-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button 
              type="submit"
              disabled={loading}
              className="px-8 py-3 rounded-xl font-bold text-white bg-[#b08d6e] hover:bg-[#8c6f55] transition-colors flex items-center gap-2 shadow-sm"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                "Initialize Project"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
