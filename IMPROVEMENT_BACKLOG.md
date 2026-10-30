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
| 08 | Validate numeric values before table replacement | Medium | Confirmed bug in shared table logic |
| 09 | Refresh settings after successful changes | Medium | Confirmed callback/design issue |
| 10 | Make backups consistent without holding up buying | Medium | Confirmed unsafe copy; implementation proposal |
| 12 | Show the current basket's price and item count | Small to medium | Optional usability idea |
| 17 | Validate transaction references once per batch | Medium | Deferred admin performance work |


## 08. Validate numeric values before table replacement

**Status:** Open. **Evidence:** A quoted CSV price of `"12,50"` committed successfully, then typed product reads raised a conversion error.

**Issue:** Import validation can accept values that the application cannot subsequently read using its declared column types.

**Why it matters:** One bad numeric cell can leave checkout, product editing or stock handling failing until the data is repaired.

**Cause:** `BaseTable.is_valid_batch()` checks required fields, columns, duplicate primary keys and barcode validity, but not ordinary numeric types. `get()` performs conversion later, after replacement has committed.

**Proposed change:** Validate declared numeric conversions before any replacement/insertion. Reject non-finite numbers and fractional values for integer columns; fill optional defaults before checking them. Return useful bad rows and preserve the previous table on failure. Reject unsupported decimal formats clearly rather than silently guessing a locale. Respect valid sentinels such as `waste_cents=-1` and legitimately negative current stock; do not add unrelated domain restrictions.

**Where:** `src/database/tables/base_table.py`: `is_valid_batch()`, `set()`, `append()`, `get()`; `src/database/tables/column.py`; product/user column definitions.

**Acceptance:** Malformed numbers, infinity and fractional integer fields fail before writes; typed reads continue working. Valid numeric inputs, optional defaults and existing sentinel values still round-trip. Check both replacement and append. Relevant tests: `tests/test_column_system.py`, `tests/test_product_table.py`, `tests/test_product_table_properties.py`, `tests/test_main_page_callbacks.py`, transaction/atomicity tests affected by shared validation.

## 09. Refresh settings after successful changes

**Status:** Open. **Evidence:** A passive tab event requests a one-second sleep and rebuilds all three data tabs, including their nested modals.

**Issue:** Settings refresh can close/reset forms and can read data before the operation that triggered it has completed.

**Why it matters:** Typed input may disappear, failed saves become hard to correct, and tables can display stale values. The arbitrary delay also makes admin interactions slower.

**Cause:** `update_settings_layout()` listens to button clicks and passive UI events, guesses that writes finish within one second, then replaces whole tab children. Forms, modals and state stores are nested in those children.

**Proposed change:** Keep forms, action controls, search input and modals mounted. Emit unique change revisions from successful mutation callbacks, with the response returned after commit. Use those revisions to refresh table data/tooltips, income backing rows, waste figures and a small economy-summary container. Refresh on settings opening to capture purchases since the previous visit. Populate stock rows and study-user choices when their dialogs open. Remove the sleep and whole-tab replacement.

**Dependencies and cautions:** Revalidate items 02, 06 and 07 after this change. Item 07 added `form_save_revision` for successful user/product saves and removed the unrelated `confirm_new_stock` trigger from product saving; extend that success-driven approach to the remaining mutations. `update_settings.data=True` currently also occurs after invalid imports roll back, so it is not a reliable success signal. Payment export can commit while displaying a warning; such committed changes still need refresh. Failed saves should preserve the open form and its input. Handle tables that were initially empty as well as table columns and tooltips.

**Where:** `src/main_layout.py`: `update_settings_layout()`, the settings layout builders; mutation callbacks in `src/main_page_callbacks.py` and `src/tables/`; existing `transaction_removal_revision` demonstrates part of the approach.

**Acceptance:** Switching tabs does not close or clear forms. Successful writes update all affected views; failed writes preserve input. Reopening settings after purchases shows current data. Stock saves do not replay product creation. Verify the interaction in a browser as well as focused callback tests. Relevant tests: `tests/test_main_page_callbacks.py`, `tests/test_edit_data_modals.py`, `tests/test_user_callbacks.py`, `tests/test_prod_callbacks.py`, `tests/test_waste_allocation.py`.

## 10. Make backups consistent without holding up buying

**Status:** Open. **Evidence:** Copying an isolated SQLite database during a write captured a mixture containing changes that were subsequently rolled back.

**Issue:** Periodic backups copy the live database file without coordinating with writes, so a backup may not represent a valid committed trip state.

**Why it matters:** Recovery files must be trustworthy, while background backup work should avoid noticeable scan/checkout delays.

**Cause:** `create_database_backup()` uses `shutil.copy()`. The periodic callback does not participate in the database lock. A global lock around the entire copy would serialize it safely within this app, but a purchase arriving during the copy would wait.

**Proposed change:** Put a native SQLite backup helper in the existing database/connection layer. Periodic backups should use a fresh dedicated source connection and incremental backup, with a separate backup mutex preventing overlap. Avoid holding the app-wide lock through the entire periodic backup. Publish the filename only after successful completion and clean up incomplete output on failure. Pre-import and pre-deletion snapshots should remain blocking under the existing transaction lock and complete before the first write.

**Cautions:** Do not use `Connection.connect()` to obtain the backup source inside a transaction: it may return the active write connection. Backing up a source connection with its own uncommitted write can self-block. Short SQLite read locks still occur; do not promise zero latency. Use no new dependency. See the [SQLite online backup documentation](https://www.sqlite.org/backup.html).

**Where:** `src/main_page_callbacks.py`: `create_database_backup()`, `backup_database()`, pre-import and transaction-removal call sites; `src/database/data_connection.py`; `src/database/connection.py`.

**Acceptance:** Concurrent purchases and periodic backups produce readable snapshots of committed data, without errors or overlap. A failed backup is not advertised as complete. A required pre-action backup failure prevents that action. Existing pre-import/deletion snapshot tests still pass. Measure purchase latency with backups active on realistic data; the review's 176 KB database took roughly 6-8 ms to back up on one machine, not a target-laptop guarantee.

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
