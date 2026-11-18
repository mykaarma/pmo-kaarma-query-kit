#!/bin/zsh
# Builds ~/.my.cnf from "My Credentials.csv" so mycli can connect without
# passwords being typed or shown. Run this yourself; it prints no secrets.
# One section per cluster: [client_<cluster>], e.g. [client_kaardbprod].
# Sections not generated from the CSV are kept. Usage: zsh setup_db_logins.sh ["path/to/My Credentials.csv"]
set -e
CSV="${1:-${0:A:h}/My Credentials.csv}"
[[ -f "$CSV" ]] || { echo "Credentials file not found: $CSV" >&2; exit 1; }
OUT="$HOME/.my.cnf"
umask 077
NEW=$(mktemp)
typeset -A seen
# "|| [[ -n $host ]]" keeps the last row when the CSV has no trailing newline
tail -n +2 "$CSV" | tr -d '\r' | while IFS=, read -r db host port user pass cluster ctype || [[ -n "$host" ]]; do
  [[ -z "$host" ]] && continue
  # MongoDB rows: write a connection URI to ~/.mongo/<db>.uri instead of ~/.my.cnf
  if [[ "$ctype" == *[Mm]ongo* ]]; then
    mkdir -p "$HOME/.mongo" && chmod 700 "$HOME/.mongo"
    printf '%s\n%s\n' "$user" "$pass" | python3 -c '
import sys, urllib.parse as u
user, pw = sys.stdin.read().split("\n")[:2]
print(f"mongodb://{u.quote_plus(user)}:{u.quote_plus(pw)}@{sys.argv[1]}:{sys.argv[2]}/{sys.argv[3]}?authSource=admin&readPreference=secondaryPreferred&directConnection=true")
' "$host" "$port" "$db" > "$HOME/.mongo/$db.uri"
    chmod 600 "$HOME/.mongo/$db.uri"
    echo "Wrote $HOME/.mongo/$db.uri" >&2
    continue
  fi
  sect=$(echo "$cluster" | tr '[:upper:]' '[:lower:]')
  [[ -n "${seen[$sect]}" ]] && continue
  seen[$sect]=1
  printf '[client_%s]\nhost = %s\nport = %s\nuser = %s\npassword = "%s"\n\n' \
    "$sect" "$host" "$port" "$user" "$pass"
done > "$NEW"
# Append existing sections whose names the CSV didn't produce
if [[ -f "$OUT" ]]; then
  awk -v gen="$(grep '^\[' "$NEW" | tr '\n' ' ')" '
    /^\[/ { keep = (index(gen, $0) == 0) }
    keep' "$OUT" >> "$NEW"
fi
mv "$NEW" "$OUT"
chmod 600 "$OUT"
echo "Wrote $OUT with sections:"; grep '^\[' "$OUT"
