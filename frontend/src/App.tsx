import { Routes, Route, NavLink } from "react-router-dom";
import Overview from "@/pages/Overview";
import ExceptionQueue from "@/pages/ExceptionQueue";
import FraudQueue from "@/pages/FraudQueue";
import Quality from "@/pages/Quality";
import Insights from "@/pages/Insights";
import ClaimDetail from "@/pages/ClaimDetail";

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border-subtle bg-bg-secondary sticky top-0 z-20">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              aria-hidden
              className="h-2.5 w-2.5 rounded-full bg-accent animate-pulse-live"
            />
            <h1 className="font-mono text-sm tracking-wide uppercase">
              ClaimsFlow <span className="text-fg-muted">· operations</span>
            </h1>
          </div>
          <nav className="flex gap-5 text-sm text-fg-secondary">
            {[
              ["Overview", "/"],
              ["Exceptions", "/queue/exceptions"],
              ["Fraud", "/queue/fraud"],
              ["Quality", "/quality"],
              ["Insights", "/insights"],
            ].map(([label, to]) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `transition-colors hover:text-fg-primary ${isActive ? "text-fg-primary" : ""}`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1 mx-auto max-w-7xl w-full px-6 py-8">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/queue/exceptions" element={<ExceptionQueue />} />
          <Route path="/queue/fraud" element={<FraudQueue />} />
          <Route path="/claims/:id" element={<ClaimDetail />} />
          <Route path="/quality" element={<Quality />} />
          <Route path="/insights" element={<Insights />} />
        </Routes>
      </main>

      <footer className="border-t border-border-subtle py-4 mt-12">
        <div className="mx-auto max-w-7xl px-6 text-xs text-fg-muted font-mono">
          ClaimsFlow PoC · synthetic data · not for production use
        </div>
      </footer>
    </div>
  );
}
