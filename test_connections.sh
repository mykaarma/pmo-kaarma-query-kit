#!/bin/zsh
# Read-only login check for every configured database. Prints no secrets.
# Uses Homebrew's mysql client (keg-only, so called by full path): mycli 2.x dropped --defaults-group-suffix.
MYSQL="$(brew --prefix mysql-client)/bin/mysql"
echo "🔌 Kaarma Query Kit — if this breaks, it's the VPN, not Abhimanyu."
for s in $(grep -o '^\[client_[a-z_]*\]' ~/.my.cnf | sed 's/\[client_//; s/\]//'); do
  printf "%-22s " "$s"
  "$MYSQL" --defaults-group-suffix=_$s --connect-timeout=8 -B -N -e "SELECT CURRENT_USER(), VERSION()" < /dev/null 2>&1 | tail -1
done
for f in ~/.mongo/*.uri(N); do
  printf "%-22s " "mongo:$(basename $f .uri)"
  python3 -c "import pymongo,sys; c=pymongo.MongoClient(open(sys.argv[1]).read().strip(), serverSelectionTimeoutMS=8000); print('ok' if c.admin.command('ping')['ok'] else 'failed')" "$f" 2>&1 | tail -1
done
echo "If anything fails: check you are on the VPN, then check that row of your credentials CSV."
