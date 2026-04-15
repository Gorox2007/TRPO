-- Scenario 1: place order atomically
BEGIN;

INSERT INTO orders (customer_id, order_date, total_amount)
VALUES (:customer_id, NOW(), 0)
RETURNING order_id;

-- For each order line, application calculates subtotal = price * quantity,
-- then inserts rows into order_items.
INSERT INTO order_items (order_id, product_id, quantity, subtotal)
VALUES (:order_id, :product_id, :quantity, :subtotal);

UPDATE orders
SET total_amount = (
    SELECT COALESCE(SUM(subtotal), 0)
    FROM order_items
    WHERE order_id = :order_id
)
WHERE order_id = :order_id;

COMMIT;


-- Scenario 2: update customer email atomically
BEGIN;

UPDATE customers
SET email = :new_email
WHERE customer_id = :customer_id;

COMMIT;


-- Scenario 3: add product atomically
BEGIN;

INSERT INTO products (product_name, price)
VALUES (:product_name, :price);

COMMIT;
