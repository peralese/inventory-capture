# Build prompt — Inventory Capture App (v1)

## Context
This is the first tool in a "Collectibles Suite" — a set of apps supporting an
auction-buying / eBay-reselling workflow. Three other tools already exist
(`auction_tracker`, `collectible_scout`, `ebay_tracker`) and currently run as
isolated islands with no shared item identifier. This new app is being built
standalone — it does NOT integrate with those tools yet. That decision is
deliberately deferred; do not add any code, config, or schema fields aimed at
future integration beyond keeping `item_id` stable and unique.

## Goal
Build the basis of a small, self-hosted "Inventory Capture" app that answers
one question: **what collectible items do I currently have, and where are
they?** It replaces a manual spreadsheet workflow. It will be used repeatedly
going forward — both to backfill existing inventory once, and to log every
new item acquired from future auctions.

## Stack
- Backend: FastAPI
- Database: SQLite
- Frontend: minimal server-rendered HTML (Jinja2) with basic forms — no SPA
  framework, no build step. This matches the simplicity level of other
  personal tools in this portfolio (e.g. `simple-task-tracker`).
- Single user, local-first. No authentication in v1.

## Schema
```sql
CREATE TABLE items (
    item_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    storage_location TEXT,
    availability_status TEXT NOT NULL DEFAULT 'In Stock',
    condition TEXT,
    photo_on_file INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Field defaults / conventions to implement
- `item_id`: auto-generated, sequential, zero-padded 4-digit string
  (`0001`, `0002`, ...), assigned server-side on insert — never user-entered.
  This continues the numbering convention already used in the source
  spreadsheet, so imported rows keep their existing IDs and new rows continue
  the sequence.
- `availability_status`: constrained to one of `In Stock`, `Reserved`,
  `Listed`, `Sold`, `Kept`. Enforce this as a dropdown in the form and
  validate server-side (reject other values).
- `photo_on_file`: boolean (0/1) only — no file path or upload handling in v1.
- `category`: free text for now (no fixed list).

## Required functionality
1. **Add item form** — name (required), category, storage_location,
   availability_status (dropdown, defaults to "In Stock"), condition,
   photo_on_file (checkbox), notes. Server assigns `item_id` on submit.
2. **Edit item form** — same fields, pre-filled, for an existing `item_id`.
3. **List / filter view** — table of all items, filterable by
   `availability_status` and `storage_location`. This is the primary "what do
   I have and where" screen.
4. **Quick status/location update** — a fast inline edit path (e.g. an
   editable dropdown/field directly in the list view, not a full-page form)
   for changing just `availability_status` or `storage_location` on an
   existing item. This will be the most frequently used action once the app
   is in daily use, so it should take one or two clicks, not a full form
   round-trip.
5. **One-time CSV/XLSX import** — a script or route to bulk-load existing
   inventory rows from a spreadsheet export into the `items` table, preserving
   `item_id` values already assigned in that source file. This only needs to
   run once against the existing data; it does not need a polished UI.

## Explicitly out of scope for this build
- Any integration with `auction_tracker`, `collectible_scout`, `ebay_tracker`,
  or `bibliopole`.
- Acquisition fields (date, source, cost) or sale fields (listing platform,
  price, sold date, fees, profit) — those belong to other tools and are not
  part of this schema.
- Authentication/login.
- Photo upload/storage — boolean flag only.
- Deployment configuration (hosting, tunneling, process supervision) — local
  dev only for this pass.

## Verification
- Confirm the app runs locally (`uvicorn` dev server) and all four
  functional pieces (add, edit, list/filter, quick update) work against a
  fresh SQLite file.
- Confirm the import script correctly loads the sample row(s) from the
  existing spreadsheet without ID collisions, and that a newly added item via
  the form gets the next sequential `item_id`.
- Flag, but do not resolve, any schema or UX decisions you're unsure of —
  surface them back to me rather than guessing silently.
