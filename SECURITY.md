# Security Policy

CognosOS may process private writing, decisions, logs, embeddings, and Markdown vault files.

Do not post any of the following in public issues, discussions, pull requests, screenshots, or logs:

- personal journal entries or vault files
- `.env` files
- API keys
- local SQLite/PostgreSQL dumps
- screenshots containing private writing
- logs that include user writing or model prompts

Remote LLM features are opt-in and require `ALLOW_REMOTE_LLM=true`. Treat any enabled remote provider as third-party processing.

For security reports, use GitHub private vulnerability reporting if it is enabled for the repository. If no private channel exists yet, contact the maintainer privately before sharing sensitive details.
