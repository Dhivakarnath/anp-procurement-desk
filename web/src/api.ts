import type {
  BuyerPolicy,
  MarketLedger,
  ProbeResult,
  ProbeTarget,
  RequestLines,
  SessionState,
  SupplierLedger,
} from "./types";

const env = (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env;

export const ENDPOINTS = {
  buyer: env.VITE_BUYER_URL || "http://localhost:8001",
  market: env.VITE_MARKET_URL || "http://localhost:8002",
  s1: env.VITE_S1_URL || "http://localhost:8003",
  s2: env.VITE_S2_URL || "http://localhost:8004",
  s3: env.VITE_S3_URL || "http://localhost:8005",
  probe: env.VITE_PROBE_URL || "http://127.0.0.1:8010",
} as const;

async function req<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch {
    throw new Error(`Could not reach ${base}. Check that docker compose is running.`);
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? body;
    } catch {
      /* keep statusText */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
}

const buyer = <T>(path: string, init?: RequestInit) => req<T>(ENDPOINTS.buyer, path, init);

export function createSession(text: string) {
  return buyer<SessionState>("/sessions", { method: "POST", body: JSON.stringify({ text }) });
}

export function getSession(id: string) {
  return buyer<SessionState>(`/sessions/${id}`);
}

export function confirmLines(id: string, lines: RequestLines, policy: BuyerPolicy) {
  return buyer<SessionState>(`/sessions/${id}/confirm`, {
    method: "POST",
    body: JSON.stringify({ lines, policy }),
  });
}

export function negotiate(id: string, supplierDid: string, lines: RequestLines) {
  return buyer<SessionState>(`/sessions/${id}/negotiate`, {
    method: "POST",
    body: JSON.stringify({ supplier_did: supplierDid, lines }),
  });
}

export function approve(id: string, quoteHash: string, supplierDid: string) {
  return buyer<SessionState>(`/sessions/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ quote_hash: quoteHash, supplier_did: supplierDid }),
  });
}

export function placeOrder(id: string) {
  return buyer<SessionState>(`/sessions/${id}/order`, { method: "POST" });
}

export function marketLedger() {
  return req<MarketLedger>(ENDPOINTS.market, "/market/ledger");
}

export function supplierLedger(role: "s1" | "s2" | "s3") {
  return req<SupplierLedger>(ENDPOINTS[role], "/ledger");
}

export function setRogue(role: "s1" | "s2" | "s3", on: boolean) {
  return req<{ rogue: boolean }>(ENDPOINTS[role], "/demo/rogue", {
    method: "POST",
    body: JSON.stringify({ on }),
  });
}

export function probeLast(target: ProbeTarget) {
  return req<ProbeResult>(ENDPOINTS.probe, `/probe/last?target=${target}`);
}

export function probeRun(target: ProbeTarget) {
  return req<ProbeResult>(ENDPOINTS.probe, "/probe/run", {
    method: "POST",
    body: JSON.stringify({ target }),
  });
}
