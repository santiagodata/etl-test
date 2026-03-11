# Design Notes — JUJU ETL Pipeline

## Stack elegido: pandas + DuckDB
Se eligió pandas + DuckDB sobre PySpark por tres razones: (1) el volumen
de datos de JUJU (bonos virtuales, ~185.000 usuarios) no justifica la
sobrecarga operacional de un cluster Spark; (2) DuckDB permite ejecutar
queries SQL analíticas directamente sobre Parquet sin infraestructura
adicional; (3) el entorno local de desarrollo es Windows, donde PySpark
requiere configuración adicional compleja. Para volúmenes mayores a 10M
de registros diarios, se recomienda migrar a PySpark o AWS Glue.

## Particionado
Los archivos curated se escriben en Parquet particionado por
`date=YYYY-MM-DD`, compatible con el comando `COPY` de Redshift:
```
COPY fact_order
FROM 's3://juju-bucket/curated/fact_order/'
IAM_ROLE 'arn:aws:iam::ACCOUNT:role/RedshiftS3Role'
FORMAT AS PARQUET;
```
Este esquema permite a Redshift hacer partition pruning y reduce el
costo de cada carga incremental.

## Claves del modelo dimensional
- `dim_user` y `dim_product` usan surrogate keys (`BIGINT IDENTITY`)
  para desacoplar el modelo del sistema fuente.
- `fact_order` usa clave primaria compuesta `(order_id, sku)` porque
  la granularidad es línea de pedido, no pedido completo.
- `DISTKEY(order_date)` en `fact_order` optimiza JOINs por fecha en
  Redshift. `DISTSTYLE ALL` en dims evita movimiento de datos en JOINs.

## Idempotencia
Técnica: **delete-then-write por partición**. Antes de escribir cada
partición `date=YYYY-MM-DD`, el job elimina la carpeta existente con
`shutil.rmtree()` y la recrea. Ejecutar el job N veces produce siempre
el mismo resultado en `output/curated/`.

## Incrementalidad
El job acepta `--since YYYY-MM-DD` para procesar solo pedidos desde
esa fecha. Si no se pasa `--since`, usa el timestamp del último run
guardado en `output/.last_run`. Esto permite ejecuciones diarias sin
reprocesar histórico.

## Registros malformados
Dos categorías van a `output/rejected/rejected_YYYY-MM-DD.csv`:
- `created_at` nulo: no se puede particionar ni ordenar temporalmente.
- `items` vacío: sin líneas de pedido no hay hecho que registrar.
Los registros con `items.price` nulo se mantienen con `price=0.0` y
se documentan en logs como advertencia (comportamiento configurable).

## Monitorización y alertas en producción
**Logs**: estructurados con `logging` de Python, formato
`timestamp [LEVEL] módulo - mensaje`. En producción se enviarían a
CloudWatch Logs o Datadog.

**Métricas clave por ejecución**:
- `pedidos_recibidos`: total de la API
- `pedidos_validos` / `pedidos_rechazados`: calidad del dato
- `tasa_rechazo`: alerta si supera el 5%
- `duracion_segundos`: alerta si supera umbral (ej. 5 min)
- `filas_fact_order`: alerta si cae a 0 inesperadamente

**Alertas recomendadas** (AWS CloudWatch / PagerDuty):
- `tasa_rechazo > 5%` → revisar fuente de datos
- `job_status = FAILED` → reintentar con backoff, notificar on-call
- `filas_escritas = 0` → posible problema en API mock o filtro

**Recuperación**: el job es idempotente, por lo que ante cualquier
fallo se puede relanzar sin riesgo de duplicados.

## Fuentes de datos
- **API mock**: `sample_data/api_orders.json` simula `/api/v1/orders`
- **CSV**: `sample_data/users.csv` y `products.csv` (fuente principal)
- **MSSQL (Docker)**: disponible con flag `--use-mssql`, útil para
  integración con sistemas legacy de JUJU