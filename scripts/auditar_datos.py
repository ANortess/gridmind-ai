from pathlib import Path
import pandas as pd

PROYECTO = Path(__file__).resolve().parent.parent
BASE = PROYECTO / 'data' / 'raw' / 'CSVs_historico_mensual'
SALIDA = PROYECTO / 'data' / 'processed' / 'gridmind_auditoria.csv'
IDS = [600, 544, 1293, 542, 14, 12, 9, 4, 1, 25, 10037, 10043]


def main():
    if not BASE.is_dir():
        raise SystemExit(f'No existe la carpeta de CSV mensuales: {BASE}')
    resultados = []
    for indicador in IDS:
        archivos = sorted((BASE / f'indicador_{indicador}').glob('*.csv'))
        total_filas = nulos = errores = vacios = 0
        fechas_min, fechas_max = [], []
        for archivo in archivos:
            try:
                df = pd.read_csv(archivo, encoding='utf-8-sig')
                if not {'datetime_utc', 'value'}.issubset(df.columns):
                    raise ValueError('Faltan columnas datetime_utc o value')
                total_filas += len(df)
                nulos += int(df['value'].isna().sum())
                if df.empty:
                    vacios += 1
                fechas = pd.to_datetime(df['datetime_utc'], utc=True, errors='coerce')
                if fechas.notna().any():
                    fechas_min.append(fechas.min())
                    fechas_max.append(fechas.max())
            except Exception as exc:
                errores += 1
                print(f'ERROR en {archivo}: {exc}')
        resultados.append({
            'indicador': indicador,
            'archivos_csv': len(archivos),
            'archivos_vacios': vacios,
            'filas': total_filas,
            'valores_nulos': nulos,
            'archivos_con_error': errores,
            'fecha_inicio': min(fechas_min) if fechas_min else None,
            'fecha_fin': max(fechas_max) if fechas_max else None,
        })
    resumen = pd.DataFrame(resultados)
    print('\n=== AUDITORÍA DE GRIDMIND AI ===')
    print(resumen.to_string(index=False))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    resumen.to_csv(SALIDA, index=False, encoding='utf-8-sig')
    print(f'\nInforme guardado: {SALIDA}')
    print('AVISO: este informe no comprueba continuidad temporal ni meses ausentes.')


if __name__ == '__main__':
    main()
