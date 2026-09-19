# -*- coding: utf-8 -*-
"""Extrae el modelo financiero de Hacienda Chada a modelo_data.json.

Lee cuatro hojas del libro y las consolida en una sola estructura por variedad:

  Consolidado por variedad : superficie, produccion, ingresos, costos, EBITDA y
                             EBITDA/ha, cada uno por temporada.
  Inputs Generales         : supuestos macro, conciliacion de superficies y la
                             tabla maestra de supuestos por variedad.
  Detalle Plantaciones     : inventario de la tasacion (portainjerto, ano,
                             marco, plantas/ha) por bloque de plantacion.
  Base Chada               : produccion y rendimiento historicos 23/24 y 24/25.

La superficie de referencia es SIEMPRE la del modelo (292,23 ha productivas).
La del KMZ no se usa para nada: el KMZ aporta geometria e identidad de cuartel,
nada mas.

El libro trae 8.338 nombres definidos y al menos uno apunta a #N/A, lo que hace
que openpyxl se niegue a abrirlo. Se reescribe una copia sin el bloque
<definedNames> antes de leer; el resto del archivo queda intacto.
"""
import datetime
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent.parent
LIBRO = RAIZ / "datos_fuente" / "Financial_Model_Hacienda_Chada_v1.xlsx"

# ── Consolidado por variedad: fila inicial de cada bloque ──────────────────
# Los seis bloques corren en paralelo, una fila por variedad y en el mismo
# orden. Aun asi cada fila se indexa por (especie, variedad) y no por posicion:
# si el libro cambia de orden, el cruce avisa en vez de mentir.
BLOQUES = {
    "superficie": 2,
    "produccion": 38,
    "ingresos": 74,
    "costos": 110,
    "ebitda": 146,
    "ebitda_ha": 184,
}
N_VARIEDADES = 33
COL_TEMPORADA_0 = 4          # columna D
N_TEMPORADAS = 21            # D..X
FILA_TEMPORADAS = 37


def sin_tildes(s):
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def norm(s):
    """Clave de comparacion: sin tildes, sin puntuacion de cola, minusculas."""
    return re.sub(r"[\s.]+$", "", sin_tildes(s).strip().lower())


def abrir_libro(ruta):
    limpio = ruta.parent / ("_%s_sin_nombres.xlsx" % ruta.stem)
    with zipfile.ZipFile(ruta) as zin, zipfile.ZipFile(limpio, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/workbook.xml":
                txt = re.sub(r"<definedNames>.*?</definedNames>", "",
                             data.decode("utf-8"), flags=re.S)
                data = txt.encode("utf-8")
            zout.writestr(item, data)
    return openpyxl.load_workbook(limpio, data_only=True)


def num(v, nd=None):
    if v is None or isinstance(v, str):
        return None
    v = float(v)
    return round(v, nd) if nd is not None else v


def serie(fila, nd=1):
    """Los 21 valores de temporada de una fila (columnas D..X)."""
    return [num(fila[COL_TEMPORADA_0 - 1 + i], nd) for i in range(N_TEMPORADAS)]


# ═══════════════════════════════════════════════════════════════════════════
# Cruce KMZ → modelo
# ═══════════════════════════════════════════════════════════════════════════
# El KMZ nombra por variedad comercial; el modelo separa ademas por manejo
# (macrotunel) y por injerto. Casi todo calza por nombre; lo que no, va aca con
# su razon. Una entrada de mas es un dato inventado, asi que la lista es corta
# y cada linea se justifica.
ALIAS = {
    # El macrotunel es una variedad aparte en el modelo (mayor precio y mayor
    # CapEx). En el KMZ es Santina con el manejo anotado entre parentesis, asi
    # que la nota del cuartel decide, no el nombre.
    ("cerezos", "santina", "macrotunel"): ("Cerezas", "Santina Macro Túnel"),
    # 8205 va rotulado "Cheery Moon" en el KMZ. El modelo no tiene esa variedad:
    # tiene "Cheery Treat Injerto.", que en la tasacion figura plantada en 2023
    # sobre portainjerto "Maxma 14 - Ch Moon". Se cruzan como el mismo bloque.
    # Es el unico cruce que no es exacto y queda marcado como aproximado.
    ("cerezos", "cheery moon", None): ("Cerezas", "Cheery Treat Injerto."),
}
CRUCE_APROXIMADO = {("cerezos", "cheery moon", None)}

# El KMZ agrupa como "Disponible" lo arrancado y lo no productivo. El modelo no
# lo incluye a proposito: es justamente el puente de 311,65 ha a 292,23 ha.
ESPECIE_SIN_MODELO = "Disponible"

ESPECIE_KMZ_A_MODELO = {
    "cerezos": "Cerezas",
    "ciruelos": "Ciruelos",
    "clementinas": "Clementinas",
    "naranjos": "Naranjos",
    "paltos": "Paltos",
    "uva de mesa": "Uva de Mesa",
    "uva vinifera": "Uva Vinifera",
}


def clave_modelo(especie, variedad):
    return "%s|%s" % (especie, variedad)


def cruzar(prop, indice_modelo):
    """Devuelve {clave del modelo: es_aproximado} para un cuartel del KMZ.

    La marca de aproximado es de la variedad que se alcanzo por alias dudoso,
    no de las que comparten poligono con ella: en un cuartel mixto, que una
    variedad calce a medias no ensucia a sus vecinas.
    """
    especie_kmz = norm(prop["especie"])
    if prop["especie"] == ESPECIE_SIN_MODELO:
        return {}

    nota = norm(prop.get("nota") or "") or None
    claves = {}
    for variedad in prop["variedades"]:
        v = norm(variedad)
        llave_alias = next((k for k in ((especie_kmz, v, nota), (especie_kmz, v, None))
                            if k in ALIAS), None)
        if llave_alias:
            destino = ALIAS[llave_alias]
            aprox = llave_alias in CRUCE_APROXIMADO
        else:
            especie_modelo = ESPECIE_KMZ_A_MODELO.get(especie_kmz)
            if not especie_modelo:
                continue
            destino, aprox = (especie_modelo, variedad), False

        clave = next((k for k in indice_modelo
                      if norm(k) == norm(clave_modelo(*destino))), None)
        if clave:
            claves[clave] = claves.get(clave, False) or aprox
    return claves


# ═══════════════════════════════════════════════════════════════════════════
def leer_consolidado(ws):
    filas = list(ws.iter_rows(min_row=1, max_row=231, max_col=24, values_only=True))
    temporadas = [filas[FILA_TEMPORADAS - 1][COL_TEMPORADA_0 - 1 + i] for i in range(N_TEMPORADAS)]

    datos = {}
    for i in range(N_VARIEDADES):
        base = filas[BLOQUES["superficie"] - 1 + i]
        especie, variedad, ha = base[0], base[1], base[2]
        if not especie or not variedad:
            raise SystemExit("Fila de superficie %d sin especie/variedad" % (BLOQUES["superficie"] + i))
        clave = clave_modelo(especie, variedad)
        registro = {"especie": especie, "variedad": variedad, "ha": num(ha, 3)}

        for bloque, fila0 in BLOQUES.items():
            if bloque == "superficie":
                continue
            fila = filas[fila0 - 1 + i]
            if norm(fila[0]) != norm(especie) or norm(fila[1]) != norm(variedad):
                raise SystemExit(
                    "El bloque '%s' no esta alineado en la fila %d: se esperaba %s / %s y vino %s / %s"
                    % (bloque, fila0 + i, especie, variedad, fila[0], fila[1]))
            # Los costos vienen negativos en el libro; se guardan en positivo y
            # el signo queda en el nombre del campo, no en el dato.
            nd = 0 if bloque in ("produccion", "ingresos", "costos", "ebitda") else 1
            valores = serie(fila, nd)
            if bloque == "costos":
                valores = [None if v is None else abs(v) for v in valores]
            registro[bloque] = valores

        datos[clave] = registro
    return temporadas, datos


def leer_inputs(ws):
    filas = list(ws.iter_rows(min_row=1, max_row=95, max_col=43, values_only=True))
    col = lambda f, letra: filas[f - 1][openpyxl.utils.column_index_from_string(letra) - 1]

    supuestos = {
        "anio_inicio": num(col(7, "C")),
        "horizonte": num(col(8, "C")),
        "tipo_cambio": num(col(9, "C")),
        "iva": num(col(11, "C"), 4),
        "impuesto_renta": num(col(12, "C"), 4),
        "apreciacion_tierra": num(col(13, "C"), 4),
        "tasa_descuento": num(col(14, "C"), 4),
        "superficie_predio": num(col(20, "C"), 2),
        "superficie_tasacion": num(col(21, "C"), 2),
        "superficie_modelada": num(col(22, "C"), 2),
        "valor_tierra_agua_clp": num(col(24, "C")),
        "valor_tierra_ha_usd": num(col(25, "C"), 0),
        "valor_comercial_clp": num(col(27, "C")),
        "valor_comercial_usd": num(col(28, "C"), 0),
        "valor_liquidacion_usd": num(col(30, "C"), 0),
    }

    # Supuestos por variedad: seccion 4, filas 45 a 77.
    campos = [
        ("anio_plantacion", "E", None), ("unidad", "F", None),
        ("rend_23_24", "G", 0), ("rend_24_25", "H", 0), ("rend_25_26", "I", 0),
        ("rend_26_27", "J", 0), ("rend_27_28", "K", 0), ("rend_28_29", "L", 0),
        ("rend_plena", "M", 0),
        ("precio_export", "N", 2), ("precio_interno_clp", "O", 0), ("pct_export", "P", 3),
        ("costo_fijo_ha", "Q", 0), ("costo_cosecha_kg", "R", 3),
        ("proceso_kg", "S", 3), ("otros_var_kg", "T", 3),
        ("gav_ha", "U", 0), ("capex_pct", "V", 3),
    ]
    por_variedad = {}
    for f in range(45, 78):
        especie, variedad = col(f, "B"), col(f, "C")
        if not especie or not variedad:
            continue
        reg = {}
        for nombre, letra, nd in campos:
            v = col(f, letra)
            reg[nombre] = v if nd is None else num(v, nd)
        por_variedad[clave_modelo(especie, variedad)] = reg
    return supuestos, por_variedad


# El modelo separa por manejo e injerto lo que la tasacion anota como una sola
# variedad. Estas son las variedades del modelo cuyo inventario hay que ir a
# buscar con otro nombre, y cuando el bloque de tasacion cubre a mas de una
# variedad del modelo se dice cual, para que nadie sume dos veces las mismas ha.
ALIAS_TASACION = {
    "santina": (["santina"], "El bloque de tasación cubre Santina y Santina Macro Túnel"),
    "santina macro tunel": (["santina"], "El bloque de tasación cubre Santina y Santina Macro Túnel"),
    "cheery treat injerto": (["cheery treat inj"], None),
    "lapins injerto": (["lapins inj"], None),
    "royal dawn": (["royal dawn", "royal dawn + c15"], None),
}


def leer_plantaciones(ws):
    """Inventario de la tasacion, agrupado por (especie, variedad) normalizada."""
    filas = list(ws.iter_rows(min_row=5, max_row=94, max_col=10, values_only=True))
    por_variedad, total = {}, 0.0
    for row in filas:
        _, especie, variedad, portainjerto, anio, ha, marco, plantas_ha, _, riego = row[:10]
        if not variedad or ha is None:
            continue
        total += float(ha)
        por_variedad.setdefault(norm(variedad), []).append({
            "especie_tasacion": especie,
            "portainjerto": (portainjerto or "").strip() or None,
            "anio": anio,
            "ha": num(ha, 2),
            "marco": marco,
            "plantas_ha": num(plantas_ha, 0),
            "riego": riego,
        })
    return por_variedad, round(total, 2)


def leer_base(ws):
    """Produccion historica por variedad (23/24, 24/25, 25/26) y n de plantas."""
    filas = list(ws.iter_rows(min_row=6, max_row=38, max_col=9, values_only=True))
    out = {}
    for row in filas:
        especie, variedad, desde, hasta, ha, plantas, p23, p24, p25 = row[:9]
        if not especie or not variedad:
            continue
        out[norm(clave_modelo(especie, variedad))] = {
            "anio_desde": desde, "anio_hasta": hasta,
            "ha_ficha": num(ha, 3), "plantas": num(plantas, 0),
            "prod_23_24": num(p23, 0), "prod_24_25": num(p24, 0), "prod_25_26": num(p25, 0),
        }
    return out


def main():
    libro = Path(sys.argv[1]) if len(sys.argv) > 1 else LIBRO
    wb = abrir_libro(libro)

    temporadas, variedades = leer_consolidado(wb["Consolidado por variedad"])
    supuestos, inputs_var = leer_inputs(wb["Inputs Generales"])
    plantaciones, ha_tasacion = leer_plantaciones(wb["Detalle Plantaciones"])
    base = leer_base(wb["Base Chada"])

    faltantes = []
    for clave, reg in variedades.items():
        extra = inputs_var.get(clave)
        if extra is None:
            extra = next((v for k, v in inputs_var.items() if norm(k) == norm(clave)), None)
        if extra is None:
            faltantes.append(clave)
        else:
            reg.update(extra)
        reg["historico"] = base.get(norm(clave))
        v = norm(reg["variedad"])
        nombres, nota_tasacion = ALIAS_TASACION.get(v, ([v], None))
        reg["plantaciones"] = [b for n in nombres for b in plantaciones.get(n, [])]
        reg["plantaciones_nota"] = nota_tasacion
        # Margen sobre ventas: la lectura que no depende de la superficie.
        reg["margen"] = [None if not ing else round(eb / ing, 4)
                         for ing, eb in zip(reg["ingresos"], reg["ebitda"])]
        reg["costo_ha"] = [None if not reg["ha"] else round(c / reg["ha"], 1) for c in reg["costos"]]
        reg["ingreso_ha"] = [None if not reg["ha"] else round(i / reg["ha"], 1) for i in reg["ingresos"]]
        # ── Control de coherencia de la produccion ────────────────────────
        # El bloque PRODUCCION del libro trae corridas las cuatro filas de Uva
        # Vinifera: la fila de Cabernet Franc lleva el valor de Cabernet
        # Sauvignon, la de Sauvignon el de Carmenere, la de Carmenere el de
        # Petit Verdot, y la de Petit Verdot el total de la especie. Ingresos,
        # costos y EBITDA estan bien -cuadran con ha x rendimiento de Inputs
        # Generales-, asi que el error es solo de ese bloque y no contamina la
        # plata. Se detecta despejando la produccion desde los ingresos y el
        # precio efectivo; donde no cuadra, el mapa usa la serie despejada y la
        # ficha lo dice. No se corrige el libro en silencio.
        precio = (reg["precio_export"] or 0) * (reg["pct_export"] if reg["pct_export"] is not None else 1)             + (reg["precio_interno_clp"] or 0) / supuestos["tipo_cambio"]             * (1 - (reg["pct_export"] if reg["pct_export"] is not None else 1))
        reg["precio_efectivo"] = round(precio, 4) if precio else None
        implicita = [None if not precio else round(i / precio) for i in reg["ingresos"]]
        ref = next((k for k in range(N_TEMPORADAS) if implicita[k]), None)
        reg["produccion_coherente"] = (
            ref is None or abs(reg["produccion"][ref] - implicita[ref]) <= 0.02 * implicita[ref])
        if not reg["produccion_coherente"]:
            reg["produccion_libro"] = reg["produccion"]
            reg["produccion"] = implicita

        reg["rend_ha"] = [None if not reg["ha"] else round(p / reg["ha"], 1) for p in reg["produccion"]]
        # La uva de mesa se modela en cajas de 8,2 kg, no en kilos: sin convertir,
        # un mapa de rendimiento pondria 3.000 "unidades/ha" de parra al lado de
        # 30.000 de ciruelo y se leeria al reves de lo que pasa en el campo.
        m = re.search(r"([\d,.]+)\s*kg", str(reg.get("unidad") or ""), re.I)
        factor = float(m.group(1).replace(",", ".")) if m else 1.0
        reg["kg_por_unidad"] = factor
        reg["rend_kg_ha"] = [None if v is None else round(v * factor) for v in reg["rend_ha"]]

    # ── Cruce con los cuarteles del KMZ ───────────────────────────────────
    geo = json.loads((RAIZ / "geo_data.json").read_text(encoding="utf-8"))
    cuarteles_por_clave = {}
    aprox_por_clave = {}
    sin_modelo = []
    for f in geo["cuarteles"]["features"]:
        p = f["properties"]
        claves = cruzar(p, variedades)
        p["modelo"] = list(claves)
        p["aprox"] = any(claves.values())
        if not claves and p["especie"] != ESPECIE_SIN_MODELO:
            sin_modelo.append(p["nombre"])
        for k, aprox in claves.items():
            cuarteles_por_clave.setdefault(k, []).append(p["cuartel"])
            if aprox:
                aprox_por_clave[k] = True

    for clave, reg in variedades.items():
        reg["cuarteles"] = cuarteles_por_clave.get(clave, [])
        reg["cruce_aproximado"] = bool(aprox_por_clave.get(clave))

    (RAIZ / "geo_data.json").write_text(
        json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ── Agregados ─────────────────────────────────────────────────────────
    idx = lambda n: [sum(v[i] or 0 for v in (r[n] for r in variedades.values()))
                     for i in range(N_TEMPORADAS)]
    ha_total = round(sum(r["ha"] for r in variedades.values()), 2)
    totales = {
        "ha": ha_total,
        "produccion": [round(x) for x in idx("produccion")],
        "ingresos": [round(x) for x in idx("ingresos")],
        "costos": [round(x) for x in idx("costos")],
        "ebitda": [round(x) for x in idx("ebitda")],
    }
    totales["ebitda_ha"] = [round(e / ha_total, 1) for e in totales["ebitda"]]
    totales["margen"] = [None if not i else round(e / i, 4)
                         for i, e in zip(totales["ingresos"], totales["ebitda"])]

    por_especie = {}
    for reg in variedades.values():
        e = por_especie.setdefault(reg["especie"], {
            "especie": reg["especie"], "variedades": 0, "ha": 0.0,
            "produccion": [0.0] * N_TEMPORADAS, "ingresos": [0.0] * N_TEMPORADAS,
            "costos": [0.0] * N_TEMPORADAS, "ebitda": [0.0] * N_TEMPORADAS,
        })
        e["variedades"] += 1
        e["ha"] = round(e["ha"] + reg["ha"], 3)
        for campo in ("produccion", "ingresos", "costos", "ebitda"):
            for i in range(N_TEMPORADAS):
                e[campo][i] += reg[campo][i] or 0
    for e in por_especie.values():
        for campo in ("produccion", "ingresos", "costos", "ebitda"):
            e[campo] = [round(x) for x in e[campo]]
        e["ebitda_ha"] = [round(x / e["ha"], 1) for x in e["ebitda"]]
        e["margen"] = [None if not i else round(x / i, 4) for i, x in zip(e["ingresos"], e["ebitda"])]

    # ── Conciliacion de superficies ───────────────────────────────────────
    # El puente de la tasacion al modelo. Los tres numeros que Rolando usa para
    # explicar el predio, con el delta explicito entre cada par.
    ha_clemenules = sum(p["ha"] for lst in plantaciones.values() for p in lst
                        if norm(p.get("especie_tasacion") or "") == "clementinos"
                        and p["ha"] == 10.18)
    conciliacion = [
        {"concepto": "Superficie plantada según tasación", "ha": supuestos["superficie_tasacion"],
         "nota": "Tasación Comercial N° 599-2026-SIMM, tablas pág. 15-17"},
        {"concepto": "Menos Clemenules (no productivo)", "ha": round(-ha_clemenules, 2),
         "nota": "10,18 ha plantadas en 1999, fuera de producción"},
        {"concepto": "Superficie plantada", "ha": round(supuestos["superficie_tasacion"] - ha_clemenules, 2),
         "nota": "Subtotal"},
        {"concepto": "Menos vinífera arrancada", "ha": round(
            supuestos["superficie_modelada"] - (supuestos["superficie_tasacion"] - ha_clemenules), 2),
         "nota": "Cabernet Sauvignon y Cabernet Franc arrancados"},
        {"concepto": "Superficie productiva modelada", "ha": supuestos["superficie_modelada"],
         "nota": "Base de todo el modelo financiero"},
    ]

    salida = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": libro.name,
        "moneda": "US$",
        "temporadas": temporadas,
        "supuestos": supuestos,
        "conciliacion_superficie": conciliacion,
        "totales": totales,
        "por_especie": sorted(por_especie.values(), key=lambda e: -e["ha"]),
        "variedades": sorted(variedades.values(), key=lambda r: (r["especie"], -r["ha"])),
        "avisos": {
            "produccion_incoherente": sorted(
                "%s / %s" % (r["especie"], r["variedad"])
                for r in variedades.values() if not r["produccion_coherente"]),
            "variedades_sin_cuartel": sorted(r["variedad"] for r in variedades.values() if not r["cuarteles"]),
            "cuarteles_sin_modelo": sorted(set(sin_modelo)),
            "ha_detalle_plantaciones": ha_tasacion,
            "inputs_faltantes": faltantes,
        },
    }

    destino = RAIZ / "modelo_data.json"
    destino.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("OK %s" % destino)
    print("  variedades=%d  ha=%s  temporadas=%d" % (len(variedades), ha_total, len(temporadas)))
    print("  EBITDA %s: US$ %s  (%s US$/ha)" % (temporadas[0], format(totales["ebitda"][0], ",d"), totales["ebitda_ha"][0]))
    print("  EBITDA %s: US$ %s  (%s US$/ha)" % (temporadas[3], format(totales["ebitda"][3], ",d"), totales["ebitda_ha"][3]))
    for k, v in salida["avisos"].items():
        print("  %-26s %s" % (k, v))


if __name__ == "__main__":
    main()
