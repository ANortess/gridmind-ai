# Entrega 02 — Datos y preparación

## GridMind AI: predicción y análisis del mercado eléctrico español

**Proyecto:** GridMind AI  
**Entrega:** 02 — Datos y preparación  
**Fecha:** 28 de octubre de 2026  
**Alcance:** demostración reproducible de adquisición y transformación de datos. **No se entrenan modelos** en esta entrega.

## Introducción

GridMind AI es una propuesta de aplicación para analizar y, en una fase posterior, predecir el precio del mercado eléctrico español. La solución combina datos reales del sistema eléctrico con técnicas de ingeniería de datos y, posteriormente, aprendizaje automático. La adquisición se realiza mediante la API e·sios de Red Eléctrica. El proyecto reúne históricos de hasta aproximadamente diez años de doce indicadores, si bien la cobertura efectiva varía por serie.

La presente entrega demuestra un recorrido verificable desde datos originales (Bronze) hasta un conjunto estructurado para aprendizaje automático (Gold). Se prioriza una muestra funcional frente al procesamiento de todos los indicadores.

## 1. Qué datos necesita el producto

El producto necesita, principalmente, **precios históricos del mercado eléctrico español**, marcas temporales fiables y variables que puedan explicar su variación. Para un modelo básico son suficientes el precio histórico y el calendario; para modelos multivariables se consideran previsiones de demanda y generación renovable, además de otras tecnologías y variables externas.

En el primer dataset **una observación Gold representa una hora de entrega eléctrica**, identificada por `fecha_utc`. La variable objetivo es `precio_spot`, procedente del indicador e·sios `600` para España (`geo_id = 3`). Las características iniciales son `precio_lag_48h`, `precio_lag_168h` y variables de calendario. Su uso definitivo dependerá de fijar el instante de emisión de la predicción y comprobar qué información era conocida entonces.

Se han descargado los indicadores `600`, `544`, `1293`, `542`, `14`, `12`, `9`, `4`, `1`, `25`, `10037` y `10043`. Su catálogo y metadatos se conservan en `data/processed/01_catalogo_indicadores.csv` y `02_detalle_indicadores.csv`. Entre las magnitudes analizadas figuran precio, demanda prevista y real, previsión solar, generación programada por tecnologías y generación medida. **Las unidades, definiciones y momentos de publicación de cada indicador deben confirmarse con sus metadatos oficiales antes de utilizarlos conjuntamente.**

La cobertura histórica es de aproximadamente diez años, pero existen diferencias de disponibilidad y cambios entre frecuencias horarias y cuarto-horarias. Para esta demostración se selecciona una muestra entre el **1 de agosto y el 30 de septiembre de 2026** (fechas locales de España) y una resolución Gold horaria.

## 2. Fuentes reales y viabilidad

### Fuente principal: API e·sios

- **Organismo:** Red Eléctrica / e·sios.
- **API:** <https://api.esios.ree.es/>
- **Acceso:** peticiones HTTP autenticadas con el token guardado en la variable de entorno `ESIOS_TOKEN`.
- **Adquisición:** consultas por indicador y periodo; los datos se guardan en CSV mensuales por indicador.
- **Actualización:** un script incremental comprueba archivos faltantes y permite refrescar periodos seleccionados, evitando repetir el histórico completo.

Los scripts `scripts/descargar_esios.py`, `scripts/actualizar_datos.py`, `scripts/unir_indicadores.py` y `scripts/auditar_datos.py` cubren adquisición, actualización, consolidación y comprobaciones básicas. Para la entrega, `scripts/preparar_entrega02.py` **lee los CSV disponibles sin consultar la red**.

Durante el desarrollo se observaron errores HTTP 504 para el indicador `10043` en consultas mensuales. Se introdujo una estrategia de división por semanas y, si procede, días. Como comprobación real, noviembre de 2016 se recuperó en cinco consultas y se generó un CSV de **33.840 registros**. También se detectó y recuperó el archivo mensual del precio del indicador `600` correspondiente a agosto de 2026: para España se comprobaron **2.976 observaciones cuarto-horarias**, sin nulos ni duplicados de instante UTC en esa selección.

**Limitación de disponibilidad:** la existencia de un CSV mensual no prueba por sí misma su continuidad interna ni la calidad de todos sus valores; es necesario auditarlo.

**Alternativa:** REData de Red Eléctrica (<https://www.ree.es/es/datos/apidatos>) u otras fuentes oficiales adecuadas para las series de mercado. Antes de sustituir la fuente habría que verificar equivalencias en definición, frecuencia, unidades, geografía y licencia.

## 3. Uso, privacidad y datos personales

La información manejada describe magnitudes agregadas del sistema eléctrico; el proyecto no requiere recopilar datos personales de consumidores. Se aplica minimización conservando identificador del indicador, fecha, zona y valor, junto con metadatos técnicos necesarios para interpretar la serie.

El token de acceso a la API se configura como variable de entorno y **no debe incluirse en GitHub**. Tampoco se publican los históricos completos en el repositorio: solo una muestra pequeña y las instrucciones para reproducir la preparación.

La reutilización está sujeta al **aviso legal oficial de e·sios**: <https://www.esios.ree.es/es/aviso-legal-y-politica-de-privacidad>. Antes de redistribuir datos o explotar comercialmente la solución se deberán revisar las condiciones vigentes, atribuir correctamente a la fuente y respetar las restricciones aplicables. Este proyecto se presenta como **prototipo académico**; no se presupone permiso para uso comercial.

## 4. Del dato bruto al dato utilizable: Bronze → Silver → Gold

### Bronze / Raw — Conservación

Los CSV originales se almacenan sin modificaciones en:

```text
data/raw/CSVs_historico_mensual/indicador_{id}/AAAA-MM.csv
```

Los campos principales son `indicator_id`, `datetime`, `datetime_utc`, `value`, `geo_id` y `geo_name`. Se conserva la fecha UTC para manejar correctamente los cambios de horario. Los JSON completos pueden mantenerse como respaldo adicional, aunque no son necesarios para ejecutar la demostración si los CSV ya están presentes.

### Silver — Calidad y normalización

El script `scripts/preparar_entrega02.py` procesa una muestra de los indicadores:

| Indicador | Serie | Filtro geográfico |
|---|---|---|
| `600` | Precio SPOT | España, `geo_id = 3` |
| `544` | Demanda prevista | Peninsular, `geo_id = 8741` |
| `542` | Previsión solar | Peninsular, `geo_id = 8741` |

Las transformaciones principales son:

1. Validación de columnas, tipos de dato y valores numéricos.
2. Interpretación de marcas temporales en UTC y delimitación por fechas locales españolas.
3. Selección de las zonas geográficas correctas.
4. Revisión de registros inválidos, duplicados y huecos temporales.
5. Normalización temporal a una referencia horaria para la demostración.
6. Rechazo de horas de precio con cobertura cuarto-horaria parcial cuando corresponda.

Los resultados se guardan en `data/processed/silver/`. Para el precio, la media horaria es una **convención provisional de preparación**, pendiente de contrastar con la definición oficial de la serie. La conversión de otras magnitudes deberá respetar su unidad y naturaleza: no todas las variables pueden agregarse indiscriminadamente con la misma operación.

### Gold — Estructura consumible por Machine Learning

El resultado está en `data/processed/gold/dataset_gridmind_gold.csv`. Cada fila corresponde a **una hora UTC válida**, con precio objetivo y retardos históricos calculables sin rellenar artificialmente las horas ausentes.

| Columna | Significado |
|---|---|
| `fecha_utc` | Hora de entrega eléctrica, en UTC |
| `precio_spot` | Variable objetivo: precio del indicador 600; unidad pendiente de confirmación documental |
| `precio_lag_48h` | Precio correspondiente a 48 horas antes |
| `precio_lag_168h` | Precio correspondiente a 168 horas antes |
| `hora_local` | Hora civil en España |
| `dia_semana` | Día de la semana |
| `mes` | Mes del año |
| `es_fin_semana` | Indicador de sábado o domingo |

Los retardos se calculan sobre un índice temporal continuo para evitar desplazamientos incorrectos ante huecos. La demanda prevista y la previsión solar quedan disponibles en Silver, pero **no se incorporan todavía al primer Gold**: falta confirmar su instante real de publicación para evitar fuga de información (*data leakage*).

### Resultados observados de la ejecución

Para el periodo de muestra indicado, la ejecución comunicó:

| Indicador | CSV leídos | Recuento reportado como Silver | Inválidas | Duplicadas |
|---|---:|---:|---:|---:|
| `600` | 4 | 5.856 | 0 | 0 |
| `544` | 4 | 17.568 | 0 | 0 |
| `542` | 4 | 5.856 | 0 | 0 |

**Gold generado: 1.296 filas.** No se comunicaron horas de precio con cobertura parcial.

> **Nota de validación:** los recuentos reportados para Silver son superiores al número de horas únicas del periodo. Antes de interpretar estas cifras como horas horarias definitivas, es necesario verificar si el informe contabiliza observaciones de entrada, pasos intermedios o filas de salida. Se preservan aquí los resultados registrados sin atribuirles una interpretación no comprobada.

La ejecución también produce `data/processed/informe_entrega02.json` y `data/sample/muestra_gridmind_gold.csv` (muestra de hasta 100 filas).

### Reproducibilidad

Desde la raíz `TFM/`, con Python y `pandas` instalados y los CSV originales disponibles:

```powershell
python scripts/preparar_entrega02.py --desde 2026-08-01 --hasta 2026-09-30
```

No es necesario volver a descargar diez años de datos. La descripción de todos los scripts y el orden de ejecución están documentados en el `README.md` del repositorio.

### Potencial de la base de datos y arquitectura futura

Aunque **PostgreSQL no es un requisito ni una implementación finalizada en esta entrega**, se ha seleccionado como base de datos prevista para el producto por su adecuación al almacenamiento y consulta de grandes series temporales mediante SQL.

La estructura proyectada incluye:

| Tabla prevista | Función |
|---|---|
| `indicadores` | Catálogo de series y metadatos |
| `mediciones` | Registros históricos validados |
| `dataset_modelo` | Conjunto de variables para modelado o una vista derivada |
| `predicciones` | Valores predichos, modelo, fecha y métricas |
| `actualizaciones` | Trazabilidad de descargas e importaciones |

El flujo previsto para el producto es:

```text
API e·sios
   ↓
Bronze (CSV originales)
   ↓
Silver (limpieza y validación con Python)
   ↓
Gold (datos preparados)
   ↓
PostgreSQL (almacenamiento y consulta)
   ↓
Python / Machine Learning
   ↓
Backend Node.js / API REST
   ↓
Frontend React
```

La separación facilita un futuro pipeline automatizado, desde la revisión incremental de la API hasta la inserción sin duplicados en PostgreSQL. Node.js expondrá datos y resultados al frontend mediante endpoints HTTP; **la limpieza se realizará en Python, no mediante peticiones GET**. Esta arquitectura es una **propuesta de desarrollo futuro**, claramente separada de lo demostrado en la entrega.

## 5. Riesgos y limitaciones

Existen meses ausentes o incompletos, cambios de frecuencia y diferencias de cobertura entre indicadores. La agregación horaria, las unidades y las definiciones oficiales deben contrastarse antes del entrenamiento. Incluir generación medida o previsiones no disponibles en el instante de predicción produciría fuga de información. Si e·sios dejara de estar disponible, se conservaría el histórico local y se estudiarían fuentes oficiales alternativas, verificando la comparabilidad de las series.

## Conclusión

Se ha demostrado un mecanismo real de adquisición y actualización de datos eléctricos, su almacenamiento trazable en archivos originales y una transformación reproducible Bronze → Silver → Gold. El primer Gold contiene **1.296 registros** utilizables para preparar experimentos de aprendizaje automático, sujetos a las verificaciones de calidad y definición temporal descritas. **No se ha entrenado aún ningún modelo**, conforme al alcance de la Entrega 02.
