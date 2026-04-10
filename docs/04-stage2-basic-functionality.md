# 4. Этап 2: Базовая функциональность

Реализация выполнена в соответствии с документацией Этапа 1:
- архитектура `Bot -> Core -> PostgreSQL`;
- команды Telegram слоя из `docs/01-services.md`;
- использование схемы `db/schema.sql`.

## 4.1 Реализованные пункты этапа

1. Сервис бота и интерфейс пользователя через Telegram Bot API  
Статус: `done`  
Реализация: long polling в `stage2_bot/telegram_api.py` + `stage2_bot/bot_service.py`.

2. Регистрация по `/start` с Telegram ID  
Статус: `done`  
Реализация: upsert в таблицу `users` в `stage2_bot/db.py`.

3. Базовые команды из проектной документации  
Статус: `done`  
Команды: `/start`, `/profile`, `/prefs`, `/next`, `/like`, `/skip`, `/help`.

## 4.2 Что покрывает Этап 2, а что нет

Покрыто:
- подключение к PostgreSQL;
- инициализация схемы;
- регистрация и базовое чтение данных пользователя;
- подготовка интерфейса под следующие этапы.

Не покрыто (будет в Этапе 3+):
- полноценный CRUD анкеты;
- выдача кандидатов и скоринг;
- полноценная обработка лайков/скипов и матчинга.

## 4.3 Быстрая проверка

1. Настроить переменные:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/dating_bot"
```

2. Запустить:

```bash
python3 -m stage2_bot.run
```

3. В Telegram отправить:
- `/start`
- `/profile`
- `/prefs`
- `/help`

