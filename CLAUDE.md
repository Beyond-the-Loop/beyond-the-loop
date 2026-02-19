# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Beyond the Loop is a full-stack AI chat/SaaS platform built as a fork of Open WebUI. It has a **dual-backend** architecture: custom business logic lives in `backend/beyond_the_loop/` while the upstream Open WebUI foundation lives in `backend/open_webui/`.

## Tech Stack

- **Frontend**: SvelteKit 2 + Svelte 4, TypeScript, Tailwind CSS 3, Vite 5
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2, Alembic (migrations)
- **Database**: PostgreSQL with pgvector extension
- **Cache/Sessions**: Redis (Valkey 8.1)
- **LLM Routing**: LiteLLM proxy (port 4000), configured via `litellm-config.yaml`
- **Real-time**: Socket.IO (Redis as message broker)

## Development Commands

### Local Infrastructure
```bash
docker-compose -f docker-compose-local.yaml up    # PostgreSQL, Redis, LiteLLM
```

### Frontend
```bash
npm run dev              # Vite dev server (port 5173)
npm run build            # Production build → /build
npm run check            # SvelteKit type checking (svelte-check)
npm run lint             # Full lint (frontend + types + backend)
npm run lint:frontend    # ESLint with --fix
npm run format           # Prettier
npm run test:frontend    # Vitest (frontend unit tests)
```

### Backend
```bash
cd backend && ./start.sh                # Uvicorn on port 8080
# Or directly:
PYTHONPATH=backend python -m uvicorn open_webui.main:app --host 0.0.0.0 --port 8080
```

### Database Migrations (Alembic)
```bash
./backend/run_alembic.sh current                      # Show current revision
./backend/run_alembic.sh upgrade head                  # Apply all migrations
./backend/run_alembic.sh revision -m "description"     # Create new migration
./backend/run_alembic.sh history                       # Show migration history
```

Migrations live in `backend/open_webui/migrations/versions/`. Migrations auto-run on app startup via `run_migrations()` in `beyond_the_loop/config.py`.

### Backend Formatting
```bash
npm run format:backend   # Black formatter (excludes venvs)
```

## Architecture

### Dual-Backend Structure

The backend has two Python packages that work together:

- **`backend/beyond_the_loop/`** — Custom business logic (payments, analytics, CRM, company management, credit system). Routers here handle: `auths`, `analytics`, `chats`, `companies`, `configs`, `domains`, `files`, `folders`, `groups`, `knowledge`, `models`, `payments`, `prompts`, `users`, `audio`, `openai`, `intercom`.

- **`backend/open_webui/`** — Upstream Open WebUI fork (core chat infrastructure, RAG, image generation, evaluations, channels, memories). Contains `main.py` (FastAPI app entry point), Alembic config, and DB models.

Both packages' routers are mounted in `backend/open_webui/main.py`. The `beyond_the_loop` package imports from `open_webui` (e.g., DB session, env vars, base models).

### Multi-Tenancy

Data is scoped by `company_id`. Company config is cached in `COMPANY_CONFIG_CACHE` (Redis-backed). Auth uses JWT tokens with configurable expiry.

### Frontend Structure

- **`src/routes/`** — SvelteKit page routes
- **`src/lib/apis/`** — Typed API client modules (one per backend domain)
- **`src/lib/components/`** — Svelte UI components (chat, layout, workspace, etc.)
- **`src/lib/stores/`** — Svelte stores for global state
- **`src/lib/utils/`** — Frontend utilities

The frontend builds to static files (`@sveltejs/adapter-static`) with `index.html` as SPA fallback, served by FastAPI in production.

### Request Flow

Chat requests go through middleware in `backend/open_webui/utils/middleware.py` (`process_chat_payload` → LiteLLM proxy → `process_chat_response`). The LiteLLM proxy handles model routing to various LLM providers (Claude, GPT, Gemini, etc.).

### Key Config Files

- `.env` — API keys, database URLs, feature flags
- `litellm-config.yaml` — LLM model definitions and routing
- `backend/open_webui/alembic.ini` — Migration configuration
- `docker-compose-local.yaml` — Local dev services (PostgreSQL, Redis, LiteLLM)
- `docker-compose-prod.yaml` — Production deployment
