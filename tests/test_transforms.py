import pytest
import pandas as pd
from unittest.mock import patch, mock_open
import json

from src.transforms import (
    deduplicate_orders,
    validate_orders,
    normalize_orders,
    flatten_items,
    build_dim_user,
    build_dim_product,
    build_fact_order,
)


# ── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_orders():
    return pd.DataFrame([
        {"order_id": "JJ-1001", "user_id": "emp_001", "amount": 150000, "currency": "COP",
         "created_at": "2025-08-18T08:30:00Z",
         "items": [{"sku": "BONO-EXITO-50K", "qty": 2, "price": 75000.0}],
         "metadata": {"source": "instant_rewards", "promo": None}},
        {"order_id": "JJ-1002", "user_id": "emp_002", "amount": 200000, "currency": "COP",
         "created_at": "2025-08-18T09:15:00Z",
         "items": [{"sku": "BONO-AMAZON-100K", "qty": 2, "price": 100000.0}],
         "metadata": {"source": "bonos_express", "promo": "SAVE10"}},
        {"order_id": "JJ-1002", "user_id": "emp_002", "amount": 200000, "currency": "COP",
         "created_at": "2025-08-18T09:15:00Z",
         "items": [{"sku": "BONO-AMAZON-100K", "qty": 2, "price": 100000.0}],
         "metadata": {"source": "bonos_express", "promo": "SAVE10"}},
    ])


@pytest.fixture
def orders_with_issues():
    return pd.DataFrame([
        {"order_id": "JJ-1003", "user_id": "emp_003", "amount": 50000, "currency": "COP",
         "created_at": None,
         "items": [{"sku": "BONO-JUMBO-50K", "qty": 1, "price": 50000.0}],
         "metadata": None},
        {"order_id": "JJ-1004", "user_id": "emp_004", "amount": 60000, "currency": "COP",
         "created_at": "2025-08-19T10:00:00Z",
         "items": [],
         "metadata": None},
        {"order_id": "JJ-1005", "user_id": "emp_005", "amount": 75000, "currency": "COP",
         "created_at": "2025-08-20T07:00:00Z",
         "items": [{"sku": "BONO-RAPPI-25K", "qty": 3, "price": 25000.0}],
         "metadata": {"source": "instant_rewards", "promo": None}},
    ])


@pytest.fixture
def sample_users():
    return pd.DataFrame([
        {"user_id": "emp_001", "email": "incentivos@exito.com",   "created_at": "2024-01-15", "country": "CO"},
        {"user_id": "emp_002", "email": "rrhh@falabella.com.co",  "created_at": "2024-02-20", "country": "CO"},
        {"user_id": "emp_003", "email": "bienestar@kokoriko.com", "created_at": "2024-04-10", "country": "CO"},
    ])


@pytest.fixture
def sample_products():
    return pd.DataFrame([
        {"sku": "BONO-EXITO-50K",   "name": "Bono Exito 50000",   "category": "Almacenes", "price": 50000.0},
        {"sku": "BONO-AMAZON-100K", "name": "Bono Amazon 100000", "category": "E-Commerce","price": 100000.0},
        {"sku": "BONO-RAPPI-25K",   "name": "Bono Rappi 25000",   "category": "Comidas",   "price": 25000.0},
    ])


# ── TESTS DEDUPLICACION ───────────────────────────────────────────────────────

def test_deduplicate_orders_elimina_duplicados(sample_orders):
    result = deduplicate_orders(sample_orders)
    assert len(result) == 2


def test_deduplicate_orders_conserva_ultimo(sample_orders):
    result = deduplicate_orders(sample_orders)
    assert result["order_id"].tolist() == ["JJ-1001", "JJ-1002"]


def test_deduplicate_orders_sin_duplicados():
    df = pd.DataFrame([
        {"order_id": "JJ-A", "amount": 100},
        {"order_id": "JJ-B", "amount": 200},
    ])
    result = deduplicate_orders(df)
    assert len(result) == 2


# ── TESTS VALIDACION ─────────────────────────────────────────────────────────

def test_validate_rechaza_created_at_nulo(orders_with_issues):
    valid, rejected = validate_orders(orders_with_issues)
    rejected_ids = rejected["order_id"].tolist()
    assert "JJ-1003" in rejected_ids


def test_validate_rechaza_items_vacio(orders_with_issues):
    valid, rejected = validate_orders(orders_with_issues)
    rejected_ids = rejected["order_id"].tolist()
    assert "JJ-1004" in rejected_ids


def test_validate_aprueba_registros_validos(orders_with_issues):
    valid, rejected = validate_orders(orders_with_issues)
    assert "JJ-1005" in valid["order_id"].tolist()


def test_validate_conteo_correcto(orders_with_issues):
    valid, rejected = validate_orders(orders_with_issues)
    assert len(valid) == 1
    assert len(rejected) == 2


# ── TESTS FLATTEN ITEMS ───────────────────────────────────────────────────────

def test_flatten_items_genera_filas_por_item():
    df = pd.DataFrame([{
        "order_id": "JJ-1001", "user_id": "emp_001", "amount": 150000,
        "currency": "COP", "created_at": "2025-08-18T08:30:00Z", "date": "2025-08-18",
        "items": [
            {"sku": "BONO-EXITO-50K",  "qty": 2, "price": 75000.0},
            {"sku": "BONO-D1-25K",     "qty": 1, "price": 25000.0},
        ],
        "metadata": None
    }])
    result = flatten_items(df)
    assert len(result) == 2


def test_flatten_items_columnas_correctas():
    df = pd.DataFrame([{
        "order_id": "JJ-1001", "user_id": "emp_001", "amount": 150000,
        "currency": "COP", "created_at": "2025-08-18T08:30:00Z", "date": "2025-08-18",
        "items": [{"sku": "BONO-EXITO-50K", "qty": 2, "price": 75000.0}],
        "metadata": None
    }])
    result = flatten_items(df)
    assert "sku"        in result.columns
    assert "qty"        in result.columns
    assert "item_price" in result.columns


def test_flatten_items_price_nulo_rellena_cero():
    df = pd.DataFrame([{
        "order_id": "JJ-1007", "user_id": "emp_006", "amount": 250000,
        "currency": "COP", "created_at": "2025-08-21T08:00:00Z", "date": "2025-08-21",
        "items": [{"sku": "BONO-D1-25K", "qty": 2, "price": None}],
        "metadata": None
    }])
    result = flatten_items(df)
    assert result["item_price"].iloc[0] == 0.0


# ── TESTS MOCK API ────────────────────────────────────────────────────────────

def test_fetch_orders_mock():
    mock_data = [
        {"order_id": "JJ-9001", "user_id": "emp_001", "amount": 50000,
         "currency": "COP", "created_at": "2025-08-18T08:00:00Z",
         "items": [{"sku": "BONO-EXITO-50K", "qty": 1, "price": 50000.0}],
         "metadata": None}
    ]
    with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
        from src.api_client import fetch_orders
        result = fetch_orders()
    assert len(result) == 1
    assert result[0]["order_id"] == "JJ-9001"


# ── TEST IDEMPOTENCIA ─────────────────────────────────────────────────────────

def test_idempotencia_no_duplica(tmp_path):
    from src.etl_job import write_curated
    import importlib, src.etl_job as etl
    etl.CURATED_DIR = tmp_path

    df = pd.DataFrame([{
        "order_id": "JJ-1001", "user_id": "emp_001", "sku": "BONO-EXITO-50K",
        "qty": 2, "unit_price": 75000.0, "amount": 150000, "currency": "COP",
        "created_at": "2025-08-18T08:30:00Z", "country": "CO",
        "product_name": "Bono Exito", "category": "Almacenes", "date": "2025-08-18"
    }])

    write_curated(df, "fact_order")
    write_curated(df, "fact_order")  # segunda ejecucion

    result = pd.read_parquet(tmp_path / "fact_order" / "date=2025-08-18" / "part-0.parquet")
    assert len(result) == 1