# JUJU ETL Pipeline

Pipeline ETL reproducible y ejecutable localmente para JUJU (Medellín, CO).
Ingesta pedidos de bonos virtuales desde una API mock y fuentes SQL,
transforma los datos y genera salidas en formato Parquet particionado.

## Stack
- **Python 3.13** con pandas + DuckDB
- **SQL Server 2022** en Docker (fuente opcional MSSQL)
- **pytest** para tests unitarios
- Salidas simulando S3: `output/raw/` y `output/curated/`

## Requisitos previos
- Python 3.10+
- Docker Desktop (para MSSQL opcional)
- Git

## Instalación y configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/santiagodata/etl-test
cd etl-test
```

### 2. Crear y activar el virtualenv
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac/Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crea un archivo `.env` en la raíz del proyecto (excluido del repo):
```
MSSQL_SERVER=localhost
MSSQL_PORT=1433
MSSQL_DATABASE=juju_db
MSSQL_USER=SA
MSSQL_PASSWORD=JujuTest123!
```

### 5. (Opcional) Levantar SQL Server con Docker
```bash
docker run -e "ACCEPT_EULA=Y" -e "SA_PASSWORD=JujuTest123!" -p 1433:1433 --name juju-sqlserver -d mcr.microsoft.com/mssql/server:2022-latest

# Inicializar base de datos
Get-Content sql/init.sql | docker exec -i juju-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U SA -P "JujuTest123!" -No

```


## Ejecución del ETL

### Ejecución completa (fuente CSV)
```bash
python -m src.etl_job
```

### Ejecución incremental desde una fecha
```bash
python -m src.etl_job --since 2025-08-20
```

### Ejecución con SQL Server como fuente
```bash
python -m src.etl_job --use-mssql --since 2025-08-18
```

## Correr los tests
```bash
python -m pytest tests/ -v
```

Resultado esperado: **12 passed** ✅

## Estructura del proyecto
```
etl-test/
├── README.md
├── requirements.txt
├── .env                      # NO incluido en repo
├── .gitignore
├── sample_data/
│   ├── api_orders.json       # 12 pedidos mock (con casos edge)
│   ├── users.csv             # 7 empresas clientes JUJU
│   └── products.csv          # 9 bonos virtuales del catálogo
├── src/
│   ├── etl_job.py            # Orquestador principal
│   ├── transforms.py         # Lógica de transformación
│   ├── api_client.py         # Ingesta API mock con retry
│   └── db.py                 # Carga CSV y MSSQL
├── sql/
│   ├── redshift-ddl.sql      # DDL dim_user, dim_product, fact_order
│   └── init.sql              # Script inicialización SQL Server
├── tests/
│   └── test_transforms.py    # 12 tests unitarios con pytest
├── output/
│   ├── raw/                  # JSON original por fecha
│   ├── curated/              # Parquet particionado por date=
│   │   ├── fact_order/
│   │   ├── dim_user/
│   │   └── dim_product/
│   └── rejected/             # Registros rechazados con motivo
└── docs/
    └── design_notes.md       # Decisiones de diseño
```

## Outputs generados

| Carpeta | Contenido |
|---|---|
| `output/raw/` | JSON original de la API por fecha de ejecución |
| `output/curated/fact_order/date=YYYY-MM-DD/` | Parquet con líneas de pedido |
| `output/curated/dim_user/` | Dimensión usuarios |
| `output/curated/dim_product/` | Dimensión productos |
| `output/rejected/` | Registros rechazados con columna `reject_reason` |

## Casos edge manejados

| Caso | Tratamiento |
|---|---|
| `order_id` duplicado | Se conserva el último registro (`keep='last'`) |
| `created_at` nulo | Rechazado a `output/rejected/` |
| `items` vacío | Rechazado a `output/rejected/` |
| `items.price` nulo | Se rellena con `0.0`, se registra en logs |
| `metadata` nulo | Se conserva el registro, metadata ignorada |

## Tiempo de ejecución
- ETL completo: ~0.5 segundos
- Tests: ~2 segundos
- Tiempo de desarrollo: ~6 horas

## Supuestos tomados
- La moneda es siempre COP (pesos colombianos)
- El archivo JSON simula una API REST real de JUJU
- Los registros con `created_at` nulo no pueden particionarse y se descartan
- `items.price` nulo se interpreta como bono sin precio definido → `0.0`