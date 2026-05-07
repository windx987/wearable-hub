# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Open Wearables is a self-hosted health/wearable data aggregation platform that unifies data from providers (Garmin, Whoop, Apple Health, Samsung Health, Polar, Suunto, etc.) and exposes it via REST API with AI-powered integrations via MCP.

**Specialized guides:** [backend/AGENTS.md](backend/AGENTS.md) · [frontend/AGENTS.md](frontend/AGENTS.md) · [mcp/README.md](mcp/README.md)

## Development

### Start everything (recommended)

```bash
docker compose up -d   # starts PostgreSQL, FastAPI, Celery, Redis, frontend
make seed              # optional: seed sample data
```

Access: Frontend `http://localhost:3000` · API `http://localhost:8000` · Swagger `http://localhost:8000/docs` · Flower `http://localhost:5555`

### Backend commands

```bash
cd backend
uv run ruff check . --fix && uv run ruff format .   # lint + format
uv run ty check .                                    # type check
uv run pytest -v --cov=app                           # all tests
uv run pytest tests/path/to/test_file.py::test_name  # single test
uv add <package>                                     # add dependency
```

### Frontend commands

```bash
cd frontend
pnpm run dev          # dev server on port 3000
pnpm run lint:fix && pnpm run format   # lint + format
pnpm run test         # all tests (Vitest)
pnpm run build        # production build
pnpm dlx shadcn@latest add <component>   # add shadcn/ui component
```

### Database migrations

```bash
make create_migration m="Description"   # generate Alembic migration
make migrate                            # apply migrations
make downgrade                          # rollback last migration
```

## Architecture

### Backend layers (strict separation)

```
Request → Route → Service → Repository → Database
Response ← Route ← Service ← Repository ←
```

- **Routes** (`app/api/routes/v1/`) — minimal, delegate to services; never call repositories directly
- **Services** (`app/services/`) — all business logic; type hints mandatory on every function
- **Repositories** (`app/repositories/`) — database CRUD only; input/output are SQLAlchemy models only
- **Schemas** (`app/schemas/`) — Pydantic validation/serialization; validation logic lives here, not in models
- **Models** (`app/models/`) — SQLAlchemy ORM table definitions using custom type aliases from `app/mappings.py`

Router hierarchy: module router → `v1/__init__.py` (adds tags) → `routes/__init__.py` (adds version prefix) → `main.py`

### Frontend layers

- **Routes** (`src/routes/`) — TanStack Router file-based pages; `_authenticated.tsx` guards protected pages
- **Hooks** (`src/hooks/api/`) — React Query hooks; always use the query key factory from `src/lib/query/keys.ts`
- **Services** (`src/lib/api/services/`) — API calls via `apiClient`
- **Components** (`src/components/`) — `ui/` = shadcn, `common/` = shared, feature dirs for everything else

### Provider integrations

New wearable providers implement `BaseProviderStrategy` in `app/services/providers/`. See [docs/dev-guides/how-to-add-new-provider.mdx](docs/dev-guides/how-to-add-new-provider.mdx).

## Key conventions

**Backend:**
- All Python functions require type annotations
- All imports at module level — never inside functions
- Route paths use kebab-case (`/heart-rate`), no trailing slashes (use `""` not `"/"` on prefixed routers — trailing slash causes 307 redirects behind HTTPS proxies)
- Use `raise_404=True` in services; raise `HTTPException` directly in routes
- In Celery/batch tasks that catch exceptions instead of re-raising, use `log_and_capture_error()` from `app.utils.sentry_helpers` — never bare `except` with only a logger call

**Frontend:**
- Never hardcode route paths — use `ROUTES` / `DEFAULT_REDIRECTS` from `src/lib/constants/routes.ts`
- Always add new query keys to the factory in `src/lib/query/keys.ts`
- Use `cn()` from `@/lib/utils` for conditional Tailwind classes
- Notifications via `toast` from `sonner`

**Documentation:**
- When adding/changing API endpoints, providers, or data schemas, update `docs/`
- When adding/removing external API endpoints (tagged `External: *`), update the `API Reference` tab in `docs/docs.json`

**Pull Requests (mandatory for AI-authored PRs):**
Include a `## Pancake Recipe` section at the very end of the PR description — generate a creative step-by-step recipe from scratch, then sign it with `**Your chef: {model name}**`.
