# Pipeline ETL JUJU

Pipeline de datos reproducible y ejecutable localmente para **JUJU** (Medellín, Colombia).
Lee pedidos de bonos virtuales desde un archivo JSON que simula una API, los transforma
y genera archivos de salida en formato Parquet dividido por fecha, simulando un flujo
de datos hacia S3 + Redshift.

---

## ¿Qué hace este proceso?

1. Lee pedidos desde `sample_data/api_orders.json` (simula una API REST)
2. Carga usuarios y productos desde archivos CSV (o SQL Server si se prefiere)
3. Transforma los datos: elimina duplicados, valida, normaliza y aplana los ítems
4. Genera archivos de salida en `output/`:
   - `raw/` → copia JSON original
   - `curated/` → Parquet dividido por fecha (compatible con carga a Redshift)
   - `rejected/` → registros rechazados con motivo
5. Es **repetible**: ejecutarlo varias veces produce siempre el mismo resultado
6. Soporta **procesamiento incremental**: con `--since` procesa solo pedidos nuevos

---

## Tecnologías usadas

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.10+ |
| Transformaciones | pandas + DuckDB |
| Formato de salida | Parquet (pyarrow) |
| Fuente opcional | SQL Server 2022 (Docker) |
| Pruebas | pytest + pytest-mock |
| Variables de entorno | python-dotenv *(solo con `--use-mssql`)* |

---

## Estructura del proyecto

```
etl-test/
├── README.md
├── requirements.txt
├── .gitignore
├── sample_data/
│   ├── api_orders.json           # 12 pedidos de prueba con casos especiales
│   ├── users.csv                 # 7 empresas clientes de JUJU
│   └── products.csv              # 9 bonos virtuales del catálogo
├── src/
│   ├── etl_job.py                # Punto de entrada principal
│   ├── transforms.py             # Lógica de transformación
│   ├── api_client.py             # Lectura del JSON con reintentos
│   └── db.py                     # Carga desde CSV o SQL Server
├── sql/
│   ├── redshift-ddl.sql          # Tablas dim_user, dim_product, fact_order
│   └── init.sql                  # Script para inicializar SQL Server en Docker
├── tests/
│   └── test_transforms.py        # 12 pruebas automáticas con pytest
├── output/
│   ├── .last_run                 # Fecha de la última ejecución exitosa
│   ├── raw/                      # JSON original por fecha
│   ├── curated/                  # Parquet dividido por fecha
│   │   ├── fact_order/
│   │   │   ├── date=2025-08-18/part-0.parquet
│   │   │   ├── date=2025-08-19/part-0.parquet
│   │   │   ├── date=2025-08-20/part-0.parquet
│   │   │   └── date=2025-08-21/part-0.parquet
│   │   ├── dim_user/
│   │   └── dim_product/
│   └── rejected/                 # Registros con errores
└── docs/
    └── design_notes.md           # Decisiones de diseño
```

---

## Requisitos previos

- **Python 3.10 o superior** → https://www.python.org/downloads/
- **Git** → https://git-scm.com/downloads
- **Docker Desktop** *(solo si quieres usar SQL Server como fuente)* → https://www.docker.com/products/docker-desktop/

Para verificar que los tienes instalados:
```bash
python --version
git --version
docker --version
```

---

## Instalación

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/santiagodata/etl-test.git
cd etl-test
```

### Paso 2 — Crear y activar el entorno virtual

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac / Linux
python -m venv .venv
source .venv/bin/activate
```

Sabrás que el entorno está activo cuando veas `(.venv)` al inicio de la línea.

### Paso 3 — Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 4 — Crear el archivo de variables de entorno

Crea un archivo llamado `.env` en la raíz del proyecto con este contenido:

```
MSSQL_SERVER=localhost
MSSQL_PORT=1433
MSSQL_DATABASE=juju_db
MSSQL_USER=SA
MSSQL_PASSWORD=JujuTest123!
```

> Este archivo está excluido del repositorio con `.gitignore` y nunca se sube.
> Solo se necesita si vas a usar `--use-mssql`. De todas formas es necesario
> crearlo para que Python no falle al importar `src/db.py`.

---

## Ejecutar el proceso ETL

### Primera ejecución

> **Importante**: usa siempre `--since` en la primera ejecución.
> El repositorio incluye `output/.last_run` con la fecha de la última ejecución del autor.
> Sin `--since`, el proceso filtra todos los pedidos y no procesa nada.

```bash
python -m src.etl_job --since 2025-08-18
```

Resultado esperado:
```
[INFO] JUJU ETL Job iniciado
[INFO] Parametros: since=2025-08-18, use_mssql=False
[INFO] Pedidos leidos del archivo: 12
[INFO] Pedidos tras filtro --since 2025-08-18: 11
[INFO] Deduplicacion: 11 -> 9 registros (2 duplicados eliminados)
[INFO] Validacion: 8 validos, 1 rechazados
[WARNING] [ALERTA] Tasa de rechazo alta: 11.1%
[INFO] fact_order: 10 registros
[INFO] Curated escrito: output/curated/fact_order/date=2025-08-18/part-0.parquet
[INFO] Curated escrito: output/curated/fact_order/date=2025-08-19/part-0.parquet
[INFO] Curated escrito: output/curated/fact_order/date=2025-08-20/part-0.parquet
[INFO] Curated escrito: output/curated/fact_order/date=2025-08-21/part-0.parquet
[WARNING] Rechazados guardados: output/rejected/rejected_YYYY-MM-DD.csv (1 registros)
[INFO] ETL Job finalizado exitosamente
[METRICA] Filas en fact_order: 10
[METRICA] Duracion total: ~0.5s
```

### Procesar solo desde una fecha

```bash
python -m src.etl_job --since 2025-08-20
```

Procesa únicamente los pedidos desde el 20 de agosto de 2025 en adelante.

### Ejecución automática (usa la fecha del último proceso)

```bash
python -m src.etl_job
```

Si existe `output/.last_run`, usa esa fecha como punto de partida.
Útil para ejecuciones diarias programadas.
Para reprocesar todo desde el inicio: `python -m src.etl_job --since 2025-08-18`

## (Opcional) SQL Server con Docker

Solo necesario si quieres usar SQL Server como fuente en lugar de los archivos CSV. Se debe tener instalado Docker Desktop para realizar el proceso.

**1. Eliminar contenedor anterior si existe (Si no existe, estos comandos mostraran error, simplemente se deben ignorar y continuar con el porceso):**
```bash
docker stop juju-sqlserver
docker rm juju-sqlserver
```

**2. Levantar SQL Server:**
```bash
docker run -e "ACCEPT_EULA=Y" -e "SA_PASSWORD=JujuTest123!" -p 1433:1433 --name juju-sqlserver -d mcr.microsoft.com/mssql/server:2022-latest
```

**3. Esperar 15 segundos e inicializar la base de datos:**

```bash
# Mac / Linux
cat sql/init.sql | docker exec -i juju-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U SA -P "JujuTest123!" -No

# Windows
Get-Content sql/init.sql | docker exec -i juju-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U SA -P "JujuTest123!" -No
```

Resultado esperado:
```
Changed database context to 'juju_db'.
(7 rows affected)
(9 rows affected)
(8 rows affected)
```

**4. Ejecutar el proceso usando SQL Server como fuente:**
```bash
python -m src.etl_job --use-mssql --since 2025-08-18
```

---

## Correr las pruebas

```bash
python -m pytest tests/ -v
```

Resultado esperado:
```
collected 12 items

tests/test_transforms.py::test_deduplicate_orders_elimina_duplicados PASSED
tests/test_transforms.py::test_deduplicate_orders_conserva_ultimo    PASSED
tests/test_transforms.py::test_deduplicate_orders_sin_duplicados     PASSED
tests/test_transforms.py::test_validate_rechaza_created_at_nulo      PASSED
tests/test_transforms.py::test_validate_rechaza_items_vacio          PASSED
tests/test_transforms.py::test_validate_aprueba_registros_validos    PASSED
tests/test_transforms.py::test_validate_conteo_correcto              PASSED
tests/test_transforms.py::test_flatten_items_genera_filas_por_item   PASSED
tests/test_transforms.py::test_flatten_items_columnas_correctas      PASSED
tests/test_transforms.py::test_flatten_items_price_nulo_rellena_cero PASSED
tests/test_transforms.py::test_fetch_orders_mock                     PASSED
tests/test_transforms.py::test_idempotencia_no_duplica               PASSED

========================= 12 passed in ~2s =========================
```

---

## Verificar que el proceso es repetible

```bash
python -m src.etl_job --since 2025-08-18
python -m src.etl_job --since 2025-08-18
```

El número de filas en `output/curated/` debe ser idéntico en ambas ejecuciones.
**Técnica usada**: borrar y reescribir por partición — antes de escribir cada carpeta
`date=YYYY-MM-DD`, el proceso elimina la carpeta existente y la recrea desde cero.

---

## Archivos de salida generados

| Archivo | Descripción |
|---|---|
| `output/raw/orders_YYYY-MM-DD.json` | Copia del JSON original, una por fecha de ejecución |
| `output/curated/fact_order/date=YYYY-MM-DD/part-0.parquet` | Tabla de hechos dividida por fecha de pedido |
| `output/curated/dim_user/date=YYYY-MM-DD/part-0.parquet` | Tabla de usuarios |
| `output/curated/dim_product/date=YYYY-MM-DD/part-0.parquet` | Tabla de productos |
| `output/rejected/rejected_YYYY-MM-DD.csv` | Registros rechazados con columna `reject_reason` |

Para cargar a Redshift desde S3:
```sql
COPY fact_order
FROM 's3://juju-bucket/curated/fact_order/'
IAM_ROLE 'arn:aws:iam::ACCOUNT_ID:role/RedshiftS3Role'
FORMAT AS PARQUET;
```

---

## Casos especiales manejados

| Caso | Registro de prueba | Tratamiento |
|---|---|---|
| Pedido duplicado | `JJ-1002` y `JJ-1005` aparecen 2 veces | Se conserva el más reciente |
| Fecha nula | `JJ-1009` | Rechazado, motivo: `created_at_nulo` |
| Sin ítems | `JJ-1010` | Rechazado, motivo: `items_vacio` |
| Precio nulo en ítem | `JJ-1007` ítem BONO-D1-25K | Se reemplaza por `0.0`, advertencia en registros |
| Sin metadatos | `JJ-1004` | Se conserva el pedido, campo ignorado |

---

## Tiempo de desarrollo

**Total: Apximadamente 7 horas. Distribuidas de la siguiente manera**

| Fase | Tiempo |
|---|--------|
| Configuración y datos de prueba | 1h     |
| Código del proceso ETL | 2:30h  |
| SQL (tablas y consultas) | 45 min |
| Pruebas automáticas | 1h     |
| Documentación | 1:45 h |

---

## Supuestos y limitaciones

- La moneda base es COP. El campo `currency` se conserva en `fact_order` para conversiones futuras.
- Los pedidos con `user_id` sin registro en usuarios se incluyen en `fact_order` con `country = NULL`.
- `output/.last_run` en el repositorio tiene la fecha de la última ejecución del autor — usar siempre `--since 2025-08-18` en la primera ejecución propia.
- El campo `created_at` de los pedidos debe venir en formato exacto `YYYY-MM-DDTHH:MM:SSZ`. Formatos con milisegundos o con zona horaria diferente a UTC (`+05:00`) no son compatibles con el filtro `--since` y el pedido sería omitido.
- Los pedidos sin `created_at` se excluyen del filtro `--since` antes de llegar a la validación. Esto significa que no aparecen ni en `curated/` ni en `rejected/` si se usan en combinación con `--since`. Sin `--since` sí llegan a la validación y son rechazados normalmente.
- La tabla `dbo.orders_db` que existe en `init.sql` no es usada por el proceso. Los pedidos siempre se leen desde `sample_data/api_orders.json`, independientemente de si se usa `--use-mssql` o no.