# Keitaro Wrapper

Обёртка над Keitaro Admin API: создание рекламных кампаний и редактор офферов в потоках.
Тестовое задание: FastAPI + SQLAlchemy (backend), React + Vite (frontend).

Полное описание требований, логики и алгоритмов — в [PRD.md](PRD.md).

## Возможности

- **Создание кампании**: название, гео-код, оффер, домен, группа, источник → кампания в
  Keitaro с двумя потоками:
  - Flow 1 — принимает трафик из выбранной страны и редиректит на Google;
  - Flow 2 — отдаёт остальной трафик выбранному офферу.
- **Редактор кампании**: добавление/удаление офферов, возврат удалённых, pin весов,
  публикация (`Push`) и отмена черновика (`Cancel`), синхронизация с Keitaro
  (`Fetch streams`).

## Запуск

Backend (Python 3.11+, [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
cp .env.example .env      # вписать KEITARO_API_KEY
uv sync
uv run uvicorn app.main:app --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

После сборки FastAPI раздаёт `frontend/dist` на <http://127.0.0.1:8000>.
Для разработки фронта: `npm run dev` — Vite проксирует `/api` на `127.0.0.1:8000`.

## Конфигурация

Секреты читаются из `backend/.env` (gitignored); переменные окружения имеют
приоритет. Шаблон — `backend/.env.example`.

| Переменная | По умолчанию |
| --- | --- |
| `KEITARO_API_KEY` | нет; приложение не стартует без ключа |
| `KEITARO_BASE_URL` | `https://tlgk.host/admin_api/v1` |
| `DB_PATH` | `backend/keitaro.db` (создаётся автоматически) |

## Структура

```
backend/
  app/
    main.py        # API, веса, создание кампаний, синхронизация
    models.py      # SQLAlchemy-модели
    keitaro.py     # HTTP-клиент Keitaro Admin API
    db.py          # SQLite/сессии
  check_weights.py # проверка алгоритма весов
frontend/
  src/App.jsx      # список кампаний, создатель, редактор потоков
  src/styles.css
```
