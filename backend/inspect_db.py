"""
Quick inspection script for market_pulse.db.
"""

import sqlite3

con = sqlite3.connect("market_pulse.db")

print("--- counts ---")
print("items:", con.execute("SELECT COUNT(*) FROM items").fetchone()[0])
print("price_snapshots:", con.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0])
print(
    "distinct leagues:",
    con.execute("SELECT DISTINCT source_league FROM items").fetchall(),
)
print(
    "distinct primary currencies seen:",
    con.execute("SELECT DISTINCT primary_currency FROM price_snapshots").fetchall(),
)

print()
print("--- distinct collection timestamps ---")
query = """
    SELECT collected_at, COUNT(*) as n
    FROM price_snapshots
    GROUP BY collected_at
    ORDER BY collected_at
"""
rows = con.execute(query).fetchall()
print(f"number of distinct timestamps: {len(rows)}")
for collected_at, n in rows:
    print(collected_at, "->", n, "rows")

print()
print("--- sample price history (first item alphabetically) ---")
first_item = con.execute("SELECT name FROM items ORDER BY name LIMIT 1").fetchone()
if first_item:
    query = """
        SELECT price_snapshots.primary_value, price_snapshots.primary_currency, price_snapshots.collected_at
        FROM price_snapshots
        JOIN items ON items.id = price_snapshots.item_id
        WHERE items.name = ?
        ORDER BY price_snapshots.collected_at
    """
    for row in con.execute(query, (first_item[0],)):
        print(first_item[0], "->", row)

con.close()