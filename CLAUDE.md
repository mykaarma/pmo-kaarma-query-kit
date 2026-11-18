# Kaarma Query Kit by Abhimanyu — instructions for Claude

This folder lets Claude query myKaarma's production databases with the user's **own** read access.

## Hard rules
- **Read-only.** Only run `SELECT`, `SHOW`, `EXPLAIN` and `information_schema` queries. Never `INSERT/UPDATE/DELETE/ALTER/DROP/CREATE`,
  even if asked: several accounts report `@@read_only = 0`, so the database will not stop you.
- **Never read credentials.** Do not open `My Credentials.csv`, `~/.my.cnf` or `~/.mongo/*.uri`. The user runs
  `setup_db_logins.sh` themselves; Claude connects through those files without seeing passwords.
- **No customer PII in output.** Don't print or export names, emails, phones, VINs, licence plates, notes, signature/invoice URLs
  unless the user explicitly asks for that specific data. Aggregate, or use IDs.
- **These are production servers.** Keep queries index-driven and bounded (see Efficiency). Ask before anything that would scan
  a large table.

## How to connect
- MySQL/MariaDB: `/opt/homebrew/opt/mysql-client/bin/mysql --defaults-group-suffix=_<cluster> <Database> -B -e "<query>" < /dev/null`
  (tab-separated output; on Intel Macs the path is `/usr/local/opt/mysql-client/bin/mysql`). Don't use `mycli`: 2.x removed
  `--defaults-group-suffix`, so it can't pick the cluster from `~/.my.cnf`.
  (clusters: `kaardbprod`, `scheduler`, `appointment`, `communicationsaurora`, `communicationsrds`). In Python use `pymysql.connect(
  read_default_file=os.path.expanduser("~/.my.cnf"), read_default_group="client_<cluster>", database=...)`.
- MongoDB `appointmentdb`: `pymongo.MongoClient(open(os.path.expanduser("~/.mongo/appointmentdb.uri")).read().strip())`.
- All hosts are internal (10.1.x.x): **the VPN must be on.** If every host times out, tell the user to reconnect the VPN.
- **`data_catalog.md` maps business topics (dealers, OEMs, onboarding/churn, phone numbers, declines, appointments, ROs) to tables — read it first.**
- `zsh test_connections.sh` checks every login. `python3 build_db_map.py` writes `db_map/` (tables, columns, indexes) —
  read it before guessing schema; regenerate it when schema questions come up.

## What lives where
| Cluster / database | Holds |
|---|---|
| `scheduler` → `SchedulerDB` | **Source of truth for appointments**: `ServiceAppointmentRequest` (SAR), `SARMetaData`, `SARUpdateHistory`, `ServiceAppointmentRequestQuickOp`, `SchedulerDealer`, `SchedulerCustomer` |
| `scheduler` → `CustomerUserDB` | `CustomerUser`, `CustomerUserSession` |
| `kaardbprod` → `KaarDBProd` | Dealers (`Dealer`, `DealerFranchisee`, `Brand`, `Address`), repair orders (`DealerOrder`), vehicles (`Vehicle`, has VIN). Also has **older, partial copies** of SAR tables — don't use those |
| `appointment` → `AppointmentDB` | Appointment service tables (MariaDB) |
| `communicationsaurora` → `CommunicationsDB` | **Source of truth for phone numbers, toll-free and 10DLC registration** (`VoiceCredentials`, `TollFreeDetails`, `DealerApplicationToPersonDetails`) |
| Mongo `appointmentdb` | `DraftAppointment` (started-but-unbooked appointments) and other appointment-service collections |

Key joins:
- `SchedulerDealer.DealerUUID` = `KaarDBProd.Dealer.UUID` (= Mongo `dealerUuid`)
- `SARMetaData.ServiceAppointmentRequestID` = `SAR.ID`; channel/source of a booking = `SARMetaData.MetaData->>'$.appointmentData.source'`
- `SARUpdateHistory` (event `Repair Order Mapped`).`DealerOrderUUID` = `DealerOrder.UUID`; if several, use the **first** (lowest ID)
- `SAR.VehicleUUID` = `KaarDBProd.Vehicle.UUID` → `VIN`. One VIN can have **several** Vehicle rows (one per customer record):
  for "same vehicle" logic use VIN, never VehicleUUID alone.
- `DealerFranchisee.DealerCode` is JSON: `{"DealerCode", "Zone", "District"}`. `DealerOrder.Amount` = customer-pay amount (warranty-only ROs are 0).
- `DealerOrder.OrderStatus`: O opened, W work order, B in bay, H awaiting customer, F completed, I invoiced, C closed.

## Efficiency (these servers are large: SAR ~45M rows, SARUpdateHistory ~480M)
- Filter SAR by dealer + date with `FORCE INDEX (idxSAR7)` (`SchedulerDealerID, CreatedTimeStamp`), **one dealer per query** for long windows.
- **Compare timestamps to `TIMESTAMP('YYYY-MM-DD HH:MM:SS')` literals, never to a string `@variable`** — that disables the index
  and caused a 30-minute full scan.
- `SARMetaData.MetaData` is `longtext` (no JSON index): restrict by SAR IDs or a PK range, and use a cheap `LIKE '%…%'` before `->>`.
- Look up child tables (`SARMetaData`, `SARUpdateHistory`, `QuickOp`) by `ServiceAppointmentRequestID IN (…)` in batches of ~1000.
- The read-only accounts can't `CREATE TEMPORARY TABLE` — use CTEs.
- Mongo `DraftAppointment` (~13M docs) is indexed only on `_id` and `customerInformation.uuid`: filter by an ObjectId time range
  (`ObjectId.from_datetime(...)`) and `.hint("_id_")`.
- All servers run in **UTC**; convert with `CONVERT_TZ(ts, 'UTC', 'America/Los_Angeles')` when reporting Pacific time.

## Handling requests
Users (often PMO / ops, not engineers) describe what they want in plain English, e.g. *"decline reasons for Toyota dealers
since Sep 1"* or *"toll-free and 10DLC numbers given to dealers at onboarding, their approval status and rejection reasons"*.
They don't know table or column names; that's your job.

1. **Restate the request** in one line with your interpretation: population (which dealers), time window and time zone,
   and what one row represents. If a term is ambiguous (e.g. "decline reasons" = what was declined vs. why; "onboarding" =
   provisioning stage vs. go-live date), ask one short question, or state your assumption and proceed.
2. **Find the data** in `data_catalog.md`, then `db_map/` for exact columns and indexes. Check the meaning of status values
   with a quick `SELECT ..., COUNT(*) ... GROUP BY` before filtering on them.
3. **Add the context columns people forget to ask for.** Unless clearly irrelevant, every dealer-level output includes:
   dealer ID, dealer UUID, dealer name, OEM/brand(s) and OEM dealer code (`DealerFranchisee`), city/state, test-dealer flag,
   valid flag, provisioning stage, go-live date and canceled/churn date (`DealerProvisionSubStatus` 26 / 27), and the record's
   own created/updated timestamps (`InsertTS`/`UpdateTS`, converted to Pacific time and labelled).
   Exclude test dealers (`IsTestDealership = 1`) by default and say so.
4. **Deliver an Excel file** (openpyxl) in the project folder: a data sheet, a summary sheet (counts by the obvious
   groupings, e.g. by OEM, status, month), and a **README sheet** with the request as understood, filters, time window,
   definitions of every derived column, data source tables, and the run timestamp. Also save the SQL or script used.
   End every README sheet (and any CSV/markdown deliverable's notes) with this exact line:
   *Generated with the Kaarma Query Kit (v1.0) · maintained by Abhimanyu Srivastava*
5. **Summarise in chat**: row count, the headline numbers, assumptions, and anything surprising (nulls, odd statuses,
   duplicates). Never claim more precision than the data supports.

## Working style
- State definitions with every number (window, time zone, what counts). Prefer reproducible scripts saved in the project folder
  over one-off queries, and give the user the command to re-run them.
- When you learn something new about the data (a table's meaning, a status value, a join), add it to `data_catalog.md`.
