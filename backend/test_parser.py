"""One-off diagnostic: call the live client + parser directly and print
raw output, bypassing the database entirely, to confirm what the parser
actually returns right now."""

from app.services.poe_ninja_client import fetch_currency_overview, parse_currency_lines

raw = fetch_currency_overview("Runes of Aldur")
parsed = parse_currency_lines(raw)

print(f"Total parsed: {len(parsed)}")
print()
print("First 10 parsed entries:")
for p in parsed[:10]:
    print(p)

print()
currencies_seen = set(p["primary_currency"] for p in parsed)
print("Distinct primary_currency values:", currencies_seen)