import { useState } from "react";
import { motion } from "framer-motion";
import { User, Shield, Briefcase, Mail, Building, Plus, Trash2 } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

export default function VendorProfile() {
  const { user } = useAuth();
  
  // Local profile states
  const [phone, setPhone] = useState("+1 (555) 019-2831");
  const [address, setAddress] = useState("100 Tech Way, Suite 400, Silicon Valley, CA");
  const [equipmentTypes, setEquipmentTypes] = useState(["UPS Systems", "Medium Voltage Switchgear", "Data Centre Chillers"]);
  const [newType, setNewType] = useState("");

  const handleAddEquipment = (e) => {
    e.preventDefault();
    if (newType.trim() && !equipmentTypes.includes(newType.trim())) {
      setEquipmentTypes([...equipmentTypes, newType.trim()]);
      setNewType("");
    }
  };

  const handleRemoveEquipment = (index) => {
    setEquipmentTypes(equipmentTypes.filter((_, i) => i !== index));
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 text-slate-800 min-h-screen">
      {/* Header */}
      <div className="mb-8 border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-extrabold tracking-tight flex items-center gap-3 text-slate-900">
          <Building className="text-[#b08d6e]" />
          Company Profile
        </h1>
        <p className="text-slate-500 text-sm mt-1">Configure company credentials, specifications, and catalog classifications.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {/* Left Card: Summary */}
        <div className="bg-white border border-slate-200 p-6 rounded-3xl text-center space-y-4 h-fit shadow-sm">
          <div className="w-20 h-20 bg-gradient-to-br from-[#b08d6e] to-blue-600 rounded-2xl flex items-center justify-center mx-auto shadow-md shadow-emerald-500/10">
            <span className="text-white font-extrabold text-2xl">
              {(user?.name || "V").charAt(0).toUpperCase()}
            </span>
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-850 truncate">{user?.name || "Vendor Corp"}</h2>
            <p className="text-xs text-slate-400 mt-1 uppercase font-semibold tracking-wider">Verified Manufacturer</p>
          </div>
          <div className="flex items-center justify-center gap-1.5 bg-slate-50 p-2 rounded-xl border border-slate-200 text-[10px] text-[#8c6f55] font-bold">
            <Shield size={12} />
            Tier IV Compliant
          </div>
        </div>

        {/* Right Info: Editing */}
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white border border-slate-200 p-6 md:p-8 rounded-3xl space-y-6 shadow-sm">
            <h3 className="text-base font-bold text-slate-850 border-b border-slate-200 pb-3 flex items-center gap-2">
              <User size={16} className="text-[#b08d6e]" />
              Corporate Identity
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Company Email</label>
                <div className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-xs text-slate-700 flex items-center gap-2">
                  <Mail size={12} className="text-slate-450" />
                  {user?.email || "vendor@company.com"}
                </div>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Contact Phone</label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-xs text-slate-800 focus:outline-none focus:border-[#b08d6e] transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Headquarters Address</label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-xs text-slate-800 focus:outline-none focus:border-[#b08d6e] transition-colors"
              />
            </div>
          </div>

          {/* Equipment Classifications */}
          <div className="bg-white border border-slate-200 p-6 md:p-8 rounded-3xl space-y-6 shadow-sm">
            <h3 className="text-base font-bold text-slate-850 border-b border-slate-200 pb-3 flex items-center gap-2">
              <Briefcase size={16} className="text-[#b08d6e]" />
              Equipment Classifications
            </h3>

            <form onSubmit={handleAddEquipment} className="flex gap-3">
              <input
                type="text"
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                placeholder="e.g. In-Row Cooling Units"
                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-xs text-slate-850 focus:outline-none focus:border-[#b08d6e] transition-colors placeholder-slate-400"
              />
              <button
                type="submit"
                className="bg-[#b08d6e] hover:bg-[#8c6f55] text-white font-bold px-4 rounded-xl text-xs flex items-center gap-1 transition-colors shadow-sm"
              >
                <Plus size={14} /> Add
              </button>
            </form>

            <div className="space-y-2">
              {equipmentTypes.map((type, idx) => (
                <div
                  key={type}
                  className="flex items-center justify-between bg-slate-50 border border-slate-200 p-3 rounded-xl hover:border-slate-300 transition-colors"
                >
                  <span className="text-xs text-slate-750 font-semibold">{type}</span>
                  <button
                    onClick={() => handleRemoveEquipment(idx)}
                    className="p-1.5 hover:bg-red-50 text-slate-500 hover:text-red-600 rounded-lg transition-colors border border-slate-200 hover:border-red-200"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
