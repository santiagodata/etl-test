import logging
import duckdb
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


def get_conn():
    """Retorna una conexión DuckDB en memoria."""
    return duckdb.connect()


def deduplicate_orders(df: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina duplicados por order_id usando DuckDB SQL.
    Estrategia: QUALIFY ROW_NUMBER() keep='last' por created_at.
    Si no existe columna created_at, deduplica solo por order_id.
    """
    conn = get_conn()
    conn.register("orders", df)
    before = len(df)

    if "created_at" in df.columns:
        result = conn.execute("""
            SELECT *
            FROM orders
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY order_id
                ORDER BY created_at DESC NULLS LAST
            ) = 1
        """).df()
    else:
        result = conn.execute("""
            SELECT *
            FROM orders
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY order_id
                ORDER BY (SELECT NULL)
            ) = 1
        """).df()

    conn.close()
    after = len(result)
    logger.info(f"Deduplicacion: {before} -> {after} registros ({before - after} duplicados eliminados)")
    return result.reset_index(drop=True)


def validate_orders(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Separa registros validos de rechazados usando DuckDB SQL.
    Rechazados: created_at nulo o items vacio.
    Retorna (df_valid, df_rejected).
    """
    conn = get_conn()
    conn.register("orders", df)

    df_valid = conn.execute("""
        SELECT *
        FROM orders
        WHERE created_at IS NOT NULL
          AND items IS NOT NULL
          AND len(items) > 0
    """).df()

    df_rejected = conn.execute("""
        SELECT *,
            CASE
                WHEN created_at IS NULL AND (items IS NULL OR len(items) = 0)
                    THEN 'created_at_nulo items_vacio'
                WHEN created_at IS NULL
                    THEN 'created_at_nulo'
                WHEN items IS NULL OR len(items) = 0
                    THEN 'items_vacio'
            END AS reject_reason
        FROM orders
        WHERE created_at IS NULL
           OR items IS NULL
           OR len(items) = 0
    """).df()

    conn.close()
    logger.info(f"Validacion: {len(df_valid)} validos, {len(df_rejected)} rechazados")
    return df_valid.reset_index(drop=True), df_rejected.reset_index(drop=True)


def normalize_orders(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza el DataFrame usando pandas:
    - Parsea created_at a datetime UTC
    - Extrae columna date (YYYY-MM-DD) para particionado
    """
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["date"] = df["created_at"].dt.strftime("%Y-%m-%d")
    logger.info(f"Normalizacion completada: {len(df)} registros")
    return df


def flatten_items(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hace explode del array items con pandas y extrae
    sku, qty y price como columnas separadas.
    Rellena price nulo con 0.0.
    """
    df = df.copy()
    df = df.explode("items").reset_index(drop=True)
    df = df[df["items"].notna()].reset_index(drop=True)

    df["sku"]        = df["items"].apply(lambda x: x.get("sku")   if isinstance(x, dict) else None)
    df["qty"]        = df["items"].apply(lambda x: x.get("qty")   if isinstance(x, dict) else None)
    df["item_price"] = df["items"].apply(lambda x: x.get("price") if isinstance(x, dict) else None)
    df["item_price"] = pd.to_numeric(df["item_price"], errors="coerce").fillna(0.0)

    df = df.drop(columns=["items"])
    logger.info(f"Flatten items: {len(df)} filas tras explode")
    return df


def build_dim_user(users_df: pd.DataFrame) -> pd.DataFrame:
    """Construye dimension de usuarios con DuckDB."""
    conn = get_conn()
    conn.register("users", users_df)
    result = conn.execute("""
        SELECT DISTINCT
            user_id,
            email,
            created_at,
            country
        FROM users
        ORDER BY user_id
    """).df()
    conn.close()
    logger.info(f"dim_user: {len(result)} registros")
    return result


def build_dim_product(products_df: pd.DataFrame) -> pd.DataFrame:
    """Construye dimension de productos con DuckDB."""
    conn = get_conn()
    conn.register("products", products_df)
    result = conn.execute("""
        SELECT DISTINCT
            sku,
            name,
            category,
            price
        FROM products
        ORDER BY sku
    """).df()
    conn.close()
    logger.info(f"dim_product: {len(result)} registros")
    return result


def build_fact_order(orders_df: pd.DataFrame,
                     users_df: pd.DataFrame,
                     products_df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye fact_order usando DuckDB SQL para los JOINs.
    Granularidad: una fila por linea de pedido (order_id + sku).
    """
    conn = get_conn()
    conn.register("orders",   orders_df)
    conn.register("users",    users_df)
    conn.register("products", products_df)

    result = conn.execute("""
        SELECT
            o.order_id,
            o.user_id,
            o.sku,
            o.qty,
            o.item_price    AS unit_price,
            o.amount,
            o.currency,
            o.date,
            o.created_at,
            u.country,
            p.name          AS product_name,
            p.category
        FROM orders o
        LEFT JOIN users    u ON o.user_id = u.user_id
        LEFT JOIN products p ON o.sku     = p.sku
        ORDER BY o.created_at
    """).df()

    conn.close()
    logger.info(f"fact_order: {len(result)} registros")
    return result


def query_curated_stats(curated_dir: Path) -> pd.DataFrame:
    """
    Lee los Parquet curated con DuckDB y genera estadisticas
    analiticas sobre las ventas de bonos JUJU.
    """
    parquet_path = str(curated_dir / "fact_order" / "*/*.parquet")
    conn = get_conn()
    try:
        stats = conn.execute(f"""
            SELECT
                category,
                COUNT(DISTINCT order_id)    AS num_ordenes,
                SUM(qty)                    AS unidades_vendidas,
                SUM(unit_price * qty)       AS revenue_cop,
                AVG(unit_price)             AS precio_promedio
            FROM read_parquet('{parquet_path}', hive_partitioning=true)
            GROUP BY category
            ORDER BY revenue_cop DESC
        """).df()
        logger.info(f"[DUCKDB] Stats curated generadas: {len(stats)} categorias")
        return stats
    except Exception as e:
        logger.warning(f"[DUCKDB] No se pudo generar stats: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    from src.api_client import fetch_orders
    from src.db import load_users, load_products

    raw        = fetch_orders()
    df_raw     = pd.DataFrame(raw)

    df_dedup          = deduplicate_orders(df_raw)
    df_valid, df_rej  = validate_orders(df_dedup)
    df_norm           = normalize_orders(df_valid)
    df_flat           = flatten_items(df_norm)

    users_df    = load_users()
    products_df = load_products()

    fact = build_fact_order(df_flat, users_df, products_df)
    print(fact.head())
    print(f"\nColumnas: {list(fact.columns)}")