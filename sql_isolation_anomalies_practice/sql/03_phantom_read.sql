-- PHANTOM READ (фантомное чтение)
-- Требуется 2 сессии
-- Уровень изоляции: READ COMMITTED

-- Session A
USE isolation_lab;
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT COUNT(*) AS cnt FROM orders WHERE amount >= 100; -- например, 1

-- Session B (параллельно)
USE isolation_lab;
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
INSERT INTO orders (customer_name, amount, status) VALUES ('Charlie', 150.00, 'NEW');
COMMIT;

-- Session A (в той же транзакции)
SELECT COUNT(*) AS cnt FROM orders WHERE amount >= 100; -- станет 2 (появился "фантом")
COMMIT;
