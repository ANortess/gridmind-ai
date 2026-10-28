#!/usr/bin/env python3
"""Actualiza e·sios: meses normales y semanas directas para 10043.

Uso desde TFM/:
    python scripts/actualizar_datos.py
    python scripts/actualizar_datos.py --seco
    python scripts/actualizar_datos.py --refrescar-meses 3

Requiere ESIOS_TOKEN en el entorno. No almacena JSON.
"""
import argparse
import csv
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Reutiliza el cliente y la escritura atómica del descargador existente.
from descargar_esios import (
    CSV_MENSUALES, PROCESSED, IDS_PREDETERMINADOS, VAL_FIELDS,
    get_json, guardar_csv, filas_valores, siguiente_mes,
)

PROYECTO = Path(__file__).resolve().parent.parent
SCRIPTS = PROYECTO / 'scripts'
LOG_CSV = PROCESSED / 'actualizaciones.csv'
# Fragmentos junto al indicador, separados de los CSV mensuales.
PARTES_ANTIGUAS = PROYECTO / 'data' / 'raw' / 'partes_actualizacion'


def retroceder_meses(d, cantidad):
    total = d.year * 12 + d.month - 1 - cantidad
    return date(total // 12, total % 12 + 1, 1)


def mes_iterador(inicio, fin):
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fin:
        yield cursor
        cursor = siguiente_mes(cursor)


def csv_valido(ruta):
    """Comprobación mínima: cabecera correcta y al menos un registro.
    Un CSV vacío se considera pendiente y se vuelve a intentar.
    """
    if not ruta.exists() or ruta.stat().st_size == 0:
        return False
    try:
        with ruta.open('r', newline='', encoding='utf-8-sig') as entrada:
            lector = csv.DictReader(entrada)
            if lector.fieldnames != VAL_FIELDS:
                return False
            return next(lector, None) is not None
    except (OSError, csv.Error, UnicodeError):
        return False


def registrar(log, indicador, mes, accion, estado, filas='', error=''):
    log.append({
        'ejecutado_utc': datetime.now(timezone.utc).isoformat(),
        'indicador_id': indicador,
        'mes': mes,
        'accion': accion,
        'estado': estado,
        'filas': filas,
        'error': error,
    })


def pedir_intervalo(ind, desde, hasta, token, pausa, usar_cache):
    """Descarga un fragmento; usa caché solamente para meses históricos ausentes."""
    parte = CSV_MENSUALES / f'indicador_{ind}' / '_partes' / f'{desde}__{hasta}.csv'
    if usar_cache and csv_valido(parte):
        return parte
    # Reaprovechar fragmentos de versiones anteriores, evitando descargarlos otra vez.
    antigua = PARTES_ANTIGUAS / f'indicador_{ind}' / parte.name
    if usar_cache and csv_valido(antigua):
        parte.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(antigua), str(parte))
        return parte
    parametros = {
        'start_date': f'{desde.isoformat()}T00:00:00',
        'end_date': f'{hasta.isoformat()}T23:59:59',
    }
    # Dos intentos antes de dividir. get_json ya espera y reintenta errores transitorios.
    respuesta = get_json(f'/indicators/{ind}', token, parametros, retries=2)
    valores = respuesta.get('indicator', {}).get('values')
    if not isinstance(valores, list) or not valores:
        raise ValueError(f'Sin registros para {desde} a {hasta}; no se sobrescribe el CSV')
    filas = list(filas_valores(ind, respuesta))
    guardar_csv(parte, VAL_FIELDS, filas)
    time.sleep(pausa)
    return parte


def obtener_fragmentos(ind, desde, hasta, token, pausa, usar_cache, nivel='mes'):
    """Mes -> semanas -> días; aborta si falla un solo día."""
    try:
        ruta = pedir_intervalo(ind, desde, hasta, token, pausa, usar_cache)
        print(f'    {desde} a {hasta}: OK ({ruta.stat().st_size:,} bytes)', flush=True)
        return [ruta]
    except Exception as exc:
        if desde == hasta:
            raise RuntimeError(f'Falló el día {desde}: {exc}') from exc
        print(f'    {desde} a {hasta}: {exc}; dividiendo en bloques más pequeños', flush=True)
        rutas = []
        cursor = desde
        # Tanto si falló el mes como una semana, pasar a trozos de 7 o 1 día.
        salto = 7 if nivel == 'mes' else 1
        while cursor <= hasta:
            fin = min(cursor + timedelta(days=salto - 1), hasta)
            rutas.extend(obtener_fragmentos(
                ind, cursor, fin, token, pausa, usar_cache,
                nivel='semana' if salto == 7 else 'dia'))
            cursor = fin + timedelta(days=1)
        return rutas


def descargar_mes(ind, desde, hasta, ruta, token, pausa, usar_cache):
    """Solo sustituye un CSV mensual si todas las partes se descargaron."""
    if ind == 10043:
        # Para este indicador conocemos los 504 mensuales: ir directamente
        # a semanas. Si falla una semana, obtener_fragmentos la divide en días.
        fragmentos = []
        cursor = desde
        while cursor <= hasta:
            fin = min(cursor + timedelta(days=6), hasta)
            print(f'    Probando semana {cursor} a {fin}...', flush=True)
            fragmentos.extend(obtener_fragmentos(
                ind, cursor, fin, token, pausa, usar_cache, nivel='semana'
            ))
            cursor = fin + timedelta(days=1)
    else:
        fragmentos = obtener_fragmentos(ind, desde, hasta, token, pausa, usar_cache)
    vistos, filas = set(), []
    for fragmento in fragmentos:
        with fragmento.open(newline='', encoding='utf-8-sig') as entrada:
            for fila in csv.DictReader(entrada):
                clave = (fila['indicator_id'], fila['datetime_utc'], fila['geo_id'])
                if clave in vistos:
                    continue
                vistos.add(clave)
                filas.append(fila)
    if not filas:
        raise ValueError('No se encontraron registros')
    filas.sort(key=lambda f: (f['datetime_utc'], f['geo_id']))
    guardar_csv(ruta, VAL_FIELDS, filas)  # Escritura atómica.
    return len(filas)


def main():
    p = argparse.ArgumentParser(description='Actualizador e·sios: mes, semana y día automáticamente.')
    p.add_argument('--ids', nargs='+', type=int, default=IDS_PREDETERMINADOS)
    p.add_argument('--desde', default='2016-10-22')
    p.add_argument('--hasta', default=date.today().isoformat())
    p.add_argument('--refrescar-meses', type=int, default=2)
    p.add_argument('--pausa', type=float, default=1.0)
    p.add_argument('--seco', action='store_true')
    p.add_argument('--sin-unificar', action='store_true')
    args = p.parse_args()

    inicio, fin = date.fromisoformat(args.desde), date.fromisoformat(args.hasta)
    if inicio > fin or args.refrescar_meses < 0 or args.pausa < 0:
        p.error('Comprueba fechas y parámetros.')
    token = os.getenv('ESIOS_TOKEN', '').strip()
    if not args.seco and not token:
        sys.exit('Falta ESIOS_TOKEN.')

    limite_reciente = retroceder_meses(fin, args.refrescar_meses - 1) if args.refrescar_meses else None
    log, cambios, errores, pendientes = [], 0, 0, 0
    for ind in args.ids:
        print(f'\nIndicador {ind}', flush=True)
        for mes in mes_iterador(inicio, fin):
            etiqueta = mes.strftime('%Y-%m')
            ruta = CSV_MENSUALES / f'indicador_{ind}' / f'{etiqueta}.csv'
            existe = csv_valido(ruta)
            refrescar = limite_reciente is not None and mes >= limite_reciente
            if existe and not refrescar:
                continue
            accion = 'refrescar' if existe else 'descargar_faltante'
            pendientes += 1
            print(f'  {etiqueta}: {accion}', flush=True)
            if args.seco:
                continue
            desde_mes = max(inicio, mes)
            hasta_mes = min(fin, siguiente_mes(mes) - timedelta(days=1))
            try:
                # Refrescos: jamás reutilizar caché, porque puede estar obsoleta.
                filas = descargar_mes(ind, desde_mes, hasta_mes, ruta, token, args.pausa,
                                      usar_cache=not refrescar)
                cambios += 1
                registrar(log, ind, etiqueta, accion, 'actualizado', filas)
                print(f'    MES COMPLETADO -> {filas} filas', flush=True)
            except Exception as exc:
                errores += 1
                registrar(log, ind, etiqueta, accion, 'error', error=str(exc))
                print(f'    ERROR; se conserva el CSV anterior: {exc}', flush=True)

    if not args.seco:
        PROCESSED.mkdir(parents=True, exist_ok=True)
        columnas = ['ejecutado_utc', 'indicador_id', 'mes', 'accion', 'estado', 'filas', 'error']
        with LOG_CSV.open('a', newline='', encoding='utf-8-sig' if not LOG_CSV.exists() else 'utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            if f.tell() == 0:
                writer.writeheader()
            writer.writerows(log)
        if cambios and not args.sin_unificar:
            print('\nReconstruyendo los CSV por indicador...')
            import unir_indicadores
            unir_indicadores.main()
    print(f'\nTerminado: {pendientes} meses pendientes, {cambios} actualizados, {errores} errores.')
    print('Nota: se comprueba la existencia y el formato, no la continuidad interna de los CSV.')


if __name__ == '__main__':
    main()
