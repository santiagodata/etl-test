import logging
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


def deduplicate_orders(df: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina duplicados por order_id, conservando el ultimo registro.
    Estrategia: keep='last' para preservar la version mas reciente.
    """
    before = len(df)
    df = df.drop_duplicates(subset=["order_id"], keep="last").reset_index(drop=True)
    after = len(df)
    logger.info(f"Deduplicacion: {before} -> {after} registros ({before - after} duplicados eliminados)")
    return df


def validate_orders(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Separa registros validos de rechazados.
    Rechazados: created_at nulo o items vacio.
    Retorna (df_valid, df_rejected).
    """
    mask_null_date  = df["created_at"].isna()
    mask_empty_items = df["items"].apply(lambda x: isinstance(x, list) and len(x) == 0)

    df_rejected = df[mask_null_date | mask_empty_items].copy()
    df_valid    = df[~(mask_null_date | mask_empty_items)].copy()

    df_rejected["reject_reason"] = ""
    df_rejected.loc[mask_null_date[df_rejected.index],  "reject_reason"] += "created_at_nulo "
    df_rejected.loc[mask_empty_items[df_rejected.index], "reject_reason"] += "items_vacio"

    logger.info(f"Validacion: {len(df_valid)} validos, {len(df_rejected)} rechazados")
    return df_valid, df_rejected


def normalize_orders(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza el DataFrame de ordenes:
    - Parsea created_at a datetime UTC
    - Extrae columna date (YYYY-MM-DD) para particionado
    - Rellena items.price nulo con precio del catalogo o 0.0
    """
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["date"]       = df["created_at"].dt.strftime("%Y-%m-%d")
    logger.info(f"Normalizacion completada: {len(df)} registros")
    return df


def flatten_items(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hace explode del array items, extrayendo sku, qty y price como columnas.
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
    """Construye dimension de usuarios."""
    df = users_df[["user_id", "email", "created_at", "country"]].drop_duplicates().copy()
    logger.info(f"dim_user: {len(df)} registros")
    return df


def build_dim_product(products_df: pd.DataFrame) -> pd.DataFrame:
    """Construye dimension de productos."""
    df = products_df[["sku", "name", "category", "price"]].drop_duplicates().copy()
    logger.info(f"dim_product: {len(df)} registros")
    return df


def build_fact_order(orders_df: pd.DataFrame,
                     users_df: pd.DataFrame,
                     products_df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye la tabla de hechos fact_order.
    JOIN entre ordenes aplanadas, usuarios y productos.
    """
    df = orders_df.merge(
        users_df[["user_id", "country"]],
        on="user_id", how="left"
    )
    df = df.merge(
        products_df[["sku", "name", "category"]],
        on="sku", how="left"
    )
    fact = df[[
        "order_id", "user_id", "sku", "qty", "item_price",
        "amount", "currency", "date", "created_at", "country",
        "name", "category"
    ]].copy()

    fact = fact.rename(columns={"item_price": "unit_price", "name": "product_name"})
    logger.info(f"fact_order: {len(fact)} registros")
    return fact


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    from src.api_client import fetch_orders
    from src.db import load_users, load_products
    import json

    raw     = fetch_orders()
    df_raw  = pd.DataFrame(raw)

    df_dedup          = deduplicate_orders(df_raw)
    df_valid, df_rej  = validate_orders(df_dedup)
    df_norm           = normalize_orders(df_valid)
    df_flat           = flatten_items(df_norm)

    users_df    = load_users()
    products_df = load_products()

    fact = build_fact_order(df_flat, users_df, products_df)
    print(fact.head())
    print(f"\nColumnas: {list(fact.columns)}")