import { esc } from "./model";
import type { ProbeResult, ProbeStep, ProbeTarget } from "./types";

const TARGETS: { id: ProbeTarget; label: string; blurb: string }[] = [
  {
    id: "peer",
    label: "Official example agent",
    blurb: "The ANP team's Remote Test Agent, running isolated next to this desk.",
  },
  {
    id: "public",
    label: "Public amap agent",
    blurb: "Live agent on agent-connect.ai. Needs outbound internet; may be slow or offline.",
  },
];

export function livePage(opts: {
  target: ProbeTarget;
  result: ProbeResult | null;
  busy: boolean;
  error: string | null;
}): string {
  const { target, result, busy, error } = opts;
  const ok = result?.ok;
  return `<main id="main" class="live" data-view="live">
    <section class="live-hero">
      <p class="live-kicker">Outside the desk</p>
      <h1>Live ANP</h1>
      <p class="live-lead">Prove the protocol against an agent we do not control, using the official ANP SDK and a public demo identity. Nothing from that call enters the buyer, the suppliers, or any model.</p>
      <div class="live-cta">
        ${TARGETS.map(
          (t) =>
            `<button type="button" class="live-target${target === t.id ? " on" : ""}" data-action="live-target" data-target="${t.id}" ${busy ? "disabled" : ""} aria-pressed="${target === t.id}">
              <strong>${esc(t.label)}</strong>
              <span>${esc(t.blurb)}</span>
            </button>`,
        ).join("")}
      </div>
      <div class="live-actions">
        <button type="button" class="primary" data-action="live-run" ${busy ? "disabled" : ""}>
          ${busy ? "Connecting…" : "Connect to live agent"}
        </button>
        ${
          result
            ? `<span class="live-status ${ok ? "ok" : "bad"}">${ok ? "Verified" : "Incomplete"}</span>`
            : `<span class="live-status muted">No run yet</span>`
        }
        ${result?.recorded ? `<span class="live-chip">Last saved run</span>` : ""}
        ${result && !result.recorded ? `<span class="live-chip live">Just now</span>` : ""}
      </div>
      ${error ? `<p class="live-error" role="alert">${esc(error)}</p>` : ""}
    </section>

    ${result ? resultPanel(result) : emptyPanel()}
    ${safetyStrip()}
  </main>`;
}

function emptyPanel(): string {
  return `<section class="live-panel" aria-label="Result">
    <h2>Waiting for a connection</h2>
    <p>Choose a target and connect. The probe will load our identity, fetch their agent description, list their tools, and make a signed call.</p>
  </section>`;
}

function resultPanel(r: ProbeResult): string {
  const them = r.them;
  return `<section class="live-panel" aria-label="Result">
    <header class="live-panel-head">
      <div>
        <h2>${esc(them?.name || "Remote agent")}</h2>
        <p class="mono">${esc(them?.did || r.ad_url)}</p>
      </div>
      <dl class="live-meta">
        <div><dt>SDK</dt><dd>${esc(r.sdk.client)}${r.sdk.auth_mode ? ` · ${esc(r.sdk.auth_mode)}` : ""}</dd></div>
        <div><dt>Our DID</dt><dd class="mono">${esc(r.us.did)}</dd></div>
        ${them?.protocol_version ? `<div><dt>Protocol</dt><dd>${esc(them.protocol_version)}</dd></div>` : ""}
      </dl>
    </header>

    <ol class="live-steps">
      ${r.steps.map((s) => stepRow(s)).join("")}
    </ol>

    ${toolsBlock(r)}
    ${exchangesBlock(r)}
    ${proofBlock(r)}
  </section>`;
}

function stepRow(s: ProbeStep): string {
  return `<li class="${s.ok ? "ok" : "bad"}">
    <span class="dot" aria-hidden="true"></span>
    <div>
      <strong>${esc(s.title)}</strong>
      <p>${esc(s.detail)}</p>
    </div>
    <span class="ms">${s.ms} ms</span>
  </li>`;
}

function toolsBlock(r: ProbeResult): string {
  if (!r.tools.length) return "";
  return `<div class="live-block">
    <h3>Interfaces they publish</h3>
    <ul class="live-tools">
      ${r.tools
        .map(
          (t) =>
            `<li><strong>${esc(t.name)}</strong>${t.description ? `<span>${esc(t.description)}</span>` : ""}${
              t.params?.length ? `<span class="mono">${esc(t.params.join(", "))}</span>` : ""
            }</li>`,
        )
        .join("")}
    </ul>
  </div>`;
}

function exchangesBlock(r: ProbeResult): string {
  if (!r.exchanges.length) return "";
  return `<div class="live-block">
    <h3>Signed exchanges</h3>
    <div class="live-exchanges">
      ${r.exchanges
        .map(
          (x) => `<article>
            <h4>${esc(x.tool)}</h4>
            <pre>ask  ${esc(JSON.stringify(x.request))}</pre>
            <pre>reply ${esc(typeof x.response === "string" ? x.response : JSON.stringify(x.response))}</pre>
          </article>`,
        )
        .join("")}
    </div>
  </div>`;
}

function proofBlock(r: ProbeResult): string {
  const p = r.proof;
  if (!p || (p.peer_saw_did == null && p.matches_ours == null)) return "";
  return `<div class="live-proof ${p.matches_ours ? "ok" : "bad"}">
    <strong>${p.matches_ours ? "Peer verified our signature" : "Peer did not confirm our DID"}</strong>
    <p class="mono">${esc(String(p.peer_saw_did ?? ""))}</p>
  </div>`;
}

function safetyStrip(): string {
  return `<aside class="live-safety" aria-label="Safety">
    <h3>How this stays safe</h3>
    <ul>
      <li>Isolated probe network — no Redis, Postgres, keys, or AWS credentials</li>
      <li>Public demo identity only — its private key is published for tests</li>
      <li>Allow-listed hosts, no redirects, size-capped replies</li>
      <li>Replies are display data only — never ranked, priced, or sent to a model</li>
    </ul>
  </aside>`;
}
