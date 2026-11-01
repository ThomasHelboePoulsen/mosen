# Swamp Machine improvement backlog

Review date: 12 October 2026. Baseline: app version 5.0.0; all 369 existing tests passed during the review. Additional isolated probes reproduced the confirmed issues below. This file records proposed work and completed maintenance; item statuses are updated as work is finished.

## How to use this file

Pick one numbered item and complete it independently. The order favors small, confirmed fixes first, followed by changes involving several callbacks. Optional ideas and admin performance work come later. This is an effort-first order, not a ranking of severity: item 07 can reassign a person's purchases and payment and deserves particular care.

Before implementation, read [the maintainer rules](.agents/mosen-maintainer.md) and [the repository guide](.agents/references/mosen-repo-guide.md). Recheck the current code and reproduce the issue: earlier items may change the relevant behavior. The proposals are starting points, and an agent should record any reason the proposed approach no longer makes sense.

For each item:

- Keep the change within that item's scope; avoid an unrelated refactor or new dependency.
- Use the existing database transaction and error-queue patterns. Preserve correctly shaped Dash pattern outputs on failures.
- Add focused regression coverage for confirmed bugs, then run the relevant tests with `.\.venv\Scripts\python.exe -m pytest ...`. Follow the repository's escalation instructions if the venv cannot launch in the sandbox.
- Update the item's status and record the change and verification when finished. Describe remaining uncertainty instead of marking an unverified fix complete.

Code locations below use file paths and function names. Function names are the primary references because line numbers will move as items are completed.

## User preferences and scope

- Expected trips have fewer than 300 users and fewer than roughly 16 purchases per user on average. Performance work should improve opening a basket, scanning products, checkout, and responsiveness during background work. Admin imports and exports may take longer.
- Product names must remain visible. A barcode may identify a component internally and may also be displayed alongside its name. Do not replace readable names with barcode-only labels.
- The preferred proposal for export rounding is to remove the optional whole-DKK rounding feature. Waste allocation has its own rounding rules; those are separate.
- Importing transactions is generally an administrator's responsibility. Keep proposed import safeguards narrow: prevent obvious invalid references or values that make ordinary app operations fail. Do not add a broad import-policy redesign.
- Failed checkout should keep the basket open, show the error, and preserve both pending data and the visible product list.
- Preserve offline operation, barcode/keyboard speed, and the locked-down kiosk behavior. Old database compatibility and migrations are not required by default.

## Work order

| Order | Item | Approximate scope | Evidence / priority |
| --- | --- | --- | --- |
| 01 | ~~Fix Reset data~~ | Small | **Done** |
| 02 | ~~Require unique product names~~ | Small | **Done** |
| 03 | ~~Protect early payments during direct user deletion~~ | Small | **Done** |
| 04 | ~~Remove optional payment-export rounding~~ | Small | **Done** |
| 05 | ~~Prevent product imports from removing purchased products~~ | Small | **Done** |
| 06 | ~~Preserve the visible basket after failed checkout~~ | Small to medium | **Done** |
| 07 | ~~Clear stale edit state on Create and Cancel~~ | Small to medium | **Done** |
| 08 | ~~Validate numeric values before table replacement~~ | Medium | **Done** |
| 09 | ~~Refresh settings after successful changes~~ | Medium | **Done** |
| 10 | ~~Make backups consistent without holding up buying~~ | Medium | **Done** |
| 12 | Show the current basket's price and item count | Small to medium | Optional usability idea |
| 17 | Validate transaction references once per batch | Medium | Deferred admin performance work |



## 12. Show the current basket's price and item count

**Status:** Open, optional. **Evidence:** The basket displays counts per product, while its header's bill describes previous purchases rather than the pending basket subtotal.

**Issue:** Users cannot easily check the total amount or total number of items they are about to buy.

**Example:** A person already owes approximately 20 DKK from earlier purchases and any waste estimate. They now scan two beers at 10 DKK each and one cola at 5 DKK. The existing header still describes that earlier bill, and the product list shows `2x: Beer` and `1x: Cola`. This proposal adds `Current basket: 3 items - 25.00 DKK`. The count includes every unit, not just the two different product types. The basket price excludes previous purchases and waste.

**Why it matters:** A combined price and count could help someone spot an extra scan or wrong multiplier before checkout. This is an optional convenience; no checkout or accounting bug has been demonstrated here.

**Cause:** `new_trans()` renders names and per-product counts without combined totals. `show_balance()` reads saved purchases and a waste estimate when the basket opens; it does not calculate the pending basket's price after each product scan.

**Proposed change:** Add a clearly labelled pending-basket subtotal and total item count, calculated from current products and the basket. Preserve the visible product names and distinguish this subtotal from the historical bill/waste preview. Derive it from current data without another full-history calculation on every product scan.

**Where:** `src/trans_layout.py`: `new_trans()`, `show_balance()`, `trans_modal()`.

**Acceptance:** Feedback updates for additions, multipliers and product removal, resets for a fresh basket, and remains correct after failed checkout. Check decimal prices and repeated products. Prerequisite: item 06. Relevant tests: `tests/test_open_trans_modal.py`; manually inspect layout and scan responsiveness.

## 17. Validate transaction references once per batch

**Status:** Deferred. **Evidence:** Importing 5,000 transactions took about 18 seconds; an isolated membership-set approach handled the same batch in about 0.07 seconds. This chiefly concerns imports.

**Issue:** Bulk transaction validation repeatedly obtains and converts the same user and product tables.

**Why it matters:** Large admin imports are unnecessarily slow. Normal checkout validates the new basket rows, so the bulk number does not establish a main-workflow problem.

**Cause:** Each transaction's existence checks call typed `get()` on both reference tables and build lists again.

**Proposed change:** If worthwhile, build user/product barcode sets once for each set/append batch under the existing lock, and validate rows using membership checks. Rebuild sets for every batch so edits/imports cannot leave stale reference state. Avoid permanent caches or a shared mutable validation context. Preserve all-or-nothing writes.

**Where:** `src/database/tables/transaction.py`: `is_valid_batch()`, `_validate_product_exists()`, `_validate_user_exists()`; batching in `src/database/tables/base_table.py`.

**Acceptance if implemented:** Valid and invalid batches behave identically; changing users/products affects the next batch; failed writes roll back. Profile ordinary checkout too and avoid regressing it. Relevant tests: `tests/test_constraints_and_atomicity.py`, `tests/test_transaction_atomicity.py`, `tests/test_transaction_rollback_behavior.py`, `tests/test_barcode_scan_performance.py`.

## Removed ideas

Items 11, 13, 14, 15 and 16 were removed from the active backlog on 12 October 2026. Remaining item numbers are unchanged.

- **11 - Scanning instructions:** No user confusion has been demonstrated. Extra guidance is optional UI work without an established need.
- **13 - Saved-purchase confirmation:** Successful checkout already closes the basket. An additional message has no demonstrated need.
- **14 - Persistent scanner visibility:** The fullscreen modal body already scrolls (`assets/bootstrap.css`). No failure on an actual laptop viewport has been reproduced.
- **15 - Browser scan investigation:** No lost or duplicated scan has been reproduced. Callback-only tests leave browser behavior unverified; check consecutive browser/scanner input when changing the scan flow rather than scheduling a speculative fix.
- **16 - Economy/payment aggregation:** The recorded speedup used 500 users and 30,000 purchases, beyond expected trips. No meaningful admin delay at realistic scale has been established; reconsider after measuring one.

## Performance evidence to retain

The existing purchase tests passed with histories of roughly 7,400-8,400 transactions, above expected usage. Their callback-workflow limits include 300 ms to open a basket, 100 ms for a product scan and 400 ms to submit. They do not measure the complete browser/scanner experience.

Additional isolated checkout probes at 300 users, 80 products and 4,500 transactions measured median core checkout times of about 74 ms for one item, 73 ms for five items and 109 ms for sixteen items. These measurements support prioritizing reliability and actual scan responsiveness over admin batch optimization. They are not latency guarantees for the trip laptop or its storage.
