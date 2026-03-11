import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

USERS_FILE    = Path(__file__).parent.parent / "sample_data" / "users.csv"
PRODUCTS_FILE = Path(__file__).parent.parent / "sample_data" / "products.csv"

# Configuracion MSSQL desde variables de entorno
MSSQL_SERVER   = os.getenv("MSSQL_SERVER")
MSSQL_PORT     = os.getenv("MSSQL_PORT", "1433")
MSSQL_DATABASE = os.getenv("MSSQL_DATABASE")
MSSQL_USER     = os.getenv("MSSQL_USER")
MSSQL_PASSWORD = os.getenv("MSSQL_PASSWORD")


def load_users(path: Path = USERS_FILE) -> pd.DataFrame:
    """Carga usuarios desde CSV."""
    try:
        df = pd.read_csv(path)
        df["created_at"] = pd.to_datetime(df["created_at"])
        logger.info(f"Usuarios cargados desde CSV: {len(df)} registros")
        return df
    except FileNotFoundError:
        logger.error(f"Archivo no encontrado: {path}")
        raise
    except Exception as e:
        logger.error(f"Error cargando usuarios: {e}")
        raise


def load_products(path: Path = PRODUCTS_FILE) -> pd.DataFrame:
    """Carga productos desde CSV."""
    try:
        df = pd.read_csv(path)
        logger.info(f"Productos cargados desde CSV: {len(df)} registros")
        return df
    except FileNotFoundError:
        logger.error(f"Archivo no encontrado: {path}")
        raise
    except Exception as e:
        logger.error(f"Error cargando productos: {e}")
        raise


def load_users_mssql() -> pd.DataFrame:
    """Carga usuarios desde SQL Server (Docker)."""
    try:
        import pymssql
        conn = pymssql.connect(
            server=MSSQL_SERVER,
            port=int(MSSQL_PORT),
            user=MSSQL_USER,
            password=MSSQL_PASSWORD,
            database=MSSQL_DATABASE
        )
        df = pd.read_sql("SELECT * FROM dbo.users", conn)
        conn.close()
        logger.info(f"Usuarios cargados desde MSSQL: {len(df)} registros")
        return df
    except Exception as e:
        logger.error(f"Error conectando a MSSQL: {e}")
        raise


def load_products_mssql() -> pd.DataFrame:
    """Carga productos desde SQL Server (Docker)."""
    try:
        import pymssql
        conn = pymssql.connect(
            server=MSSQL_SERVER,
            port=int(MSSQL_PORT),
            user=MSSQL_USER,
            password=MSSQL_PASSWORD,
            database=MSSQL_DATABASE
        )
        df = pd.read_sql("SELECT * FROM dbo.products", conn)
        conn.close()
        logger.info(f"Productos cargados desde MSSQL: {len(df)} registros")
        return df
    except Exception as e:
        logger.error(f"Error conectando a MSSQL: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    # Probar CSV
    users    = load_users()
    products = load_products()
    print(users)
    print(products)

    # Probar MSSQL
    users_sql    = load_users_mssql()
    products_sql = load_products_mssql()
    print(users_sql)
    print(products_sql)