#!/usr/bin/env python3
"""Builds db_map/ — a map of databases, tables, columns and indexes.

Connects with ~/.my.cnf sections (see setup_db_logins.sh); never reads passwords itself.
Only queries information_schema. Re-run any time to refresh:

    python3 build_db_map.py

Outputs:
    db_map/README.md            overview: every cluster -> schemas -> table counts
    db_map/scheduler_tables.md         scheduler tables in detail (columns, indexes)
    db_map/<cluster>.md         full table list per cluster
"""
import datetime
import os
import pymysql

CLUSTERS = ["kaardbprod", "scheduler", "appointment", "communicationsaurora", "communicationsrds"]
SYSTEM_SCHEMAS = ("mysql", "information_schema", "performance_schema", "sys")

# Scheduler cluster: every table in these schemas gets full column/index detail.
SCHEDULER_SOURCE = ("scheduler", ("SchedulerDB", "CustomerUserDB"))
SCHEDULER_TABLE_PATTERNS = ("%",)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_map")


def connect(cluster):
    return pymysql.connect(
        read_default_file=os.path.expanduser("~/.my.cnf"),
        read_default_group=f"client_{cluster}",
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )


def query(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def fmt_rows(n):
    if n is None:
        return "–"
    n = int(n)
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return str(n)


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |")
    return "\n".join(out)


def list_tables(conn):
    return query(conn, f"""
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS, TABLE_TYPE
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA NOT IN {SYSTEM_SCHEMAS}
        ORDER BY TABLE_SCHEMA, TABLE_NAME""")


def scheduler_detail(conn, schema):
    like = " OR ".join(["TABLE_NAME LIKE %s"] * len(SCHEDULER_TABLE_PATTERNS))
    tables = query(conn, f"""
        SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND ({like}) ORDER BY TABLE_NAME""",
        (schema, *SCHEDULER_TABLE_PATTERNS))
    names = [t["TABLE_NAME"] for t in tables]
    if not names:
        return tables, {}, {}
    ph = ",".join(["%s"] * len(names))
    cols, idx = {}, {}
    for c in query(conn, f"""
            SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, EXTRA
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({ph})
            ORDER BY TABLE_NAME, ORDINAL_POSITION""", (schema, *names)):
        cols.setdefault(c["TABLE_NAME"], []).append(c)
    for i in query(conn, f"""
            SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE,
                   GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS COLS
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({ph})
            GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE
            ORDER BY TABLE_NAME, INDEX_NAME = 'PRIMARY' DESC, INDEX_NAME""", (schema, *names)):
        idx.setdefault(i["TABLE_NAME"], []).append(i)
    return tables, cols, idx


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    overview = [f"# Database map\n\n_Generated {now} by `build_db_map.py`. Re-run it to refresh._\n",
                "Scheduler tables: see [scheduler_tables.md](scheduler_tables.md).\n"]
    summary_rows = []
    scheduler_done = False

    for cluster in CLUSTERS:
        try:
            conn = connect(cluster)
        except pymysql.err.OperationalError as e:
            summary_rows.append((cluster, "–", "–", f"❌ cannot connect: {e.args[0]}"))
            continue
        with conn:
            version = query(conn, "SELECT VERSION() AS v")[0]["v"]
            tables = list_tables(conn)
            by_schema = {}
            for t in tables:
                by_schema.setdefault(t["TABLE_SCHEMA"], []).append(t)
            for schema, ts in by_schema.items():
                summary_rows.append((cluster, schema, len(ts), f"✅ {version}"))
            lines = [f"# Cluster `{cluster}` ({version})\n\n_Generated {now}._\n"]
            for schema, ts in by_schema.items():
                lines.append(f"\n## {schema} ({len(ts)} tables)\n")
                lines.append(md_table(["Table", "Rows (approx)", "Type"],
                                      [(t["TABLE_NAME"], fmt_rows(t["TABLE_ROWS"]), t["TABLE_TYPE"]) for t in ts]))
            with open(os.path.join(OUT_DIR, f"{cluster}.md"), "w") as f:
                f.write("\n".join(lines) + "\n")

            if cluster == SCHEDULER_SOURCE[0]:
                write_scheduler(conn, SCHEDULER_SOURCE[1], version, now)
                scheduler_done = True

    if not scheduler_done:
        print(f"WARNING: could not connect to {SCHEDULER_SOURCE[0]}; scheduler_tables.md not refreshed")
    overview.append(md_table(["Cluster", "Schema", "Tables", "Status"], summary_rows))
    mapped = [c for c in CLUSTERS if os.path.exists(os.path.join(OUT_DIR, f"{c}.md"))]
    overview.append("\nPer-cluster table lists: " + ", ".join(f"[{c}]({c}.md)" for c in mapped))
    with open(os.path.join(OUT_DIR, "README.md"), "w") as f:
        f.write("\n".join(overview) + "\n")
    print(f"Wrote {OUT_DIR}")


def write_scheduler(conn, schemas, version, now):
    lines = ["# Scheduler tables\n",
             f"_Generated {now}. Source: cluster `{SCHEDULER_SOURCE[0]}` "
             f"(dr-mykaarmaschedulerdb-ro, {version}), schemas {', '.join(f'`{s}`' for s in schemas)}._\n",
             "Copies of several of these tables (ServiceAppointmentRequest, SARMetaData, SARUpdateHistory, …) "
             "also exist in KaarDBProd; see [kaardbprod.md](kaardbprod.md).\n"]
    detail = []
    for schema in schemas:
        tables, cols, idx = scheduler_detail(conn, schema)
        lines.append(f"## {schema} ({len(tables)} tables)\n")
        lines.append(md_table(["Table", "Rows (approx)", "Columns", "Indexes"],
                              [(f"[{t['TABLE_NAME']}](#{schema.lower()}{t['TABLE_NAME'].lower()})",
                                fmt_rows(t["TABLE_ROWS"]), len(cols.get(t["TABLE_NAME"], [])),
                                len(idx.get(t["TABLE_NAME"], []))) for t in tables]))
        lines.append("")
        for t in tables:
            name = t["TABLE_NAME"]
            detail.append(f"\n## {schema}.{name}\n\n~{fmt_rows(t['TABLE_ROWS'])} rows\n")
            detail.append("**Columns**\n")
            detail.append(md_table(["Column", "Type", "Null", "Key", "Extra"],
                                   [(c["COLUMN_NAME"], c["COLUMN_TYPE"], c["IS_NULLABLE"], c["COLUMN_KEY"], c["EXTRA"])
                                    for c in cols.get(name, [])]))
            if idx.get(name):
                detail.append("\n**Indexes**\n")
                detail.append(md_table(["Index", "Unique", "Columns"],
                                       [(i["INDEX_NAME"], "no" if i["NON_UNIQUE"] else "yes", i["COLS"])
                                        for i in idx[name]]))
    with open(os.path.join(OUT_DIR, "scheduler_tables.md"), "w") as f:
        f.write("\n".join(lines + detail) + "\n")


if __name__ == "__main__":
    main()
