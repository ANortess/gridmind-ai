# GridMind AI

**TFM — Predicción y análisis del mercado eléctrico español.**

GridMind AI utiliza datos históricos y operativos publicados por e·sios (Red Eléctrica) para construir una base reproducible de preparación de datos y, posteriormente, modelos de predicción y una aplicación web.

> **Estado:** descarga y actualización de indicadores implementadas; demostración Bronze → Silver → Gold preparada para la Entrega 02. PostgreSQL, los modelos predictivos, Node.js y React son fases futuras.

## Entrega 02

Documento académico: [`docs/entregas/02_datos_y_preparacion.md`](docs/entregas/02_datos_y_preparacion.md).

Para reproducir solamente la demostración de limpieza y Gold, con los CSV originales ya descargados:

```powershell
python -m pip install pandas
python scripts/preparar_entrega02.py --desde 2026-08-01 --hasta 2026-09-30
```

El script lee archivos locales; no llama a la API. Genera archivos Silver, Gold, un informe JSON y una muestra reducida en `data/sample/`.

## Estructura del repositorio

```text
TFM/
├── data/
│   ├── raw/
│   │   ├── CSVs_historico_mensual/  # CSV originales, no subir a Git
│   │   └── JSONs_originales/        # Respaldo opcional
│   ├── unified/                     # Un CSV por indicador, no subir a Git
│   ├── processed/                   # Informes y derivados locales
│   │   ├── silver/
│   │   └── gold/
│   └── sample/                      # Muestra pequeña para el repositorio
├── scripts/
│   ├── descargar_esios.py
│   ├── actualizar_datos.py
│   ├── unir_indicadores.py
│   ├── auditar_datos.py
│   └── preparar_entrega02.py
├── docs/
│   └── entregas/
│       └── 02_datos_y_preparacion.md
└── README.md
```

## ¿Para qué sirve cada script?

| Script | Función | ¿Cuándo se usa? |
|---|---|---|
| `descargar_esios.py` | Descarga inicial de indicadores y metadatos desde e·sios. | Al iniciar el histórico o recuperar una serie desde cero. |
| `actualizar_datos.py` | Revisa meses ausentes; puede consultar en bloques menores cuando la API falla. | Mantenimiento periódico del histórico. |
| `unir_indicadores.py` | Agrupa los CSV mensuales en un CSV por indicador. | Después de descargas o reparaciones. |
| `auditar_datos.py` | Cuenta registros y revisa errores de lectura, nulos y rangos de fechas. | Para comprobar la calidad básica del histórico. |
| `preparar_entrega02.py` | Prepara Silver y Gold de una muestra, emite informe y documentación. | Para reproducir la Entrega 02. |

## Orden de ejecución

### A. Si ya tienes descargado el histórico (caso actual)

Desde `TFM/`:

```powershell
# 1. Verificar o recuperar meses que falten, sin refrescar los existentes
python -u scripts/actualizar_datos.py --refrescar-meses 0

# 2. Reconstruir los CSV por indicador
python scripts/unir_indicadores.py

# 3. Auditar los CSV mensuales
python scripts/auditar_datos.py

# 4. Producir Silver y Gold para la entrega
python scripts/preparar_entrega02.py --desde 2026-08-01 --hasta 2026-09-30
```

**Nota:** el paso 1 es opcional para reproducir la entrega si los CSV de agosto y septiembre ya están presentes. El actualizador revisa principalmente la existencia y el formato de los meses, no garantiza la continuidad interna de cada serie. No hace falta ejecutar la actualización cada vez que se genera Gold.

### B. Si otra persona no tiene el histórico

1. Solicitar y configurar su propio token de API e·sios mediante la variable de entorno `ESIOS_TOKEN` (no publicarlo).
2. Consultar las opciones de descarga: `python scripts/descargar_esios.py --help`.
3. Descargar únicamente los indicadores y periodos necesarios para la demostración.
4. Continuar con unificación, auditoría y preparación de la muestra.

Las opciones precisas de descarga dependen de la versión de `descargar_esios.py` presente en el repositorio. Se recomienda usar `--help` antes de lanzar descargas extensas.

## Resultados de la Entrega 02

Muestra reproducida entre el **1 de agosto y el 30 de septiembre de 2026** (fecha local de España):

- Indicadores empleados: `600` (precio), `544` (demanda prevista) y `542` (previsión solar).
- Silver: validación y normalización temporal de las tres series.
- Gold: **1.296 filas**, con objetivo precio, retardos de 48 y 168 horas, y calendario.
- Informe: `data/processed/informe_entrega02.json`.
- Muestra de repositorio: `data/sample/muestra_gridmind_gold.csv`.

Los recuentos específicos de Silver deben contrastarse con la definición de las métricas emitidas por el script; véase la nota metodológica en el documento de entrega.

## Uso responsable y Git

**No publicar**: tokens, `.env`, archivos JSON completos, los millones de registros CSV ni datos personales innecesarios. El repositorio debe incluir código, documentación, una muestra pequeña y las instrucciones de reproducción. Comprueba el contenido de `git status` antes de cada `git add`.

Fuente: e·sios / Red Eléctrica — <https://api.esios.ree.es/>. La reutilización está sujeta a su [aviso legal](https://www.esios.ree.es/es/aviso-legal-y-politica-de-privacidad), incluidas las condiciones de atribución y restricciones aplicables.

## Evolución prevista

1. Ampliar validaciones de continuidad, unidades y disponibilidad temporal de predictores.
2. Automatizar un pipeline incremental de actualización → auditoría → Silver → Gold.
3. Importar datos validados a **PostgreSQL**.
4. Entrenar y evaluar modelos con separación cronológica de entrenamiento y prueba.
5. Exponer consultas y predicciones con **Node.js** y mostrarlas en **React**.
6. Evaluar el despliegue en **Railway** y **Vercel**.

Estas fases **no forman parte de la funcionalidad demostrada en la Entrega 02**.
