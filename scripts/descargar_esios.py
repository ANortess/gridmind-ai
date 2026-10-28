#!/usr/bin/env python3
"""Descarga e·sios por meses, reanudable con CSV existentes; JSON opcional."""
import argparse
import csv
import json
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROYECTO = Path(__file__).resolve().parent.parent
CSV_MENSUALES = PROYECTO / 'data' / 'raw' / 'CSVs_historico_mensual'
JSON_ORIGINALES = PROYECTO / 'data' / 'raw' / 'JSONs_originales'
PROCESSED = PROYECTO / 'data' / 'processed'
API_BASE = 'https://api.esios.ree.es'
IDS_PREDETERMINADOS = [600, 544, 1293, 542, 14, 12, 9, 4, 1, 25, 10037, 10043]
CAT_FIELDS = ['indicator_id', 'name', 'short_name', 'description']
DET_FIELDS = ['indicator_id', 'name', 'short_name', 'composited', 'step_type', 'disaggregated', 'magnitudes', 'tiempos', 'geos', 'values_updated_at']
VAL_FIELDS = ['indicator_id', 'datetime', 'datetime_utc', 'value', 'geo_id', 'geo_name']


def get_json(path, token, params=None, retries=4):
    url = API_BASE + path + ('?' + urlencode(params) if params else '')
    headers = {
        'Accept': 'application/json; application/vnd.esios-api-v1+json',
        'Content-Type': 'application/json',
        'x-api-key': token,
        'User-Agent': 'GridMind-TFM/1.0',
    }
    for intento in range(retries):
        try:
            with urlopen(Request(url, headers=headers), timeout=90) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(f'Autenticación denegada: HTTP {exc.code}') from None
            if exc.code not in (429, 500, 502, 503, 504) or intento == retries - 1:
                raise RuntimeError(f'HTTP {exc.code} consultando {path}') from None
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if intento == retries - 1:
                raise RuntimeError(f'Error consultando {path}: {exc}') from None
        time.sleep(min(45, 3 * (2 ** intento)) + random.random())


def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix('.tmp')
    with temporal.open('w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False)
    temporal.replace(ruta)


def cargar_json(ruta):
    with ruta.open(encoding='utf-8') as f:
        return json.load(f)


def guardar_csv(ruta, columnas, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix('.tmp')
    with temporal.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columnas, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(filas)
    temporal.replace(ruta)


def csv_cell(obj):
    return json.dumps(obj, ensure_ascii=False) if isinstance(obj, (list, dict)) else obj


def siguiente_mes(d):
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def meses_entre(inicio, fin):
    d = inicio.replace(day=1)
    while d <= fin:
        yield d
        d = siguiente_mes(d)


def hace_anios(d, anios):
    try:
        return d.replace(year=d.year - anios)
    except ValueError:
        return d.replace(year=d.year - anios, day=28)


def filas_valores(indicador_id, payload):
    for valor in payload.get('indicator', {}).get('values', []):
        yield {
            'indicator_id': indicador_id,
            'datetime': valor.get('datetime'),
            'datetime_utc': valor.get('datetime_utc'),
            'value': valor.get('value'),
            'geo_id': valor.get('geo_id'),
            'geo_name': valor.get('geo_name'),
        }


def fila_detalle(indicador_id, payload):
    obj = payload.get('indicator', {})
    return {
        'indicator_id': indicador_id,
        'name': obj.get('name'),
        'short_name': obj.get('short_name'),
        'composited': obj.get('composited'),
        'step_type': obj.get('step_type'),
        'disaggregated': obj.get('disaggregated'),
        'magnitudes': csv_cell(obj.get('magnitud', [])),
        'tiempos': csv_cell(obj.get('tiempo', [])),
        'geos': csv_cell(obj.get('geos', [])),
        'values_updated_at': obj.get('values_updated_at'),
    }


def main():
    parser = argparse.ArgumentParser(description='Descarga mensual reanudable de datos e·sios.')
    parser.add_argument('--ids', nargs='+', type=int, default=IDS_PREDETERMINADOS)
    parser.add_argument('--todos', action='store_true', help='Descargar todos los IDs del catálogo (puede ser enorme).')
    parser.add_argument('--anios', type=int, default=10)
    parser.add_argument('--desde', help='YYYY-MM-DD')
    parser.add_argument('--hasta', help='YYYY-MM-DD')
    parser.add_argument('--pausa', type=float, default=1.0)
    parser.add_argument('--limite', type=int, default=0, help='Máximo de meses por indicador; 0 = todos.')
    parser.add_argument('--guardar-json', action='store_true', help='Guardar las respuestas JSON además de CSV.')
    parser.add_argument('--forzar', action='store_true', help='Volver a solicitar meses que ya tienen CSV; no usar salvo necesidad.')
    args = parser.parse_args()

    if not 1 <= args.anios <= 10:
        parser.error('--anios debe estar entre 1 y 10')
    fin = date.fromisoformat(args.hasta) if args.hasta else date.today()
    inicio = date.fromisoformat(args.desde) if args.desde else hace_anios(fin, args.anios)
    if inicio > fin:
        parser.error('La fecha inicial es posterior a la final')
    token = os.getenv('ESIOS_TOKEN', '').strip()
    if not token:
        sys.exit('Falta ESIOS_TOKEN. Configura la variable de entorno.')

    CSV_MENSUALES.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if args.guardar_json:
        JSON_ORIGINALES.mkdir(parents=True, exist_ok=True)

    catalog_path = JSON_ORIGINALES / 'catalogo.json'
    catalog = cargar_json(catalog_path) if catalog_path.exists() else get_json('/indicators', token)
    if args.guardar_json and not catalog_path.exists():
        guardar_json(catalog_path, catalog)
    indicadores = catalog.get('indicators', [])
    guardar_csv(PROCESSED / '01_catalogo_indicadores.csv', CAT_FIELDS, (
        {'indicator_id': x.get('id'), 'name': x.get('name'),
         'short_name': x.get('short_name'), 'description': x.get('description')}
        for x in indicadores
    ))
    ids = sorted({int(x['id']) for x in indicadores if x.get('id') is not None}) if args.todos else sorted(set(args.ids))
    if args.todos:
        print(f'ATENCIÓN: se descargarán {len(ids)} indicadores.')

    detalles = []
    errores = []
    for numero, indicador_id in enumerate(ids, 1):
        print(f'[{numero}/{len(ids)}] Indicador {indicador_id}')
        detail_path = JSON_ORIGINALES / f'indicador_{indicador_id}_detalle.json'
        try:
            if detail_path.exists():
                detail = cargar_json(detail_path)
            else:
                detail = get_json(f'/indicators/{indicador_id}', token,
                                  {'start_date': '2000-01-01T00:00:00', 'end_date': '2000-01-01T00:00:00'})
                detail.get('indicator', {}).pop('values', None)
                if args.guardar_json:
                    guardar_json(detail_path, detail)
            detalles.append(fila_detalle(indicador_id, detail))
        except Exception as exc:
            print(f'  Detalle fallido: {exc}')
            errores.append({'indicator_id': indicador_id, 'mes': 'detalle', 'error': str(exc)})

        procesados = 0
        for mes in meses_entre(inicio, fin):
            if args.limite and procesados >= args.limite:
                break
            procesados += 1
            etiqueta = mes.strftime('%Y-%m')
            csv_path = CSV_MENSUALES / f'indicador_{indicador_id}' / f'{etiqueta}.csv'
            json_path = JSON_ORIGINALES / f'indicador_{indicador_id}' / f'{etiqueta}.json'
            # A diferencia del script anterior, basta con que exista el CSV válido.
            if csv_path.exists() and csv_path.stat().st_size > 0 and not args.forzar:
                print(f'  {etiqueta}: CSV existente, se omite')
                continue
            ultimo = min(fin, siguiente_mes(mes) - timedelta(days=1))
            primero = max(inicio, mes)
            params = {
                'start_date': f'{primero.isoformat()}T00:00:00',
                'end_date': f'{ultimo.isoformat()}T23:59:59',
            }
            try:
                payload = cargar_json(json_path) if json_path.exists() and not args.forzar else get_json(
                    f'/indicators/{indicador_id}', token, params)
                valores = payload.get('indicator', {}).get('values')
                if not isinstance(valores, list):
                    raise ValueError('Respuesta sin indicator.values')
                if args.guardar_json:
                    guardar_json(json_path, payload)
                guardar_csv(csv_path, VAL_FIELDS, filas_valores(indicador_id, payload))
                print(f'  {etiqueta}: {len(valores)} filas')
            except Exception as exc:
                print(f'  {etiqueta}: ERROR {exc}')
                errores.append({'indicator_id': indicador_id, 'mes': etiqueta, 'error': str(exc)})
            time.sleep(args.pausa)

    if detalles:
        guardar_csv(PROCESSED / '02_detalle_indicadores.csv', DET_FIELDS, detalles)
    # Se guardan los fallos de esta ejecución, no el histórico de ejecuciones anteriores.
    guardar_csv(PROCESSED / 'errores_ultima_ejecucion.csv', ['indicator_id', 'mes', 'error'], errores)
    print(f'Finalizado. Errores en esta ejecución: {len(errores)}')
    print('Revisa también errores.csv y la auditoría histórica: no se corrigen huecos automáticamente.')


if __name__ == '__main__':
    main()
