import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import {
  House, Users, Camera, ClipboardText, SignOut, GraduationCap, ChartBar, UserCircle, Lock
} from "@phosphor-icons/react";

const adminLinks = [
  { to: "/dashboard", label: "Dashboard", icon: House, tid: "sidebar-dashboard" },
  { to: "/students", label: "Students", icon: Users, tid: "sidebar-students" },
  { to: "/scan", label: "Face Scan", icon: Camera, tid: "sidebar-scan" },
  { to: "/attendance", label: "Attendance", icon: ClipboardText, tid: "sidebar-attendance" },
  { to: "/settings/password", label: "Change Password", icon: Lock, tid: "sidebar-password" },
];
const studentLinks = [
  { to: "/my", label: "My Dashboard", icon: ChartBar, tid: "sidebar-my-dashboard" },
  { to: "/my/scan", label: "Mark Attendance", icon: Camera, tid: "sidebar-my-scan" },
  { to: "/my/attendance", label: "My Attendance", icon: ClipboardText, tid: "sidebar-my-attendance" },
  { to: "/my/settings/password", label: "Change Password", icon: Lock, tid: "sidebar-my-password" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const links = user?.role === "admin" ? adminLinks : studentLinks;
  const nav = useNavigate();

  return (
    <div className="min-h-screen bg-white flex">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-[var(--sa-border)] bg-[var(--sa-surface)] flex flex-col">
        <div className="px-6 py-6 border-b border-[var(--sa-border)]">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 bg-[var(--sa-primary)] flex items-center justify-center">
              <GraduationCap size={22} color="#fff" weight="bold" />
            </div>
            <div>
              <div className="font-heading font-extrabold text-[15px] leading-tight">SMART</div>
              <div className="font-mono-tech text-[10px] tracking-widest text-[var(--sa-muted)]">ATTENDANCE.AI</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-4">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              data-testid={l.tid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-6 py-3 text-sm text-[var(--sa-text)] hover:bg-white transition-all duration-200 ${
                  isActive ? "sa-nav-active" : "border-l-[3px] border-transparent"
                }`
              }
            >
              <l.icon size={18} weight="bold" />
              <span>{l.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-[var(--sa-border)] p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full bg-[var(--sa-primary)] text-white flex items-center justify-center font-heading font-bold">
              {user?.name?.[0] || "U"}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">{user?.name}</div>
              <div className="text-[10px] font-mono-tech uppercase tracking-wider text-[var(--sa-muted)]">{user?.role}</div>
            </div>
          </div>
          <button
            data-testid="logout-button"
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-[var(--sa-border)] hover:bg-white text-sm rounded-md transition-all"
          >
            <SignOut size={16} weight="bold" /> Logout
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0">
        <header className="h-16 border-b border-[var(--sa-border)] px-8 flex items-center justify-between bg-white">
          <div className="font-mono-tech text-[11px] tracking-[0.2em] uppercase text-[var(--sa-muted)]">
            AI SMART ATTENDANCE SYSTEM // FACE RECOGNITION
          </div>
          <div className="flex items-center gap-2 text-xs font-mono-tech text-[var(--sa-muted)]">
            <UserCircle size={16} /> {user?.email}
          </div>
        </header>
        <div className="p-6 md:p-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
