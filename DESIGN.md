---
name: ANP Procurement Desk
description: One buyer agent sourcing a part from three supplier agents, shown as an exchange quote board.
colors:
  ink: "#0f1e2e"
  ink-raised: "#1d3247"
  ink-text: "#dfe7ee"
  ink-muted: "#a9b9c8"
  ground: "#eef2f5"
  sheet: "#ffffff"
  sheet-tint: "#f7f9fb"
  rule: "#cdd6de"
  rule-soft: "#e3e9ee"
  text: "#0f1e2e"
  muted: "#4f6274"
  trace-tint: "#e2e9f0"
  lead: "#1f7a4d"
  lead-ink: "#17633e"
  lead-wash: "#e7f5ed"
  lead-on-ink: "#2fbf71"
  warn: "#c47f17"
  warn-ink: "#8a5806"
  warn-wash: "#fcf2e0"
  warn-edge: "#f0d6a6"
  bad: "#b42318"
  bad-wash: "#fdeceb"
  bad-edge: "#f3c4bf"
  party-buyer: "#1d4ed8"
  party-market: "#0f766e"
  party-s1: "#b45309"
  party-s2: "#3f6212"
  party-s3: "#6b21a8"
typography:
  headline:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(20px, 2vw, 26px)"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
    fontVariation: "'wdth' 85"
  title:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "18px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
    fontVariation: "'wdth' 85"
  section-label:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "0.05em"
    fontVariation: "'wdth' 80"
  figure:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 650
    fontFeature: "'tnum'"
    fontVariation: "'wdth' 90"
  body:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "'tnum'"
  body-small:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "'tnum'"
  label:
    fontFamily: "Archivo, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "'tnum'"
  mono:
    fontFamily: "ui-monospace, SF Mono, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
rounded:
  edge: "3px"
  pill: "999px"
  mark: "50%"
spacing:
  hair: "4px"
  tight: "8px"
  base: "12px"
  block: "14px"
  section: "22px"
  page: "clamp(1rem, 2vw, 1.75rem)"
components:
  button-primary:
    backgroundColor: "{colors.lead}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.edge}"
    padding: "11px 18px"
  button-primary-hover:
    backgroundColor: "{colors.lead-ink}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.edge}"
    padding: "8px 12px"
  scenario-chip:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.text}"
    rounded: "{rounded.edge}"
    padding: "6px 14px"
  scenario-chip-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
  input:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.text}"
    rounded: "{rounded.edge}"
    padding: "10px 12px"
  top-bar:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ink-text}"
    height: "56px"
  seq-number:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.muted}"
    typography: "{typography.mono}"
    rounded: "{rounded.edge}"
    padding: "2px 6px"
  seq-number-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
  message-traced:
    backgroundColor: "{colors.trace-tint}"
  board-leader-row:
    backgroundColor: "{colors.lead-wash}"
    textColor: "{colors.lead-ink}"
  step-now:
    backgroundColor: "{colors.lead-wash}"
    textColor: "{colors.lead-ink}"
  tag-bad:
    backgroundColor: "{colors.bad-wash}"
    textColor: "{colors.bad}"
    rounded: "{rounded.edge}"
    padding: "4px 10px"
  tag-warn:
    backgroundColor: "{colors.warn-wash}"
    textColor: "{colors.warn-ink}"
    rounded: "{rounded.edge}"
    padding: "4px 10px"
  question-bar:
    backgroundColor: "{colors.warn-wash}"
    textColor: "{colors.text}"
    padding: "14px 16px"
  party-mark:
    rounded: "{rounded.mark}"
    size: "30px"
---

# Design System: ANP Procurement Desk

## Overview

**Creative North Star: "The Exchange Quote Board"**

The desk reads like a commodity exchange screen in daylight: an ink navy bar, a cool grey ground, and white ruled sheets that hold aligned columns of numbers. Every party has a lane, every message carries one sequence number that appears in both the sender's and the receiver's lane, and the quote board ranks live quotes in a ruled table. Density is high but quiet. The surface is calm, exact, and adult, and colour is spent only where it carries meaning.

Structure comes from 1px rules, not from containers. Sheets sit flush on the ground with a single hairline border; there are no cards, no rounded panels, and no elevation shadows. Headings are Archivo set narrow on its width axis, and every number in the product is tabular so columns line up across rows and lanes.

The build rejects the SaaS dashboard of cards, charts and sidebars, and the consumer chat app of bubbles and timestamps. Messages are ruled list rows, not bubbles.

**Key Characteristics:**
- Ink navy bar over a cool grey ground with white ruled sheets.
- Archivo narrowed for headings; tabular numerals everywhere.
- One green for the lead: the current step, the leading quote, the approve action, verified seals.
- Amber for questions, red for exclusions and failures.
- Party colours live only in drawn marks and lane headers.
- Square-shouldered geometry: 3px corners, circles only for marks and step dots.

## Colors

A cool, desaturated navy-grey field with three meaning-bearing hues (green, amber, red) and five party hues held strictly to identification.

### Primary
- **Settlement Green** (lead): the single signal for "this is the one". The current step in the process rail, the leader row on the quote board, the approve button, verified signature seals, the "Ranked" message title, focus outlines and the text caret. Its ink variant (lead-ink) carries green text on white and the button hover; its wash (lead-wash) fills the current step and the leader row.
- **Bar Green** (lead-on-ink): the brighter green used only for the selected tab underline on the ink bar, where Settlement Green would not read.

### Secondary
- **Query Amber** (warn): questions a supplier asks back. The question bar uses the amber wash with an amber edge; amber ink carries the question title and the "Question" tag.

### Tertiary
- **Exclusion Red** (bad): a quote that is out of the running or a step that failed. "No" in the need-by column, the "Declined" tag, a failed step, an invalid seal, the error strip. Always paired with a word or icon, never colour alone.

### Party colours
- **Buyer Blue**, **Marketplace Teal**, **S1 Rust**, **S2 Olive**, **S3 Violet**: identification only. They colour the ring and initials of each party's drawn mark and the lane header name. Nothing else.

### Neutral
- **Desk Ink** (ink): the top bar, pressed scenario chips, pressed sequence numbers, completed step dots, and body text.
- **Raised Ink** (ink-raised): count pills inside the bar.
- **Bar Text / Bar Muted** (ink-text, ink-muted): tab labels and the bar note on ink.
- **Cool Ground** (ground): the page behind every sheet.
- **Sheet / Sheet Tint** (sheet, sheet-tint): white working surfaces; the tint marks a focused lane and the "N earlier messages" line.
- **Rule / Soft Rule** (rule, rule-soft): sheet borders and header rules; row dividers inside sheets.
- **Slate Muted** (muted): secondary text, column headers, field labels. Passes AA on white.
- **Trace Tint** (trace-tint): a neutral navy wash on a traced message row, in both lanes.

### Named Rules
**The Green Means Lead Rule.** Green marks the leading or next-to-act thing and verified state: current step, leader row, approve action, verified seal, focus. It is never decoration, never a section accent, never a second "success" theme.

**The Marks-Only Rule.** Party colours appear only in party marks and lane header names. Rows, tables, backgrounds and buttons stay neutral, so the semantic hues are never confused with identity.

**The Neutral Trace Rule.** Tracing a message highlights it with the neutral navy trace tint, not green, because a trace is a reading aid, not a verdict.

## Typography

**Display Font:** Archivo (variable, width 75–100, weight 400–700), falling back to system-ui
**Body Font:** Archivo, same family
**Label/Mono Font:** ui-monospace stack for sequence numbers, SKUs, run ids and hashes

**Character:** One grotesque doing everything, with the width axis carrying hierarchy: headings and section labels are set narrow (80–90%), body runs at full width. Tabular numerals are on at the body level so prices, times and totals align in columns.

### Hierarchy
- **Headline** (650, clamp 20–26px, 1.2, width 85%): the request title in the strip. Party view titles step up to 24px.
- **Title** (650, 17–18px, 1.2): the decision headline and conversation heads.
- **Section label** (650, 15px, uppercase, 0.05em, width 80%): section headings such as Message Lanes and Quote Board; they are the heading itself, always followed by a plain-sentence note. Lane names use the same treatment at 14px, 0.04em, in the party colour.
- **Figure** (650, 20px, width 90%, tabular): unit prices on the quote board; rank at 16px.
- **Body** (400, 15px, 1.45): default text; decision prose capped at 70ch.
- **Body small** (400, 13.5px): message titles (600), notes, hints, scenario chips.
- **Label** (400, 12–12.5px): field and fact labels, column headers (500), message detail lines.
- **Mono** (12–13px): sequence numbers, SKUs, hashes.

### Named Rules
**The Tabular Everywhere Rule.** Numerals are tabular on the body, so any number in any column lines up. Never switch to proportional figures for a price or a time.

**The Width-Not-Weight Rule.** Hierarchy comes from the width axis and size before weight. Headings narrow to 80–90%; weights stay between 400 and 650.

## Layout

A full-width desk, not a centred column. The page gutter is fluid (clamp 1rem → 1.75rem) and every sheet aligns to it. The first viewport stacks: sticky 56px ink bar with tabs, scenario bar, request strip with the seven-step process rail, five message lanes, then the quote board and decision.

- **Lanes:** a five-column grid, the Buyer lane wider (1.35fr against 1fr). Lane message lists clamp to clamp(9rem, 24vh, 14rem), or 7.25rem on short viewports, and scroll inside the lane. When rows are scrolled past, a full-width "N earlier messages" line appears at the top of the lane, counting only whole rows; choosing it scrolls the lane back up.
- **Process rail:** seven equal cells divided by soft rules, bleeding to the sheet edges.
- **Quote board:** a ruled table, numeric columns right-aligned, the "Why" column free to wrap.
- **Party views:** a head band (mark, identity, facts), then a 1.4fr / 1fr main and side grid.
- **Rhythm:** 8px inside controls, 12px between fields, 14px between stacked blocks, 22px before a party view's section heads.
- **Responsive:** at 1280px the bar note hides; at 1100px lanes wrap to three columns; at 1020px the party grid and decision go single-column and the rail splits 4 + 3; at 720px and below the tabs become a 3-column grid under the brand, the quote board moves above the lanes, each board row becomes a stacked block of labelled cells (three per line, supplier and reason spanning the row), lanes stack to one column, and the rail splits into two columns.

## Elevation & Depth

Flat. Depth is tonal and ruled: ink bar, grey ground, white sheets, hairline borders. There are no elevation shadows anywhere. The only box-shadows are state: a 3px pale ring on a focused input, and a green pulse ring on the step that is working.

### Named Rules
**The Ruled Sheet Rule.** A container is a white sheet with a 1px rule border flush on the ground. No shadow, no radius, no card stacking. Inside, rows are divided by the soft rule.

## Shapes

Square-shouldered. Controls, inputs, tags and sequence numbers take a 3px corner; sheets and tables take none. Circles are reserved for party marks (a coloured 2px ring around initials, 24–56px) and step dots in the rail. Count pills in the bar are the one fully rounded capsule. Icons are authored 24-grid line SVGs at 1.8 stroke with round caps, drawn at 16px in currentColor.

## Components

### Buttons
Plain and decisive.
- **Shape:** gently squared (3px).
- **Primary:** Settlement Green fill, white 600 text, 11px × 18px. Used for the one forward action at a gate: confirm the request, approve the exact quote.
- **Hover / Focus:** hover darkens to lead-ink over 0.2s; focus shows a 2px green outline offset 2px.
- **Ghost:** transparent with a 1px rule border, 8px × 12px, 13.5px text; hover turns the border ink. Icon-only ghosts are 8px square and always carry an aria-label.
- **Disabled:** 60% opacity with a progress cursor.

### Chips (scenario bar)
- **Style:** white with a 1px rule border, 3px corner, 6px × 14px, 13.5px.
- **State:** pressed fills Desk Ink with white text; hover darkens the border to ink.

### Cards / Containers
- **Corner Style:** square.
- **Background:** white sheet on Cool Ground.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** 1px rule outside, 1px soft rule between rows.
- **Internal Padding:** 12–18px depending on density.

### Inputs / Fields
- **Style:** white, 1px rule border, 3px corner, 10px × 12px; textareas at 16px. Labels sit above in 13px muted.
- **Focus:** border goes ink and a 3px pale navy ring appears; the caret is green.

### Navigation
- **Style:** tabs on the ink bar, 14px Bar Muted text with a party mark and a count pill.
- **States:** hover goes white; selected is white with a 2px Bar Green underline.
- **Mobile:** at 720px and below the tabs form a centred 3-column grid and count pills hide.

### Process Rail (signature)
Seven cells with a numbered 24px step dot. Done: ink dot with a check. Now: green dot and green-washed cell with 600 green text. Working: the green dot pulses. Failed: red dot and red-washed cell.

### Message Lane (signature)
A lane header with the party mark and the uppercase party name in its colour, then ruled message rows. Each row is a four-area grid: mono sequence button, direction arrow, a 13.5px 600 title with the peer in 400 muted, a 12.5px muted detail line, and a seal icon. Row titles take tone colour: green for the lead, amber for questions, red for exclusions. Choosing a sequence number presses it to ink, tints that message in both lanes with the trace tint, and dims every other message to 45%. Choosing a lane header focuses that lane on the sheet tint and dims the others to 38%. New rows arrive with a 4px rise and fade (0.45s, expo-out ease).

### Quote Board (signature)
A ruled table: rank, supplier with mark, reply tag, unit price as a figure, basis, lead time, need-by, seal, validity, line total, gap to leader, and a plain-sentence reason. The leader row takes the green wash and green figures, settling in from a deeper green over 1.2s. Refusals and questions are never ranked; their price cell drops to muted 15px.

### Question Bar
Amber wash with an amber edge, a question icon, the supplier's question as a sentence, and an inline field for the answer.

### Decision
A ruled sheet under the board: the outcome as a title and sentence on the left, the exact line total, a locked hash in mono and the approve button on the right.

## Do's and Don'ts

### Do:
- **Do** build every container as a white sheet with a 1px rule border on the cool grey ground.
- **Do** keep numerals tabular and right-align numeric columns.
- **Do** narrow headings on the Archivo width axis (80–90%) instead of adding weight.
- **Do** spend green only on the lead: current step, leader row, the approve action, verified seals and focus.
- **Do** pair every colour signal with a word or icon (Yes / No, Verified, Declined, a check or cross).
- **Do** clamp lane lists by whole rows and show the "N earlier messages" line when rows are hidden.
- **Do** use authored line SVG icons at 16px in currentColor.
- **Do** honour reduced motion: all animation and transition stop.

### Don't:
- **Don't** use cards, rounded panels or drop shadows for structure.
- **Don't** put party colours on rows, backgrounds, buttons or tables; they belong to marks and lane headers.
- **Don't** use green for a trace highlight, a section accent or decoration.
- **Don't** render messages as chat bubbles or add avatars beyond the party mark.
- **Don't** use corners larger than 3px on controls; circles are only for marks, step dots and count pills.
- **Don't** set a heading as a small label above another heading; section labels are the heading.
