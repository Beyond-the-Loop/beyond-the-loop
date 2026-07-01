#!/usr/bin/env bash
# Copy to env.staging.sh / env.prod.sh (both gitignored) and fill in.
# Usage: source tests/load/env.staging.sh && k6 run tests/load/chat-completion.js

# Target: staging on K8s
export BASE_URL="https://staging.chat.beyondtheloop.ai"

# DB id of a Model row (NOT the friendly name from litellm-config.yaml).
# To find it: log in via UI, GET /api/models with your token, pick a cheap one.
# Prefer Haiku or Gemini Flash to keep test cost low.
export MODEL_ID="REPLACE_ME"

# Pool of test users. Create dedicated load-test accounts, not real users.
# Multiple accounts spread load across company_id partitions if you multi-tenant.
export USERS_JSON='[
  {"email":"loadtest+1@beyondtheloop.ai","password":"REPLACE_ME"},
  {"email":"loadtest+2@beyondtheloop.ai","password":"REPLACE_ME"}
]'

# Seconds of idle time between requests per VU (simulates human read time).
export THINK_TIME=2

# Streaming vs. non-streaming. Keep true to match real chat behavior.
export STREAM=true
