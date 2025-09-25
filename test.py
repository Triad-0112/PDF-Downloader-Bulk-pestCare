import requests
import json

# --- Credentials and Endpoint ---
# Use the exact credentials from your config file
username = "adm.malang@pestcare.id"
password = "J4ng4nT4ny4"
login_url = "https://api.pestcare.id/web/api/auth/login"

# --- Request Details ---
payload = {
    "username": username,
    "password": password
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Content-Type': 'application/json'
}

print(f"Attempting to POST to: {login_url}")
print(f"With payload: {json.dumps(payload)}")
print("-" * 30)

# --- Make the Request and Print Everything ---
try:
    # Set a timeout to prevent the script from hanging indefinitely
    response = requests.post(login_url, headers=headers, json=payload, timeout=15)

    print(f"Status Code: {response.status_code}")
    print("\n--- Response Headers ---")
    for key, value in response.headers.items():
        print(f"{key}: {value}")

    print("\n--- Response Body (Text) ---")
    print(response.text)

    # Try to print the JSON response if it's valid
    try:
        print("\n--- Response Body (JSON) ---")
        print(response.json())
    except json.JSONDecodeError:
        print("\n[Could not decode JSON from response body.]")

except requests.exceptions.RequestException as e:
    print(f"\nAN ERROR OCCURRED: {e}")
