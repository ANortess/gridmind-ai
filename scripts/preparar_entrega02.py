#!/usr/bin/env python3
"""Entrega 02 GridMind AI: Bronze (CSV mensual) -> Silver -> Gold.
Ejecutar desde cualquier directorio: python scripts/preparar_entrega02.py
No descarga datos ni toca los originales.
"""
import argparse
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw' / 'CSVs_historico_mensual'
OUT = ROOT / 'data' / 'processed'
SILVER = OUT / 'silver'
GOLD = OUT / 'gold'
SAMPLE = ROOT / 'data' / 'sample'
DOC = ROOT / 'docs' / 'entregas' / '02_datos_y_preparacion.md'
REQUIRED = {'indicator_id', 'datetime_utc', 'value', 'geo_id'}
INDICATORS = {600: ('precio_spot_espana', 3), 544: ('demanda_prevista', 8741), 542: ('solar_prevista', 8741)}


def load_indicator(indicator_id, geo_id, start, end):
    folder = RAW / f'indicador_{indicator_id}'
    # Se lee desde el mes anterior para cubrir el inicio local de un mes (UTC vs Madrid)
    month_before = (start - pd.DateOffset(months=1)).strftime('%Y-%m')
    month_after = (end + pd.DateOffset(months=1)).strftime('%Y-%m')
    files = [p for p in sorted(folder.glob('????-??.csv')) if month_before <= p.stem <= month_after]
    if not files:
        raise FileNotFoundError(f'No hay CSV mensuales para {indicator_id} en {folder}')
    chunks = []
    for p in files:
        try:
            df = pd.read_csv(p, encoding='utf-8-sig', low_memory=False)
            if not REQUIRED.issubset(df.columns):
                print(f'  AVISO: columnas insuficientes en {p.name}; omitido')
                continue
            df = df[['indicator_id', 'datetime_utc', 'value', 'geo_id']].copy()
            chunks.append(df)
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
            print(f'  AVISO: {p.name} no legible: {exc}')
    if not chunks:
        raise ValueError(f'No se encontraron CSV legibles para {indicator_id}')
    df = pd.concat(chunks, ignore_index=True)
    total = len(df)
    df['geo_id'] = pd.to_numeric(df['geo_id'], errors='coerce')
    df = df.loc[df['geo_id'] == geo_id].copy()
    if df.empty:
        raise ValueError(f'Indicador {indicator_id}: geo_id={geo_id} sin datos; revisa las zonas del CSV')
    df['datetime_utc'] = pd.to_datetime(df['datetime_utc'], utc=True, errors='coerce')
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    invalid = int((df['datetime_utc'].isna() | df['value'].isna()).sum())
    df = df.dropna(subset=['datetime_utc', 'value'])
    df = df.loc[(df['datetime_utc'].dt.tz_convert('Europe/Madrid').dt.tz_localize(None) >= start)
                & (df['datetime_utc'].dt.tz_convert('Europe/Madrid').dt.tz_localize(None) < end)].copy()
    conflicts = int(df.duplicated(subset=['datetime_utc'], keep=False).sum())
    # Se conservan los valores más recientes en orden de archivo, y se reportan conflictos.
    df = df.drop_duplicates(subset=['datetime_utc'], keep='last').sort_values('datetime_utc')
    return df[['datetime_utc', 'value']], {'filas_archivos_leidos': total, 'filas_silver': len(df),
                                          'filas_invalidas': invalid, 'filas_duplicadas_en_grupo': conflicts,
                                          'archivos_leidos': len(files), 'geo_id': geo_id}


def hourly(df, name, is_price):
    s = df.set_index('datetime_utc')['value'].sort_index()
    aggregates = s.resample('1h').agg(['mean', 'count'])
    # Precio: un precio horario o cuatro cuarto-horarios; otras coberturas parciales se excluyen.
    if is_price:
        bad = ~aggregates['count'].isin([1, 4])
        aggregates.loc[bad, 'mean'] = float('nan')
        incomplete = int(bad.sum())
    else:
        incomplete = 0
    result = aggregates[['mean']].rename(columns={'mean': name})
    return result, incomplete


def make_doc(stats, start, end, gold_rows):
    desc = f'''# Entrega 02 — Datos y preparación — GridMind AI

> Fecha de elaboración: generada automáticamente con `python scripts/preparar_entrega02.py`.
> Periodo de la muestra: **{start.date()} a {(end - pd.Timedelta(days=1)).date()}** (fechas locales de España).

## 1. Qué datos necesita el producto

GridMind AI busca predecir y analizar el precio del mercado eléctrico español. Para la primera fase, una **observación Gold representa una hora de entrega eléctrica en España peninsular**, identificada inequívocamente por `fecha_utc`. La variable objetivo es `precio_spot` del indicador 600 (geo_id=3). Las variables predictoras de esta demostración son calendario y precios históricos retardados (`precio_lag_48h` y `precio_lag_168h`). El sistema completo también considera demanda prevista (544) y previsión solar (542), entre otros indicadores, pero su inclusión como predictores exige verificar cuándo estaban publicados. Se dispone de CSV históricos de aproximadamente diez años, con cobertura y resolución variables según indicador. La muestra reproducible de esta entrega utiliza el periodo indicado arriba.

## 2. Fuentes reales y viabilidad

**Fuente principal:** API e·sios de Red Eléctrica, `https://api.esios.ree.es/` (acceso mediante token `ESIOS_TOKEN` y peticiones HTTP a indicadores). Los scripts `scripts/descargar_esios.py` y `scripts/actualizar_datos.py` descargan y actualizan CSV por indicador y mes. Para esta entrega, `scripts/preparar_entrega02.py` consume esos CSV existentes sin acceder a la red. El histórico es amplio, pero existen cambios de frecuencia (horaria/cuarto-horaria), huecos y fallos ocasionales HTTP 504; el indicador 10043 requirió consultar intervalos menores. **Alternativa:** API REData de Red Eléctrica (`https://www.ree.es/es/datos/apidatos`) para indicadores compatibles o fuentes oficiales del mercado para precios; la equivalencia exacta debe comprobarse antes de sustituir series.

## 3. Uso, privacidad y datos personales

Los indicadores utilizados son agregados del sistema eléctrico; el dataset no requiere nombres, contactos, identificadores de personas ni otros datos personales. Se almacena el identificador de indicador, zona, fecha y valor. Antes de publicar o comercializar resultados hay que respetar el **aviso legal de e·sios** (`https://www.esios.ree.es/es/aviso-legal-y-politica-de-privacidad`), incluidas sus condiciones de reutilización, atribución, fechas de actualización y restricciones de uso comercial. Este proyecto se presenta como ejercicio académico; **no se presume una licencia irrestricta para uso comercial**. El token API se mantiene fuera del repositorio.

## 4. Del dato bruto al dato utilizable: Bronze → Silver → Gold

**Bronze / Raw.** `data/raw/CSVs_historico_mensual/indicador_{{id}}/AAAA-MM.csv`. Se conservan sin modificarlos. Columnas fuente utilizadas: `indicator_id`, `datetime_utc`, `value`, `geo_id`. Los JSON originales pueden conservarse como respaldo de respuestas completas.

**Silver.** El script valida columnas y tipos, interpreta UTC, filtra zona (600 → España 3; 544 y 542 → peninsular 8741), filtra el periodo por fecha local de Madrid, elimina filas inválidas, resuelve duplicados de instante y agrega promedios a horas UTC. Para el precio descarta agregaciones con 2 o 3 observaciones cuando la frecuencia es cuarto-horaria: no inventa un precio horario con una hora parcial. La media horaria de precios es una transformación de trabajo, pendiente de contrastar con la definición oficial del indicador. Se guardan CSV en `data/processed/silver/`. No se mezclan tecnologías energéticas de unidades distintas.

**Gold.** `data/processed/gold/dataset_gridmind_gold.csv`. **Una fila = una hora UTC con precio objetivo y ambos retardos observados válidos**, sin completar huecos artificialmente. Columnas: `fecha_utc`, `precio_spot` (objetivo, unidad a verificar en metadatos de indicador), `precio_lag_48h`, `precio_lag_168h`, `hora_local`, `dia_semana`, `mes`, `es_fin_semana`. Los retardos se calculan sobre un índice horario UTC continuo para evitar desplazamientos erróneos cuando faltan horas. Se han elegido 48 y 168 horas como variables históricas conservadoras para un futuro experimento de pronóstico del día siguiente; antes de entrenar hay que fijar formalmente la hora de emisión del pronóstico y comprobar disponibilidad. **No se han entrenado modelos todavía.** Las series 544 y 542 quedan en Silver como evidencia de preparación multivariable, pero no entran en este primer Gold para evitar una fuga de información por fechas de publicación no verificadas.

**Resultados de la ejecución (muestra):**

| Indicador | CSV leídos | Filas Silver | Inválidas | Duplicadas antes de resolver | Horas con cobertura parcial de precio |
|---|---:|---:|---:|---:|---:|
'''
    for indicator_id in (600, 544, 542):
        st = stats[str(indicator_id)]
        desc += f"| {indicator_id} | {st['archivos_leidos']} | {st['filas_silver']} | {st['filas_invalidas']} | {st['filas_duplicadas_en_grupo']} | {st['horas_precio_parciales']} |\n"
    desc += f'''
**Filas Gold:** {gold_rows}. **Reproducibilidad:** desde la raíz del proyecto, `python scripts/preparar_entrega02.py --desde {start.date()} --hasta {(end - pd.Timedelta(days=1)).date()}`. La muestra para el repositorio está en `data/sample/muestra_gridmind_gold.csv` (máximo 100 filas). `data/processed/informe_entrega02.json` documenta los recuentos. Los CSV de millones de filas no deben subirse a Git.

## 5. Riesgos y limitaciones

Hay meses ausentes o incompletos y cambios históricos de granularidad que pueden sesgar el análisis. Una hora faltante puede impedir calcular correctamente retardos de precio; por eso se descarta del Gold en lugar de imputarse sin criterio. La disponibilidad de previsiones de demanda y solar **a la hora real de predicción** todavía debe verificarse antes de introducirlas en ML. Si e·sios deja de estar disponible, se conservará el histórico local y se evaluarán series equivalentes de otras fuentes oficiales con trazabilidad de procedencia y unidad. La muestra Gold demuestra el proceso, pero no garantiza por sí sola la cobertura completa de diez años.
'''
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(desc, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Prepara Silver, Gold, informe y entrega 02')
    parser.add_argument('--desde', default='2026-08-01', help='Primera fecha local YYYY-MM-DD')
    parser.add_argument('--hasta', default='2026-09-30', help='Última fecha local inclusiva YYYY-MM-DD')
    args = parser.parse_args()
    start = pd.Timestamp(args.desde)
    end = pd.Timestamp(args.hasta) + pd.Timedelta(days=1)
    if not start < end:
        parser.error('--desde debe ser anterior o igual a --hasta')
    for p in (SILVER, GOLD, SAMPLE):
        p.mkdir(parents=True, exist_ok=True)
    stats = {}
    frames = {}
    for indicator_id, (name, geo) in INDICATORS.items():
        print(f'Preparando Silver: {indicator_id} ({name})', flush=True)
        df, report = load_indicator(indicator_id, geo, start, end)
        hourly_df, incomplete = hourly(df, name, is_price=(indicator_id == 600))
        hourly_df.index.name = 'fecha_utc'
        hourly_df.dropna().to_csv(SILVER / f'{name}_horario.csv', encoding='utf-8')
        report['horas_precio_parciales'] = incomplete
        report['horas_con_datos'] = int(hourly_df[name].notna().sum())
        stats[str(indicator_id)] = report
        frames[indicator_id] = hourly_df
        print(f"  Filas origen/zona: {report['filas_silver']}; horas válidas: {report['horas_con_datos']}")
    price = frames[600]['precio_spot_espana'].rename('precio_spot')
    # Resample crea el índice horario completo; shift(48/168) es desplazamiento REAL de horas.
    complete_idx = pd.date_range(price.index.min(), price.index.max(), freq='1h', tz='UTC')
    price = price.reindex(complete_idx)
    gold = pd.DataFrame({'precio_spot': price, 'precio_lag_48h': price.shift(48),
                         'precio_lag_168h': price.shift(168)})
    local = gold.index.tz_convert('Europe/Madrid')
    gold['hora_local'] = local.hour
    gold['dia_semana'] = local.dayofweek
    gold['mes'] = local.month
    gold['es_fin_semana'] = (local.dayofweek >= 5).astype(int)
    gold = gold.dropna(subset=['precio_spot', 'precio_lag_48h', 'precio_lag_168h'])
    gold.index.name = 'fecha_utc'
    gold.to_csv(GOLD / 'dataset_gridmind_gold.csv', encoding='utf-8')
    gold.head(100).to_csv(SAMPLE / 'muestra_gridmind_gold.csv', encoding='utf-8')
    report = {'desde_local_inclusive': str(start.date()), 'hasta_local_inclusive': str((end - pd.Timedelta(days=1)).date()),
              'indicadores': stats, 'filas_gold': len(gold), 'aviso': 'Confirmar unidad de indicador 600 y disponibilidad de datos antes de entrenar.'}
    (OUT / 'informe_entrega02.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    make_doc(stats, start, end, len(gold))
    print(f'\nGold: {len(gold)} filas | Muestra: {min(len(gold),100)} filas')
    print(f'Informe: {OUT / "informe_entrega02.json"}')
    print(f'Documentación: {DOC}')
    if gold.empty:
        print('AVISO: Gold vacío. Amplía --desde/--hasta y verifica los datos del indicador 600.')


if __name__ == '__main__':
    main()
