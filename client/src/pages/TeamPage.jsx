import { useState } from "react";
import { createPortal } from "react-dom";
import { X, Search, BookOpen, UserPlus, User } from "lucide-react";

export default function TeamPage() {
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState("engineering");

  return (
    <div className="flex flex-col h-screen bg-[#1a1a1a] text-white">
      {/* ─── Main Content ─── */}
      <div className="flex-1 p-10 max-w-6xl mx-auto w-full pt-16">
        <h1 className="text-[22px] font-bold tracking-tight mb-8">Team</h1>

        <div className="flex items-center justify-between mb-4">
          <div className="relative w-64">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8a847b]" />
            <input
              type="text"
              placeholder="Filter members"
              className="w-full bg-[#222222] border border-[#333330] rounded-md py-1.5 pl-9 pr-3 text-sm text-white focus:outline-none focus:border-[#333330] transition-colors"
            />
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-[#333330] text-sm font-medium hover:bg-[#333330] transition-colors">
              <BookOpen size={14} />
              Docs
            </button>
            <button
              onClick={() => setIsInviteOpen(true)}
              className="flex items-center gap-2 bg-[#b08d6e] hover:bg-[#b08d6e]/90 text-white px-3 py-1.5 rounded-md text-sm font-medium transition-colors"
            >
              <UserPlus size={14} />
              Invite members
            </button>
          </div>
        </div>

        {/* Table Area */}
        <div className="border border-[#333330] rounded-lg overflow-hidden bg-[#222222]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[#222222] border-b border-[#333330]">
              <tr>
                <th className="px-6 py-4 font-semibold text-[11px] text-[#8a847b] tracking-widest uppercase">Member</th>
                <th className="px-6 py-4 font-semibold text-[11px] text-[#8a847b] tracking-widest uppercase">MFA</th>
                <th className="px-6 py-4 font-semibold text-[11px] text-[#8a847b] tracking-widest uppercase">Role</th>
                <th className="px-6 py-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#333330]">
              <tr className="hover:bg-[#333330]/30 transition-colors group">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full border border-[#333330] flex items-center justify-center bg-[#1a1a1a]">
                      <User size={14} className="text-[#8a847b]" />
                    </div>
                    <span className="font-medium text-[13px]">wmangesh91@gmail.com</span>
                    <span className="px-1.5 py-0.5 rounded-full border border-[#333330] text-[9px] font-bold text-[#8a847b] bg-[#333330]">YOU</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-1.5 text-[#8a847b] text-[13px]">
                    Disabled <X size={12} className="text-[#8a847b]" />
                  </div>
                </td>
                <td className="px-6 py-4 text-white font-medium text-[13px]">Project Management</td>
                <td className="px-6 py-4 text-right">
                  <button className="px-3 py-1.5 rounded-md border border-[#333330] text-xs font-medium text-[#8a847b] hover:text-white hover:border-[#52525b] transition-colors bg-[#1a1a1a]">
                    Leave team
                  </button>
                </td>
              </tr>
            </tbody>
            <tfoot className="bg-[#222222] border-t border-[#333330]">
              <tr>
                <td colSpan={4} className="px-6 py-3 text-xs text-[#8a847b]">
                  1 member
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {isInviteOpen && createPortal(
        <>
          <div
            className="fixed inset-0"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)', zIndex: 99998 }}
            onClick={() => setIsInviteOpen(false)}
          />
          <div
            className="fixed right-0 top-0 bottom-0 bg-[#222222] border-l border-[#333330] flex flex-col shadow-2xl animate-in slide-in-from-right"
            style={{ width: '600px', zIndex: 99999 }}
          >

            {/* Header */}
            <div className="px-6 pt-5 pb-4 border-b border-[#333330]">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-white mb-0.5">Invite team members</h2>
                  <p className="text-[#8a847b] text-xs">
                    Send invitations and choose the access each new team member receives.
                  </p>
                </div>
                <button 
                  onClick={() => setIsInviteOpen(false)}
                  className="p-1 hover:bg-[#333330] rounded-md transition-colors text-[#8a847b] hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto px-6 py-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">

              {/* SSO Callout */}
              <div className="mb-5">
                <h3 className="text-sm font-semibold text-white mb-0.5">Single Sign-On (SSO) available</h3>
                <p className="text-[#8a847b] text-xs mb-3">
                  Enforce login via your company identity provider for added security and access control. Available on Team plan and above.
                </p>
                <div className="flex items-center gap-3">
                  <button className="flex items-center gap-2 px-3 py-1 rounded-md border border-[#333330] text-xs font-medium hover:bg-[#333330] transition-colors">
                    <BookOpen size={14} />
                    Docs
                  </button>
                  {/* Upgrade button removed as requested */}
                </div>
              </div>

              {/* Roles */}
              <div className="flex flex-col gap-3 mb-5">
                <h3 className="text-sm font-semibold text-white">Role</h3>
                <div className="flex flex-col rounded-lg border border-[#333330] overflow-hidden bg-[#1a1a1a]">

                  {/* Project Management & Leadership Team */}
                  <label className={`flex gap-3 p-3 cursor-pointer transition-colors ${selectedRole === "management" ? "bg-[#333330]/50 border border-[#b08d6e]/50 relative" : "hover:bg-[#222222]"}`}>
                    <div className="pt-0.5">
                      <input
                        type="radio"
                        name="role"
                        value="management"
                        checked={selectedRole === "management"}
                        onChange={() => setSelectedRole("management")}
                        className="accent-[#b08d6e] w-4 h-4"
                      />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-white mb-1">Project Management & Leadership Team</div>
                      <div className="text-xs text-[#8a847b]">
                        Full oversight and approval authority. Manage organization settings, billing, and all project data.
                      </div>
                    </div>
                  </label>

                  <div className="h-px bg-[#333330] w-full" />

                  {/* Engineering & Technical Team */}
                  <label className={`flex gap-3 p-3 cursor-pointer transition-colors ${selectedRole === "engineering" ? "bg-[#333330]/50 border border-[#b08d6e]/50 relative" : "hover:bg-[#222222]"}`}>
                    <div className="pt-0.5">
                      <input
                        type="radio"
                        name="role"
                        value="engineering"
                        checked={selectedRole === "engineering"}
                        onChange={() => setSelectedRole("engineering")}
                        className="accent-[#b08d6e] w-4 h-4"
                      />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-white mb-1">Engineering & Technical Team</div>
                      <div className="text-xs text-[#8a847b]">
                        Manage design models, commissioning checklists, and RFI processes. Cannot delete projects or manage billing.
                      </div>
                    </div>
                  </label>

                  <div className="h-px bg-[#333330] w-full" />

                  {/* Execution & Site Team */}
                  <label className={`flex gap-3 p-3 cursor-pointer transition-colors ${selectedRole === "execution" ? "bg-[#333330]/50 border border-[#b08d6e]/50 relative" : "hover:bg-[#222222]"}`}>
                    <div className="pt-0.5">
                      <input
                        type="radio"
                        name="role"
                        value="execution"
                        checked={selectedRole === "execution"}
                        onChange={() => setSelectedRole("execution")}
                        className="accent-[#b08d6e] w-4 h-4"
                      />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-white mb-1">Execution & Site Team</div>
                      <div className="text-xs text-[#8a847b]">
                        View schedules, submit field reports, and access approved documents. Limited write access.
                      </div>
                    </div>
                  </label>

                </div>
              </div>

              {/* Email Addresses */}
              <div className="flex flex-col gap-3 mb-4">
                <h3 className="text-sm font-semibold text-white">Email addresses</h3>
                <textarea
                  rows={4}
                  placeholder="name@example.com, name2@example.com, ..."
                  className="w-full bg-[#1a1a1a] border border-[#333330] rounded-lg p-3 text-sm text-white focus:outline-none focus:border-[#b08d6e] transition-colors resize-none"
                />
              </div>

            </div>

            {/* Footer */}
            <div className="px-8 py-4 border-t border-[#333330] bg-[#222222] flex items-center justify-end gap-3">
              <button
                onClick={() => setIsInviteOpen(false)}
                className="px-4 py-2 rounded-md border border-[#333330] text-sm font-medium text-white hover:bg-[#333330] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => setIsInviteOpen(false)}
                className="bg-[#b08d6e] hover:bg-[#b08d6e]/90 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
              >
                Send invitation
              </button>
            </div>

          </div>
        </>,
        document.body
      )}
    </div>
  );
}
