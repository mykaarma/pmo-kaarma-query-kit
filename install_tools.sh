#!/bin/zsh
# Installs the database clients and Python libraries Claude uses. Safe to re-run.
set -e
if ! command -v brew >/dev/null; then
  echo "Homebrew is required: https://brew.sh — install it, then re-run this script." >&2; exit 1
fi
brew install mysql-client mongosh
python3 -m pip install --user --quiet pymysql pymongo openpyxl
echo "Installed: $("$(brew --prefix mysql-client)/bin/mysql" --version), $(mongosh --version 2>/dev/null | head -1 | sed 's/^/mongosh /')"
echo "Next: fill in your own credentials CSV, then run: zsh setup_db_logins.sh \"My Credentials.csv\""
