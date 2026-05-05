-- DIRTY READ (грязное чтение)
-- Требуется 2 сессии: Session A и Session B
-- Уровень изоляции: READ UNCOMMITTED

-- Session A
USE isolation_lab;
SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
START TRANSACTION;
UPDATE accounts SET balance = balance - 300 WHERE id = 1;
-- Пока НЕ COMMIT/ROLLBACK

-- Session B (параллельно)
USE isolation_lab;
SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
START TRANSACTION;
SELECT balance FROM accounts WHERE id = 1; -- увидит 700.00 (грязные данные)
COMMIT;

-- Session A
ROLLBACK; -- откат до 1000.00

-- Проверка
SELECT id, owner_name, balance FROM accounts WHERE id = 1;
