import type { GuardFlag, PartyId, RankedQuote, Reply, RequestLines, SessionState, Thread } from "./types";

export const PARTIES: Record<PartyId, { name: string; short: string; role: string }> = {
  buyer: { name: "Buyer", short: "BY", role: "Procurement agent" },
  market: { name: "Marketplace", short: "MK", role: "Catalog search" },
  s1: { name: "S1", short: "S1", role: "Contract supplier" },
  s2: { name: "S2", short: "S2", role: "Factory, can expedite" },
  s3: { name: "S3", short: "S3", role: "Seal specialist" },
};

export const PARTY_ORDER: PartyId[] = ["buyer", "market", "s1", "s2", "s3"];
export const SUPPLIERS = ["s1", "s2", "s3"] as const;
export type SupplierId = (typeof SUPPLIERS)[number];

export function supplierId(didOrName: string): SupplierId | null {
  const m = didOrName.toLowerCase().match(/s[123]/);
  return m ? (m[0] as SupplierId) : null;
}

export function esc(s: unknown): string {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export const money = (n: number) =>
  `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export const qty = (n: number) => n.toLocaleString("en-US");
export const seqLabel = (n: number) => String(n).padStart(3, "0");
export const shortHash = (h: string | null | undefined) =>
  h ? `${h.slice(0, 15)}…${h.slice(-6)}` : "—";

export function clock(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function describeLines(l: RequestLines): string {
  return `${qty(l.quantity)} × ${l.part}`;
}

export function attrText(attrs: Record<string, string>): string {
  const pairs = Object.entries(attrs).filter(([, v]) => v);
  return pairs.length ? pairs.map(([k, v]) => `${k}: ${v}`).join(", ") : "none";
}

export type Tone = "plain" | "lead" | "warn" | "bad";

export type Message = {
  seq: number;
  at: string;
  from: PartyId;
  to: PartyId | null;
  title: string;
  detail: string;
  tone: Tone;
  verified?: boolean;
  requestId?: string;
  orderId?: string;
  gate?: boolean;
  flagged?: boolean;
};

type Draft = Omit<Message, "seq">;

export function replyTime(r: Reply): string {
  return r.check?.reply_timestamp || r.at;
}

export function replyTitle(r: Reply): { title: string; detail: string; tone: Tone } {
  const p = r.payload;
  if (!r.signature_verified || !p) {
    return { title: "Reply rejected", detail: r.check?.signature || "signature or transport failed", tone: "bad" };
  }
  if (p.kind === "quote" && p.round) {
    const prev = p.previous_unit_price;
    const moved = prev != null && (p.unit_price ?? 0) < prev;
    return moved
      ? {
          title: `Down to ${money(p.unit_price ?? 0)}`,
          detail: `from ${money(prev)}${p.final_offer ? " · best and final" : ""}`,
          tone: "plain",
        }
      : { title: `Holds at ${money(p.unit_price ?? 0)}`, detail: "best and final", tone: "plain" };
  }
  if (p.kind === "quote") {
    const expedited = p.delivery === "expedited";
    return {
      title: `Quote ${money(p.unit_price ?? 0)}`,
      detail: expedited
        ? `expedited in ${p.lead_time_days} days, +${money(p.expedite_premium ?? 0)} per unit`
        : `${p.price_basis} price · ships in ${p.lead_time_days} days`,
      tone: "plain",
    };
  }
  if (p.kind === "refusal") {
    return {
      title: "Can't meet date",
      detail: `needs ${p.lead_time_days} days, need-by is ${p.need_by_days}`,
      tone: "bad",
    };
  }
  return { title: "Question", detail: `needs ${p.missing_attribute} before pricing`, tone: "warn" };
}

export function buildMessages(s: SessionState | null): Message[] {
  if (!s) return [];
  const out: Draft[] = [];
  const ev = s.events;
  const first = ev[0];
  if (first && s.lines) {
    out.push({
      at: first.at,
      from: "buyer",
      to: null,
      title: "Request read",
      detail: s.extract_unavailable ? "by the fallback parser (Bedrock unavailable)" : "by Claude Haiku",
      tone: "plain",
    });
  }
  const confirmed = ev.find((e) => e.sentence.startsWith("You confirmed"));
  if (confirmed && s.lines) {
    out.push({
      at: confirmed.at,
      from: "buyer",
      to: null,
      title: "Request confirmed",
      detail: describeLines(s.lines),
      tone: "plain",
      gate: true,
    });
    out.push({
      at: confirmed.at,
      from: "buyer",
      to: "market",
      title: "Catalog search",
      detail: `“${s.lines.part}”`,
      tone: "plain",
    });
  }
  const market = ev.find((e) => e.mark === "market");
  if (market) {
    const names = s.market_hits.map((h) => h.name).join(", ");
    out.push({
      at: market.at,
      from: "market",
      to: "buyer",
      title: s.market_hits.length ? `${s.market_hits.length} matches` : "No catalog match",
      detail: s.market_hits.length ? names : "no supplier lists this part",
      tone: s.market_hits.length ? "plain" : "bad",
    });
  }

  for (const thread of Object.values(s.threads)) {
    const sid = supplierId(thread.supplier_did);
    if (!sid) continue;
    for (const r of thread.replies) {
      const req = r.request;
      const c = req?.counter;
      let title = "Quote request";
      let detail = req ? `${qty(req.lines.quantity)} units · ${req.lines.need_by_days} days` : "";
      if (c) {
        title = `Counter, round ${c.round}`;
        detail = `asks ${money(c.target_unit_price)}${c.rival_unit_price != null ? ` · rival offer ${money(c.rival_unit_price)}` : ""}`;
      } else if (req?.negotiation) {
        title = "Answer sent";
        detail = attrText(req.lines.attributes);
      }
      out.push({ at: req?.timestamp || r.at, from: "buyer", to: sid, title, detail, tone: "plain", requestId: req?.request_id });
      const t = replyTitle(r);
      const flagged = Boolean(r.guard?.length);
      out.push({
        at: replyTime(r),
        from: sid,
        to: "buyer",
        ...t,
        detail: flagged ? `${t.detail} · injected text flagged` : t.detail,
        tone: flagged ? "bad" : t.tone,
        verified: r.signature_verified,
        requestId: req?.request_id,
        flagged,
      });
    }
  }

  const lastRank = [...ev].reverse().find((e) => e.detail && "eligible" in e.detail);
  const guarded = new Set<string>();
  for (const e of ev) {
    if (e.detail && "spec_answer" in e.detail) {
      const pair = Object.entries(e.detail.spec_answer as Record<string, string>)[0];
      out.push({ at: e.at, from: "buyer", to: null, title: "Spec sheet answer", detail: pair ? `${pair[0]}: ${pair[1]}` : "", tone: "plain" });
    }
    if (e.detail && "round" in e.detail && "target" in e.detail) {
      out.push({
        at: e.at,
        from: "buyer",
        to: null,
        title: `Round ${e.detail.round}`,
        detail: `counter at ${money(Number(e.detail.target))}`,
        tone: "plain",
      });
    }
    if (e.detail && "guard" in e.detail) {
      const did = String(e.detail.supplier_did ?? "");
      if (!guarded.has(did)) {
        guarded.add(did);
        const flags = e.detail.guard as GuardFlag[];
        out.push({
          at: e.at,
          from: "buyer",
          to: null,
          title: "Injected text ignored",
          detail: flags.some((f) => f.kind === "instruction")
            ? `${supplierId(did)?.toUpperCase() ?? "Supplier"}: ${flags.length} flags, quarantined`
            : `${supplierId(did)?.toUpperCase() ?? "Supplier"}: ${flags.length} flag${flags.length > 1 ? "s" : ""}, ranking unchanged`,
          tone: "bad",
          flagged: true,
        });
      }
    }
    if (e === lastRank && e.detail) {
      const winner = e.detail.winner as string | null;
      const waiting =
        !winner && Object.values(s.threads).some((t) => t.replies.some((r) => r.kind === "question"));
      out.push({
        at: e.at,
        from: "buyer",
        to: null,
        title: winner ? `Ranked: ${winner} leads` : waiting ? "Ranked: waiting on answers" : "Ranked: no eligible quote",
        detail: `${e.detail.eligible} eligible`,
        tone: winner ? "lead" : waiting ? "warn" : "bad",
      });
    }
    if (e.sentence.startsWith("You approved")) {
      out.push({
        at: e.at,
        from: "buyer",
        to: null,
        title: "Quote approved",
        detail: shortHash(e.detail.quote_hash as string),
        tone: "lead",
        gate: true,
      });
    }
  }

  if (s.order && s.approved_supplier) {
    const sid = supplierId(s.approved_supplier);
    const orderEvent = ev.find((e) => e.detail && e.detail.order_id === s.order?.order_id);
    if (sid && orderEvent) {
      out.push({
        at: orderEvent.at,
        from: "buyer",
        to: sid,
        title: "Signed order",
        detail: shortHash(s.approved_hash),
        tone: "plain",
        orderId: s.order.order_id,
      });
      out.push({
        at: orderEvent.at,
        from: sid,
        to: "buyer",
        title: s.order.accepted ? "Order accepted" : "Order refused",
        detail: s.order.accepted ? `order ${s.order.order_id.slice(0, 8)}` : s.order.message,
        tone: s.order.accepted ? "lead" : "bad",
        verified: true,
        orderId: s.order.order_id,
      });
    }
  }

  const indexed = out.map((m, i) => ({ m, i }));
  indexed.sort((a, b) => {
    const ta = Date.parse(a.m.at) || 0;
    const tb = Date.parse(b.m.at) || 0;
    return ta - tb || a.i - b.i;
  });
  return indexed.map(({ m }, i) => ({ ...m, seq: i + 1 }));
}

export const STEPS = ["Request", "Confirm", "Discover", "Quote", "Negotiate", "Rank", "Approve", "Order"] as const;

export type StepState = { index: number; failed: boolean; done: boolean };

export function openQuestions(s: SessionState | null): Thread[] {
  if (!s) return [];
  return Object.values(s.threads).filter((t) => t.latest?.kind === "question");
}

export function stepState(s: SessionState | null): StepState {
  if (!s) return { index: 0, failed: false, done: false };
  switch (s.status) {
    case "awaiting_confirm":
      return { index: 1, failed: false, done: false };
    case "searching":
      return { index: 2, failed: false, done: false };
    case "no_suppliers":
      return { index: 2, failed: true, done: false };
    case "quoting":
      return { index: 3, failed: false, done: false };
    case "negotiating":
      return { index: 4, failed: false, done: false };
    case "approved":
      return { index: 7, failed: false, done: false };
    case "ordered":
      return { index: 7, failed: false, done: true };
    case "order_refused":
      return { index: 7, failed: true, done: false };
    default:
      if (s.ranking?.winner) return { index: 6, failed: false, done: false };
      if (openQuestions(s).length) return { index: 3, failed: false, done: false };
      return { index: 5, failed: true, done: false };
  }
}

export type BoardRow = {
  sid: SupplierId;
  thread: Thread;
  reply: Reply | null;
  ranked: RankedQuote | null;
  leader: boolean;
};

export function boardRows(s: SessionState | null): BoardRow[] {
  if (!s) return [];
  const all = [...(s.ranking?.eligible ?? []), ...(s.ranking?.excluded ?? [])];
  const rows: BoardRow[] = [];
  for (const thread of Object.values(s.threads)) {
    const sid = supplierId(thread.supplier_did);
    if (!sid) continue;
    const ranked = all.find((r) => r.supplier_did === thread.supplier_did) ?? null;
    rows.push({
      sid,
      thread,
      reply: thread.latest,
      ranked,
      leader: Boolean(s.ranking?.winner && s.ranking.winner.supplier_did === thread.supplier_did),
    });
  }
  const order = (r: BoardRow) =>
    r.ranked?.eligible && r.ranked.rank ? r.ranked.rank : r.reply?.kind === "quote" ? 50 : r.reply?.kind === "question" ? 60 : 70;
  return rows.sort((a, b) => order(a) - order(b) || a.sid.localeCompare(b.sid));
}

export function modelNote(s: SessionState | null): string {
  if (!s) return "";
  const replies = Object.values(s.threads).flatMap((t) => t.replies);
  const worded = replies.some((r) => r.payload?.phrasing_from_model);
  if (s.extract_unavailable && !worded) return "Bedrock unavailable: code wording shown. Numbers are unaffected.";
  return "Haiku reads and explains, Nova words supplier replies. Code sets every number.";
}

/** Signed prices a supplier offered in this run, opening first. */
export function pricePath(thread: Thread): number[] {
  return thread.replies
    .filter((r) => r.signature_verified && r.payload?.kind === "quote")
    .map((r) => r.payload!.unit_price ?? 0);
}

export function guardFlags(s: SessionState | null): Array<{ thread: Thread; reply: Reply }> {
  if (!s) return [];
  return Object.values(s.threads).flatMap((t) =>
    t.replies.filter((r) => r.guard?.length).map((reply) => ({ thread: t, reply })),
  );
}

/** Best opening price that met the date, versus the winning price. */
export function savings(s: SessionState | null): { opening: number; final: number; total: number } | null {
  const w = s?.ranking?.winner;
  if (!s || !w) return null;
  const openings = Object.values(s.threads)
    .map((t) => t.replies.find((r) => r.signature_verified && r.payload?.kind === "quote" && r.payload.meets_date))
    .filter((r): r is Reply => Boolean(r))
    .map((r) => r.payload!.unit_price ?? 0);
  if (!openings.length) return null;
  const opening = Math.min(...openings);
  const final = w.quote.unit_price;
  return { opening, final, total: Math.max(0, (opening - final) * w.quote.quantity) };
}

export function sparkline(values: number[], label: string): string {
  if (values.length < 2) return "";
  const w = 76;
  const h = 22;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [
    2 + (i * (w - 4)) / (values.length - 1),
    2 + ((max - v) * (h - 4)) / span,
  ]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const [lx, ly] = pts[pts.length - 1];
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="${esc(label)}"><path d="${d}"/><circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="2.2"/></svg>`;
}
