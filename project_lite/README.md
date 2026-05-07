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

4. Этап 4 (без дополнительных инструментов) - реализовано:
- оптимизация ранжирования под top-N выдачу без полной сортировки всех кандидатов
- дополнительные индексы PostgreSQL для горячих запросов бота
- unit-тесты на стандартном `unittest`, без `pytest` и без Celery
- локальный сценарий запуска и проверки без Redis, Celery и Docker-оркестрации

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

## Запуск Stage 4

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

## Тесты

Stage 4 сделан без дополнительных инструментов, поэтому тесты запускаются стандартной библиотекой:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Что изменилось в Stage 4

- `core.py`: для предкэшируемой пачки кандидатов используется top-N отбор без полной сортировки всего списка.
- `schema.sql`: добавлены индексы под частые выборки пользователей и фото.
- Архитектура по-прежнему монолитная: только Python + PostgreSQL + Telegram Bot API.
- В этой версии намеренно нет Celery, Redis и других дополнительных сервисов.

## Основные команды

- `/start` - регистрация.
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
- [docs/06-stage4-performance-testing-local.md](docs/06-stage4-performance-testing-local.md)
