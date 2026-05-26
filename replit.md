# Workspace

## Overview

pnpm workspace monorepo using TypeScript, plus a standalone Python Telegram bot at the workspace root.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)
- **Python version**: 3.12
- **Telegram bot library**: python-telegram-bot 21.11.1

## Telegram Bot

- Entry point: `bot.py`
- Dependencies: `requirements.txt`
- Required secrets: `TELEGRAM_BOT_TOKEN`, `CHART_IMG_API_KEY`
- Run command: `python bot.py`
- Bot behavior: sends EURUSD charts from chart-img.com API v2 for the last 10 candles using official interval IDs (`5m`, `15m`, `1h`, `4h`).
- Supported messages:
  - `М5` — EURUSD 5-minute chart
  - `М15` — EURUSD 15-minute chart
  - `H1` — EURUSD 1-hour chart
  - `H4` — EURUSD 4-hour chart
  - `All` — all four charts

## Key Commands

- `python bot.py` — run the Telegram bot
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.
