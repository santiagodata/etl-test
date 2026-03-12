import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

ORDERS_FILE = Path(__file__).parent.parent / "sample_data" / "api_orders.json"
RAW_OUTPUT  = Path(__file__).parent.parent / "output" / "raw"


def fetch_orders(since: str = None, retries: int = 3) -> list[dict]:
    """
    Lee pedidos desde el archivo JSON simulando una API mock.
    Filtra por fecha si se pasa since (YYYY-MM-DD).
    Implementa retry con backoff exponencial.
    """
    attempt = 0
    while attempt < retries:
        try:
            logger.info(f"Intentando leer pedidos (intento {attempt + 1}/{retries})")
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                orders = json.load(f)
            logger.info(f"Pedidos leidos del archivo: {len(orders)}")

            if since:
                since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                filtered = []
                for o in orders:
                    if not o.get("created_at"):
                        continue
                    order_dt = datetime.strptime(o["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    if order_dt.date() >= since_dt.date():
                        filtered.append(o)
                logger.info(f"Pedidos tras filtro --since {since}: {len(filtered)}")
                return filtered

            return orders

        except FileNotFoundError as e:
            logger.error(f"Archivo no encontrado: {ORDERS_FILE}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON malformado: {e}")
            raise
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"Error inesperado: {e}. Reintentando en {wait}s...")
            time.sleep(wait)
            attempt += 1

    raise RuntimeError(f"No se pudo leer pedidos tras {retries} intentos")


def save_raw(orders: list[dict], output_dir: Path = RAW_OUTPUT):
    """
    Guarda los pedidos originales en output/raw/ como JSON.
    Nombre de archivo: orders_YYYY-MM-DD.json
    Si no hay pedidos, no crea el archivo para evitar JSONs vacios.
    Sobreescribe si ya existe (idempotencia).
    """
    if not orders:
        logger.info("Sin pedidos nuevos — no se genera archivo raw.")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_path = output_dir / f"orders_{date_str}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    logger.info(f"Raw guardado en: {output_path} ({len(orders)} registros)")
    return output_path


if __name__ == "__main__":
    orders = fetch_orders()
    save_raw(orders)
    print(f"Total pedidos: {len(orders)}")