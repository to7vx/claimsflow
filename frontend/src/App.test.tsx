import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, beforeEach, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  // Stub fetch — the dashboard hits /api/v1 on render.
  global.fetch = vi.fn().mockImplementation((url: string) => {
    const body = url.includes("overview")
      ? {
          period: "week",
          total_claims: 42,
          auto_adjudication_rate: 0.84,
          avg_decision_seconds: 2.1,
          pending_exceptions: 6,
          fraud_holds: 1,
          total_paid_sar: 123_456,
        }
      : url.includes("decisions")
        ? []
        : url.includes("quality")
          ? { override_rate: 0.04, median_confidence: 0.91, low_confidence_count: 3 }
          : [];
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(body),
    } as Response);
  });
});

function renderApp(initialPath = "/") {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App shell", () => {
  it("renders header with the operations branding", () => {
    renderApp();
    expect(
      screen.getByRole("heading", { level: 1, name: /Operations overview/i }),
    ).toBeInTheDocument();
    // Both header banner ("ClaimsFlow · operations") and footer mention the name.
    expect(screen.getAllByText(/ClaimsFlow/).length).toBeGreaterThan(0);
  });

  it("renders the exception queue page", () => {
    renderApp("/queue/exceptions");
    expect(
      screen.getByRole("heading", { name: /Exception queue/i }),
    ).toBeInTheDocument();
  });

  it("renders the insights page", () => {
    renderApp("/insights");
    expect(
      screen.getByRole("heading", { name: /Provider insights/i }),
    ).toBeInTheDocument();
  });
});
