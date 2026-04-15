# Telegram Dating Bot Practice

Репозиторий по практике Dating Bot.

## Этапы

1. Этап 1 (проектирование) - готово:
- [docs/01-services.md](docs/01-services.md)
- [docs/02-architecture.md](docs/02-architecture.md)
- [docs/03-database-schema.md](docs/03-database-schema.md)

2. Этап 2 (базовая функциональность) - реализовано:
- Telegram Bot API интеграция (long polling)
- регистрация пользователя по `/start`
- базовые команды из этапа 1: `/start`, `/profile`, `/prefs`, `/next`, `/like`, `/skip`, `/help`

## Архитектура Этапа 2

- `Bot` слой: `stage2_bot/bot_service.py`, `stage2_bot/telegram_api.py`
- `Core` слой: `stage2_bot/core.py`
- `Data` слой (PostgreSQL): `stage2_bot/db.py`, `db/schema.sql`

## Требования

- Python 3.11+
- PostgreSQL
- Python-пакет `psycopg[binary]`

Установка зависимости:

```bash
pip install psycopg[binary]
```

## Запуск Stage 2

1. Подготовить переменные:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/dating_bot"
```

2. Запустить бота:

```bash
python3 -m stage2_bot.run
```

При старте бот автоматически применит SQL из `db/schema.sql`.

## Что уже работает в Этапе 2

- `/start`: создает/обновляет пользователя в таблице `users` по `telegram_id`
- `/profile`: показывает базовые поля профиля
- `/prefs`: создает дефолтные предпочтения (если отсутствуют) и показывает их
- `/next`, `/like`, `/skip`: базовые заглушки интерфейса до Этапа 3

Подробный отчет: [docs/04-stage2-basic-functionality.md](docs/04-stage2-basic-functionality.md)

