# Demo 01 — Basic agent memory loop

MEMORYBANK gives an AI agent a portable, file-backed long-term memory. Memories
are stored as JSONL and retrieved with a hybrid score that blends **lexical
relevance**, **importance**, and **exponential recency decay** — so the most
useful facts surface first, just like a production agent-memory layer, but with
zero dependencies.

## Setup

Seed a bank from the realistic input file (one fact per line, optionally with
`#tags` and an `!importance`):

```sh
while IFS= read -r line; do
  python -m memorybank --path /tmp/agent.jsonl remember "$line"
done < demos/01-basic/seed_memories.txt
```

Or just store a couple directly:

```sh
python -m memorybank --path /tmp/agent.jsonl \
  remember "User prefers dark mode and concise answers" --tag prefs --importance 3
python -m memorybank --path /tmp/agent.jsonl \
  remember "Deployment uses Docker compose with six services" --tag infra
```

## Recall

When the agent needs context, query the bank:

```sh
python -m memorybank --path /tmp/agent.jsonl recall "what UI preferences does the user have" --format table
```

The `prefs` memory ranks first because it is both relevant and high-importance.
Each `recall` also "touches" the returned memories, refreshing their recency so
frequently-used facts decay slower.

## Inspect

```sh
python -m memorybank --path /tmp/agent.jsonl stats
```

Returns the count, tag histogram, and total access count for the bank.
