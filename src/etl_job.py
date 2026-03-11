import argparse
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.api_client import fetch_orders, save_raw
from src.db import load_users, load_products, load_users_mssql, load_products_mssql
from src.transforms import (
    deduplicate_orders, validate_orders, normalize_orders,
    flatten_items, build_dim_user, build_dim_product, build_fact_order
)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent
OUTPUT_DIR    = BASE_DIR / "output"
CURATED_DIR   = OUTPUT_DIR / "curated"
REJECTED_DIR  = OUTPUT_DIR / "rejected"
LAST_RUN_FILE = OUTPUT_DIR / ".last_run"


# ── Helpers ───────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="JUJU ETL Job")
    parser.add_argument("--since", type=str, default=None,
                        help="Fecha desde la que procesar pedidos (YYYY-MM-DD)")
    parser.add_argument("--use-mssql", action="store_true",
                        help="Usar SQL Server como fuente en lugar de CSV")
    return parser.parse_args()


def get_last_run() -> str | None:
    if LAST_RUN_FILE.exists():
        return LAST_RUN_FILE.read_text().strip()
    return None


def save_last_run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    logger.info(f"Ultimo run guardado en: {LAST_RUN_FILE}")


def write_curated(df: pd.DataFrame, table: str):
    """
    Escribe DataFrame en Parquet particionado por date=YYYY-MM-DD.
    Idempotente: elimina la particion existente antes de escribir.
    """
    for date_val, group in df.groupby("date"):
        partition_path = CURATED_DIR / table / f"date={date_val}"

        # Idempotencia: borrar particion existente antes de escribir
        if partition_path.exists():
            shutil.rmtree(partition_path)
            logger.info(f"Particion existente eliminada: {partition_path}")

        partition_path.mkdir(parents=True, exist_ok=True)
        out_file = partition_path / "part-0.parquet"
        group.drop(columns=["date"]).to_parquet(out_file, index=False)
        logger.info(f"Curated escrito: {out_file} ({len(group)} filas)")


def write_rejected(df: pd.DataFrame):
    """Guarda registros rechazados en output/rejected/."""
    if df.empty:
        return
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    date_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file  = REJECTED_DIR / f"rejected_{date_str}.csv"
    df.to_csv(out_file, index=False)
    logger.warning(f"Rechazados guardados: {out_file} ({len(df)} registros)")


# ── Pipeline principal ────────────────────────────────────────────────────────
def run(since: str = None, use_mssql: bool = False):
    start = time.time()
    logger.info("=" * 60)
    logger.info("JUJU ETL Job iniciado")
    logger.info(f"Parametros: since={since}, use_mssql={use_mssql}")
    logger.info("=" * 60)

    # 1. Determinar fecha de inicio
    if not since:
        since = get_last_run()
        if since:
            logger.info(f"Usando last_run como since: {since}")

    # 2. Ingesta desde API mock
    raw_orders = fetch_orders(since=since)
    logger.info(f"[METRICA] Pedidos recibidos de API: {len(raw_orders)}")

    # 3. Guardar raw
    save_raw(raw_orders)

    # 4. Cargar dimensiones
    if use_mssql:
        logger.info("Cargando dimensiones desde MSSQL...")
        users_df    = load_users_mssql()
        products_df = load_products_mssql()
    else:
        logger.info("Cargando dimensiones desde CSV...")
        users_df    = load_users()
        products_df = load_products()

    # 5. Transformaciones
    df = pd.DataFrame(raw_orders)

    # Si no hay pedidos, terminar limpiamente
    if df.empty:
        logger.info("No hay pedidos nuevos para procesar. ETL finalizado.")
        save_last_run()
        return

    df = deduplicate_orders(df)
    df_valid, df_rejected = validate_orders(df)

    logger.info(f"[METRICA] Pedidos validos: {len(df_valid)}")
    logger.info(f"[METRICA] Pedidos rechazados: {len(df_rejected)}")

    # Alerta si tasa de rechazo > 5%
    total = len(df_valid) + len(df_rejected)
    reject_rate = len(df_rejected) / total if total > 0 else 0
    if reject_rate > 0.05:
        logger.warning(f"[ALERTA] Tasa de rechazo alta: {reject_rate:.1%}")

    df_valid = normalize_orders(df_valid)
    df_flat  = flatten_items(df_valid)

    # 6. Construir tablas dimensionales y de hechos
    dim_user    = build_dim_user(users_df)
    dim_product = build_dim_product(products_df)
    fact        = build_fact_order(df_flat, users_df, products_df)

    # 7. Escribir curated (particionado, idempotente)
    write_curated(fact,        "fact_order")
    write_curated(dim_user.assign(date=datetime.now(timezone.utc).strftime("%Y-%m-%d")), "dim_user")
    write_curated(dim_product.assign(date=datetime.now(timezone.utc).strftime("%Y-%m-%d")), "dim_product")

    # 8. Guardar rechazados
    write_rejected(df_rejected)

    # 9. Guardar timestamp del run
    save_last_run()

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"[METRICA] Filas en fact_order: {len(fact)}")
    logger.info(f"[METRICA] Duracion total: {elapsed:.2f}s")
    logger.info("ETL Job finalizado exitosamente")
    logger.info("=" * 60)


if __name__ == "__main__":
    args = parse_args()
    run(since=args.since, use_mssql=args.use_mssql)