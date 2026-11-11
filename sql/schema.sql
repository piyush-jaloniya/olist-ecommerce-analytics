-- Olist star schema (SQLite). Rebuilt from scratch by the `model` stage.
-- Grain of each table is stated in its comment. Money is REAL: compare with ROUND(x, 2).
-- Date keys are integers in YYYYMMDD form. Flags are 0/1 integers.
-- SQLite only enforces foreign keys when this pragma is on for the connection.
PRAGMA foreign_keys = ON;

-- Drop children first so the file can be re-run on an existing database.
DROP TABLE IF EXISTS fact_order_payments;
DROP TABLE IF EXISTS fact_order_items;
DROP TABLE IF EXISTS fact_orders;
DROP TABLE IF EXISTS dim_seller;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_date;

-- One row per calendar day, 2016-01-01 to 2018-12-31 (1,096 rows).
CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,           -- YYYYMMDD
    full_date     TEXT    NOT NULL UNIQUE,       -- YYYY-MM-DD
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month         INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name    TEXT    NOT NULL,
    year_month    TEXT    NOT NULL,              -- YYYY-MM
    day_of_month  INTEGER NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week   INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),  -- 1 = Monday
    day_name      TEXT    NOT NULL,
    is_weekend    INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
);

-- One row per source customer_id (one per order). A real person can have several
-- customer_id values; customer_unique_id identifies the person (repeat-buyer analysis).
CREATE TABLE dim_customer (
    customer_key        INTEGER PRIMARY KEY,
    customer_id         TEXT    NOT NULL UNIQUE,
    customer_unique_id  TEXT    NOT NULL,
    zip_code_prefix     INTEGER,
    city                TEXT,
    state               TEXT,
    latitude            REAL,                    -- NULL when the ZIP has no geolocation row
    longitude           REAL
);

-- One row per product. category_name_english is 'unknown' when the category is missing.
CREATE TABLE dim_product (
    product_key            INTEGER PRIMARY KEY,
    product_id             TEXT    NOT NULL UNIQUE,
    category_name          TEXT    NOT NULL,
    category_name_english  TEXT    NOT NULL,
    name_length            INTEGER,
    description_length     INTEGER,
    photos_qty             INTEGER,
    weight_g               REAL,
    length_cm              REAL,
    height_cm              REAL,
    width_cm               REAL
);

-- One row per seller.
CREATE TABLE dim_seller (
    seller_key       INTEGER PRIMARY KEY,
    seller_id        TEXT    NOT NULL UNIQUE,
    zip_code_prefix  INTEGER,
    city             TEXT,
    state            TEXT,
    latitude         REAL,                       -- NULL when the ZIP has no geolocation row
    longitude        REAL
);

-- One row per order. Order-grain measures (payment total, review score) live here so they
-- are never summed across item rows.
CREATE TABLE fact_orders (
    order_key                    INTEGER PRIMARY KEY,
    order_id                     TEXT    NOT NULL UNIQUE,
    customer_key                 INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    order_status                 TEXT    NOT NULL,
    is_delivered                 INTEGER NOT NULL CHECK (is_delivered IN (0, 1)),
    purchase_date_key            INTEGER NOT NULL REFERENCES dim_date (date_key),
    approved_date_key            INTEGER REFERENCES dim_date (date_key),
    carrier_date_key             INTEGER REFERENCES dim_date (date_key),
    delivered_date_key           INTEGER REFERENCES dim_date (date_key),
    estimated_delivery_date_key  INTEGER NOT NULL REFERENCES dim_date (date_key),
    review_creation_date_key     INTEGER REFERENCES dim_date (date_key),
    purchase_timestamp           TEXT    NOT NULL,
    approved_timestamp           TEXT,
    carrier_timestamp            TEXT,
    delivered_timestamp          TEXT,
    delivery_date_inconsistent   INTEGER NOT NULL CHECK (delivery_date_inconsistent IN (0, 1)),
    delivery_delay_days          INTEGER,        -- NULL unless delivered and consistent
    is_late                      INTEGER CHECK (is_late IN (0, 1)),  -- NULL when delay is NULL
    item_count                   INTEGER NOT NULL DEFAULT 0 CHECK (item_count >= 0),
    items_price_total            REAL    NOT NULL DEFAULT 0,
    items_freight_total          REAL    NOT NULL DEFAULT 0,
    payment_count                INTEGER NOT NULL DEFAULT 0 CHECK (payment_count >= 0),
    payment_total                REAL    NOT NULL DEFAULT 0,
    review_score                 INTEGER CHECK (review_score BETWEEN 1 AND 5)  -- NULL if no review
);

-- One row per order item.
CREATE TABLE fact_order_items (
    order_item_key      INTEGER PRIMARY KEY,
    order_key           INTEGER NOT NULL REFERENCES fact_orders (order_key),
    order_item_id       INTEGER NOT NULL,        -- item sequence within the order (source value)
    product_key         INTEGER NOT NULL REFERENCES dim_product (product_key),
    seller_key          INTEGER NOT NULL REFERENCES dim_seller (seller_key),
    purchase_date_key   INTEGER NOT NULL REFERENCES dim_date (date_key),
    is_delivered        INTEGER NOT NULL CHECK (is_delivered IN (0, 1)),
    shipping_limit_timestamp TEXT NOT NULL,
    price               REAL    NOT NULL CHECK (price > 0),
    freight_value       REAL    NOT NULL CHECK (freight_value >= 0),
    UNIQUE (order_key, order_item_id)
);

-- One row per payment row (an order can be paid with several methods).
CREATE TABLE fact_order_payments (
    order_payment_key           INTEGER PRIMARY KEY,
    order_key                   INTEGER NOT NULL REFERENCES fact_orders (order_key),
    payment_sequential          INTEGER NOT NULL,
    payment_type                TEXT    NOT NULL CHECK (payment_type IN
                                    ('credit_card', 'boleto', 'voucher', 'debit_card', 'unknown')),
    payment_installments        INTEGER NOT NULL CHECK (payment_installments >= 0),
    payment_value               REAL    NOT NULL CHECK (payment_value >= 0),
    payment_value_non_positive  INTEGER NOT NULL CHECK (payment_value_non_positive IN (0, 1)),
    UNIQUE (order_key, payment_sequential)
);

-- Indexes on the columns used for joins and filters in the analysis queries.
CREATE INDEX idx_dim_customer_unique_id   ON dim_customer (customer_unique_id);
CREATE INDEX idx_dim_customer_state       ON dim_customer (state);
CREATE INDEX idx_dim_product_category_en  ON dim_product (category_name_english);
CREATE INDEX idx_dim_seller_state         ON dim_seller (state);
CREATE INDEX idx_fact_orders_customer     ON fact_orders (customer_key);
CREATE INDEX idx_fact_orders_purchase     ON fact_orders (purchase_date_key);
CREATE INDEX idx_fact_orders_status       ON fact_orders (order_status);
CREATE INDEX idx_fact_items_order         ON fact_order_items (order_key);
CREATE INDEX idx_fact_items_product       ON fact_order_items (product_key);
CREATE INDEX idx_fact_items_seller        ON fact_order_items (seller_key);
CREATE INDEX idx_fact_items_purchase      ON fact_order_items (purchase_date_key);
CREATE INDEX idx_fact_payments_order      ON fact_order_payments (order_key);
CREATE INDEX idx_fact_payments_type       ON fact_order_payments (payment_type);