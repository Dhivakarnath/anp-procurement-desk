import type {
  BuyerPolicy,
  Ledgers,
  PartyId,
  ProbeResult,
  ProbeTarget,
  RequestLines,
  SessionState,
} from "./types";

export type Mode = "desk" | "live";
export type View = "overview" | PartyId;

export type Ui = {
  mode: Mode;
  view: View;
  text: string;
  scenario: string | null;
  session: SessionState | null;
  draft: RequestLines | null;
  policy: BuyerPolicy | null;
  ledgers: Ledgers;
  ledgerErrors: Partial<Record<PartyId, string>>;
  busy: string | null;
  error: string | null;
  trace: number | null;
  focus: PartyId | null;
  answers: Record<string, string>;
  showHistory: boolean;
  seen: number;
  leader: string | null;
  liveTarget: ProbeTarget;
  liveResult: ProbeResult | null;
  liveError: string | null;
};

export const SCENARIOS = [
  {
    id: "bolts10",
    label: "Bolts, 10 days",
    text: "Need 2000 stainless steel hex bolts M8x40 within 10 days for assembly line 3.",
    note: "S1 holds a contract; S2 can only make the date by expediting at a premium. The buyer bargains both down to their floors.",
  },
  {
    id: "bolts30",
    label: "Bolts, 30 days",
    text: "Need 2000 stainless steel hex bolts M8x40 within 30 days.",
    note: "With 30 days S2 needs no expedite, so bargaining turns into a real contest with S1's contract price.",
  },
  {
    id: "seal",
    label: "Shaft seal, needs compound",
    text: "Need 300 shaft seals 45mm within 14 days.",
    note: "All three ask for the compound. The buyer answers FKM from its spec sheet, then plays S1 and S3 against each other.",
  },
  {
    id: "inject",
    label: "Prompt injection attempt",
    text: "Need 300 shaft seals 45mm within 14 days.",
    note: "S3 is compromised for this run: it hides instructions and a fake price in its replies. Watch the buyer flag them, quarantine S3, and award on signed numbers only.",
  },
  {
    id: "none",
    label: "Part nobody sells",
    text: "Need 50 titanium flange gaskets DN100 within 7 days.",
    note: "No catalog lists the part, so nothing is sent to any supplier.",
  },
] as const;

export function initialUi(): Ui {
  return {
    mode: "desk",
    view: "overview",
    text: SCENARIOS[0].text,
    scenario: null,
    session: null,
    draft: null,
    policy: null,
    ledgers: { market: null, s1: null, s2: null, s3: null },
    ledgerErrors: {},
    busy: null,
    error: null,
    trace: null,
    focus: null,
    answers: { compound: "FKM" },
    showHistory: false,
    seen: 0,
    leader: null,
    liveTarget: "peer",
    liveResult: null,
    liveError: null,
  };
}
