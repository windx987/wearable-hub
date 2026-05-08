# SDK Onboarding: Create User → Invitation Code → Connect SDK

This guide walks through the full flow to onboard a mobile user onto the platform using the Flutter (or iOS/Android) SDK.

---

## Overview

```
1. Authenticate (get JWT)
        ↓
2. Create a user (POST /users)
        ↓
3. Generate an invitation code (POST /users/{id}/invitation-code)
        ↓
4. Share code with mobile user
        ↓
5. SDK redeems code → gets tokens → starts syncing HealthKit data
```

---

## Prerequisites

- Backend running locally: `docker compose up -d`
- Admin credentials: `admin@admin.com` / `your-secure-password`
- Flutter SDK example app running on simulator: `flutter run` (inside `flutter-open-wearables-sdk/example/`)

---

## Step 1 — Authenticate

All admin endpoints require a JWT Bearer token. Get one by logging in:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@admin.com&password=your-secure-password" \
  | jq -r .access_token)

echo $TOKEN
```

> Note: Use form-encoded data (`application/x-www-form-urlencoded`), NOT JSON.

---

## Step 2 — Create a User

Create a user record to represent the mobile app user.

**Request:**
```bash
curl -s -X POST "http://localhost:8000/api/v1/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "สมชาย",
    "last_name": "ใจดี",
    "email": "somchai@example.com"
  }' | jq .
```

All fields are optional — you can create a user with no data:
```bash
curl -s -X POST "http://localhost:8000/api/v1/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .
```

**Response:**
```json
{
  "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "created_at": "2026-05-08T...",
  "first_name": "สมชาย",
  "last_name": "ใจดี",
  "email": "somchai@example.com",
  "last_synced_at": null,
  "last_synced_provider": null
}
```

Save the `id` — you'll need it in the next step.

```bash
USER_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

---

## Step 3 — Generate an Invitation Code

Generate a single-use 8-character code for the user. Any previously generated codes for this user are automatically expired.

**Request:**
```bash
curl -s -X POST \
  "http://localhost:8000/api/v1/users/$USER_ID/invitation-code" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Response:**
```json
{
  "id": "...",
  "code": "ABC12345",
  "user_id": "...",
  "expires_at": "2026-05-09T10:00:00Z",
  "created_at": "2026-05-08T10:00:00Z"
}
```

The `code` is an 8-character uppercase alphanumeric string (e.g. `ABC12345`).

> Codes are **single-use** and **expire after 24 hours**. Generate a fresh one if it's already been redeemed or expired.

---

## Step 4 — Connect the Flutter SDK

Open the Flutter example app on the simulator (or device).

1. In the app, find the **Host URL** field — enter your backend URL:
   - Local: `http://localhost:8000`
   - Or your ngrok/tunnel URL if testing on a real device

2. Find the **Invitation Code** field — enter the code from Step 3 (e.g. `ABC12345`)

3. Tap **Connect** (or equivalent button)

The SDK will:
- Call `POST /api/v1/invitation-code/redeem` internally
- Receive `access_token`, `refresh_token`, and `user_id`
- Store credentials on-device
- Begin syncing HealthKit data immediately

You should see in the Flutter terminal:
```
flutter: [OpenWearablesSDK] Session restored: userId=<your-user-id>
flutter: [OpenWearablesSDK] Background observers registered for 40 types
flutter: [OpenWearablesSDK] Sync complete: N samples across 40 types
```

---

## Step 5 — Verify the Connection

Check that data is flowing into the backend:

```bash
# Check user's last sync time
curl -s "http://localhost:8000/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '{last_synced_at, last_synced_provider}'

# Check database directly
docker compose exec db psql -U open-wearables -d open-wearables \
  -c "SELECT email, last_synced_at, last_synced_provider FROM \"user\" WHERE id = '$USER_ID';"
```

---

## API Key Alternative (for server-to-server)

Instead of a JWT Bearer token, admin API endpoints also accept an API key via `X-Open-Wearables-API-Key` header.

Get an API key from the portal: http://localhost:3000 → **Credentials** tab → **Create API Key**

```bash
# Create user with API key instead of JWT
curl -s -X POST "http://localhost:8000/api/v1/users" \
  -H "X-Open-Wearables-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}' | jq .

# Generate invitation code with API key
curl -s -X POST \
  "http://localhost:8000/api/v1/users/$USER_ID/invitation-code" \
  -H "X-Open-Wearables-API-Key: YOUR_API_KEY" | jq .
```

> Note: Invitation code generation requires developer-level auth (JWT or API key). The SDK redeem endpoint (`POST /api/v1/invitation-code/redeem`) is public — no auth needed.

---

## Full One-Liner Script

```bash
# Set your credentials
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@admin.com&password=your-secure-password" \
  | jq -r .access_token)

# Create user
USER_ID=$(curl -s -X POST "http://localhost:8000/api/v1/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name": "Test", "email": "test@example.com"}' \
  | jq -r .id)

# Generate invitation code
curl -s -X POST \
  "http://localhost:8000/api/v1/users/$USER_ID/invitation-code" \
  -H "Authorization: Bearer $TOKEN" | jq '{code, expires_at}'
```

Output:
```json
{
  "code": "ABC12345",
  "expires_at": "2026-05-09T10:00:00Z"
}
```

Enter this code in the Flutter SDK app to complete onboarding.
