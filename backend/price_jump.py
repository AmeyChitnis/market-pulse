import sqlite3
con = sqlite3.connect("market_pulse.db")
query = """
    SELECT price_snapshots.primary_value, price_snapshots.primary_currency, price_snapshots.collected_at
    FROM price_snapshots
    JOIN items ON items.id = price_snapshots.item_id
    WHERE items.name = 'Ancient Infuser'
    ORDER BY price_snapshots.collected_at
"""
for row in con.execute(query):
    print(row)
con.close()