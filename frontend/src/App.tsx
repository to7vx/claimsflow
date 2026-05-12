import { Routes, Route, NavLink } from "react-router-dom";

/**
 * Top-level shell. Real pages land in Module 7.
 * The scaffold renders a placeholder so `npm run dev` works immediately
 * after `npm install` — a recruiter cloning the repo on Module 1 still sees
 * something coherent.
 */
export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border-subtle bg-bg-secondary">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              aria-hidden
              className="h-2.5 w-2.5 rounded-full bg-accent animate-pulse-live"
            />
            <h1 className="font-mono text-sm tracking-wide uppercase">
              ClaimsFlow <span className="text-fg-muted">/ scaffold</span>
            </h1>
          </div>
          <nav className="flex gap-4 text-sm text-fg-secondary">
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

      <main className="flex-1 mx-auto max-w-7xl w-full px-6 py-12">
        <Routes>
          <Route path="/" element={<Placeholder title="Overview" />} />
          <Route path="/queue/exceptions" element={<Placeholder title="Exception Queue" />} />
          <Route path="/queue/fraud" element={<Placeholder title="Fraud Hold Queue" />} />
          <Route path="/quality" element={<Placeholder title="AI Quality" />} />
          <Route path="/insights" element={<Placeholder title="Insights" />} />
        </Routes>
      </main>
    </div>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <section className="panel p-10">
      <p className="font-mono text-xs uppercase tracking-wider text-fg-muted">Module 7 placeholder</p>
      <h2 className="mt-3 text-3xl font-semibold">{title}</h2>
      <p className="mt-4 max-w-xl text-fg-secondary">
        This view ships in Module 7. The scaffold proves the build pipeline,
        routing, design tokens, and TanStack Query are wired up correctly.
      </p>
    </section>
  );
}
