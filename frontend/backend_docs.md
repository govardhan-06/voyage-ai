# Voyage AI — Backend API Documentation

> **Base URL**: `http://localhost:8000`  
> **Content-Type**: `application/json`  
> **Auth**: JWT Bearer token (where noted)

---

## 1. Authentication (`/auth`)

### POST `/auth/register`

Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "password": "securePassword123"
}
```

**Response** `200 OK`:
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "created_at": "2026-02-14T16:00:00",
  "updated_at": "2026-02-14T16:00:00",
  "preferences": null,
  "metadata": null
}
```

**Error** `400`:
```json
{ "detail": "Email already registered" }
```

---

### POST `/auth/login`

Authenticate and receive a JWT token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response** `200 OK`:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "65f1a2b3c4d5e6f7a8b9c0d1"
}
```

**Error** `401`:
```json
{ "detail": "Incorrect email or password" }
```

---

## 2. Users (`/users`)

> All user endpoints require `Authorization: Bearer <token>` header.

### GET `/users/me`

Get the current authenticated user's profile.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response** `200 OK`:
```json
{
  "_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "email": "user@example.com",
  "name": "John Doe",
  "created_at": "2026-02-14T16:00:00",
  "updated_at": "2026-02-14T16:00:00",
  "preferences": {
    "budget_range": { "min": 500, "max": 3000 },
    "travel_style": ["adventure", "cultural"],
    "interests": ["hiking", "food", "photography"],
    "preferred_climate": ["tropical"],
    "preferred_destinations": ["Japan", "Italy"],
    "accommodation_type": ["hotel"],
    "food_preferences": ["vegetarian"],
    "activity_preferences": ["outdoor"],
    "risk_tolerance": "moderate"
  },
  "metadata": {
    "last_login": "2026-02-14T16:00:00",
    "total_trips": 5
  }
}
```

---

### GET `/users/me/preferences`

Get only the user's preferences.

**Response** `200 OK`:
```json
{
  "budget_range": { "min": 500, "max": 3000 },
  "travel_style": ["adventure", "cultural"],
  "interests": ["hiking", "food", "photography"],
  "preferred_climate": ["tropical"],
  "preferred_destinations": ["Japan", "Italy"],
  "accommodation_type": ["hotel"],
  "food_preferences": ["vegetarian"],
  "activity_preferences": ["outdoor"],
  "risk_tolerance": "moderate"
}
```

---

### PATCH `/users/me/preferences`

Update user preferences. Performs a deep merge with existing preferences — you can send partial updates.

**Request Body** (all fields optional):
```json
{
  "budget_range": { "min": 1000, "max": 5000 },
  "travel_style": ["luxury"],
  "interests": ["spa", "wine-tasting"],
  "preferred_climate": ["mediterranean"],
  "preferred_destinations": ["France", "Greece"],
  "accommodation_type": ["boutique-hotel", "resort"],
  "food_preferences": ["local-cuisine"],
  "activity_preferences": ["relaxation", "cultural"],
  "risk_tolerance": "low"
}
```

**Response** `200 OK`: Returns the full updated preferences object (same structure as GET).

---

## 3. Trips (`/trips`)

### GET `/trips/user/{user_id}`

List all trips for a user with optional time-range and status filters. Results are sorted newest-first.

**Path Parameters:**

| Param | Type | Description |
|---|---|---|
| `user_id` | string | User's MongoDB ID |

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `from_date` | string | null | Start of date range (`YYYY-MM-DD`), filters on `created_at` |
| `to_date` | string | null | End of date range (`YYYY-MM-DD`), filters on `created_at` |
| `trip_status` | string | null | Filter by status: `planning`, `finalized`, or `cancelled` |
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 20 | Max results (1–100) |

**Example:** `GET /trips/user/65f1a2b3c4d5e6f7a8b9c0d1?from_date=2026-01-01&to_date=2026-12-31&trip_status=finalized&limit=10`

**Response** `200 OK`:
```json
{
  "trips": [
    {
      "_id": "65f1a2b3c4d5e6f7a8b9c0d1",
      "user_id": "65f1a2b3c4d5e6f7a8b9c0d1",
      "title": "Trip to Tokyo, Japan",
      "status": "finalized",
      "created_at": "2026-02-14T16:00:00",
      "updated_at": "2026-02-14T17:30:00",
      "trip_constraints": {
        "destination": "Tokyo, Japan",
        "start_date": "2026-03-15",
        "end_date": "2026-03-20",
        "duration_days": 5,
        "budget": 3000,
        "travel_group": "solo",
        "traveler_count": 1,
        "special_constraints": []
      },
      "current_version": 2,
      "final_itinerary_version": 2
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10
}
```

**Errors:** `400` Invalid date format

---

### GET `/trips/user/{user_id}/itineraries`

List all itinerary versions across all trips for a user, with optional time-range filter. Results are sorted newest-first.

**Path Parameters:**

| Param | Type | Description |
|---|---|---|
| `user_id` | string | User's MongoDB ID |

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `from_date` | string | null | Start of date range (`YYYY-MM-DD`), filters on `created_at` |
| `to_date` | string | null | End of date range (`YYYY-MM-DD`), filters on `created_at` |
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 20 | Max results (1–100) |

**Example:** `GET /trips/user/65f1a2b3c4d5e6f7a8b9c0d1/itineraries?from_date=2026-02-01&limit=5`

**Response** `200 OK`:
```json
{
  "itineraries": [
    {
      "_id": "65f1a2b3c4d5e6f7a8b9c0d2",
      "trip_id": "65f1a2b3c4d5e6f7a8b9c0d1",
      "version_number": 2,
      "created_at": "2026-02-14T17:30:00",
      "created_by": "ai",
      "change_summary": "Added more food experiences on Day 2",
      "itinerary": {
        "total_cost_estimate": 2500,
        "currency": "USD",
        "days": [
          {
            "day_number": 1,
            "date": "2026-03-15",
            "activities": [
              {
                "time": "09:00",
                "title": "Visit Senso-ji Temple",
                "description": "Explore Tokyo's oldest temple...",
                "location": {
                  "name": "Senso-ji Temple",
                  "address": "2-3-1 Asakusa, Taito City",
                  "latitude": 35.7148,
                  "longitude": 139.7967
                },
                "cost_estimate": 0,
                "tags": ["culture", "sightseeing"]
              }
            ]
          }
        ]
      }
    }
  ],
  "total": 2,
  "skip": 0,
  "limit": 5
}
```

**Errors:** `400` Invalid date format

---

### POST `/trips/chat`

**Main conversational endpoint.** Handles the full trip planning flow through multiple turns using a `thread_id` for session continuity.

**Request Body:**
```json
{
  "user_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "message": "Plan a trip to Japan for 5 days",
  "thread_id": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | string | ✅ | User's MongoDB ID |
| `message` | string | ✅ | User's message text |
| `thread_id` | string \| null | ❌ | `null` for new session, UUID string to continue |

#### Response Statuses

The response `status` field drives frontend behavior:

---

#### Status: `"clarifying"`

Agent needs more information to plan the trip. Show the message and prompt for user input.

```json
{
  "status": "clarifying",
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "That sounds great! What's your budget range for this trip?",
  "data": {
    "slots_collected": {
      "destination": "Tokyo, Japan",
      "duration_days": 5,
      "travel_group": "solo"
    }
  }
}
```

**Next step:** Call `POST /trips/chat` again with the same `thread_id` and the user's answer.

---

#### Status: `"reviewing"`

Draft itinerary is ready for user review. Show the itinerary and ask for approval.

```json
{
  "status": "reviewing",
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Here's your draft itinerary for Tokyo, Japan! Review it below and reply 'approve' to finalize, or tell me what you'd like to change.",
  "data": {
    "itinerary": {
      "title": "5 Days in Tokyo",
      "summary": "An exciting cultural and culinary journey...",
      "total_cost_estimate": 2500,
      "currency": "USD",
      "days": [
        {
          "day_number": 1,
          "date": "2026-03-15",
          "activities": [
            {
              "time": "09:00",
              "title": "Visit Senso-ji Temple",
              "description": "Explore Tokyo's oldest temple...",
              "location_name": "Senso-ji Temple",
              "location_address": "2-3-1 Asakusa, Taito City",
              "latitude": 35.7148,
              "longitude": 139.7967,
              "cost_estimate": 0,
              "tags": ["culture", "sightseeing"]
            }
          ]
        }
      ]
    },
    "trip_request": {
      "destination": "Tokyo, Japan",
      "duration_days": 5,
      "budget_max": 3000,
      "travel_group": "solo",
      "traveler_count": 1,
      "start_date": "2026-03-15",
      "interests": ["culture", "food"]
    },
    "trip_strategy": {
      "destination_overview": "...",
      "recommended_flights": [...],
      "recommended_hotels": [...],
      "daily_themes": [...]
    }
  }
}
```

**Next step:** Call `POST /trips/chat` with:
- `"approve"` → finalizes the trip  
- Any other text → treated as revision feedback, agent re-plans

---

#### Status: `"complete"`

Trip has been finalized and saved.

```json
{
  "status": "complete",
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Your trip has been saved! Trip ID: 65f1a2b...",
  "data": {
    "trip_id": "65f1a2b3c4d5e6f7a8b9c0d1",
    "itinerary_version_id": "65f1a2b3c4d5e6f7a8b9c0d2",
    "itinerary": { ... },
    "trip_request": { ... }
  }
}
```

---

#### Status: `"planning"`

Agent is actively processing (rare — usually resolves within the same request).

```json
{
  "status": "planning",
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Working on your trip plan...",
  "data": {
    "trip_request": { ... }
  }
}
```

---

#### Error Response `500`:
```json
{ "detail": "Trip planning failed: <error message>" }
```

---

### Typical Conversation Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Turn 1: POST /trips/chat                                    │
│   → { user_id, message: "Trip to Japan", thread_id: null }  │
│   ← { status: "clarifying", thread_id: "abc...", ... }      │
├─────────────────────────────────────────────────────────────┤
│ Turn 2: POST /trips/chat                                    │
│   → { user_id, message: "5 days, $3k budget, solo",         │
│        thread_id: "abc..." }                                 │
│   ← { status: "reviewing", itinerary: {...}, ... }           │
├─────────────────────────────────────────────────────────────┤
│ Turn 3a: Approve                                            │
│   → { user_id, message: "approve", thread_id: "abc..." }    │
│   ← { status: "complete", trip_id: "...", ... }              │
│                                                              │
│ Turn 3b: Request changes                                    │
│   → { user_id, message: "Add more food spots on day 2",     │
│        thread_id: "abc..." }                                 │
│   ← { status: "reviewing", itinerary: {updated...}, ... }   │
└─────────────────────────────────────────────────────────────┘
```

---

### GET `/trips/{trip_id}`

Get saved trip details.

**Response** `200 OK`:
```json
{
  "_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "user_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "title": "Trip to Tokyo, Japan",
  "status": "planning",
  "created_at": "2026-02-14T16:00:00",
  "updated_at": "2026-02-14T16:00:00",
  "trip_constraints": {
    "destination": "Tokyo, Japan",
    "start_date": "2026-03-15",
    "end_date": "2026-03-20",
    "duration_days": 5,
    "budget": 3000,
    "travel_group": "solo",
    "traveler_count": 1,
    "special_constraints": []
  },
  "current_version": 1,
  "final_itinerary_version": null
}
```

**Errors:** `400` Invalid trip ID | `404` Trip not found

---

### GET `/trips/{trip_id}/itinerary`

Get the latest itinerary version for a trip.

**Response** `200 OK`:
```json
{
  "_id": "65f1a2b3c4d5e6f7a8b9c0d2",
  "trip_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "version_number": 1,
  "created_at": "2026-02-14T16:00:00",
  "created_by": "ai",
  "change_summary": "Initial AI-generated itinerary",
  "itinerary": {
    "total_cost_estimate": 2500,
    "currency": "USD",
    "days": [
      {
        "day_number": 1,
        "date": "2026-03-15",
        "activities": [
          {
            "time": "09:00",
            "title": "Visit Senso-ji Temple",
            "description": "...",
            "location": {
              "name": "Senso-ji Temple",
              "address": "2-3-1 Asakusa, Taito City",
              "latitude": 35.7148,
              "longitude": 139.7967
            },
            "cost_estimate": 0,
            "tags": ["culture", "sightseeing"]
          }
        ]
      }
    ]
  }
}
```

**Error:** `404` No itinerary found

---

### GET `/trips/{trip_id}/conversations`

Get conversation history for a trip.

**Response** `200 OK`:
```json
{
  "_id": "65f1a2b3c4d5e6f7a8b9c0d3",
  "trip_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "user_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "created_at": "2026-02-14T16:00:00",
  "messages": [
    {
      "role": "user",
      "content": "Plan a trip to Japan",
      "timestamp": "2026-02-14T16:00:00"
    },
    {
      "role": "ai",
      "content": "Great! I have all the details...",
      "timestamp": "2026-02-14T16:00:05"
    }
  ]
}
```

**Error:** `404` No conversation found

---

## Data Models Reference

### UserPreferences
```json
{
  "budget_range": { "min": number | null, "max": number | null },
  "travel_style": ["adventure", "cultural", "luxury", ...],
  "interests": ["hiking", "food", "photography", ...],
  "preferred_climate": ["tropical", "mediterranean", ...],
  "preferred_destinations": ["Japan", "Italy", ...],
  "accommodation_type": ["hotel", "hostel", "resort", ...],
  "food_preferences": ["vegetarian", "local-cuisine", ...],
  "activity_preferences": ["outdoor", "relaxation", ...],
  "risk_tolerance": "low" | "moderate" | "high"
}
```

### Itinerary Day Activity
```json
{
  "time": "09:00",
  "title": "Activity Title",
  "description": "Detailed description...",
  "location": {
    "name": "Place Name",
    "address": "Full address",
    "latitude": 35.7148,
    "longitude": 139.7967
  },
  "cost_estimate": 50,
  "tags": ["culture", "food"]
}
```

### Chat Response Envelope
```json
{
  "status": "clarifying" | "planning" | "reviewing" | "complete",
  "thread_id": "uuid-string",
  "message": "Human-readable AI message",
  "data": { /* status-dependent payload */ }
}
```
