# Kaarma Query Kit by Abhimanyu

*Ask myKaarma's databases questions in plain English, from Claude.*

Set-up takes about 15 minutes. Afterwards you can ask Claude things like *"which dealers went live last month, by OEM?"* and it
queries the databases directly, read-only, with **your own** access.

## Before you start
1. **Your own database logins.** Ask the DBA / platform team for read-only accounts on the servers below (request
   **SELECT-only** grants). Never use someone else's credentials — every query is logged against the account that ran it.
2. **VPN on.** All database hosts are internal; nothing connects without the VPN.
3. **Homebrew** installed on your Mac (https://brew.sh).

## 1. Get the kit
Copy the `db-access-kit` folder to your Mac (for example `~/Documents/db-access-kit`) and open that folder in Claude Code.
Claude reads `CLAUDE.md` there automatically (the rules: read-only, no PII, efficient queries) and uses `data_catalog.md` to find data.
It starts fresh: no history from anyone else's sessions.

## 2. Install the tools
```bash
zsh install_tools.sh
```
Installs `mycli`, `mysql-client`, `mongosh` and the Python libraries `pymysql`, `pymongo`, `openpyxl`.

## 3. Add your credentials (you do this, not Claude)
1. Copy `credentials_template.csv` to `My Credentials.csv` in the same folder.
2. Replace `<your.username>` and `<your password>` on each row with your own. Delete rows for servers you don't have access to.
3. Run:
   ```bash
   zsh setup_db_logins.sh "My Credentials.csv"
   ```
   This writes `~/.my.cnf` (MySQL) and `~/.mongo/<db>.uri` (MongoDB), readable only by you, and prints no passwords.
   Claude connects through these files and never sees your passwords. **Don't paste passwords into Claude.**
4. Optional but recommended: lock the CSV with `chmod 600 "My Credentials.csv"`, or delete it once setup works.

## 4. Check it works
```bash
zsh test_connections.sh
```
Each server should print your username and version. A timeout means the VPN is off. "Access denied" means that row's
username or password is wrong, or the account isn't allowed from your network; ask the DBA.

## 5. Map the databases (once)
Ask Claude: *"build the database map"*. It runs `python3 build_db_map.py`, which writes `db_map/` with every table,
column and index, so it can write correct queries without guessing.

## Day to day
- Open Claude Code in the kit folder and ask in plain English. You don't need to know table or column names. Examples:
  - *"Fetch decline reasons for Toyota dealers since 1 Sep till today."*
  - *"Which toll-free and 10DLC numbers were given to dealers during onboarding, what's their approval status, and the rejection reasons?"*
  - *"List dealers that went live this quarter, with their OEM and go-live date."*
- Claude adds useful context columns you didn't ask for (dealer ID, OEM, dealer code, go-live / churn date, created and
  modified dates) and delivers an Excel file with a README sheet explaining every column and filter.
- `data_catalog.md` is the shared map of where data lives. When Claude learns something new it adds it there; share
  improvements back so everyone benefits.
- `.claude/settings.json` pre-approves read-only `mycli` / `mongosh` commands and **blocks Claude from opening your credential files**.
- If your password changes: update `My Credentials.csv`, re-run `setup_db_logins.sh`.

## Rules
- Read-only queries only. Some accounts technically allow writes, so this is on us, not the database.
- Don't export customer personal data (names, contact details, VINs) unless you need it for a specific, approved purpose.
- Production servers: keep questions bounded (dealer + date range). Claude knows the efficient query patterns.

Questions: Abhimanyu Srivastava.
