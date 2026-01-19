# Memory Feature Implementation Plan

## Overview

This plan breaks down the Memory Feature into vertical slices, each delivering end-to-end functionality. Estimated timeline: ~2 weeks for production-ready implementation.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
├─────────────────────────────────────────────────────────────┤
│  Settings Page    │   Editor Sidebar   │   Rating Modal     │
│  /settings/profile│   (preference      │   (post-export     │
│                   │    toggles)        │    prompt)         │
└─────────┬─────────┴─────────┬──────────┴─────────┬──────────┘
          │                   │                    │
          ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                      │
├─────────────────────────────────────────────────────────────┤
│  /api/auth/*      │  /api/preferences/* │  /api/ratings/*   │
│  Magic link       │  CRUD + learning    │  Submit + query   │
└─────────┬─────────┴─────────┬───────────┴─────────┬─────────┘
          │                   │                     │
          ▼                   ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database (PostgreSQL)                     │
├─────────────────────────────────────────────────────────────┤
│  users            │  user_preferences   │  draft_ratings    │
│  magic_links      │  preference_events  │                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Authentication (Days 1-3)

### Slice 1.1: Database Schema

**File**: `apps/api/migrations/003_user_auth.sql`

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Magic links table
CREATE TABLE magic_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_magic_links_token ON magic_links(token);
CREATE INDEX idx_magic_links_expires ON magic_links(expires_at);
```

### Slice 1.2: Auth Service

**File**: `apps/api/services/auth_service.py`

**Functions**:
- `create_user(email: str) -> User`
- `get_user_by_email(email: str) -> User | None`
- `get_user_by_id(user_id: str) -> User | None`
- `create_magic_link(user_id: str) -> MagicLink`
- `validate_magic_link(token: str) -> User | None`
- `invalidate_magic_link(token: str) -> None`

**Models**:
```python
class User(BaseModel):
    id: str
    email: str
    created_at: datetime
    last_login_at: datetime | None

class MagicLink(BaseModel):
    id: str
    user_id: str
    token: str
    expires_at: datetime
```

### Slice 1.3: Auth Router

**File**: `apps/api/routers/auth.py`

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/request-link` | POST | Send magic link to email |
| `/api/auth/verify` | POST | Verify magic link token |
| `/api/auth/me` | GET | Get current user (requires auth) |
| `/api/auth/logout` | POST | Clear session |

**Request/Response**:
```python
# POST /api/auth/request-link
class RequestLinkInput(BaseModel):
    email: EmailStr

class RequestLinkResponse(BaseModel):
    message: str  # "Check your email"

# POST /api/auth/verify
class VerifyInput(BaseModel):
    token: str

class VerifyResponse(BaseModel):
    user: User
    session_token: str
```

### Slice 1.4: Email Service

**File**: `apps/api/services/email_service.py`

**Functions**:
- `send_magic_link_email(email: str, link: str) -> bool`

**Dependencies**:
- Use Resend, SendGrid, or AWS SES
- Environment variable: `EMAIL_API_KEY`

**Template**:
```
Subject: Sign in to Resume Optimizer

Click this link to sign in (valid for 15 minutes):
{magic_link_url}

If you didn't request this, ignore this email.
```

### Slice 1.5: Session Management

**File**: `apps/api/middleware/session_auth.py`

**Approach**:
- JWT-based session tokens
- Stored in httpOnly cookie
- 7-day expiration with refresh

**Functions**:
- `create_session_token(user_id: str) -> str`
- `verify_session_token(token: str) -> str | None`  # Returns user_id
- `get_current_user(request: Request) -> User | None`

### Slice 1.6: Frontend Auth UI

**Files**:
- `apps/web/app/auth/login/page.tsx` - Email input form
- `apps/web/app/auth/verify/page.tsx` - Token verification (from email link)
- `apps/web/app/hooks/useAuth.ts` - Auth state hook
- `apps/web/app/components/auth/AuthGuard.tsx` - Protected route wrapper

**Flow**:
1. User enters email on `/auth/login`
2. API sends magic link
3. User clicks link → `/auth/verify?token=xxx`
4. Frontend calls verify API
5. On success, redirect to app with session cookie set

### Slice 1.7: Auth Tests

**File**: `apps/api/tests/test_auth.py`

**Test Cases**:
- Create user and request magic link
- Verify valid magic link
- Reject expired magic link
- Reject already-used magic link
- Get current user with valid session
- Reject invalid session token

---

## Phase 2: Preferences System (Days 4-7)

### Slice 2.1: Preferences Schema

**File**: `apps/api/migrations/004_preferences.sql`

```sql
-- User preferences (aggregated)
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    -- Writing style
    tone VARCHAR(50),  -- formal, conversational, confident, humble
    structure VARCHAR(50),  -- bullets, paragraphs, mixed
    sentence_length VARCHAR(50),  -- concise, detailed, mixed
    first_person BOOLEAN,
    -- Content choices
    quantification_preference VARCHAR(50),  -- heavy_metrics, qualitative, balanced
    achievement_focus BOOLEAN,  -- true = achievements, false = responsibilities
    -- Raw preferences JSON for extensibility
    custom_preferences JSONB DEFAULT '{}',
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Preference events (for learning)
CREATE TABLE preference_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id VARCHAR(255),  -- Which resume session
    event_type VARCHAR(50) NOT NULL,  -- edit, suggestion_accept, suggestion_reject
    event_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pref_events_user ON preference_events(user_id);
CREATE INDEX idx_pref_events_type ON preference_events(event_type);
```

### Slice 2.2: Preferences Service

**File**: `apps/api/services/preferences_service.py`

**Functions**:
- `get_preferences(user_id: str) -> UserPreferences`
- `update_preferences(user_id: str, updates: dict) -> UserPreferences`
- `record_event(user_id: str, event: PreferenceEvent) -> None`
- `compute_preferences_from_events(user_id: str) -> UserPreferences`

**Models**:
```python
class UserPreferences(BaseModel):
    tone: str | None = None
    structure: str | None = None
    sentence_length: str | None = None
    first_person: bool | None = None
    quantification_preference: str | None = None
    achievement_focus: bool | None = None
    custom_preferences: dict = {}

class PreferenceEvent(BaseModel):
    event_type: Literal["edit", "suggestion_accept", "suggestion_reject"]
    event_data: dict
    thread_id: str | None = None
```

### Slice 2.3: Preferences Router

**File**: `apps/api/routers/preferences.py`

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/preferences` | GET | Get user preferences |
| `/api/preferences` | PATCH | Update preferences |
| `/api/preferences/reset` | POST | Reset to defaults |
| `/api/preferences/events` | POST | Record preference event |

### Slice 2.4: Edit Tracking Integration

**File**: `apps/web/app/hooks/useEditTracking.ts`

**What to Track**:
```typescript
interface EditEvent {
  type: 'text_change' | 'section_reorder' | 'formatting_change';
  before: string;
  after: string;
  section?: string;
  metadata?: Record<string, unknown>;
}
```

**Integration Points**:
- Hook into Tiptap editor's `onUpdate` event
- Debounce events (batch within 2 seconds)
- Send to `/api/preferences/events` in background

### Slice 2.5: Suggestion Tracking

**File**: `apps/web/app/hooks/useSuggestionTracking.ts`

**What to Track**:
- Suggestion shown (with content)
- Suggestion accepted
- Suggestion rejected
- Suggestion modified before accepting

**Integration**:
- Wrap existing suggestion accept/reject handlers
- Record event type + suggestion content

### Slice 2.6: Preferences in Draft Generation

**File**: `apps/api/workflow/nodes/drafting.py` (modify)

**Changes**:
1. Accept `user_preferences` in state
2. Include preferences in LLM prompt for draft generation
3. Adjust suggestion generation based on preferences

**Prompt Addition**:
```
User Style Preferences:
- Tone: {preferences.tone or "not specified"}
- Structure: {preferences.structure or "not specified"}
- Achievement focus: {preferences.achievement_focus or "balanced"}
...

Generate the resume matching these preferences where specified.
```

### Slice 2.7: Settings Page UI

**File**: `apps/web/app/settings/profile/page.tsx`

**Sections**:
1. **Writing Style**
   - Tone selector (radio buttons)
   - Structure selector
   - First person toggle

2. **Content Preferences**
   - Achievement vs responsibility slider
   - Quantification preference selector

3. **Actions**
   - Save changes button
   - Reset to defaults button
   - Delete all data button

### Slice 2.8: Editor Sidebar

**File**: `apps/web/app/components/optimize/PreferenceSidebar.tsx`

**Features**:
- Collapsed by default (icon button to expand)
- Quick toggles for common preferences
- "View all" link to full settings page
- Shows "Learned from your edits" indicator

### Slice 2.9: Preferences Tests

**File**: `apps/api/tests/test_preferences.py`

**Test Cases**:
- Get default preferences for new user
- Update preferences
- Record edit event
- Record suggestion event
- Compute preferences from events
- Reset preferences

---

## Phase 3: Ratings System (Days 8-10)

### Slice 3.1: Ratings Schema

**File**: `apps/api/migrations/005_ratings.sql`

```sql
CREATE TABLE draft_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id VARCHAR(255) NOT NULL,
    -- Ratings
    overall_quality INTEGER CHECK (overall_quality BETWEEN 1 AND 5),
    ats_satisfaction BOOLEAN,
    would_send_as_is BOOLEAN,
    -- Optional feedback
    feedback_text TEXT,
    -- Metadata
    job_title VARCHAR(255),
    company_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ratings_user ON draft_ratings(user_id);
CREATE INDEX idx_ratings_thread ON draft_ratings(thread_id);
```

### Slice 3.2: Ratings Service

**File**: `apps/api/services/ratings_service.py`

**Functions**:
- `submit_rating(user_id: str, rating: DraftRating) -> DraftRating`
- `get_rating(thread_id: str) -> DraftRating | None`
- `get_user_ratings(user_id: str, limit: int = 10) -> list[DraftRating]`
- `get_rating_summary(user_id: str) -> RatingSummary`

**Models**:
```python
class DraftRating(BaseModel):
    thread_id: str
    overall_quality: int | None = None  # 1-5
    ats_satisfaction: bool | None = None
    would_send_as_is: bool | None = None
    feedback_text: str | None = None
    job_title: str | None = None
    company_name: str | None = None

class RatingSummary(BaseModel):
    total_ratings: int
    average_quality: float | None
    would_send_rate: float | None  # % that said yes
```

### Slice 3.3: Ratings Router

**File**: `apps/api/routers/ratings.py`

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ratings` | POST | Submit rating |
| `/api/ratings/{thread_id}` | GET | Get rating for thread |
| `/api/ratings/history` | GET | Get user's rating history |
| `/api/ratings/summary` | GET | Get user's rating summary |

### Slice 3.4: Rating Modal UI

**File**: `apps/web/app/components/optimize/RatingModal.tsx`

**Trigger**: Show after successful export (after download initiated)

**UI Elements**:
1. Star rating (1-5) - "How was this draft?"
2. ATS thumbs up/down - "Happy with ATS optimization?"
3. Yes/No - "Would you send this as-is?"
4. Optional text feedback
5. Skip button
6. Submit button

**Behavior**:
- Modal appears as overlay
- Can be dismissed (skip)
- Saves to localStorage if not authenticated
- Syncs to server if authenticated

### Slice 3.5: Rating History in Profile

**File**: `apps/web/app/settings/profile/page.tsx` (add section)

**Section**: Rating History
- Summary stats (avg rating, total ratings)
- Recent ratings list
- Link to detailed history page (optional)

### Slice 3.6: Ratings Tests

**File**: `apps/api/tests/test_ratings.py`

**Test Cases**:
- Submit rating
- Get rating by thread
- Get user rating history
- Get rating summary
- Update existing rating

---

## Phase 4: Anonymous to Auth Migration (Days 11-12)

### Slice 4.1: LocalStorage Schema

**File**: `apps/web/app/hooks/useLocalPreferences.ts`

**LocalStorage Keys**:
```typescript
const STORAGE_KEYS = {
  preferences: 'resume_agent:preferences',
  pendingEvents: 'resume_agent:pending_events',
  pendingRatings: 'resume_agent:pending_ratings',
  anonymousId: 'resume_agent:anonymous_id',
};
```

### Slice 4.2: Migration Service

**File**: `apps/api/services/migration_service.py`

**Functions**:
- `migrate_anonymous_data(user_id: str, data: AnonymousData) -> MigrationResult`

**Models**:
```python
class AnonymousData(BaseModel):
    preferences: UserPreferences | None
    events: list[PreferenceEvent]
    ratings: list[DraftRating]
    anonymous_id: str

class MigrationResult(BaseModel):
    preferences_migrated: bool
    events_migrated: int
    ratings_migrated: int
```

### Slice 4.3: Migration Router

**File**: `apps/api/routers/auth.py` (add endpoint)

**Endpoint**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/migrate` | POST | Migrate anonymous data to user |

**Called**: After successful magic link verification, if localStorage has data

### Slice 4.4: Frontend Migration Flow

**File**: `apps/web/app/auth/verify/page.tsx` (modify)

**Flow**:
1. Verify magic link token
2. Check localStorage for anonymous data
3. If data exists, call `/api/auth/migrate`
4. Clear localStorage after successful migration
5. Redirect to app

### Slice 4.5: Save Prompt Component

**File**: `apps/web/app/components/auth/SavePrompt.tsx`

**Triggers**:
- After first completed resume
- When returning to app (if not authenticated)
- After 3+ preference events recorded

**UI**:
- Non-intrusive banner or modal
- "Save your preferences?" message
- Email input + "Save" button
- "Maybe later" dismiss option

---

## Phase 5: Testing & Polish (Days 13-14)

### Integration Tests

**File**: `apps/api/tests/integration/test_memory_flow.py`

**Scenarios**:
1. New user flow: anonymous → preferences → auth → migration
2. Returning user flow: login → preferences applied → edit → new preferences saved
3. Rating flow: generate draft → export → rate → view in history

### E2E Tests

**File**: `apps/web/e2e/tests/memory.spec.ts`

**Test Cases**:
- Magic link login flow
- Preferences page loads with defaults
- Update preference and verify persistence
- Rate a draft after export
- Anonymous data migration on login

### Error Handling

**Backend**:
- Graceful fallback if preferences service fails
- Retry logic for email sending
- Rate limiting on auth endpoints

**Frontend**:
- Offline support for preference/rating capture
- Sync queue for pending events
- Clear error messages

### Monitoring

- Log preference event counts
- Track auth conversion rate (anonymous → authenticated)
- Alert on email delivery failures

---

## File Structure Summary

```
apps/api/
├── migrations/
│   ├── 003_user_auth.sql
│   ├── 004_preferences.sql
│   └── 005_ratings.sql
├── services/
│   ├── auth_service.py
│   ├── email_service.py
│   ├── preferences_service.py
│   ├── ratings_service.py
│   └── migration_service.py
├── routers/
│   ├── auth.py
│   ├── preferences.py
│   └── ratings.py
├── middleware/
│   └── session_auth.py
└── tests/
    ├── test_auth.py
    ├── test_preferences.py
    ├── test_ratings.py
    └── integration/test_memory_flow.py

apps/web/app/
├── auth/
│   ├── login/page.tsx
│   └── verify/page.tsx
├── settings/
│   └── profile/page.tsx
├── components/
│   ├── auth/
│   │   ├── AuthGuard.tsx
│   │   └── SavePrompt.tsx
│   └── optimize/
│       ├── RatingModal.tsx
│       └── PreferenceSidebar.tsx
├── hooks/
│   ├── useAuth.ts
│   ├── useEditTracking.ts
│   ├── useSuggestionTracking.ts
│   └── useLocalPreferences.ts
└── e2e/tests/
    └── memory.spec.ts
```

---

## Environment Variables

```bash
# Email service
EMAIL_API_KEY=xxx
EMAIL_FROM_ADDRESS=noreply@example.com

# JWT
JWT_SECRET=xxx
JWT_EXPIRY_DAYS=7

# Magic link
MAGIC_LINK_EXPIRY_MINUTES=15
FRONTEND_URL=http://localhost:3000
```

---

## Dependencies

**Backend**:
- `pyjwt` - JWT token handling
- `resend` or `sendgrid` - Email sending
- `email-validator` - Email validation

**Frontend**:
- No new dependencies (uses existing React patterns)

---

## Rollout Plan

1. **Week 1**: Auth + Preferences backend, Settings UI
2. **Week 2**: Ratings, Migration, Integration testing
3. **Soft launch**: Feature flag for beta users
4. **GA**: Remove feature flag, enable for all

---

## Implementation Progress

### Phase 1: Authentication - COMPLETE (2025-01-15)

**Files Created:**
- `apps/api/migrations/003_user_auth.sql` - Database schema for users, magic_links, user_sessions
- `apps/api/services/auth_service.py` - Core auth service with JWT, magic links, user management
- `apps/api/services/email_service.py` - Email service with Resend integration + console fallback
- `apps/api/routers/auth.py` - Auth API endpoints (request-link, verify, me, logout, refresh)
- `apps/api/middleware/session_auth.py` - Session middleware dependencies for protected routes
- `apps/api/tests/test_auth.py` - 34 comprehensive tests (all passing)

**Files Modified:**
- `apps/api/main.py` - Added auth router
- `apps/api/requirements.txt` - Added pyjwt, resend, email-validator
- `.env.example` - Added auth-related environment variables

**Test Results:** 34/34 tests passing

### Phase 2: Preferences System - COMPLETE (2025-01-15)

**Files Created:**
- `apps/api/migrations/004_preferences.sql` - Database schema for user_preferences, preference_events
- `apps/api/services/preferences_service.py` - Preferences CRUD, event recording, preference computation
- `apps/api/routers/preferences.py` - Preferences API endpoints (get, update, reset, events, compute)
- `apps/api/tests/test_preferences.py` - 24 comprehensive tests (all passing)

**Files Modified:**
- `apps/api/main.py` - Added preferences router

**Endpoints:**
- `GET /api/preferences` - Get user preferences
- `PATCH /api/preferences` - Update preferences
- `POST /api/preferences/reset` - Reset to defaults
- `DELETE /api/preferences` - Delete all preference data
- `POST /api/preferences/events` - Record preference event
- `GET /api/preferences/events` - Get preference events
- `POST /api/preferences/compute` - Compute preferences from events
- `POST /api/preferences/events/anonymous` - Record events for anonymous users

**Test Results:** 24/24 tests passing

### Phase 3: Ratings System - COMPLETE (2025-01-15)

**Files Created:**
- `apps/api/migrations/005_ratings.sql` - Database schema for draft_ratings
- `apps/api/services/ratings_service.py` - Ratings CRUD, history, summary
- `apps/api/routers/ratings.py` - Ratings API endpoints
- `apps/api/tests/test_ratings.py` - 20 comprehensive tests (all passing)

**Files Modified:**
- `apps/api/main.py` - Added ratings router

**Endpoints:**
- `POST /api/ratings` - Submit a rating
- `GET /api/ratings/{thread_id}` - Get rating for a thread
- `GET /api/ratings/history` - Get user's rating history
- `GET /api/ratings/summary` - Get user's rating summary
- `DELETE /api/ratings/{rating_id}` - Delete a rating
- `POST /api/ratings/anonymous` - Submit anonymous rating

**Test Results:** 20/20 tests passing

### Phase 4: Migration Service - COMPLETE (2025-01-15)

**Files Created:**
- `apps/api/services/migration_service.py` - Anonymous to authenticated data migration
- `apps/api/tests/test_migration.py` - 29 comprehensive tests (all passing)

**Files Modified:**
- `apps/api/routers/auth.py` - Added `/api/auth/migrate` endpoint

**Features:**
- Preferences migration with conflict resolution (server wins)
- Events migration with type filtering (edit, suggestion_accept, suggestion_reject)
- Ratings migration with duplicate detection
- Automatic cleanup of anonymous data after migration
- Partial failure handling with detailed error reporting

**Test Results:** 29/29 tests passing

### Phase 5: Integration Tests - COMPLETE (2025-01-15)

**Files Created:**
- `apps/api/tests/test_memory_flow.py` - 9 integration tests

**Test Coverage:**
- Full auth flow: request-link → verify → me → logout
- Deactivated user blocking
- Migration flow with service integration
- Error handling for protected routes
- Input validation (invalid email, expired tokens)

**Test Results:** 9/9 tests passing

**Total Backend Tests:** 116 passing (34 auth + 24 preferences + 20 ratings + 29 migration + 9 integration)

---

## Frontend Implementation Status

### Phase 1.6: Auth UI - COMPLETE (2025-01-15)

**Files Created:**
- `apps/web/app/auth/login/page.tsx` - Email input form with magic link request
- `apps/web/app/auth/verify/page.tsx` - Token verification with migration flow
- `apps/web/app/hooks/useAuth.tsx` - Auth context with login, verify, logout, refresh
- `apps/web/app/components/auth/AuthGuard.tsx` - Protected route wrapper + OptionalAuth

**Files Modified:**
- `apps/web/app/layout.tsx` - Added AuthProvider wrapper

### Phase 2.7-2.8: Preferences UI - COMPLETE (2025-01-15)

**Files Created:**
- `apps/web/app/hooks/usePreferences.ts` - Preferences hook with localStorage fallback
- `apps/web/app/settings/profile/page.tsx` - Full settings page with:
  - Writing style preferences (tone, structure, sentence length, first person)
  - Content preferences (quantification, achievement focus)
  - Reset to defaults functionality
  - User info display and logout

### Phase 3.4: Rating Modal - COMPLETE (2025-01-15)

**Files Created:**
- `apps/web/app/components/optimize/RatingModal.tsx` - Post-export rating modal with:
  - Star rating (1-5)
  - ATS satisfaction thumbs up/down
  - Would-send-as-is yes/no
  - Optional text feedback
  - Anonymous user localStorage support

### Phase 4.4-4.5: Migration UI - COMPLETE (2025-01-15)

**Files Created:**
- `apps/web/app/components/auth/SavePrompt.tsx` - Floating prompt for anonymous users
- Migration flow integrated in verify page (checks localStorage, calls /api/auth/migrate)

---

## Success Criteria

- [x] Magic link auth works end-to-end (Phase 1 complete - backend + frontend)
- [x] Preferences persist across sessions (Phase 2 complete - backend API + frontend settings)
- [x] Preferences influence draft generation (Phase 2.6 complete - integrated into drafting workflow)
- [x] Ratings captured and displayed (Phase 3 complete - backend API + frontend modal)
- [x] Anonymous → auth migration works (Phase 4 complete - backend API + frontend flow)
- [x] Backend tests pass (134/134)
- [x] Frontend auth UI (login, verify, AuthGuard)
- [x] Frontend preferences UI (settings page, usePreferences hook)
- [x] Frontend ratings UI (RatingModal, SavePrompt)
- [x] Frontend build passes
- [ ] E2E tests for memory feature
- [x] Preferences integrated into drafting workflow
- [x] No regressions in existing functionality (134 Memory tests + core tests pass)
- [x] E2E tests for memory feature (13 tests passing)

---

## E2E Tests - COMPLETE (2025-01-15)

**File Created:**
- `apps/web/e2e/tests/memory-feature.spec.ts` - 13 E2E tests with mocked APIs

**Test Coverage:**
- Authentication: login page, magic link request, token verification, invalid token handling
- Preferences: settings page display, tone changing, first person toggle, reset functionality
- Anonymous User: localStorage storage, save prompt
- Migration: anonymous data migration on login
- Workflow Integration: preferences in localStorage, Start Optimization button visibility

**Test Results:** 13/13 passing in 6.2 seconds

---

## Phase 2.6: Preferences in Draft Generation - COMPLETE (2025-01-15)

**Files Modified:**
- `apps/api/workflow/state.py` - Added `user_preferences` field to ResumeState
- `apps/api/workflow/graph.py` - Updated `create_initial_state()` to accept user_preferences
- `apps/api/workflow/nodes/drafting.py` - Added `_format_user_preferences()` helper, integrated preferences into `_build_drafting_context()` and `RESUME_DRAFTING_PROMPT`
- `apps/api/routers/optimize.py` - Added `user_preferences` to StartWorkflowRequest, passed to initial state
- `apps/api/tests/test_drafting.py` - Added 12 tests for `_format_user_preferences()` function

**Integration Points:**
1. `StartWorkflowRequest` accepts optional `user_preferences` dict
2. Preferences are stored in workflow state via `create_initial_state()`
3. `draft_resume_node` extracts preferences and passes to `_build_drafting_context()`
4. `_format_user_preferences()` converts preference dict to LLM-friendly prompt text
5. Preferences section added to context with guidance for each preference type

**Preference Mappings:**
- tone: formal/conversational/confident/humble → LLM-friendly descriptions
- structure: bullets/paragraphs/mixed → formatting guidance
- sentence_length: concise/detailed/mixed → style guidance
- first_person: true/false → voice guidance ("I" vs implied)
- quantification_preference: heavy_metrics/qualitative/balanced → emphasis guidance
- achievement_focus: true/false → content focus guidance

**Test Results:** 12/12 new tests passing, 38/38 total drafting tests passing
