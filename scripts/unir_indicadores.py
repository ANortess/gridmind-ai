from pathlib import Path
import csv

PROYECTO = Path(__file__).resolve().parent.parent
ORIGEN = PROYECTO / 'data' / 'raw' / 'CSVs_historico_mensual'
DESTINO = PROYECTO / 'data' / 'unified'
IDS = [600, 544, 1293, 542, 14, 12, 9, 4, 1, 25, 10037, 10043]


def main():
    if not ORIGEN.is_dir():
        raise SystemExit(f'No existe la carpeta de CSV mensuales: {ORIGEN}')
    DESTINO.mkdir(parents=True, exist_ok=True)
    for indicador in IDS:
        archivos = sorted((ORIGEN / f'indicador_{indicador}').glob('*.csv'))
        if not archivos:
            print(f'Indicador {indicador}: sin archivos')
            continue
        salida = DESTINO / f'indicador_{indicador}_10_anios.csv'
        temporal = salida.with_suffix('.tmp')
        filas, vacios, incompatibles, encabezado_base = 0, 0, 0, None
        try:
            with temporal.open('w', newline='', encoding='utf-8-sig') as destino:
                escritor = csv.writer(destino)
                for archivo in archivos:
                    with archivo.open('r', newline='', encoding='utf-8-sig') as origen:
                        lector = csv.reader(origen)
                        encabezado = next(lector, None)
                        if not encabezado:
                            vacios += 1
                            continue
                        if encabezado_base is None:
                            encabezado_base = encabezado
                            escritor.writerow(encabezado_base)
                        elif encabezado != encabezado_base:
                            incompatibles += 1
                            print(f'AVISO: columnas diferentes en {archivo}')
                            continue
                        for fila in lector:
                            if not fila:
                                continue
                            if len(fila) != len(encabezado_base):
                                raise ValueError(f'Fila con columnas incorrectas en {archivo}')
                            escritor.writerow(fila)
                            filas += 1
            if encabezado_base is None or incompatibles:
                temporal.unlink(missing_ok=True)
                print(f'Indicador {indicador}: no se reemplaza el destino; revisa archivos vacíos/incompatibles')
                continue
            temporal.replace(salida)
        finally:
            temporal.unlink(missing_ok=True)
        print(f'Indicador {indicador}: {filas:,} filas | {len(archivos)} archivos | {vacios} vacíos -> {salida.name}')
    print(f'\nUnificación terminada: {DESTINO}')
    print('NOTA: se unen los CSV disponibles; no se rellenan meses ausentes ni se eliminan duplicados.')


if __name__ == '__main__':
    main()
