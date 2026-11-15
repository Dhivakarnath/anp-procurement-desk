import "./style.css";
import * as api from "./api";
import { livePage } from "./live";
import { PARTY_ORDER, buildMessages, openQuestions } from "./model";
import { overview } from "./overview";
import { partyView } from "./party";
import { errorBar, requestStrip, scenarioBar, topBar } from "./shell";
import { SCENARIOS, initialUi, type Mode, type Ui, type View } from "./state";
import type { BuyerPolicy, PartyId, ProbeTarget, RequestLines, SessionState } from "./types";

const app = document.querySelector<HTMLDivElement>("#app")!;
let ui: Ui = initialUi();

function viewFromHash(): { mode: Mode; view: View } {
  const h = location.hash.replace("#", "");
  if (h === "live-anp" || h === "live") return { mode: "live", view: "overview" };
  if ((PARTY_ORDER as string[]).includes(h)) return { mode: "desk", view: h as PartyId };
  return { mode: "desk", view: "overview" };
}

function render(): void {
  if (ui.mode === "live") {
    document.title = "Live ANP · ANP Procurement Desk";
    app.innerHTML = `${topBar(ui)}${livePage({
      target: ui.liveTarget,
      result: ui.liveResult,
      busy: Boolean(ui.busy),
      error: ui.liveError,
    })}`;
    return;
  }
  document.title = "ANP Procurement Desk";
  const body = ui.view === "overview" ? overview(ui) : partyView(ui.view, ui);
  app.innerHTML = `${topBar(ui)}
    <main id="main" class="desk" data-view="${ui.view}">
      ${scenarioBar(ui)}
      ${errorBar(ui)}
      ${requestStrip(ui)}
      <div class="view" aria-live="polite">${body}</div>
    </main>`;
  ui.seen = buildMessages(ui.session).length;
  ui.leader = ui.session?.ranking?.winner?.supplier_did ?? null;
  app.querySelectorAll<HTMLElement>(".lanes .msgs").forEach((list) => {
    const rows = [...list.querySelectorAll<HTMLElement>(".msg")];
    if (list.scrollHeight > list.clientHeight) {
      let fit = 0;
      for (const r of rows.slice().reverse()) {
        if (fit + r.offsetHeight > list.clientHeight) break;
        fit += r.offsetHeight;
      }
      list.style.height = `${fit}px`;
    }
    const traced = list.querySelector<HTMLElement>(".msg.traced");
    const bottom = list.scrollHeight - list.clientHeight;
    if (traced) {
      const above = rows.filter((r) => r.offsetTop < traced.offsetTop).slice(-1)[0];
      list.scrollTop = Math.min(above ? above.offsetTop : 0, bottom);
    } else {
      list.scrollTop = bottom;
    }
    updateMore(list);
  });
}

async function loadLive(target: ProbeTarget = ui.liveTarget): Promise<void> {
  ui.liveTarget = target;
  ui.liveError = null;
  try {
    ui.liveResult = await api.probeLast(target);
  } catch {
    ui.liveResult = null;
  }
  render();
}

async function runLive(): Promise<void> {
  ui.busy = "Connecting to live agent…";
  ui.liveError = null;
  render();
  try {
    ui.liveResult = await api.probeRun(ui.liveTarget);
  } catch (err) {
    ui.liveError = (err as Error).message;
  } finally {
    ui.busy = null;
    render();
  }
}

function updateMore(list: HTMLElement): void {
  const more = list.previousElementSibling as HTMLButtonElement | null;
  if (!more?.classList.contains("more")) return;
  const hidden = [...list.querySelectorAll<HTMLElement>(".msg")].filter(
    (r) => r.offsetTop + r.offsetHeight / 2 < list.scrollTop,
  ).length;
  more.hidden = hidden === 0;
  more.textContent = `${hidden} earlier message${hidden === 1 ? "" : "s"}`;
}

async function refreshLedgers(): Promise<void> {
  const jobs: Array<[PartyId, Promise<unknown>]> = [
    ["market", api.marketLedger()],
    ["s1", api.supplierLedger("s1")],
    ["s2", api.supplierLedger("s2")],
    ["s3", api.supplierLedger("s3")],
  ];
  const results = await Promise.allSettled(jobs.map(([, p]) => p));
  results.forEach((r, i) => {
    const party = jobs[i][0] as "market" | "s1" | "s2" | "s3";
    if (r.status === "fulfilled") {
      (ui.ledgers as Record<string, unknown>)[party] = r.value;
      delete ui.ledgerErrors[party];
    } else {
      ui.ledgerErrors[party] = `${party.toUpperCase()}'s service did not answer: ${(r.reason as Error).message}`;
    }
  });
}

async function run(label: string, task: () => Promise<SessionState | void>): Promise<void> {
  ui.busy = label;
  ui.error = null;
  render();
  try {
    const next = await task();
    if (next) {
      ui.session = next;
      ui.draft = next.confirmed ? null : structuredClone(next.lines);
      if (!next.confirmed) ui.policy = structuredClone(next.policy);
    }
    await refreshLedgers();
  } catch (err) {
    ui.error = (err as Error).message;
  } finally {
    ui.busy = null;
    render();
  }
}

/** Run a long buyer call while showing each saved step as it lands. */
async function live(sessionId: string, task: () => Promise<SessionState>): Promise<SessionState> {
  let active = true;
  const tick = async (): Promise<void> => {
    while (active) {
      await new Promise((r) => setTimeout(r, 450));
      try {
        const latest = await api.getSession(sessionId);
        if (!active) return;
        ui.session = latest;
        ui.busy = latest.status === "negotiating" ? `Negotiating, round ${latest.round}…` : ui.busy;
        render();
      } catch {
        /* the final response still arrives */
      }
    }
  };
  void tick();
  try {
    return await task();
  } finally {
    active = false;
  }
}

function startRun(text: string, scenario: string | null = null): void {
  ui.seen = 0;
  ui.session = null;
  ui.draft = null;
  ui.policy = null;
  ui.trace = null;
  ui.focus = null;
  ui.showHistory = false;
  ui.text = text;
  void run("Reading request…", async () => {
    await api.setRogue("s3", scenario === "inject").catch(() => undefined);
    return api.createSession(text);
  });
}

function syncPolicy(): BuyerPolicy {
  const form = app.querySelector<HTMLFormElement>('form[data-form="confirm"]');
  const base: BuyerPolicy = ui.policy ?? { target_unit_price: null, walk_away_unit_price: null, max_rounds: 4 };
  if (!form) return base;
  const fd = new FormData(form);
  const num = (k: string) => {
    const v = Number(fd.get(k));
    return fd.get(k) !== "" && Number.isFinite(v) && v > 0 ? v : null;
  };
  ui.policy = {
    target_unit_price: num("target_unit_price"),
    walk_away_unit_price: num("walk_away_unit_price"),
    max_rounds: Math.min(6, Math.max(0, Math.round(Number(fd.get("max_rounds")) || 0))),
  };
  return ui.policy;
}

function syncDraft(): RequestLines | null {
  const form = app.querySelector<HTMLFormElement>('form[data-form="confirm"]');
  if (!form || !ui.draft) return ui.draft;
  const fd = new FormData(form);
  const attributes: Record<string, string> = {};
  form.querySelectorAll<HTMLInputElement>("[data-attr-key]").forEach((k) => {
    const i = k.dataset.attrKey!;
    const v = form.querySelector<HTMLInputElement>(`[data-attr-val="${i}"]`)?.value ?? "";
    if (k.value.trim()) attributes[k.value.trim()] = v.trim();
  });
  ui.draft = {
    part: String(fd.get("part") ?? "").trim(),
    quantity: Math.max(1, Number(fd.get("quantity")) || 1),
    need_by_days: Math.max(1, Number(fd.get("need_by_days")) || 1),
    attributes,
    notes: ui.draft.notes,
  };
  return ui.draft;
}

app.addEventListener("input", (e) => {
  const t = e.target as HTMLElement;
  if (t.id === "request-text") ui.text = (t as HTMLTextAreaElement).value;
  if (t instanceof HTMLInputElement && t.name === "answer") {
    const attr = t.closest<HTMLFormElement>("form")?.dataset.attr;
    if (attr) ui.answers[attr] = t.value;
  }
});

app.addEventListener("submit", (e) => {
  e.preventDefault();
  const form = e.target as HTMLFormElement;
  const s = ui.session;
  if (!s) return;
  if (form.dataset.form === "confirm") {
    const lines = syncDraft();
    const policy = syncPolicy();
    if (!lines?.part) return;
    void run("Searching and requesting quotes…", () =>
      live(s.session_id, () => api.confirmLines(s.session_id, lines, policy)),
    );
  }
  if (form.dataset.form === "answer") {
    const attr = form.dataset.attr!;
    const value = String(new FormData(form).get("answer") ?? "").trim();
    if (!value || !s.lines) return;
    ui.answers[attr] = value;
    const lines: RequestLines = { ...s.lines, attributes: { ...s.lines.attributes, [attr]: value } };
    const targets = openQuestions(s).map((t) => t.supplier_did);
    void run("Sending answers…", () =>
      live(s.session_id, async () => {
        let latest = s;
        for (const did of targets) latest = await api.negotiate(s.session_id, did, lines);
        return latest;
      }),
    );
  }
});

app.addEventListener("click", (e) => {
  const el = (e.target as HTMLElement).closest<HTMLElement>("[data-action]");
  if (!el || (el as HTMLButtonElement).disabled) return;
  const a = el.dataset.action;
  const s = ui.session;
  switch (a) {
    case "mode": {
      const mode = (el.dataset.mode as Mode) || "desk";
      ui.mode = mode;
      location.hash = mode === "live" ? "live-anp" : ui.view === "overview" ? "" : ui.view;
      render();
      window.scrollTo({ top: 0 });
      if (mode === "live" && !ui.liveResult) void loadLive();
      break;
    }
    case "live-target":
      void loadLive((el.dataset.target as ProbeTarget) || "peer");
      break;
    case "live-run":
      void runLive();
      break;
    case "view":
      location.hash = el.dataset.view === "overview" ? "" : el.dataset.view!;
      ui.mode = "desk";
      ui.view = (el.dataset.view as View) ?? "overview";
      render();
      window.scrollTo({ top: 0 });
      break;
    case "scenario": {
      const sc = SCENARIOS.find((x) => x.id === el.dataset.id);
      if (!sc) return;
      ui.scenario = sc.id;
      startRun(sc.text, sc.id);
      break;
    }
    case "own":
      ui = { ...initialUi(), view: ui.view, ledgers: ui.ledgers, scenario: "own", text: "" };
      render();
      app.querySelector<HTMLTextAreaElement>("#request-text")?.focus();
      break;
    case "extract":
      if (ui.text.trim()) startRun(ui.text.trim(), "own");
      break;
    case "reset":
      ui = { ...initialUi(), view: ui.view, ledgers: ui.ledgers };
      render();
      break;
    case "dismiss":
      ui.error = null;
      render();
      break;
    case "add-attr":
      syncDraft();
      syncPolicy();
      if (ui.draft) {
        let key = "attribute";
        let n = 1;
        while (key in ui.draft.attributes) key = `attribute ${++n}`;
        ui.draft.attributes[key] = "";
      }
      render();
      break;
    case "remove-attr": {
      syncDraft();
      syncPolicy();
      if (!ui.draft) return;
      const i = Number(el.dataset.index);
      const entries = Object.entries(ui.draft.attributes).filter((_, j) => j !== i);
      ui.draft.attributes = Object.fromEntries(entries);
      render();
      break;
    }
    case "approve": {
      const w = s?.ranking?.winner;
      if (!s || !w) return;
      void run("Approving…", () => api.approve(s.session_id, w.quote_hash, w.supplier_did));
      break;
    }
    case "order":
      if (s) void run("Sending signed order…", () => api.placeOrder(s.session_id));
      break;
    case "trace": {
      const n = Number(el.dataset.seq);
      ui.trace = ui.trace === n ? null : n;
      ui.focus = null;
      render();
      app.querySelector<HTMLElement>(`.seq[data-seq="${n}"]`)?.focus();
      break;
    }
    case "focus": {
      const p = el.dataset.party as PartyId;
      ui.focus = ui.focus === p ? null : p;
      ui.trace = null;
      render();
      app.querySelector<HTMLElement>(`.lane-focus[data-party="${p}"]`)?.focus();
      break;
    }
    case "history":
      ui.showHistory = !ui.showHistory;
      render();
      break;
    case "lane-top": {
      const list = el.nextElementSibling as HTMLElement | null;
      list?.scrollTo({ top: 0, behavior: "smooth" });
      break;
    }
  }
});

app.addEventListener(
  "scroll",
  (e) => {
    const t = e.target as HTMLElement;
    if (t.classList?.contains("msgs")) updateMore(t);
  },
  true,
);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && (ui.trace || ui.focus)) {
    ui.trace = null;
    ui.focus = null;
    render();
  }
});

window.addEventListener("hashchange", () => {
  const next = viewFromHash();
  ui.mode = next.mode;
  ui.view = next.view;
  render();
  if (ui.mode === "live" && !ui.liveResult) void loadLive();
});

{
  const next = viewFromHash();
  ui.mode = next.mode;
  ui.view = next.view;
}
render();
if (ui.mode === "live") void loadLive();
else void refreshLedgers().then(render);
