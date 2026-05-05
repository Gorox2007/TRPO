-- MySQL 8.0+ (InnoDB)
CREATE DATABASE IF NOT EXISTS isolation_lab;
USE isolation_lab;

DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS orders;

CREATE TABLE accounts (
    id INT PRIMARY KEY,
    owner_name VARCHAR(100) NOT NULL,
    balance DECIMAL(12,2) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT INTO accounts (id, owner_name, balance) VALUES
(1, 'Alice', 1000.00),
(2, 'Bob', 500.00);

INSERT INTO orders (customer_name, amount, status) VALUES
('Alice', 120.00, 'NEW'),
('Bob',  80.00, 'NEW');
