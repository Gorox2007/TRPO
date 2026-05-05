-- NON-REPEATABLE READ (неповторяющееся чтение)
-- Требуется 2 сессии
-- Уровень изоляции: READ COMMITTED

-- Session A
USE isolation_lab;
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT balance FROM accounts WHERE id = 2; -- 500.00

-- Session B (параллельно)
USE isolation_lab;
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
UPDATE accounts SET balance = 900 WHERE id = 2;
COMMIT;

-- Session A (в той же транзакции)
SELECT balance FROM accounts WHERE id = 2; -- уже 900.00
COMMIT;
