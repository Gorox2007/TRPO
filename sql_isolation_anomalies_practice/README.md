# SQL Isolation Anomalies Practice

Папка содержит готовую практику по аномалиям изоляции для MySQL 8.0.

## Содержимое

- `REPORT.md` — готовый отчет
- `sql/00_init.sql` — подготовка БД и тестовых данных
- `sql/01_dirty_read.sql`
- `sql/02_non_repeatable_read.sql`
- `sql/03_phantom_read.sql`
- `sql/04_lost_update.sql`

## Быстрый запуск

1. Запустите MySQL 8.0.
2. Откройте две SQL-сессии.
3. Выполните `sql/00_init.sql`.
4. По очереди воспроизведите сценарии из `sql/01..04`.
5. Добавьте скриншоты в отчет.
