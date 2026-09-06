import { useState } from "react";
import {
  LayoutDashboard,
  FileText,
  ClipboardList,
  LogOut,
  Menu,
  Activity } from "lucide-react";

type Page = "dashboard" | "logs" | "review";

interface LayoutProps {
  active: Page;
  onNavigate: (page: Page) => void;
  onLogout: () => void;
  children: React.ReactNode;
}

const navItems: { key: Page; label: string; icon: React.ElementType }[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "logs", label: "Parsed Logs", icon: FileText },
  { key: "review", label: "Review Queue", icon: ClipboardList },
];

export default function Layout({ active, onNavigate, onLogout, children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={[
          "fixed inset-y-0 left-0 z-50 w-64 border-r border-neutral-200 bg-white flex flex-col transition-transform md:translate-x-0 md:static",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
      >
        <div className="flex items-center gap-2 border-b border-neutral-200 px-5 py-4">
          <div className="rounded-lg bg-orange-500 p-1.5">
            <Activity className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight">Universal Log</span>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => {
            const isActive = active === item.key;
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                onClick={() => {
                  onNavigate(item.key);
                  setSidebarOpen(false);
                }}
                className={[
                  "w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-neutral-900 text-white"
                    : "text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900",
                ].join(" ")}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-neutral-200 p-3">
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-4 py-3 md:px-6">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-2 text-neutral-600 hover:bg-neutral-100 md:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span className="text-xs text-neutral-500 font-medium">Connected</span>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
