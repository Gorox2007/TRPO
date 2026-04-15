INSERT INTO customers (first_name, last_name, email)
VALUES
    ('Ivan', 'Petrov', 'ivan.petrov@example.com'),
    ('Anna', 'Sidorova', 'anna.sidorova@example.com')
ON CONFLICT (email) DO NOTHING;

INSERT INTO products (product_name, price)
VALUES
    ('Mechanical Keyboard', 125.00),
    ('USB-C Hub', 49.90),
    ('27 inch Monitor', 299.00)
ON CONFLICT DO NOTHING;
