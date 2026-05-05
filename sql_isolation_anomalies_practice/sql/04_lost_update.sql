-- LOST UPDATE (потерянное обновление)
-- Демонстрация через read-modify-write в двух сессиях
-- Уровень изоляции: READ COMMITTED

-- Подготовка
USE isolation_lab;
UPDATE accounts SET balance = 1000 WHERE id = 1;

-- Session A
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT balance FROM accounts WHERE id = 1; -- 1000
-- приложение вычисляет новое значение: 1000 - 100 = 900

-- Session B (параллельно)
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT balance FROM accounts WHERE id = 1; -- 1000
-- приложение вычисляет новое значение: 1000 - 200 = 800
UPDATE accounts SET balance = 800 WHERE id = 1;
COMMIT;

-- Session A (продолжает со старым расчетом)
UPDATE accounts SET balance = 900 WHERE id = 1;
COMMIT;

-- Проверка
SELECT balance FROM accounts WHERE id = 1;
-- Фактически 900, хотя ожидалось 700 (одно изменение потеряно)
