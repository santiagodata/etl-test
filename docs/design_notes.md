# Notas de diseño — Pipeline ETL JUJU
 
## Tecnologías elegidas: pandas + DuckDB
Se eligió pandas + DuckDB sobre PySpark porque el volumen de JUJU (miles de pedidos diarios) no justifica la complejidad de un clúster Spark. DuckDB permite ejecutar consultas SQL complejas directamente sobre los datos en memoria y sobre archivos Parquet sin ningún servidor adicional. Para volúmenes superiores a 10 millones de filas por día se recomienda migrar a PySpark o AWS Glue.
 
## Particionado y carga a Redshift
Los archivos procesados se escriben en formato Parquet divididos por fecha (`date=YYYY-MM-DD`), lo que los hace compatibles con el comando `COPY` de Redshift:
```sql
COPY fact_order
FROM 's3://juju-bucket/curated/fact_order/'
IAM_ROLE 'arn:aws:iam::ACCOUNT_ID:role/RedshiftS3Role'
FORMAT AS PARQUET;
```
Dividir por fecha permite que Redshift lea solo las particiones necesarias al filtrar por fecha, y que cada ejecución diaria solo escriba el día correspondiente sin tocar el histórico.
 
## Claves del modelo dimensional
- `dim_user` y `dim_product`: claves artificiales (`BIGINT IDENTITY`) para desacoplar el modelo de la fuente. Tablas pequeñas con `DISTSTYLE ALL`: se replican en todos los nodos para evitar movimiento de datos al hacer consultas.
- `fact_order`: clave primaria compuesta `(order_id, sku)` porque la granularidad es línea de pedido, no pedido completo. `DISTKEY(order_date)` y `SORTKEY(order_date, user_sk)` aceleran consultas por rango de fechas.
 
## Idempotencia
Técnica: **borrar y reescribir por partición** — antes de escribir cada carpeta `date=YYYY-MM-DD`, el proceso elimina la carpeta existente con `shutil.rmtree()` y la recrea. Ejecutar el proceso N veces con los mismos datos produce siempre el mismo resultado, sin duplicar registros.
 
## Registros con errores
- `created_at` nulo → rechazado: sin fecha no se puede dividir por partición.
- `items` vacío → rechazado: sin líneas de pedido no hay nada que registrar.
- `items.price` nulo → se reemplaza por `0.0` y se anota una advertencia en los registros de ejecución.
- `metadata` nulo → se conserva el pedido, el campo se ignora.
 
## Seguimiento en producción
**Registros de ejecución**: formato estructurado con el módulo `logging` de Python; en producción se envían a CloudWatch Logs o Datadog.
 
**Métricas mínimas por ejecución**:
 
| Métrica | Alerta |
|---|---|
| Tasa de rechazo | Advertencia si supera el 5% |
| Filas en `fact_order` | Crítico si es 0 |
| Duración total | Advertencia si supera 300 segundos |
| Estado del proceso | Crítico si termina con error |
 
**Recuperación**: al ser idempotente, ante cualquier fallo basta con volver a ejecutar con el mismo `--since` sin riesgo de duplicar datos.
 
## Decisiones de diseño
| Decisión tomada | Opción descartada | Motivo |
|---|---|---|
| Borrar y reescribir por partición | Actualizar registro por registro | Más simple e igualmente correcto |
| Parquet dividido por fecha | CSV plano | Formato nativo de Redshift, entre 3 y 10 veces más eficiente en lectura |
| LEFT JOIN en `fact_order` | INNER JOIN | Conserva pedidos sin usuario registrado para auditoría |
| Archivo `.last_run` en disco | Tabla de control en base de datos | Suficiente para ejecución local; en producción se reemplaza por una tabla de auditoría en Redshift |