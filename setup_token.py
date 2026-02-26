"""
setup_token.py  --  One-time YouTube OAuth setup for stockzero_bot
Run this locally on your PC with the client_secret JSON file.

Steps:
  1. Go to console.cloud.google.com → New project (e.g. "stockzero-bot")
  2. APIs & Services → Enable "YouTube Data API v3"
  3. APIs & Services → Credentials → Create OAuth Client ID
     - Application type: Desktop app
     - Download the JSON → save next to this script
  4. Run:  python setup_token.py client_secret_XXXX.json
  5. Browser opens → log in with the YouTube channel account → Allow
  6. Script prints TOKEN_JSON_B64 → add to GitHub Secrets
"""

import base64
import json
import os
import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_token.py <client_secret_xxxx.json>")
        sys.exit(1)

    secret_file = sys.argv[1]
    if not os.path.exists(secret_file):
        print(f"File not found: {secret_file}")
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes),
    }

    out_file = "token_stockzero.json"
    with open(out_file, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"\nToken saved: {out_file}")

    b64 = base64.b64encode(json.dumps(token_data).encode()).decode()
    print("\n" + "=" * 60)
    print("TOKEN_JSON_B64 (add this as GitHub Secret 'TOKEN_JSON'):")
    print("=" * 60)
    print(b64)
    print("=" * 60)
    print("\nGitHub Secrets path:")
    print("  https://github.com/skrrskrr31/stockzero_bot/settings/secrets/actions")


if __name__ == "__main__":
    main()
