# CognosOS

CognosOS is a local-first forced-writing and cognitive workflow prototype. It helps a user move from mental loop to structured writing, decision trace, next action, and future review.

The durable user-facing output is Markdown. Obsidian is optional: it can open the Markdown vault folder directly, but the same files also work in VS Code, Typora, iA Writer, Finder, or any Markdown editor.

## Status

This is an early prototype, not a production SaaS product.

CognosOS is not medical advice, therapy, CBT treatment, diagnosis, or crisis support. It is a personal thinking and writing tool. Remote model calls should be treated as third-party data processing.

The default launcher binds services to `127.0.0.1` for single-user local use. Do not expose the backend to a LAN, reverse proxy, or public internet without adding authentication first.

## What It Includes

- A Vite/React Breakthrough Canvas frontend.
- A FastAPI backend.
- SQLite for the local launcher, with PostgreSQL/pgvector support for heavier use.
- Markdown vault export for user-visible notes.
- Optional Gemini providers for extraction, judging, and embeddings.
- Time capsules, trigger events, and module run records for future review loops.

## Architecture

```text
Frontend
  -> staged forced-writing session
  -> save entry

Backend
  -> raw entry
  -> extractor provider: mock or Gemini
  -> embedding provider: mock, sentence-transformers, or Gemini
  -> retrieval and deterministic trigger rules
  -> judge provider: mock or Gemini
  -> cards, trigger events, time capsules
  -> Markdown projection
```

Recommended storage split:

```text
Markdown = durable user-visible storage
Database = internal index, embeddings, processing state, and reminders
```

## Privacy Model

- `.env` is ignored by git. Do not commit API keys.
- `.env.example` contains empty placeholders only.
- Remote LLM calls are blocked unless `ALLOW_REMOTE_LLM=true`.
- The default providers are local/mock providers.
- Markdown files are written to `COGNOSOS_VAULT_PATH`.
- Local SQLite databases are ignored by git.

Gemini setup lives in your local `.env`:

```env
ALLOW_REMOTE_LLM=true
GEMINI_API_KEY=
LLM_PROVIDER=gemini
EMBEDDING_PROVIDER=gemini
```

What can leave your machine:

| Mode | Network | Data sent | Default |
| --- | --- | --- | --- |
| Mock extractor/judge | No | Nothing | Yes |
| Mock embedding fallback | No | Nothing | Yes, when local embedding is unavailable |
| Sentence-transformers embedding | No | Nothing | Optional |
| Gemini extractor/judge | Yes | User writing and derived context needed for extraction or trigger judging | No |
| Gemini embedding | Yes | Card text, module text, or search query text sent for embedding | No |

## Storage and Backup

- Markdown vault: the durable user-visible writing output.
- SQLite/PostgreSQL: internal processing state, embeddings, trigger events, time capsules, and module run state.
- If you delete the database, Markdown notes remain, but internal indexes, reminders, embeddings, and processing history may be lost.
- Full database-from-Markdown rebuild is not implemented yet.
- Back up both the Markdown vault and database if you need full recovery.

## Quick Start

Prerequisites:

- Python 3.11 or newer.
- Node.js 20 or newer.
- npm.
- macOS or Linux for the shell launcher. Windows is not yet documented.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
cp .env.example .env
cd frontend
npm install
npm run build
cd ..
./scripts/start-cognosos.command
```

The launcher uses local SQLite by default and serves the built frontend at:

```text
http://127.0.0.1:5173/
```

Default local ports:

```text
Backend:  http://127.0.0.1:8000/
Frontend: http://127.0.0.1:5173/
```

The launcher writes the local SQLite file to:

```text
./cognosos_demo.db
```

## Development

Backend:

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Markdown Vault

Set the vault folder in `.env`:

```env
COGNOSOS_VAULT_PATH=./obsidian-vault-demo
COGNOSOS_DAILY_FOLDER=Calendar
```

Legacy aliases still work:

```env
MARKDOWN_VAULT_PATH=./obsidian-vault-demo
MARKDOWN_DAILY_FOLDER=Calendar
OBSIDIAN_VAULT_PATH=./obsidian-vault-demo
OBSIDIAN_DAILY_FOLDER=Calendar
```

Open the vault folder with Obsidian or any Markdown editor.

## macOS Launcher

For local development, double-click:

```text
CognosOS Launcher.app
```

The app bundle is a convenience wrapper around:

```bash
./scripts/start-cognosos.command
```

It is not a signed distributable Mac app. Keep it at the repository root, or set `COGNOSOS_PROJECT_DIR` to the repository path before launching it from another location.

## Optional Providers

For local sentence-transformers embeddings:

```bash
pip install -e ".[embeddings]"
```

For Gemini LLM and embedding providers:

```bash
pip install -e ".[gemini]"
```

Gemini embeddings use the configured `EMBEDDING_DIM`; the current PostgreSQL vector schema expects `1024`.

## PostgreSQL

The Docker Compose service is for local development only. It uses `pgvector/pgvector:pg16`, the default `postgres/postgres` credentials, and initializes:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

Run migrations with:

```bash
docker compose up -d
alembic upgrade head
```

## API Examples

Health:

```bash
curl http://localhost:8000/health
```

Create an entry:

```bash
curl -X POST http://localhost:8000/entries \
  -H "Content-Type: application/json" \
  -d '{"content":"今天有点焦虑，系统太复杂了。","source":"text"}'
```

Search:

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"系统太复杂","statuses":["open"],"days_back":90,"limit":5,"min_similarity":0.1}'
```

## Tests

```bash
pytest
cd frontend && npm run build
```

Tests use SQLite dependency overrides, so they do not require Docker or pgvector.

## Troubleshooting

Stop local services started by the launcher:

```bash
./scripts/stop-cognosos.command
```

Rebuild the frontend:

```bash
cd frontend
npm run build
```

Before publishing a fork or public repository, scan the current tree and git history for secrets. For example:

```bash
gitleaks detect --source .
```

## MVP Limitations

- The default extractor and judge are deterministic mock providers.
- If `sentence-transformers` is not installed, the app falls back to the deterministic mock embedder.
- Hybrid retrieval currently applies SQL filters first and cosine ranking in Python for SQLite/PostgreSQL portability.
- Graph files are thin wrappers around services and can be wired into external LangGraph later.
- The macOS launcher is for local development, not app-store distribution.

## License

MIT.
