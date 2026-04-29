# Practical Task: Online Store Transactions

## Что внутри

- `init/01-schema.sql` - создание таблиц `customers`, `products`, `orders`, `order_items`
- `init/02-seed.sql` - стартовые данные
- `transactions.sql` - SQL-шаблоны транзакций по трем сценариям
- `app/main.py` - Python-скрипт (psycopg), который выполняет все 3 сценария в транзакциях
- `Dockerfile` и `docker-compose.yml` - запуск приложения и PostgreSQL

## Сценарии

1. Размещение заказа:
- создается запись в `orders`;
- добавляются позиции в `order_items`;
- пересчитывается `orders.total_amount` как сумма `subtotal`.

2. Обновление email клиента:
- `UPDATE customers ...` выполняется в транзакции;
- при ошибке/исключении изменения откатываются.

3. Добавление нового продукта:
- `INSERT INTO products ...` выполняется атомарно;
- при ошибке изменения откатываются.

## Запуск

```bash
docker compose up --build
```

После старта контейнер `app` выполнит все три сценария и выведет результат в логи.
