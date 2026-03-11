-- ============================================================
-- JUJU ETL — DDL compatible con Redshift / DuckDB
-- Modelo dimensional: dim_user, dim_product, fact_order
-- ============================================================

-- ── DIMENSION USUARIOS ───────────────────────────────────────
CREATE TABLE dim_user (
    user_sk     BIGINT        IDENTITY(1,1) PRIMARY KEY,
    user_id     VARCHAR(64)   NOT NULL,
    email       VARCHAR(255),
    country     VARCHAR(8),
    created_at  DATE,
    UNIQUE (user_id)
)
DISTSTYLE ALL;

-- ── DIMENSION PRODUCTOS ──────────────────────────────────────
CREATE TABLE dim_product (
    product_sk  BIGINT        IDENTITY(1,1) PRIMARY KEY,
    sku         VARCHAR(64)   NOT NULL,
    name        VARCHAR(255),
    category    VARCHAR(100),
    price       DECIMAL(12,2),
    UNIQUE (sku)
)
DISTSTYLE ALL;

-- ── TABLA DE HECHOS ──────────────────────────────────────────
-- Granularidad: una fila por linea de pedido (order_id + sku)
CREATE TABLE fact_order (
    order_id      VARCHAR(64)   NOT NULL,
    user_id       VARCHAR(64),
    user_sk       BIGINT        REFERENCES dim_user(user_sk),
    sku           VARCHAR(64),
    product_sk    BIGINT        REFERENCES dim_product(product_sk),
    qty           INT,
    unit_price    DECIMAL(12,2),
    amount        DECIMAL(12,2),
    currency      VARCHAR(8),
    order_date    DATE,
    created_at    TIMESTAMP,
    country       VARCHAR(8),
    product_name  VARCHAR(255),
    category      VARCHAR(100),
    PRIMARY KEY (order_id, sku)
)
DISTKEY(order_date)
SORTKEY(order_date, user_sk);

-- ============================================================
-- QUERIES DE EJEMPLO
-- ============================================================

-- 1. Detectar duplicados en fact_order
SELECT
    order_id,
    sku,
    COUNT(*) AS cnt
FROM fact_order
GROUP BY order_id, sku
HAVING COUNT(*) > 1;

-- 2. Ventas totales por pais
SELECT
    u.country,
    SUM(f.amount)        AS total_ventas_cop,
    COUNT(DISTINCT f.order_id) AS num_ordenes
FROM fact_order f
JOIN dim_user u ON f.user_sk = u.user_sk
GROUP BY u.country
ORDER BY total_ventas_cop DESC;

-- 3. Top productos por categoria
SELECT
    p.category,
    p.name,
    SUM(f.qty)           AS unidades_vendidas,
    SUM(f.unit_price * f.qty) AS revenue_cop
FROM fact_order f
JOIN dim_product p ON f.product_sk = p.product_sk
GROUP BY p.category, p.name
ORDER BY revenue_cop DESC;

-- 4. Ventas diarias (para monitoreo de pipeline)
SELECT
    order_date,
    COUNT(DISTINCT order_id) AS ordenes,
    SUM(amount)              AS total_cop
FROM fact_order
GROUP BY order_date
ORDER BY order_date;

-- 5. Carga incremental desde Parquet en S3 a Redshift
-- COPY fact_order
-- FROM 's3://juju-bucket/curated/fact_order/'
-- IAM_ROLE 'arn:aws:iam::ACCOUNT:role/RedshiftS3Role'
-- FORMAT AS PARQUET;