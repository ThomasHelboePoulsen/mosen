# Swamp Machine Repo Guide

## Domain

Swamp Machine/Mosemaskinen is a local trip purchase system. It is a Danish "stregsystem": a self-checkout/accounting system for trip purchases, combined with dashboards and graphs. Users and products are represented by barcodes. During trips, people scan purchases through the machine, admins update products/users/settings, and the app exports payment information at the end.

Operational assumptions:

- Trips use fresh data for each version; migrations and schema-compatibility shims are normally unnecessary.
- Laptops are weak and often offline.
- The app can run in a browser, but is usually run as a locked-down self-checkout where normal users should not casually exit the app.
- Runtime reliability matters more than broad extensibility.
- UI should be clear under stress and friendly to barcode scanner workflows.
- Users may read the screen from a distance while holding a scanner. Keep the purchase flow simple and check visual changes on smaller laptop viewports, including Windows display scaling, as well as wide monitors.

## Application Shape

- `main.py`: desktop entrypoint; starts Dash server and opens `pywebview`.
- `app.py`: creates the Dash app and initializes `Container` with `Database` and `TopUserChartData`.
- `src/main_layout.py`: main page, settings modal, top user chart modal, and layout-level callbacks.
- `src/main_page_callbacks.py`: settings uploads/downloads, payment export, edit/delete modal, backup, study users.
- `src/trans_layout.py`: transaction modal and barcode scanning flow.
- `src/modals.py`: modal body definitions for users, products, payments, settings dialogs.
- `src/tables/user_callbacks.py` and `src/tables/prod_callbacks.py`: create/edit callbacks for users/products and product stock.
- `assets/styling.css`: app-specific CSS. `assets/bootstrap.css` is vendor-style and should rarely be edited.

## Database Pattern

Use `Container.get(Database)` for DB access. Do not instantiate extra production `Database` objects or use `Connection` directly outside tests.

Tables live in `src/database/tables/`:

- `users`: `barcode`, `name`, `rank`, `team`, `is_guest`, `waste_cents`, `paid_cents`
- `prods`: `barcode`, `name`, `price`, `category`, `current_stock`, `initial_stock`
- `transactions`: `barcode_user`, `barcode_prod`, `timestamp`
- `temporary`: current transaction basket, `barcode_prod`, `name`
- `settings`: password/show bill/waste/backup/cache settings

`BaseTable.get_untyped()` returns string data from cache. `BaseTable.get()` returns typed columns. Public helpers like `get_users()` return untyped data; table internals often use typed data. Prefer typed data when adding new behavior or changing existing data logic.

`BaseTable.set()` replaces the whole table only after every row validates. `append()` also inserts only on full validation success. By default, append validation sees existing plus new rows; `TransactionTable` sets `_append_requires_existing_rows = False` because it validates individual transactions and their references. Only opt out when validation has no cross-row constraints. Avoid converting the full transaction history to records during checkout.

Users and products inherit `BarcodeTable`, which keeps a barcode membership index alongside the DataFrame cache. Use `db.barcode_exists()` or `contains_barcode()` for membership checks. Keep both caches refreshed together under the DB lock, including imports, reset, and rollback.

No migrations or schema-compatibility shims are expected by default. If schema changes are needed, update the table class, tests, and fresh DB behavior. Only add migrations or old-DB read fallbacks if the user explicitly says old trip databases must survive.

## Data Import

Importing full data sets is a common admin workflow and may happen at initial setup or later during a trip. Treat upload/import behavior as a first-class path.

Initial bootstrap imports may omit optional columns because the app can safely fill defaults. Later replacement imports are different: once optional fields have been set or maintained by the program, missing columns can accidentally overwrite meaningful state with defaults. For example, an initial user import may omit `is_guest`, but a later user export/edit/reimport should include it so guest flags are not silently reset.

In general:

- Keep optional columns optional for true first-load/bootstrap imports when defaults are safe.
- For replacement imports into non-empty tables, preserve existing optional values or require the import to include columns that may already contain meaningful data.
- Fill defaults through table definitions instead of scattered callback code.
- Add tests for both initial imports and later replacement imports when changing columns.
- Avoid making imports depend on current UI-only fields unless the table schema truly requires them.

## Transactions And Errors

Use:

- `@db_transaction_raises` when exceptions should propagate into `callback_with_error_queue`.
- `@db_transaction_result(fallback_values=...)` when callback error paths need shaped fallback outputs.
- `TransactionResult(..., commit=False)` when returning values but intentionally rolling back.

`callback_with_error_queue(num_outputs, ...)` appends one extra error queue output. Tests usually call the decorated callback and receive normal outputs plus the error output.

Important Dash gotcha: pattern-matching outputs such as `Output({"type": "user_input", "index": ALL}, "value")` need a list of outputs, even when returning `no_update`. Use `[no_update] * expected_count`, not a single `no_update`.

Audit success, no-op, validation-warning, and exception paths. `callback_with_error_queue`'s generic scalar fallbacks cannot supply the per-component list for an `ALL` output. Supply a correctly shaped tuple through `db_transaction_result(fallback_values=...)`, as in `update_settings` and `edit_new_data_modals`. Fallbacks apply when an error has no returned values; preserve explicit `Result`/`TransactionResult` values so intentional validation alerts still open. `MATCH` resolves one component and does not need an outer list per match.

## UI Patterns

Keep admin screens functional and dense. Avoid marketing-style layouts.

Tables should let admins see a full row where possible. Headers may wrap, but avoid horizontal scrolling unless truly necessary.

Modals under settings are nested in tab children. Do not rebuild settings tab children on passive tab render; rebuilding closes open modals.

Use `admin_data_revision` after successful writes that require refreshing admin tables or economy data; update existing component properties through that event. Keep failed saves open with their entered values and emit no success revision. Clear stale edit identity when starting a new form or cancelling/closing it. Checkout clears the basket only after successful persistence; opening the basket rebuilds its display from the DB in the same callback.

The economy refresh chain is `admin_data_revision` -> `update_settings_layout` -> `income_table_all_rows.data` -> `update_income_lookup`. The last callback owns both income and transaction table data, reads current transactions, and preserves the active search. When moving outputs, trace imports, edits, removals, and payment export through the whole chain; avoid a second writer overwriting filtered data.

Transaction removal pairs `derived_virtual_data` with `derived_virtual_selected_rows`, which share the full sorted/filtered ordering across native pages. Search changes reset pagination and clear transaction selection so an old row index cannot select a different transaction.

Graphs showing counts should use `src.analytics.bar_chart_format.format_count_bar_chart`: no x-axis title, y-axis title `amount`, integer y ticks. Hide x tick labels for charts whose x-axis is only a Plotly index.

## Money And Exports

Persist money-like per-user fields in cents:

- `paid_cents`: early/pre-settled payment; any positive amount marks the user fully settled, with zero remaining due
- `waste_cents`: allocated waste; `-1` means no persisted allocation yet

Display/export DKK amounts for people. Purchase totals use current product prices, so price edits revalue past purchases. Preserve the existing Python floating-point summation behavior when optimizing income calculations. Guests remain included.

Payment export uses Excel (`to_excel`) to avoid locale-dependent CSV decimal issues. Export amounts without rounding; admins round in Excel. A cleared "Add income" number field arrives as `None` and means zero. Keep `openpyxl` in `requirements.txt` and test real workbook output when touching exports.

Waste allocation lives in `src/analytics/waste_allocation.py`. Payment export recalculates and persists waste before exporting.

## Testing

Use the local venv:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_file.py
```

Do not substitute another Python interpreter for test runs. In the managed Codex sandbox this venv launcher may need escalated execution; if process launch fails, rerun the same venv command with escalation.

Run focused tests first:

- User create/edit/delete: `tests/test_user_callbacks.py`, `tests/test_edit_data_modals.py`
- Product create/edit/stock: `tests/test_prod_callbacks.py`
- Transaction flow: `tests/test_open_trans_modal.py`
- Payment/waste/export/economy: `tests/test_waste_allocation.py`
- Top buyer graph: `tests/test_top_user_chart.py`
- DB/table behavior: `tests/test_*table*.py`, `tests/test_data_connection.py`, transaction tests
- Barcode membership caches: `tests/test_barcode_table.py`, `tests/test_transaction_table.py`
- Scan/backup performance: `tests/test_barcode_scan_performance.py`, `tests/test_backup_performance.py`

Test fixtures usually create `Database(tmp_path / "...db")` and register it with `Container.set(Database, db)`. If code needs `TopUserChartData`, register it too.

Prefer minimal Arrange / Act / Assert tests. For small fixes, use a few explicit rows and obvious expected values, with one main behavior per test. Reuse fixtures and extend existing parametrized cases when that keeps the test clear. Avoid new harnesses, generated scenarios, or combined multi-behavior tests for a small regression.

Performance checks measure specific workflow phases, not necessarily browser rendering or transport. State what a reported timing includes. Run timing-sensitive checks without other suites or benchmarks competing for resources, including work from other agents. Trace and profile the failing path; check history before attributing a slowdown to a recent commit. Keep existing performance limits unless changing the target is explicitly part of the task. Repeated DataFrame filters or full-history conversions in loops are worth measuring before adding more caching or abstraction.

## Backups

Use `db.backup_to()` and the SQLite backup API. The backup uses a separate source connection to capture committed data and replaces its destination atomically. Preserve its separate backup lock so background copies do not hold the application DB lock. Avoid copying a live `.db` file directly or using the active transaction connection as the backup source.

Pre-import and pre-removal backups happen before writes and intentionally survive a later rollback. Relevant checks are in `tests/test_connection_transactions.py` and `tests/test_backup_performance.py`.

## Offline And Packaging

Avoid runtime network dependencies. Keep assets local under `assets/`. Be cautious with packages that make PyInstaller builds larger or more fragile.

Build command from `README.md`:

```powershell
pyinstaller -F -n "swampmachine.exe" --distpath "." --clean --icon "assets\favicon.ico" --add-data "assets:assets" --log-level=WARN main.py
```

The app blocks some keys and hides the taskbar in `main.py`; do not casually change this without considering the locked-down self-checkout use case.
