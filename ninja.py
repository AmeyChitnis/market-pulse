import httpx

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://poe.ninja/poe1/economy/",
}

resp = httpx.get(
    "https://poe.ninja/poe1/api/economy/exchange/current/overview",
    params={"league": "Mirage", "type": "Currency"},
    headers=headers,
    timeout=10.0,
)
print("status:", resp.status_code)
data = resp.json()
print("primary:", data["core"]["primary"])
print("num lines:", len(data["lines"]))
print("first line:", data["lines"][0])
print("first item:", data["items"][0])