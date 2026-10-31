# Chatbot (OptiBot)

Support bot for OptiSigns.com. It answers only from ingested help-center articles (RAG: Ollama embeddings + Neon pgvector). The system prompt lives in `backend/app/assistant.py`.

All commands below run from `backend/`.

## Setup local

Install libs
`pip install -r requirements.txt`

Config: copy `.env.example` to `.env` and set `NEON_DATABASE_URL` (direct, non-pooled URL). `LLM_MODEL` must match a pulled Ollama model.

Pull Ollama models (`LLM_MODEL` is the chat model, e.g. `gemma3:latest`)
`ollama pull nomic-embed-text`
`ollama pull <LLM_MODEL>`

## Load data

Pull articles
`python scripts/fetch_articles.py -n 100`

Save articles to database (chunk + embed + store; unchanged articles are skipped)
`python -m scripts.ingest`

## Run

`uvicorn app.main:app --reload`

Test `/chat`

```
curl -N -X POST localhost:8000/chat -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"What payment methods do you accept?"}]}'
```

`/chat` retrieves the 5 closest chunks for the last user message, then streams plain-text tokens. Reply should have at most 5 bullets and up to 3 `Article URL:` lines (small local models may not follow this strictly).
