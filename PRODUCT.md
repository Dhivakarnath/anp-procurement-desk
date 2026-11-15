# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: Python 3.12 and FastAPI for the Buyer, the marketplace, and suppliers S1, S2, and S3. The desk is hand-built with Vite, TypeScript, and CSS, with no component library. Frontend stack was left open; backend language was already fixed.

## Users

A person watching a live procurement, and the person who types the request and approves the order. They are at a desk, in ordinary daylight, and they need to see what each party did without reading a log.

## Product Purpose

Show one buyer finding suppliers it does not already know, talking with each of them, and placing an order only after a person confirms the request and approves the winning quote. Success means a visitor can point at the screen and say who was found, what each supplier answered, which quote ranked first, and why.

## Positioning

The buyer starts knowing only the marketplace. Suppliers appear because a search matched their catalogs. Price, lead time, and the winner come from each supplier's own data and from fixed checks. The models phrase language. They do not set the price or pick the winner.

## Operating Context

Docker Compose runs the marketplace, Buyer, S1, S2, and S3, Postgres, and Redis behind local HTTPS names. Temporary AWS credentials are exported in the terminal and read by boto3. The only AWS call is Bedrock Converse. The Buyer uses Haiku. The suppliers use Nova.

## Capabilities and Constraints

The Buyer searches the marketplace, then talks with each supplier on its own thread. A person confirms the extracted lines before anything is sent, and approves one exact quote before an order is placed. The Buyer can return to one supplier and change quantity, date, or a missing attribute. Ranking runs again on the latest valid quote from each supplier. A quote counts only when the signature verifies, the quote has not expired, and the lead time meets the requested date. The lowest such price wins. Catalog rows are sample data and must be labeled as sample data. There is no payment, no ERP, and no shared conversation among suppliers.

## Brand Commitments

Calm trading desk: quiet, exact, adult. The screen tells the story in order, with a distinct drawn mark for the Buyer, the marketplace, and each supplier. Not a SaaS dashboard of cards, charts, and sidebars. Not a consumer chat app of bubbles and timestamps.

## Evidence on Hand

Research notes in docs/. No customer quotes, no live catalogs, and no production orders. Sample catalogs are fixtures.

## Product Principles

Show the next step only after it has happened. Keep each supplier's reply on its own thread. Put the checks in sentences on the story, and keep the signature detail one action away. Let a person stop the process before a request is sent and before an order is placed. Treat sample catalog data as sample data.

## Accessibility & Inclusion

The story has to be readable without color as the only signal. Text contrast meets WCAG 2.2 AA. The flow works from the keyboard. Motion respects reduced-motion settings.
