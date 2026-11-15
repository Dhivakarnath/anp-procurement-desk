import { icon } from "./icons";
import {
  PARTIES,
  PARTY_ORDER,
  boardRows,
  buildMessages,
  clock,
  esc,
  guardFlags,
  money,
  openQuestions,
  pricePath,
  qty,
  savings,
  seqLabel,
  shortHash,
  sparkline,
  type Message,
} from "./model";
import { mark } from "./shell";
import type { Ui } from "./state";
import type { PartyId } from "./types";

function direction(m: Message, p: PartyId): { name: "out" | "in" | "self" | "person"; text: string } {
  if (m.gate) return { name: "person", text: "Human decision" };
  if (m.to === null) return { name: "self", text: "Internal step" };
  if (m.from === p) return { name: "out", text: `Sent to ${PARTIES[m.to].name}` };
  return { name: "in", text: `From ${PARTIES[m.from].name}` };
}

export function messageRow(m: Message, p: PartyId, ui: Ui): string {
  const dir = direction(m, p);
  const other = m.to === null ? "" : m.from === p ? PARTIES[m.to].name : PARTIES[m.from].name;
  const traced = (ui.trace === m.seq ? " traced" : "") + (m.seq > ui.seen ? " fresh" : "");
  const flag = m.flagged ? `<span class="flag">${icon("alert", "Injected text flagged and ignored")}</span>` : "";
  const sig =
    m.verified === undefined
      ? ""
      : m.verified
        ? `<span class="ok">${icon("shield", "Signature verified")}</span>`
        : `<span class="bad">${icon("shieldOff", "Signature failed")}</span>`;
  const seal = flag || sig ? `<span class="seal">${flag}${sig}</span>` : "";
  return `<li class="msg tone-${m.tone}${traced}" data-seq="${m.seq}">
    <button type="button" class="seq" data-action="trace" data-seq="${m.seq}" aria-pressed="${ui.trace === m.seq}" aria-label="Trace message ${seqLabel(m.seq)}" title="Message ${seqLabel(m.seq)} at ${clock(m.at)}">${seqLabel(m.seq)}</button>
    <span class="dir dir-${dir.name}" title="${esc(dir.text)}">${icon(dir.name, dir.text)}</span>
    <span class="msg-title" title="${esc(m.title)}${other ? ` ${m.from === p ? "to" : "from"} ${esc(other)}` : ""}">${esc(m.title)}${other ? `<span class="msg-peer"> ${m.from === p ? "to" : "from"} ${esc(other)}</span>` : ""}</span>
    <time class="msg-time" datetime="${esc(m.at)}">${clock(m.at)}</time>
    <span class="msg-detail" title="${esc(m.detail)}">${esc(m.detail)}</span>
    ${seal}
  </li>`;
}

function laneEmpty(p: PartyId, ui: Ui): string {
  const s = ui.session;
  if (!s || !s.confirmed) return p === "buyer" && s ? "Waiting for you to confirm the request." : "Waiting for a confirmed request.";
  if (p === "market") return "Searching…";
  if (s.status === "no_suppliers") return "Not contacted. The marketplace found no catalog for this part.";
  if (p !== "buyer" && !Object.keys(s.threads).some((d) => d.includes(`${p}.test`)))
    return `Not contacted. ${PARTIES[p].name}'s catalog does not list this part.`;
  return "Waiting…";
}

function lanes(ui: Ui): string {
  const msgs = buildMessages(ui.session);
  return `<section class="lanes-wrap" aria-labelledby="lanes-h">
    <div class="sec-head">
      <h2 id="lanes-h">Message lanes</h2>
      <p class="sec-note">Each number is one message. It appears in the sender's lane and the receiver's lane. Select a number to trace it, or a party name to focus that party.</p>
    </div>
    <div class="lanes ${ui.trace || ui.focus ? "has-focus" : ""}">
      ${PARTY_ORDER.map((p) => {
        const mine = msgs.filter((m) => m.from === p || m.to === p);
        const focused = ui.focus === p ? " focused" : "";
        const dim =
          (ui.focus && ui.focus !== p) || (ui.trace && !mine.some((m) => m.seq === ui.trace)) ? " dim" : "";
        return `<div class="lane${focused}${dim}" data-party="${p}">
          <div class="lane-head">
            <button type="button" class="lane-focus" data-action="focus" data-party="${p}" aria-pressed="${ui.focus === p}">
              ${mark(p)}<span class="lane-name"><strong>${PARTIES[p].name}</strong><span>${PARTIES[p].role}</span></span>
            </button>
            <button type="button" class="ghost icon-only" data-action="view" data-view="${p}" aria-label="Open ${PARTIES[p].name} view" title="Open ${PARTIES[p].name} view">${icon("open")}</button>
          </div>
          ${
            mine.length
              ? `<button type="button" class="more" data-action="lane-top" hidden></button>
                 <ol class="msgs">${mine.map((m) => messageRow(m, p, ui)).join("")}</ol>`
              : `<p class="lane-empty">${esc(laneEmpty(p, ui))}</p>`
          }
        </div>`;
      }).join("")}
    </div>
  </section>`;
}

export function questionBar(ui: Ui): string {
  const qs = openQuestions(ui.session);
  if (!qs.length) return "";
  const attr = qs[0].latest?.payload?.missing_attribute || "detail";
  const names = qs.map((t) => t.supplier_name).join(", ");
  return `<form class="question" data-form="answer" data-attr="${esc(attr)}">
    <span class="q-icon">${icon("ask")}</span>
    <p><strong>${esc(names)} ${qs.length > 1 ? "need" : "needs"} the ${esc(attr)}</strong> before pricing. Your answer goes back as a signed counter-request to ${qs.length > 1 ? "each of them" : "that supplier"} only.</p>
    <label class="q-field">${esc(attr[0].toUpperCase() + attr.slice(1))}
      <input name="answer" value="${esc(ui.answers[attr] ?? "")}" required />
    </label>
    <button type="submit" class="primary" ${ui.busy ? "disabled" : ""}>${icon("send")}${ui.busy ? esc(ui.busy) : `Send to ${qs.length} supplier${qs.length > 1 ? "s" : ""}`}</button>
  </form>`;
}

export function guardBanner(ui: Ui): string {
  const hits = guardFlags(ui.session);
  if (!hits.length) return "";
  const first = hits[0];
  const flags = hits.flatMap((h) => h.reply.guard ?? []);
  const reasons = [...new Set(flags.map((f) => f.reason))];
  const note = first.reply.payload?.note || first.reply.payload?.phrasing || "";
  return `<div class="guard" role="status">
    <span class="g-icon">${icon("alert")}</span>
    <div>
      <p><strong>Prompt injection blocked.</strong> ${esc(first.thread.supplier_name)}'s signed replies carried text aimed at the buyer agent. The text was ignored and ${esc(first.thread.supplier_name)} is quarantined: no more counters, and it cannot win the award. Prices, dates and ranks come only from signed fields, and approval stays with you.</p>
      <blockquote>${esc(note)}</blockquote>
      <p class="g-reasons">${reasons.map((r) => `<span class="tag bad">${esc(r)}</span>`).join("")}</p>
    </div>
  </div>`;
}

function replyCell(kind: string | null | undefined, verified: boolean, flagged = false): string {
  if (flagged) return `<span class="tag bad">${icon("alert")}Flagged</span>`;
  if (!verified) return `<span class="tag bad">Rejected</span>`;
  if (kind === "quote") return `<span class="tag">Quote</span>`;
  if (kind === "refusal") return `<span class="tag bad">Declined</span>`;
  if (kind === "question") return `<span class="tag warn">Question</span>`;
  return `<span class="tag">—</span>`;
}

export function quoteBoard(ui: Ui): string {
  const s = ui.session;
  const rows = boardRows(s);
  let body: string;
  if (!s || !s.confirmed) {
    body = `<p class="board-empty">Quotes appear here once you confirm a request.</p>`;
  } else if (s.status === "no_suppliers") {
    body = `<p class="board-empty">No supplier's catalog lists “${esc(s.lines?.part)}”. Nothing was sent to S1, S2 or S3, so there is nothing to rank.</p>`;
  } else if (!rows.length) {
    body = `<p class="board-empty">Waiting for replies…</p>`;
  } else {
    body = `<div class="table-scroll"><table class="board">
      <thead><tr>
        <th scope="col">Rank</th><th scope="col">Supplier</th><th scope="col">Reply</th>
        <th scope="col" class="num">Opening</th><th scope="col" class="num">Final price</th><th scope="col">Price path</th>
        <th scope="col" class="num">Delivery</th><th scope="col">Meets ${s.lines?.need_by_days}-day need-by</th>
        <th scope="col">Signature</th><th scope="col">Valid until</th>
        <th scope="col" class="num">vs leader</th><th scope="col">Why</th>
      </tr></thead>
      <tbody>
      ${rows
        .map((r) => {
          const p = r.reply?.payload;
          const verified = Boolean(r.reply?.signature_verified);
          const price = p?.kind === "quote" ? money(p.unit_price ?? 0) : "—";
          const lead = p?.lead_time_days != null ? `${p.lead_time_days} days` : "—";
          const meets =
            p?.kind === "question" ? "Not priced" : p?.meets_date ? "Yes" : p ? "No" : "—";
          const path = pricePath(r.thread);
          const opening = path.length ? money(path[0]) : "—";
          const basis = p?.kind === "quote" ? `${p.price_basis}${p.delivery === "expedited" ? " + expedite" : ""}` : "";
          const moves = path.length - 1;
          const pathCell = moves
            ? `${sparkline(path, `Price path ${path.map((v) => money(v)).join(", ")}`)}<span class="path-note">${moves} move${moves > 1 ? "s" : ""}${p?.final_offer ? " · final" : ""}</span>`
            : p?.kind === "quote"
              ? `<span class="path-note">${s.policy.max_rounds ? "Not countered" : "Bargaining off"}</span>`
              : "—";
          const flagged = Boolean(r.thread.replies.some((x) => x.guard?.length));
          let why = r.ranked?.reason || r.reply?.check?.signature || "";
          if (r.leader) why = moves ? "Lowest price after bargaining" : "Lowest unit price among eligible quotes";
          else if (p?.kind === "refusal") why = p.reason || why;
          else if (p?.kind === "question") why = `Asked for ${p.missing_attribute} before pricing`;
          else if (r.ranked?.eligible) why = p?.final_offer ? "Eligible, hit its floor above the leader" : "Eligible, higher unit price";
          else if (r.ranked?.reason.includes("walk-away")) why = "Above your walk-away price";
          if (flagged && r.ranked?.eligible) why += ". Injected text ignored";
          const best = s.ranking?.winner?.quote.unit_price;
          const spread =
            r.leader ? "Leader" : p?.kind === "quote" && best != null ? `+${money((p.unit_price ?? 0) - best)}` : "—";
          const changed = r.leader && ui.leader !== r.thread.supplier_did ? " changed" : "";
          return `<tr class="${r.leader ? "leader" : ""}${changed} kind-${p?.kind ?? "none"}" data-party="${r.sid}">
            <td class="rank" data-label="Rank">${r.ranked?.eligible && r.ranked.rank ? r.ranked.rank : "—"}</td>
            <td class="sup" data-label="Supplier"><span class="who">${mark(r.sid)}${esc(r.thread.supplier_name)}</span></td>
            <td data-label="Reply">${replyCell(p?.kind, verified, flagged)}</td>
            <td class="num opening" data-label="Opening" title="${esc(basis)}">${opening}</td>
            <td class="num price" data-label="Final price">${price}</td>
            <td class="path" data-label="Price path">${pathCell}</td>
            <td class="num" data-label="Delivery">${lead}${p?.delivery === "expedited" ? `<span class="sub">expedited</span>` : ""}</td>
            <td class="${meets === "Yes" ? "ok" : meets === "No" ? "bad" : "muted"}" data-label="Meets need-by">${meets}</td>
            <td class="${verified ? "ok" : "bad"}" data-label="Signature">${verified ? `${icon("shield")}Verified` : `${icon("shieldOff")}Failed`}</td>
            <td class="num" data-label="Valid until">${p?.kind === "quote" ? clock(p.expires_at) : "—"}</td>
            <td class="num spread" data-label="vs leader">${spread}</td>
            <td class="why" data-label="Why">${esc(why)}</td>
          </tr>`;
        })
        .join("")}
      </tbody></table></div>`;
  }
  return `<section class="board-wrap" aria-labelledby="board-h">
    <div class="sec-head">
      <h2 id="board-h">Quote board</h2>
      <p class="sec-note">The buyer bargains each supplier toward your ask, citing the best signed rival price. Eligible means a verified signature, an unexpired quote, the date met and a price within your walk-away. Lowest final price wins.</p>
    </div>
    ${guardBanner(ui)}
    ${questionBar(ui)}
    ${body}
    ${decision(ui)}
  </section>`;
}

export function decision(ui: Ui): string {
  const s = ui.session;
  if (!s?.ranking) return "";
  const r = s.ranking;
  const w = r.winner;
  const negotiating = s.status === "negotiating" || s.status === "quoting";
  const source = r.explanation_unavailable ? "Written by code" : "Worded by Claude Haiku, numbers checked by code";
  let action = "";
  if (s.order) {
    const who = w?.supplier_name ?? "the supplier";
    action = `<div class="act ${s.order.accepted ? "ok" : "bad"}">
      <div><strong>${icon(s.order.accepted ? "check" : "cross")} ${s.order.accepted ? `Order accepted by ${esc(who)}` : "Order refused"}</strong>
      <span>${s.order.accepted && w ? `${qty(w.quote.quantity)} × ${esc(w.quote.part_name)} at ${money(w.quote.unit_price)}, total ${money(w.quote.unit_price * w.quote.quantity)}` : esc(s.order.message)}</span>
      <span class="mono">Order ${esc(s.order.order_id.slice(0, 8))}</span></div></div>`;
  } else if (w && s.approved_hash === w.quote_hash) {
    action = `<div class="act">
      <div><strong>Approved ${esc(w.supplier_name)} at ${money(w.quote.unit_price)}</strong>
      <span class="mono">${esc(shortHash(w.quote_hash))}</span></div>
      <button type="button" class="primary" data-action="order" ${ui.busy ? "disabled" : ""}>${ui.busy ? esc(ui.busy) : `Place signed order with ${esc(w.supplier_name)}`}</button></div>`;
  } else if (w && negotiating) {
    action = `<div class="act"><div><strong>Negotiation in progress</strong><span>Approval opens when the buyer finishes bargaining.</span></div></div>`;
  } else if (w) {
    action = `<div class="act">
      <div><strong>${esc(w.supplier_name)} · ${money(w.quote.unit_price)} × ${qty(w.quote.quantity)} = ${money(w.quote.unit_price * w.quote.quantity)}</strong>
      <span>You approve this exact quote. Its hash is locked; any change needs a new approval.</span>
      <span class="mono">${esc(shortHash(w.quote_hash))}</span></div>
      <button type="button" class="primary" data-action="approve" ${ui.busy ? "disabled" : ""}>${ui.busy ? esc(ui.busy) : `Approve ${esc(w.supplier_name)}'s quote`}</button></div>`;
  }
  const headline = w
    ? `${esc(w.supplier_name)} ${negotiating ? "leads" : "wins"} at ${money(w.quote.unit_price)} per unit`
    : openQuestions(s).length
      ? "Waiting on answers before anything can be ranked"
      : "No eligible quote";
  const sv = savings(s);
  const saved =
    sv && sv.total > 0
      ? `<p class="saved">${icon("down")}Bargained down from the best opening offer of ${money(sv.opening)}: <strong>${money(sv.total)} saved</strong> on ${qty(w!.quote.quantity)} units.</p>`
      : "";
  return `<div class="decision">
    <div class="decision-text">
      <h3>${headline}${negotiating ? `<span class="live">${s.round ? `Round ${s.round} in progress` : "Collecting quotes"}</span>` : ""}</h3>
      ${saved}
      <p>${esc(r.explanation)}</p>
      <p class="source">${source}</p>
    </div>
    ${action}
  </div>`;
}

export function overview(ui: Ui): string {
  return `${lanes(ui)}${quoteBoard(ui)}`;
}
