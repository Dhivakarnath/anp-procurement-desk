import { icon } from "./icons";
import {
  PARTIES,
  PARTY_ORDER,
  STEPS,
  attrText,
  buildMessages,
  describeLines,
  esc,
  modelNote,
  money,
  seqLabel,
  stepState,
} from "./model";
import { SCENARIOS, type Ui } from "./state";
import type { PartyId } from "./types";

export function mark(p: PartyId, size: "sm" | "lg" = "sm"): string {
  return `<span class="mark mark-${size}" data-party="${p}" aria-hidden="true">${PARTIES[p].short}</span>`;
}

export function modeSwitch(ui: Ui): string {
  return `<div class="mode" role="tablist" aria-label="Product areas">
    <button type="button" role="tab" class="mode-tab" data-action="mode" data-mode="desk" aria-selected="${ui.mode === "desk"}">Desk</button>
    <button type="button" role="tab" class="mode-tab" data-action="mode" data-mode="live" aria-selected="${ui.mode === "live"}">Live ANP</button>
  </div>`;
}

export function topBar(ui: Ui): string {
  const msgs = buildMessages(ui.session);
  const count = (p: PartyId) => msgs.filter((m) => m.from === p || m.to === p).length;
  const tab = (id: Ui["view"], label: string, extra = "") =>
    `<button type="button" role="tab" class="tab" data-action="view" data-view="${id}" aria-selected="${ui.view === id}">${label}${extra}</button>`;
  if (ui.mode === "live") {
    return `<header class="bar bar-live">
      <div class="brand">ANP Procurement Desk</div>
      ${modeSwitch(ui)}
      <p class="bar-note">Official SDK · public demo identity · isolated from the desk</p>
    </header>`;
  }
  return `<header class="bar">
    <div class="brand">ANP Procurement Desk</div>
    ${modeSwitch(ui)}
    <nav class="tabs" role="tablist" aria-label="Views">
      ${tab("overview", "Overview")}
      ${PARTY_ORDER.map((p) =>
        tab(
          p,
          `${mark(p)}<span>${PARTIES[p].name}</span>`,
          ui.session ? `<span class="count">${count(p)}</span>` : "",
        ),
      ).join("")}
    </nav>
    ${modelNote(ui.session) ? `<p class="bar-note">${esc(modelNote(ui.session))}</p>` : ""}
  </header>`;
}

export function scenarioBar(ui: Ui): string {
  const busy = Boolean(ui.busy);
  return `<div class="scenarios" role="group" aria-label="Scenarios">
    <span class="scen-label">Scenario</span>
    ${SCENARIOS.map(
      (s) =>
        `<button type="button" class="scen" data-action="scenario" data-id="${s.id}" aria-pressed="${ui.scenario === s.id}" ${busy ? "disabled" : ""}>${esc(s.label)}</button>`,
    ).join("")}
    <button type="button" class="scen" data-action="own" aria-pressed="${ui.scenario === "own"}" ${busy ? "disabled" : ""}>Type your own</button>
    <span class="scen-spacer"></span>
    ${
      ui.session
        ? `<button type="button" class="ghost" data-action="reset" ${busy ? "disabled" : ""}>${icon("reset")}New run</button>`
        : ""
    }
  </div>`;
}

export function errorBar(ui: Ui): string {
  if (!ui.error) return "";
  return `<div class="error" role="alert">${icon("cross")}<span>${esc(ui.error)}</span>
    <button type="button" class="ghost" data-action="dismiss">Dismiss</button></div>`;
}

function rail(ui: Ui): string {
  const st = stepState(ui.session);
  return `<ol class="rail" aria-label="Process">
    ${STEPS.map((name, i) => {
      let cls = "todo";
      if (i < st.index || (st.done && i === st.index)) cls = "done";
      else if (i === st.index) cls = st.failed ? "failed" : "now";
      const live = cls === "now" && ui.busy ? " working" : "";
      return `<li class="step ${cls}${live}" ${cls === "now" ? 'aria-current="step"' : ""}>
        <span class="step-dot">${cls === "done" ? icon("check") : cls === "failed" ? icon("cross") : i + 1}</span>
        <span>${name}</span></li>`;
    }).join("")}
  </ol>`;
}

function composer(ui: Ui): string {
  const scen = SCENARIOS.find((s) => s.id === ui.scenario);
  return `<div class="composer">
    <label for="request-text">Describe what you need</label>
    <div class="composer-row">
      <textarea id="request-text" rows="2" ${ui.busy ? "disabled" : ""}>${esc(ui.text)}</textarea>
      <button type="button" class="primary" data-action="extract" ${ui.busy ? "disabled" : ""}>${ui.busy ? esc(ui.busy) : "Read request"}</button>
    </div>
    <p class="hint">${
      scen ? esc(scen.note) : "Plain language is fine. The buyer turns it into a part, a quantity and a date, and you check it before anyone is contacted."
    }</p>
  </div>`;
}

function confirmGate(ui: Ui): string {
  const d = ui.draft!;
  const s = ui.session!;
  const pol = ui.policy;
  const attrs = Object.entries(d.attributes);
  return `<form class="gate" data-form="confirm" aria-label="Check the request">
    <div class="gate-head">
      <p class="gate-note">${icon("lock")}Nothing has been sent yet. ${
        s.extract_unavailable
          ? "Bedrock was unavailable, so the fallback parser read your sentence. Check every field."
          : "Claude Haiku read your sentence. Check every field."
      }</p>
    </div>
    <div class="fields">
      <label class="f f-part">Part<input name="part" value="${esc(d.part)}" required /></label>
      <label class="f">Quantity<input name="quantity" type="number" min="1" value="${d.quantity}" required /></label>
      <label class="f">Need-by (days)<input name="need_by_days" type="number" min="1" value="${d.need_by_days}" required /></label>
    </div>
    <fieldset class="attrs">
      <legend>Attributes</legend>
      ${
        attrs.length
          ? attrs
              .map(
                ([k, v], i) => `<div class="attr-row">
          <input aria-label="Attribute name" data-attr-key="${i}" value="${esc(k)}" />
          <input aria-label="Attribute value" data-attr-val="${i}" value="${esc(v)}" />
          <button type="button" class="ghost" data-action="remove-attr" data-index="${i}">Remove</button></div>`,
              )
              .join("")
          : `<p class="hint">None. Some parts need one, such as the compound for a shaft seal.</p>`
      }
      <button type="button" class="ghost" data-action="add-attr">Add attribute</button>
    </fieldset>
    <fieldset class="limits">
      <legend>Your limits for bargaining</legend>
      <label class="f">Target unit price ($)<input name="target_unit_price" type="number" min="0" step="0.01" value="${pol?.target_unit_price ?? ""}" placeholder="8% below best" />
        <span class="f-note">Sent to suppliers as your ask.</span></label>
      <label class="f">Walk-away unit price ($)<input name="walk_away_unit_price" type="number" min="0" step="0.01" value="${pol?.walk_away_unit_price ?? ""}" placeholder="No limit" />
        <span class="f-note">Never leaves the buyer. Quotes above it are excluded.</span></label>
      <label class="f">Bargaining rounds<input name="max_rounds" type="number" min="0" max="6" value="${pol?.max_rounds ?? 4}" />
        <span class="f-note">The buyer runs these by itself. 0 turns bargaining off.</span></label>
    </fieldset>
    <div class="gate-actions">
      <button type="submit" class="primary" ${ui.busy ? "disabled" : ""}>${ui.busy ? esc(ui.busy) : "Confirm, search and negotiate"}</button>
    </div>
  </form>`;
}

export function requestStrip(ui: Ui): string {
  const s = ui.session;
  let head: string;
  let body = "";
  if (!s) {
    head = `<h1>New sourcing run</h1>`;
    body = composer(ui);
  } else if (!s.confirmed && ui.draft) {
    head = `<h1>Check the request</h1>`;
    body = confirmGate(ui);
  } else {
    const l = s.lines!;
    const msgs = buildMessages(s);
    head = `<h1>${esc(describeLines(l))}</h1>
      <dl class="facts">
        <div><dt>Need-by</dt><dd>${l.need_by_days} days</dd></div>
        <div><dt>Attributes</dt><dd>${esc(attrText(l.attributes))}</dd></div>
        <div><dt>Your ask</dt><dd>${s.policy.target_unit_price != null ? money(s.policy.target_unit_price) : "—"}</dd></div>
        <div><dt>Bargaining</dt><dd>${s.round ? `Round ${s.round} of ${s.policy.max_rounds}` : s.policy.max_rounds ? "Not started" : "Off"}</dd></div>
        <div><dt>Messages</dt><dd>${msgs.length ? `No. 001–${seqLabel(msgs.length)}` : "—"}</dd></div>
        <div><dt>Run</dt><dd class="mono">${esc(s.session_id.slice(0, 8))}</dd></div>
      </dl>`;
  }
  return `<section class="strip" aria-label="Request">
    <div class="strip-head">${head}</div>
    ${body}
    ${rail(ui)}
  </section>`;
}
