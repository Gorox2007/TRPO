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

3. Этап 3 (анкеты и ранжирование) - реализовано:
- CRUD анкеты через команды `/profile`, `/profile_set`, `/profile_delete`
- добавление фото через Telegram photo message или `/photo_add`
- обновление предпочтений через `/prefs`
- ранжирование кандидатов по первичным, поведенческим и комбинированным факторам
- in-memory кэш предварительно отранжированной очереди кандидатов
- рабочие `/next`, `/like`, `/skip` с созданием взаимных мэтчей

## Архитектура

- `Bot` слой: `stage2_bot/bot_service.py`, `stage2_bot/telegram_api.py`
- `Core` слой: `stage2_bot/core.py`, `stage2_bot/cache.py`
- `Data` слой (PostgreSQL): `stage2_bot/db.py`, `db/schema.sql`

## Требования

- Python 3.11+
- PostgreSQL
- Python-пакет `psycopg[binary]`

Установка зависимости:

```bash
pip install psycopg[binary]
```

## Запуск Stage 3

1. Подготовить переменные:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/dating_bot"
```

2. Запустить бота из папки `project`:

```bash
python3 -m stage2_bot.run
```

При старте бот автоматически применит SQL из `db/schema.sql`.

## Основные команды

- `/start [referral_code]` - регистрация и реферальный код.
- `/profile` - просмотр анкеты.
- `/profile_set birth_date=2000-01-31 gender=female city=Москва bio="Люблю кофе"` - создание или обновление анкеты.
- `/profile_delete` - удаление анкеты.
- `/prefs age=18-35 gender=any city=any distance=50` - обновление предпочтений.
- `/next` - следующий кандидат из ранжированной очереди.
- `/like` - лайк текущего кандидата.
- `/skip` - пропуск текущего кандидата.
- `/photo_add file_id=... unique_id=...` - ручное добавление фото для тестов.

Подробные отчеты:
- [docs/04-stage2-basic-functionality.md](docs/04-stage2-basic-functionality.md)
- [docs/05-stage3-profiles-ranking-cache.md](docs/05-stage3-profiles-ranking-cache.md)
