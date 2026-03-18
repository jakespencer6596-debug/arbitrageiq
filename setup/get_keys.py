# setup/get_keys.py
# Guided key acquisition — opens each signup page and collects keys

import webbrowser
import time
import os

ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '.env')

def write_env(key, value):
    """Append or update a key in .env"""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r') as f:
            lines = f.readlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
    if not updated:
        lines.append(f"{key}={value}\n")
    with open(ENV_PATH, 'w') as f:
        f.writelines(lines)
    print(f"  Written to .env: {key}={'*' * (len(value)-4) + value[-4:]}")

def get_key(name, url, instructions, env_key, optional=False):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"Opening: {url}")
    print(f"\nInstructions: {instructions}")
    webbrowser.open(url)
    time.sleep(2)
    prompt = f"Paste your {name} key here (or press Enter to skip): " if optional else f"Paste your {name} key here: "
    while True:
        val = input(prompt).strip()
        if val:
            write_env(env_key, val)
            break
        elif optional:
            print(f"  Skipping {name}")
            break
        else:
            print("  This key is required. Please complete signup and paste it.")

print("\n ArbitrageIQ — API Key Setup")
print("This will open 4 browser tabs. Complete each signup, then paste the key.\n")

# 1. The Odds API
get_key(
    "The Odds API",
    "https://the-odds-api.com/#get-access",
    "Sign up for free. After confirming email, go to your dashboard and copy the API key shown.",
    "ODDS_API_KEY"
)

# 2. FRED (Federal Reserve)
get_key(
    "FRED API Key",
    "https://fredaccount.stlouisfed.org/apikeys",
    "Click 'Request API Key'. Fill in name/email. The key is shown immediately on the next page.",
    "FRED_API_KEY"
)

# 3. Telegram Bot Token
get_key(
    "Telegram Bot Token",
    "https://web.telegram.org/k/#@BotFather",
    "Message @BotFather. Send /newbot. Name: ArbitrageIQ. Username: ArbitrageIQ_Bot (or similar). Copy the HTTP token it gives you.",
    "TELEGRAM_BOT_TOKEN"
)

# 4. GitHub Repo URL
print(f"\n{'='*60}")
print("GitHub Repository")
print(f"{'='*60}")
print("Please provide your GitHub repo URL (e.g. https://github.com/yourname/arbitrageiq)")
print("If you don't have one yet, create it now at https://github.com/new (name it 'arbitrageiq')")
webbrowser.open("https://github.com/new")
while True:
    repo_url = input("Paste your GitHub repo URL: ").strip()
    if repo_url.startswith("https://github.com/"):
        write_env("GITHUB_REPO_URL", repo_url)
        break
    print("  Must be a full GitHub URL starting with https://github.com/")

# Static values — no keys needed
write_env("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
write_env("OPEN_METEO_HISTORICAL_URL", "https://archive-api.open-meteo.com/v1/archive")
write_env("NWS_API_URL", "https://api.weather.gov")
write_env("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")
write_env("PREDICTIT_API_URL", "https://www.predictit.org/api/marketdata/all/")
write_env("TELEGRAM_CHAT_ID", "PENDING")
write_env("BUDGET_MODE", "true")
write_env("DISCREPANCY_THRESHOLD_WEATHER", "0.15")
write_env("DISCREPANCY_THRESHOLD_ECONOMIC", "0.15")
write_env("DISCREPANCY_THRESHOLD_POLITICAL", "0.10")
write_env("DISCREPANCY_THRESHOLD_SPORTS", "0.05")

print("\nSetup complete! Keys written to .env")
print("One more step: After the app starts, message your Telegram bot to register for alerts.")
