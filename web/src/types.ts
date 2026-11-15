export type PartyId = "buyer" | "market" | "s1" | "s2" | "s3";

export type RequestLines = {
  part: string;
  quantity: number;
  need_by_days: number;
  attributes: Record<string, string>;
  notes: string;
};

export type StoryEvent = {
  id: string;
  at: string;
  mark: string;
  sentence: string;
  detail: Record<string, unknown>;
};

export type ReplyPayload = {
  kind: "quote" | "refusal" | "question";
  quote_id: string;
  supplier_did: string;
  sku: string;
  part_name: string;
  quantity?: number;
  unit_price?: number;
  price_basis?: "contract" | "list" | "volume";
  lead_time_days?: number;
  need_by_days?: number;
  meets_date?: boolean;
  expires_at?: string;
  missing_attribute?: string;
  reason?: string;
  delivery?: "standard" | "expedited";
  expedite_premium?: number;
  round?: number;
  opening_unit_price?: number | null;
  previous_unit_price?: number | null;
  final_offer?: boolean;
  phrasing: string;
  phrasing_from_model: boolean;
  note?: string;
};

export type CounterOffer = {
  round: number;
  target_unit_price: number;
  rival_unit_price: number | null;
  previous_quote_hash: string | null;
};

export type GuardFlag = {
  field: string;
  kind: "instruction" | "number";
  reason: string;
  text: string;
};

export type BuyerPolicy = {
  target_unit_price: number | null;
  walk_away_unit_price: number | null;
  max_rounds: number;
};

export type SentRequest = {
  request_id: string;
  url: string;
  lines: RequestLines;
  negotiation: boolean;
  counter?: CounterOffer | null;
  nonce: string;
  timestamp: string;
  body_digest: string;
};

export type Reply = {
  at: string;
  kind: ReplyPayload["kind"] | null;
  payload: ReplyPayload | null;
  signature_verified: boolean;
  quote_hash: string | null;
  check: {
    signature?: string;
    quote_hash?: string | null;
    discovery_url?: string;
    certificate_host?: string;
    recovered_did?: string | null;
    reply_nonce?: string;
    reply_timestamp?: string;
  };
  sentence: string;
  request?: SentRequest | null;
  guard?: GuardFlag[];
};

export type Thread = {
  supplier_did: string;
  supplier_name: string;
  public_url: string;
  description_url: string;
  matched_sku: string;
  recovered_did?: string;
  replies: Reply[];
  latest: Reply | null;
};

export type RankedQuote = {
  supplier_did: string;
  supplier_name: string;
  quote: ReplyPayload & { unit_price: number; lead_time_days: number; quantity: number };
  quote_hash: string;
  signature_verified: boolean;
  quote_valid: boolean;
  date_met: boolean;
  rank: number | null;
  eligible: boolean;
  reason: string;
};

export type MarketHit = {
  did: string;
  name: string;
  public_url: string;
  description_url: string;
  matched_sku: string;
  matched_name: string;
};

export type SessionState = {
  session_id: string;
  status: string;
  lines: RequestLines | null;
  policy: BuyerPolicy;
  spec_answers: Record<string, string>;
  round: number;
  confirmed: boolean;
  market_hits: MarketHit[];
  threads: Record<string, Thread>;
  ranking: {
    eligible: RankedQuote[];
    excluded: RankedQuote[];
    winner: RankedQuote | null;
    explanation: string;
    explanation_unavailable: boolean;
  } | null;
  approved_hash: string | null;
  approved_supplier: string | null;
  order: { accepted: boolean; order_id: string; message: string } | null;
  events: StoryEvent[];
  extract_unavailable: boolean;
};

export type EnvelopeFacts = {
  sender_did: string;
  url: string;
  timestamp: string;
  nonce: string;
  body_digest: string;
  key_id: string;
};

export type SupplierEntry =
  | {
      type: "quote";
      at: string;
      request_id: string | null;
      negotiation?: boolean;
      counter?: CounterOffer | null;
      request_flags?: GuardFlag[];
      rogue?: boolean;
      envelope: EnvelopeFacts;
      signature_ok: boolean;
      signature_check: string;
      lines: RequestLines | null;
      trace: string[];
      reply: (ReplyPayload & { quote_hash: string | null; reply_nonce: string }) | null;
    }
  | {
      type: "order";
      at: string;
      order_id: string | null;
      envelope: EnvelopeFacts;
      signature_ok: boolean;
      signature_check: string;
      quote_hash?: string;
      quote?: ReplyPayload | null;
      accepted: boolean;
      message: string;
    };

export type PriceBookRow = {
  sku: string;
  name: string;
  list_price: number;
  contract_price: number | null;
  volume_tiers: Array<{ min_qty: number; unit_price: number }>;
  stock_qty: number;
  lead_time_days: number;
  required_attribute: string | null;
  floor_price: number | null;
  concession_rate: number;
  expedite_lead_days: number | null;
  expedite_premium: number;
  expedite_premium_floor: number;
};

export type SupplierLedger = {
  rogue?: boolean;
  role: "s1" | "s2" | "s3";
  name: string;
  did: string;
  public_base: string;
  role_line: string;
  key_id: string;
  contract_buyers: string[];
  price_book: PriceBookRow[];
  entries: SupplierEntry[];
};

export type MarketEntry = {
  type: "search";
  at: string;
  part: string;
  quantity: number;
  catalogs_checked: Array<{ name: string; did: string; source: string }>;
  hits: MarketHit[];
  sentence: string;
};

export type MarketLedger = {
  role: "market";
  name: string;
  did: string;
  public_base: string;
  role_line: string;
  catalogs: Array<{
    name: string;
    did: string;
    description_url: string;
    source: string;
    offers: Array<{ sku: string; name: string; description: string; attributes: Record<string, string> }>;
  }>;
  entries: MarketEntry[];
};

export type Ledgers = {
  market: MarketLedger | null;
  s1: SupplierLedger | null;
  s2: SupplierLedger | null;
  s3: SupplierLedger | null;
};

export type ProbeTarget = "peer" | "public";

export type ProbeStep = {
  id: string;
  title: string;
  ok: boolean;
  detail: string;
  ms: number;
};

export type ProbeResult = {
  run_id: string;
  target: ProbeTarget;
  ad_url: string;
  started_at: string;
  finished_at?: string;
  ok: boolean;
  recorded: boolean;
  sdk: { client: string; auth_mode?: string };
  us: { did: string; key_type?: string; curve?: string; did_url?: string };
  them: {
    name?: string;
    did?: string;
    description?: string;
    protocol_version?: string;
    owner?: string;
    interfaces?: number;
  } | null;
  tools: Array<{ name: string; description?: string; params?: string[]; endpoint?: string }>;
  exchanges: Array<{ tool: string; request: unknown; response: unknown }>;
  proof: { peer_saw_did?: string; matches_ours?: boolean };
  steps: ProbeStep[];
};
