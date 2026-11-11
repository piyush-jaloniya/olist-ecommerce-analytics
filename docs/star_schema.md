# Olist star schema

## Overview

The star schema provides an analysis-ready model for the Olist marketplace data while
keeping order-grain measures separate from item-grain measures. The star database is
built from the cleaned staging database by the `model` stage.

## Grain table

| Table | Grain | Expected rows |
|---|---|---:|
| `dim_date` | One row per calendar day | 1,096 |
| `dim_customer` | One row per source `customer_id` | 99,441 |
| `dim_product` | One row per product | 32,951 |
| `dim_seller` | One row per seller | 3,095 |
| `fact_orders` | One row per order | 99,441 |
| `fact_order_items` | One row per order item | 112,650 |
| `fact_order_payments` | One row per payment row | 103,886 |

## ER diagram

```mermaid
erDiagram
    dim_date {
        INTEGER date_key PK
        TEXT full_date
        INTEGER year
        INTEGER quarter
        INTEGER month
        TEXT month_name
        TEXT year_month
        INTEGER day_of_month
        INTEGER day_of_week
        TEXT day_name
        INTEGER is_weekend
    }
    dim_customer {
        INTEGER customer_key PK
        TEXT customer_id
        TEXT customer_unique_id
        INTEGER zip_code_prefix
        TEXT city
        TEXT state
        REAL latitude
        REAL longitude
    }
    dim_product {
        INTEGER product_key PK
        TEXT product_id
        TEXT category_name
        TEXT category_name_english
        INTEGER name_length
        INTEGER description_length
        INTEGER photos_qty
        REAL weight_g
        REAL length_cm
        REAL height_cm
        REAL width_cm
    }
    dim_seller {
        INTEGER seller_key PK
        TEXT seller_id
        INTEGER zip_code_prefix
        TEXT city
        TEXT state
        REAL latitude
        REAL longitude
    }
    fact_orders {
        INTEGER order_key PK
        TEXT order_id
        INTEGER customer_key FK
        TEXT order_status
        INTEGER is_delivered
        INTEGER purchase_date_key FK
        INTEGER approved_date_key FK
        INTEGER carrier_date_key FK
        INTEGER delivered_date_key FK
        INTEGER estimated_delivery_date_key FK
        INTEGER review_creation_date_key FK
        TEXT purchase_timestamp
        TEXT approved_timestamp
        TEXT carrier_timestamp
        TEXT delivered_timestamp
        INTEGER delivery_date_inconsistent
        INTEGER delivery_delay_days
        INTEGER is_late
        INTEGER item_count
        REAL items_price_total
        REAL items_freight_total
        INTEGER payment_count
        REAL payment_total
        INTEGER review_score
    }
    fact_order_items {
        INTEGER order_item_key PK
        INTEGER order_key FK
        INTEGER order_item_id
        INTEGER product_key FK
        INTEGER seller_key FK
        INTEGER purchase_date_key FK
        INTEGER is_delivered
        TEXT shipping_limit_timestamp
        REAL price
        REAL freight_value
    }
    fact_order_payments {
        INTEGER order_payment_key PK
        INTEGER order_key FK
        INTEGER payment_sequential
        TEXT payment_type
        INTEGER payment_installments
        REAL payment_value
        INTEGER payment_value_non_positive
    }
    dim_customer ||--o{ fact_orders : customer_key
    dim_date ||--o{ fact_orders : date_keys
    fact_orders ||--o{ fact_order_items : order_key
    fact_orders ||--o{ fact_order_payments : order_key
    dim_product ||--o{ fact_order_items : product_key
    dim_seller ||--o{ fact_order_items : seller_key
    dim_date ||--o{ fact_order_items : purchase_date_key
```

The `dim_date` table is referenced several times by `fact_orders` for purchase,
approved, carrier, delivered, estimated, and review creation dates.

## Design decisions

1. Keep order-grain facts in `fact_orders`, item-grain facts in `fact_order_items`,
   and payment-row facts in `fact_order_payments` so order-grain measures are never
   double-counted across items.
2. Use `customer_id` as the dimension grain and keep `customer_unique_id` for repeat
   buyer analysis; the data contains 96,096 real people, 2,997 repeat buyers, 250 people
   with more than one ZIP, and 39 with more than one state.
3. Do not create a separate geography dimension; latitude and longitude live on
   `dim_customer` and `dim_seller`.
4. Use surrogate integer keys on dimensions while retaining the natural source IDs.
5. Keep all orders, including orders without items. Revenue is the sum of `price` for
   delivered orders, with freight reported separately.
6. Use a calendar dimension spanning 2016-01-01 through 2018-12-31.
7. Exclude review comment text from the model; retain review score and relevant dates.

## Conventions

- Date keys are integers in `YYYYMMDD` form.
- Flags are stored as `0`/`1` integers.
- Money is stored as `REAL`; compare monetary calculations with `ROUND(x, 2)`.
- `review_score` is `NULL` when an order has no review.
- `delivery_delay_days` and `is_late` are `NULL` unless the order is delivered and
  consistent.
- Item and payment totals are `0` when an order has none.
- Latitude and longitude are `NULL` when the ZIP has no geolocation row.
