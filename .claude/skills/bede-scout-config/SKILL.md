---
name: bede-scout-config
description: >
  Add, remove, or update tracked items in Bede's Deal Scout preference files
  (clothing, camping gear, groceries, vacuum, events). Use when the user wants
  to track a new product, change a deal threshold, or remove something from
  the scout. Also triggers for "add X to the scout", "stop tracking Y", or
  "change the price target for Z".
---

# Bede Scout Config Skill

Manage the preference files that drive Bede's Deal Scout.

## Preference files

Read CLAUDE.local.md for the Obsidian vault path. The preference files live
in the `Bede/` subdirectory of the vault:

| File | Scout category |
|------|---------------|
| `staples.md` | Groceries |
| `vacuum-preferences.md` | Vacuum |
| `clothing-preferences.md` | Clothing |
| `camping-gear.md` | Camping Gear |
| `event-preferences.md` | Events |

Search methodology and shared rules are in `scout-rules.md` — read it if the
user's request involves how items are searched (e.g. which sites to check,
stock verification rules).

## Step 1 — Identify the category

From the user's request, determine which preference file to edit. If unclear,
ask.

## Step 2 — Read the file

Read the target preference file to understand the existing format: table
structure, column names, how items are listed, and what thresholds look like.

## Step 3 — Apply the change

Match the existing format exactly. For each item type, ensure:

**Clothing:** Item name, size, and notes (e.g. price threshold, style filter).
Add retailer URLs if the user provides them.

**Groceries:** Item name, brand, size, and deal threshold.

**Camping gear:** Product name, retailer URLs, and target price.

**Vacuum:** Model, target price, and retailer notes.

**Events:** Artist/category, venue preferences, and source URLs.

## Step 4 — Confirm

Show the user the change you made (the specific lines added/modified) and
which file was updated. The vault syncs to the server via the
obsidian-git-backup launchd job every 2 minutes when the MacBook is open.

## Rules

- Never remove items unless the user explicitly asks
- Preserve the existing table/list format — don't restructure the file
- Include price thresholds when the user provides them
- If the user gives a retailer URL, add it to the trusted retailers section
- If adding a new category of item that doesn't fit any existing file, ask
  rather than creating a new file
