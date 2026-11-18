# Kaarma Query Kit by Abhimanyu

*Ask myKaarma's databases questions in plain English, from Claude.*

Open this folder in Claude Code, ask something like *"toll-free and 10DLC numbers given to dealers at onboarding, with
approval status and rejection reasons"*, and Claude finds the right tables, runs read-only queries with **your own**
database access, and hands back an Excel file with a README sheet explaining every column.

- **Setup (≈15 min):** [ONBOARDING.md](ONBOARDING.md)
- **Where data lives:** [data_catalog.md](data_catalog.md) — improve it when you learn something, and open a PR
- **Rules Claude follows:** [CLAUDE.md](CLAUDE.md) — read-only, no customer PII, index-friendly queries

> This repo contains **no credentials and no data**. Each person uses their own database logins (see ONBOARDING.md).
> `.gitignore` blocks credential files and data exports — please keep it that way.

Maintained by Abhimanyu Srivastava.
