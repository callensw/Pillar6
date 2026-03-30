import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { path: "/", label: "Home" },
  { path: "/system", label: "System" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-navy-900">
      {/* Header */}
      <header className="border-b border-navy-700 bg-navy-800">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center font-bold text-sm">
              P6
            </div>
            <span className="text-lg font-semibold text-white">
              Pillar6 Research Assistant
            </span>
          </Link>
          <nav className="flex gap-6">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`text-sm font-medium transition-colors ${
                  location.pathname === item.path
                    ? "text-blue-400"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
