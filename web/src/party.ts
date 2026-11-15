import { ENDPOINTS } from "./api";
import { icon } from "./icons";
import {
  PARTIES,
  attrText,
  buildMessages,
  clock,
  esc,
  money,
  pricePath,
  qty,
  savings,
  seqLabel,
  shortHash,
  supplierId,
  type Message,
  type SupplierId,
} from "./model";
import { decision, guardBanner, messageRow, questionBar } from "./overview";
import { mark } from "./shell";
import type { Ui } from "./state";
import type { PartyId, Reply, SupplierEntry, Thread } from "./types";

function head(p: PartyId, ui: Ui, did: string | undefined, roleLine: string, source: string): string {
  return `<section class="party-head" data-party="${p}">
    ${mark(p, "lg")}
    <div class="party-id">
      <h2>${PARTIES[p].name}<span>${esc(PARTIES[p].role)}</span></h2>
      <p>${esc(roleLine)}</p>
    </div>
    <dl class="party-facts">
      <div><dt>Identity</dt><dd class="mono">${esc(did ?? `did:wba:${p}.test:agent`)}</dd></div>
      <div><dt>Public address</dt><dd class="mono">https://${p}.test</dd></div>
      <div><dt>This view reads</dt><dd class="mono">${esc(source)}</dd></div>
    </dl>
    ${ui.ledgerErrors[p] ? `<p class="error-inline">${icon("cross")}${esc(ui.ledgerErrors[p])}</p>` : ""}
  </section>`;
}

function seqsFor(msgs: Message[], key: { requestId?: string | null; orderId?: string | null }): string {
  const hit = msgs.filter(
    (m) => (key.requestId && m.requestId === key.requestId) || (key.orderId && m.orderId === key.orderId),
  );
  return hit.length ? hit.map((m) => seqLabel(m.seq)).join(" · ") : "—";
}

function kv(rows: Array<[string, string]>, cls = ""): string {
  return `<dl class="kv ${cls}">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("")}</dl>`;
}

/* ---------- Buyer ---------- */

function replyFacts(r: Reply): string {
  const req = r.request;
  return `<details class="facts-detail"><summary>Signature and hash details</summary>
    ${kv([
      ["Request nonce", `<span class="mono">${esc(req?.nonce ?? "—")}</span>`],
      ["Request digest", `<span class="mono">${esc(req?.body_digest ?? "—")}</span>`],
      ["Signed for", `<span class="mono">${esc(req?.url ?? "—")}</span>`],
      ["Reply check", esc(r.check?.signature ?? "—")],
      ["Reply nonce", `<span class="mono">${esc(r.check?.reply_nonce ?? "—")}</span>`],
      ["Signer recovered", `<span class="mono">${esc(r.check?.recovered_did ?? "not verified")}</span>`],
      ["Quote hash", `<span class="mono">${esc(r.quote_hash ?? "none (no price offered)")}</span>`],
    ])}
  </details>`;
}

function conversation(thread: Thread, msgs: Message[], ui: Ui): string {
  const sid = supplierId(thread.supplier_did) as SupplierId;
  const mine = msgs.filter((m) => m.from === sid || m.to === sid);
  return `<section class="convo" data-party="${sid}">
    <header class="convo-head">
      ${mark(sid)}
      <div><h3>${esc(thread.supplier_name)}</h3>
      <p>Found through the marketplace · catalog item <span class="mono">${esc(thread.matched_sku)}</span></p></div>
      <button type="button" class="ghost" data-action="view" data-view="${sid}">${icon("open")}${esc(thread.supplier_name)} view</button>
    </header>
    <ol class="msgs">${mine.map((m) => messageRow(m, "buyer", ui)).join("")}</ol>
    ${untrusted(thread)}
    ${thread.replies.map((r) => replyFacts(r)).join("")}
  </section>`;
}

function untrusted(thread: Thread): string {
  const r = [...thread.replies].reverse().find((x) => x.guard?.length);
  if (!r) return "";
  const flags = r.guard ?? [];
  return `<div class="untrusted">
    <h4>${icon("alert")}Untrusted text in ${esc(thread.supplier_name)}'s reply, not acted on</h4>
    ${r.payload?.note ? `<p><span class="muted">Note field</span><q>${esc(r.payload.note)}</q></p>` : ""}
    ${r.payload?.phrasing ? `<p><span class="muted">Wording</span><q>${esc(r.payload.phrasing)}</q></p>` : ""}
    <p class="muted">Signed price used instead: <strong>${money(r.payload?.unit_price ?? 0)}</strong></p>
    <ul class="plain">${[...new Set(flags.map((f) => f.reason))].map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
  </div>`;
}

function buyerView(ui: Ui): string {
  const s = ui.session;
  const msgs = buildMessages(s);
  const top = head(
    "buyer",
    ui,
    "did:wba:buyer.test:agent",
    "Finds suppliers only through the marketplace, signs every request, verifies every reply, and ranks in code.",
    `${ENDPOINTS.buyer}/sessions`,
  );
  if (!s) return `${top}<p class="view-empty">Start a run from the scenario bar to see the buyer's side.</p>`;
  const internal = msgs.filter((m) => m.from === "buyer" && (m.to === null || m.to === "market"));
  const marketReply = msgs.filter((m) => m.from === "market");
  const threads = Object.values(s.threads);
  const ranked = [...(s.ranking?.eligible ?? []), ...(s.ranking?.excluded ?? [])];
  const eligibility = threads.map((t) => {
    const r = ranked.find((x) => x.supplier_did === t.supplier_did);
    const kind = t.latest?.kind;
    return `<tr data-party="${supplierId(t.supplier_did)}">
      <td><span class="who">${mark(supplierId(t.supplier_did) as SupplierId)}${esc(t.supplier_name)}</span></td>
      <td class="${t.latest?.signature_verified ? "ok" : "bad"}">${t.latest?.signature_verified ? "Yes" : "No"}</td>
      <td>${r && kind === "quote" ? (r.quote_valid ? "Yes" : "No") : "—"}</td>
      <td>${kind === "question" ? "Not priced" : r ? (r.date_met ? "Yes" : "No") : kind === "refusal" ? "No" : "—"}</td>
      <td class="${r?.eligible ? "ok" : "bad"}">${r?.eligible ? `Rank ${r.rank}` : kind === "question" ? "Waiting on answer" : "Excluded"}</td>
    </tr>`;
  });
  const maxRound = Math.max(0, ...threads.map((t) => pricePath(t).length - 1));
  const bargaining = threads.some((t) => pricePath(t).length)
    ? `<h3 class="block-h">Bargaining rounds</h3>
      <div class="table-scroll"><table class="grid rounds">
        <thead><tr><th scope="col">Supplier</th><th scope="col" class="num">Opening</th>${Array.from(
          { length: maxRound },
          (_, i) => `<th scope="col" class="num">Round ${i + 1}</th>`,
        ).join("")}<th scope="col">Outcome</th></tr></thead>
        <tbody>${threads
          .map((t) => {
            const path = pricePath(t);
            const sid = supplierId(t.supplier_did) as SupplierId;
            const last = t.latest?.payload;
            const cells = Array.from({ length: maxRound + 1 }, (_, i) =>
              path[i] != null ? `<td class="num${i && path[i] < path[i - 1] ? " down" : ""}">${money(path[i])}</td>` : `<td class="num muted">—</td>`,
            ).join("");
            const r = ranked.find((x) => x.supplier_did === t.supplier_did);
            const outcome = !path.length
              ? last?.kind === "refusal"
                ? "Could not meet the date"
                : "No price"
              : r?.eligible
                ? `Rank ${r.rank}${last?.final_offer ? ", at its floor" : ""}`
                : r?.reason ?? "Excluded";
            return `<tr data-party="${sid}"><td><span class="who">${mark(sid)}${esc(t.supplier_name)}</span></td>${cells}<td>${esc(outcome)}</td></tr>`;
          })
          .join("")}</tbody></table></div>`
    : "";
  const sv = savings(s);
  const limits = kv([
    ["Your ask (sent)", s.policy.target_unit_price != null ? money(s.policy.target_unit_price) : "—"],
    ["Walk-away (never sent)", s.policy.walk_away_unit_price != null ? money(s.policy.walk_away_unit_price) : "No limit"],
    ["Rounds used", `${s.round} of ${s.policy.max_rounds}`],
    ["Spec sheet answers", Object.keys(s.spec_answers).length ? esc(attrText(s.spec_answers)) : "None needed"],
    ["Saved by bargaining", sv && sv.total > 0 ? `<strong class="ok">${money(sv.total)}</strong>` : "—"],
  ]);
  return `${top}
  <div class="party-grid">
    <div class="party-main">
      ${guardBanner(ui)}
      ${bargaining}
      <h3 class="block-h">Conversations with suppliers</h3>
      ${questionBar(ui)}
      ${threads.length ? threads.map((t) => conversation(t, msgs, ui)).join("") : `<p class="view-empty">${s.status === "no_suppliers" ? "No supplier was contacted. The marketplace found no catalog for this part." : "No supplier contacted yet."}</p>`}
    </div>
    <aside class="party-side">
      <h3 class="block-h">Private limits</h3>
      <p class="side-note">Held only by the buyer. The ask goes out with each counter; the walk-away never does. The buyer only cites rival prices it holds as signed quotes.</p>
      ${limits}
      <h3 class="block-h">Own steps and search</h3>
      <ol class="msgs">${[...internal, ...marketReply].sort((a, b) => a.seq - b.seq).map((m) => messageRow(m, "buyer", ui)).join("")}</ol>
      ${
        threads.length
          ? `<h3 class="block-h">Eligibility check</h3>
      <div class="table-scroll"><table class="grid">
        <thead><tr><th scope="col">Supplier</th><th scope="col">Signature</th><th scope="col">Quote valid</th><th scope="col">Date met</th><th scope="col">Result</th></tr></thead>
        <tbody>${eligibility.join("")}</tbody></table></div>`
          : ""
      }
      ${decision(ui)}
    </aside>
  </div>`;
}

/* ---------- Marketplace ---------- */

function marketView(ui: Ui): string {
  const L = ui.ledgers.market;
  const top = head(
    "market",
    ui,
    L?.did,
    L?.role_line ?? "Matches confirmed request lines to published catalogs. Never sees prices.",
    `${ENDPOINTS.market}/market/ledger`,
  );
  if (!L) return `${top}<p class="view-empty">Loading the marketplace's records…</p>`;
  const part = ui.session?.lines?.part;
  const since = Date.parse(ui.session?.events[0]?.at ?? "") || 0;
  const entries =
    ui.showHistory || !part ? L.entries : L.entries.filter((e) => e.part === part && Date.parse(e.at) >= since);
  const older = L.entries.length - entries.length;
  return `${top}
  <div class="party-grid">
    <div class="party-main">
      <h3 class="block-h">Searches received</h3>
      ${
        entries.length
          ? `<div class="table-scroll"><table class="grid">
        <thead><tr><th scope="col">Time</th><th scope="col">Part asked for</th><th scope="col" class="num">Qty</th><th scope="col">Catalogs checked</th><th scope="col">Result</th></tr></thead>
        <tbody>${entries
          .map(
            (e) => `<tr>
          <td class="num">${clock(e.at)}</td>
          <td>${esc(e.part)}</td>
          <td class="num">${qty(e.quantity)}</td>
          <td>${e.catalogs_checked.map((c) => `${esc(c.name)} <span class="muted">(${esc(c.source === "live" ? "live catalog" : "registry")})</span>`).join(", ")}</td>
          <td class="${e.hits.length ? "" : "bad"}">${e.hits.length ? `Matched ${e.hits.map((h) => esc(h.name)).join(", ")}` : "No match"}</td>
        </tr>`,
          )
          .join("")}</tbody></table></div>`
          : `<p class="view-empty">No searches for this run yet.</p>`
      }
      ${older > 0 ? `<button type="button" class="ghost" data-action="history">Show ${older} earlier search${older > 1 ? "es" : ""}</button>` : ""}
      ${ui.showHistory && part ? `<button type="button" class="ghost" data-action="history">Show this run only</button>` : ""}
    </div>
    <aside class="party-side">
      <h3 class="block-h">Published catalogs</h3>
      <p class="side-note">Read live from each supplier's public agent description. The marketplace never sees prices, contracts or quotes.</p>
      <div class="table-scroll"><table class="grid">
        <thead><tr><th scope="col">Supplier</th><th scope="col">Item</th><th scope="col">Attributes</th></tr></thead>
        <tbody>${L.catalogs
          .flatMap((c) =>
            c.offers.map(
              (o) => `<tr data-party="${supplierId(c.name)}">
            <td><span class="who">${mark(supplierId(c.name) as SupplierId)}${esc(c.name)}</span></td>
            <td class="item">${esc(o.name)}<br /><span class="sku">${esc(o.sku)}</span></td>
            <td>${esc(attrText(o.attributes))}</td></tr>`,
            ),
          )
          .join("")}</tbody></table></div>
    </aside>
  </div>`;
}

/* ---------- Supplier ---------- */

function entryBlock(e: SupplierEntry, msgs: Message[], name: string): string {
  if (e.type === "order") {
    return `<article class="entry">
      <header class="entry-head">
        <span class="entry-seq">No. ${seqsFor(msgs, { orderId: e.order_id })}</span>
        <strong>Order received</strong>
        <time class="num">${clock(e.at)}</time>
        <span class="${e.signature_ok ? "ok" : "bad"}">${icon(e.signature_ok ? "shield" : "shieldOff")}${e.signature_ok ? "Signature verified" : "Signature failed"}</span>
      </header>
      <div class="entry-cols">
        <div><h4>Received</h4>${kv([
          ["From", `<span class="mono">${esc(e.envelope.sender_did)}</span>`],
          ["Quote hash", `<span class="mono">${esc(shortHash(e.quote_hash))}</span>`],
          ["Nonce", `<span class="mono">${esc(e.envelope.nonce)}</span>`],
        ])}</div>
        <div><h4>Checks</h4><ol class="trace">
          <li>Quote hash looked up in ${esc(name)}'s own archive.</li>
          <li>Supplier, buyer identity and expiry rechecked from the stored quote.</li>
        </ol></div>
        <div><h4>Replied</h4>${kv([
          ["Result", `<span class="${e.accepted ? "ok" : "bad"}">${e.accepted ? "Accepted" : "Refused"}</span>`],
          ["Message", esc(e.message)],
        ])}</div>
      </div>
    </article>`;
  }
  const r = e.reply;
  const l = e.lines;
  let replied: Array<[string, string]> = [["Result", `<span class="bad">No reply: request rejected</span>`]];
  if (r?.kind === "quote") {
    const moved = r.previous_unit_price != null && (r.unit_price ?? 0) < r.previous_unit_price;
    replied = [
      ["Result", r.round ? (moved ? "Signed revised quote" : "Signed hold") : "Signed quote"],
      ["Unit price", `<strong>${money(r.unit_price ?? 0)}</strong> (${esc(r.price_basis)}${r.delivery === "expedited" ? " + expedite" : ""})`],
      ...(r.round && r.previous_unit_price != null
        ? ([["Previous offer", `${money(r.previous_unit_price)}${r.final_offer ? " · now best and final" : ""}`]] as Array<[string, string]>)
        : []),
      ["Lead time", `${r.lead_time_days} days${r.delivery === "expedited" ? " (expedited)" : ""}`],
      ["Valid until", clock(r.expires_at)],
      ["Quote hash", `<span class="mono">${esc(shortHash(r.quote_hash))}</span>`],
      ["Wording", r.phrasing_from_model ? "Amazon Nova" : "Code (model unavailable)"],
    ];
  } else if (r?.kind === "refusal") {
    replied = [
      ["Result", `<span class="bad">Signed refusal</span>`],
      ["Reason", esc(r.reason)],
      ["Wording", r.phrasing_from_model ? "Amazon Nova" : "Code (model unavailable)"],
    ];
  } else if (r?.kind === "question") {
    replied = [
      ["Result", `<span class="warn">Signed question</span>`],
      ["Asked for", esc(r.missing_attribute)],
      ["Wording", r.phrasing_from_model ? "Amazon Nova" : "Code (model unavailable)"],
    ];
  }
  return `<article class="entry">
    <header class="entry-head">
      <span class="entry-seq">No. ${seqsFor(msgs, { requestId: e.request_id })}</span>
      <strong>${e.counter ? `Counter-offer, round ${e.counter.round}` : e.negotiation ? "Answer received" : "Quote request received"}</strong>
      <time class="num">${clock(e.at)}</time>
      <span class="${e.signature_ok ? "ok" : "bad"}">${icon(e.signature_ok ? "shield" : "shieldOff")}${e.signature_ok ? "Signature verified" : "Signature failed"}</span>
    </header>
    <div class="entry-cols">
      <div><h4>Received</h4>${kv([
        ["From", `<span class="mono">${esc(e.envelope.sender_did)}</span>`],
        ["Part", esc(l?.part ?? "—")],
        ["Quantity", l ? qty(l.quantity) : "—"],
        ["Need-by", l ? `${l.need_by_days} days` : "—"],
        ["Attributes", esc(l ? attrText(l.attributes) : "—")],
        ...(e.counter
          ? ([
              ["Buyer asks", `<strong>${money(e.counter.target_unit_price)}</strong>`],
              ["Rival cited", e.counter.rival_unit_price != null ? money(e.counter.rival_unit_price) : "none"],
            ] as Array<[string, string]>)
          : []),
        ["Nonce", `<span class="mono">${esc(e.envelope.nonce)}</span>`],
      ])}</div>
      <div><h4>Price-book decision</h4><ol class="trace">${e.trace.map((t) => `<li>${esc(t)}</li>`).join("")}</ol></div>
      <div><h4>Replied</h4>${kv(replied)}${
        r?.note ? `<p class="injected">${icon("alert")}Injected into the note field: <q>${esc(r.note)}</q></p>` : ""
      }</div>
    </div>
  </article>`;
}

function supplierView(sid: SupplierId, ui: Ui): string {
  const L = ui.ledgers[sid];
  const top = head(sid, ui, L?.did, L?.role_line ?? "", `${ENDPOINTS[sid]}/ledger`);
  if (!L) return `${top}<p class="view-empty">Loading ${PARTIES[sid].name}'s records…</p>`;
  const s = ui.session;
  const msgs = buildMessages(s);
  const thread = s ? Object.values(s.threads).find((t) => supplierId(t.supplier_did) === sid) : undefined;
  const reqIds = new Set((thread?.replies ?? []).map((r) => r.request?.request_id).filter(Boolean));
  const orderId = s?.order?.order_id;
  const inRun = (e: SupplierEntry) =>
    e.type === "quote" ? reqIds.has(e.request_id ?? "") : Boolean(orderId && e.order_id === orderId);
  const entries = (ui.showHistory ? L.entries : L.entries.filter(inRun)).slice().reverse();
  const older = L.entries.filter((e) => !inRun(e)).length;
  let empty = "No run yet. Start one from the scenario bar.";
  if (s?.confirmed && !thread)
    empty = `Not contacted in this run. ${L.name}'s catalog does not list “${s.lines?.part}”, so the marketplace never returned it.`;
  else if (s && !s.confirmed) empty = "Nothing received. The request has not been confirmed yet.";

  const book = L.price_book
    .map(
      (b) => `<tr>
      <td class="item">${esc(b.name)}<br /><span class="sku">${esc(b.sku)}</span>${
        b.required_attribute ? `<br /><span class="warn">Requires ${esc(b.required_attribute)}</span>` : ""
      }</td>
      <td class="nowrap">List ${money(b.list_price)}${
        b.contract_price != null ? `<br />Contract ${money(b.contract_price)}` : ""
      }${b.volume_tiers.map((t) => `<br />${qty(t.min_qty)}+ at ${money(t.unit_price)}`).join("")}${
        b.floor_price != null ? `<br /><span class="floor">Floor ${money(b.floor_price)}</span>` : ""
      }</td>
      <td class="nowrap">${qty(b.stock_qty)} in stock<br />${b.lead_time_days}-day lead${
        b.expedite_lead_days != null
          ? `<br />Expedite ${b.expedite_lead_days} days, +${money(b.expedite_premium)}<br /><span class="floor">Fee floor +${money(b.expedite_premium_floor)}</span>`
          : ""
      }</td></tr>`,
    )
    .join("");

  const rogue = L.rogue
    ? `<div class="guard" role="status"><span class="g-icon">${icon("alert")}</span><div><p><strong>Compromised for this demo run.</strong> ${esc(L.name)} adds hidden instructions and a fake price to the free-text fields of its replies. Its signed numbers stay honest, so the buyer can still rank it.</p></div></div>`
    : "";
  return `${top}
  ${rogue}
  <div class="party-grid">
    <div class="party-main">
      <h3 class="block-h">Messages ${L.name} received and answered</h3>
      ${entries.length ? entries.map((e) => entryBlock(e, msgs, L.name)).join("") : `<p class="view-empty">${esc(empty)}</p>`}
      ${older > 0 && !ui.showHistory ? `<button type="button" class="ghost" data-action="history">Show ${older} message${older > 1 ? "s" : ""} from earlier runs</button>` : ""}
      ${ui.showHistory ? `<button type="button" class="ghost" data-action="history">Show this run only</button>` : ""}
    </div>
    <aside class="party-side">
      <h3 class="block-h">Private price book</h3>
      <p class="side-note">Only ${esc(L.name)}'s desk holds this. The buyer sees nothing but the signed reply. Floors are never disclosed; each counter moves ${Math.round((L.price_book[0]?.concession_rate ?? 0.5) * 100)}% of the way toward the floor. Sample data.</p>
      <div class="table-scroll"><table class="grid">
        <thead><tr><th scope="col">Item</th><th scope="col">Prices</th><th scope="col">Supply</th></tr></thead>
        <tbody>${book}</tbody></table></div>
      <h3 class="block-h">Contract accounts</h3>
      ${
        L.contract_buyers.length
          ? `<ul class="plain">${L.contract_buyers.map((d) => `<li class="mono">${esc(d)}</li>`).join("")}</ul>`
          : `<p class="side-note">None. Every buyer pays list or volume price.</p>`
      }
    </aside>
  </div>`;
}

export function partyView(p: PartyId, ui: Ui): string {
  if (p === "buyer") return buyerView(ui);
  if (p === "market") return marketView(ui);
  return supplierView(p, ui);
}
