import os
import time
from decimal import Decimal

import psycopg


def wait_for_db(dsn: str, attempts: int = 30, delay_seconds: int = 2) -> None:
    last_error = None
    for _ in range(attempts):
        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            return
        except psycopg.OperationalError as exc:
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError(f"Database is not ready after {attempts} attempts") from last_error


def place_order(conn: psycopg.Connection, customer_id: int, items: list[tuple[int, int]]) -> tuple[int, Decimal]:
    if not items:
        raise ValueError("Order must contain at least one item")

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (customer_id, order_date, total_amount)
                VALUES (%s, NOW(), 0)
                RETURNING order_id;
                """,
                (customer_id,),
            )
            order_id_row = cur.fetchone()
            if not order_id_row:
                raise RuntimeError("Failed to create order")
            order_id = order_id_row[0]

            for product_id, quantity in items:
                if quantity <= 0:
                    raise ValueError(f"Quantity must be positive for product {product_id}")

                cur.execute(
                    "SELECT price FROM products WHERE product_id = %s FOR SHARE;",
                    (product_id,),
                )
                price_row = cur.fetchone()
                if not price_row:
                    raise ValueError(f"Product with id={product_id} was not found")

                price = Decimal(price_row[0])
                subtotal = price * quantity

                cur.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, subtotal)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (order_id, product_id, quantity, subtotal),
                )

            cur.execute(
                """
                UPDATE orders
                SET total_amount = (
                    SELECT COALESCE(SUM(subtotal), 0)
                    FROM order_items
                    WHERE order_id = %s
                )
                WHERE order_id = %s;
                """,
                (order_id, order_id),
            )

            cur.execute("SELECT total_amount FROM orders WHERE order_id = %s;", (order_id,))
            total_row = cur.fetchone()
            if not total_row:
                raise RuntimeError("Order total was not calculated")
            total_amount = Decimal(total_row[0])

    return order_id, total_amount


def update_customer_email(conn: psycopg.Connection, customer_id: int, new_email: str) -> None:
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                SET email = %s
                WHERE customer_id = %s;
                """,
                (new_email, customer_id),
            )
            if cur.rowcount != 1:
                raise ValueError(f"Customer with id={customer_id} was not found")


def add_product(conn: psycopg.Connection, product_name: str, price: Decimal) -> int:
    if price < 0:
        raise ValueError("Price must be non-negative")

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO products (product_name, price)
                VALUES (%s, %s)
                RETURNING product_id;
                """,
                (product_name, price),
            )
            product_row = cur.fetchone()
            if not product_row:
                raise RuntimeError("Failed to create product")
            product_id = product_row[0]

    return product_id


def print_demo_state(conn: psycopg.Connection, order_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.order_id, c.email, o.total_amount
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_id = %s;
            """,
            (order_id,),
        )
        order_row = cur.fetchone()

        cur.execute(
            """
            SELECT oi.order_item_id, p.product_name, oi.quantity, oi.subtotal
            FROM order_items oi
            JOIN products p ON p.product_id = oi.product_id
            WHERE oi.order_id = %s
            ORDER BY oi.order_item_id;
            """,
            (order_id,),
        )
        item_rows = cur.fetchall()

    print("Order snapshot:")
    print(order_row)
    for row in item_rows:
        print(row)


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/store_db")

    wait_for_db(dsn)

    with psycopg.connect(dsn) as conn:
        order_id, total_amount = place_order(conn, customer_id=1, items=[(1, 2), (2, 1)])
        update_customer_email(conn, customer_id=1, new_email="ivan.updated@example.com")
        product_id = add_product(conn, product_name="Webcam 4K", price=Decimal("159.99"))

        print(f"Scenario 1 done: order_id={order_id}, total_amount={total_amount}")
        print("Scenario 2 done: customer email updated")
        print(f"Scenario 3 done: new product_id={product_id}")
        print_demo_state(conn, order_id)


if __name__ == "__main__":
    main()
