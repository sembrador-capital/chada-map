# -*- coding: utf-8 -*-
"""Extrae el modelo financiero de Hacienda Chada a modelo_data.json.

Lee cuatro hojas del libro y las consolida en una sola estructura por variedad:

  Fuente 2 Rendimientos    : cosecha real por variedad, ultimas tres temporadas.
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

# ── Escenarios ────────────────────────────────────────────────────────────
# Cada escenario es un libro completo, no un ajuste sobre otro: el modelo
# pesimista trae su propia hoja Consolidado, sus propios supuestos y sus propias
# proyecciones. Se leen los dos con el mismo lector -asi los dos pasan por los
# mismos chequeos- y cada uno deja su JSON.
#
# El primero manda. Es el que escribe el cruce de variedades en geo_data.json y
# contra el que se comparan los demas: el mapa dibuja una sola geometria y una
# sola leyenda, asi que si un escenario cambiara la lista de variedades o sus
# hectareas, el mapa estaria pintando un arbol que no corresponde. Eso se
# verifica y detiene el script.
#
# Para agregar un escenario: una entrada mas aca y el libro en datos_fuente/.
# El mapa lee esta misma lista desde los JSON generados, asi que no hay que
# tocar index.html.
ESCENARIOS = [
    {"id": "v6", "nombre": "v6",
     "libro": "Financial_Model_Hacienda_Chada_v6.xlsx",
     "salida": "modelo_data.json",
     # La nota es texto de pantalla, no comentario: va con tildes como todo lo
     # que termina a la vista del usuario.
     "nota": "Ultima version del modelo financiero."},
]
# Con un solo escenario el mapa no muestra el selector ni la tabla comparativa:
# los esconde cuando la lista trae menos de dos. Para volver a comparar basta
# agregar aca la entrada del otro libro -id, nombre, archivo de salida y nota- y
# correr el script; no hay que tocar index.html.

# La consola de Windows sale en cp1252 y revienta con cualquier caracter fuera
# de esa tabla. El JSON ya estaba escrito cuando eso pasaba, asi que el script
# moria justo mientras contaba que habia terminado bien: el peor momento para
# morir, porque quien lo corre concluye que no se genero nada. Se fuerza utf-8
# y, si la consola no puede con algun caracter, se reemplaza en vez de abortar.
for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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
# lo incluye a proposito: es parte del puente de 311,65 ha a 284,02 ha.
ESPECIE_SIN_MODELO = "Disponible"

# Cuarteles arrendados a terceros. El negocio no los explota, asi que el modelo
# v6 dejo de contar su superficie (de 292,23 a 284,02 ha). En el mapa van
# aparte, en gris y con su propia rama, igual que "Disponible", y no entran en
# ningun agregado ni en el filtro de EBITDA. La ha de cada uno es la que el
# modelo dejo de contar al sacarlo -Candy Hearts perdio 3,80 ha y Sweet
# Celebration 4,41-, y su suma (8,21) es el ultimo escalon de la conciliacion.
# Si aparecen o se van cuarteles arrendados, se edita solo esta tabla.
ESPECIE_ARRENDADO = "Arrendado"
ARRENDADOS = {
    "5174": {"variedad": "Candy Hearts", "ha": 3.80},
    "5133": {"variedad": "Sweet Celebration", "ha": 4.41},
}

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
# Lectura del libro
# ═══════════════════════════════════════════════════════════════════════════
# Nada se lee por numero de fila. El libro lo edita gente que agrega variedades,
# inserta filas y mueve secciones, y una constante como "el bloque de costos
# empieza en la fila 110" convierte cualquiera de esas ediciones en datos
# corridos. Cada bloque se busca por su titulo, la cantidad de variedades sale
# de contar entre la cabecera y el total, y las temporadas de contar columnas.
# Lo unico que sigue siendo posicional son las COLUMNAS de la tabla de
# supuestos, y por eso se validan contra su cabecera antes de usarlas.

CAB_CONSOLIDADO = {
    "produccion": "PRODUCCIÓN TOTAL",
    "ingresos": "INGRESOS",
    "costos": "COSTOS",
    "ebitda": "EBITDA",
    "ebitda_ha": "EBITDA/ha",
}
FIN_SUPERFICIE = "TOTAL SUPERFICIE MODELADA"
COL_TEMPORADA_0 = 4          # columna D: la primera temporada


def fila_de(filas, texto, col=0, desde=0):
    """Indice 0-based de la fila cuyo texto en esa columna calza exacto."""
    objetivo = norm(texto)
    for i in range(desde, len(filas)):
        v = filas[i][col]
        if v is not None and norm(v) == objetivo:
            return i
    return None


def exigir(fila, que, donde):
    if fila is None:
        sys.exit("No encontre '%s' en %s. Si la hoja cambio de estructura, "
                 "revisa que el titulo siga escrito igual." % (que, donde))
    return fila


def leer_consolidado(ws):
    filas = list(ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=30, values_only=True))

    i_cab = exigir(fila_de(filas, "Especie"), "Especie", "Consolidado por variedad")
    i_fin = exigir(fila_de(filas, FIN_SUPERFICIE), FIN_SUPERFICIE, "Consolidado por variedad")
    n = i_fin - i_cab - 1
    if n < 1:
        sys.exit("El bloque de superficie quedo vacio entre la cabecera y '%s'" % FIN_SUPERFICIE)

    i_prod = exigir(fila_de(filas, CAB_CONSOLIDADO["produccion"]), CAB_CONSOLIDADO["produccion"],
                    "Consolidado por variedad")
    cabecera = filas[i_prod]
    temporadas = []
    for j in range(COL_TEMPORADA_0 - 1, len(cabecera)):
        if cabecera[j] in (None, ""):
            break
        temporadas.append(cabecera[j])
    if not temporadas:
        sys.exit("La fila de '%s' no trae temporadas a la derecha" % CAB_CONSOLIDADO["produccion"])

    inicios = {"superficie": i_cab + 1}
    for bloque, titulo in CAB_CONSOLIDADO.items():
        inicios[bloque] = exigir(fila_de(filas, titulo), titulo, "Consolidado por variedad") + 1

    datos = {}
    vacias = 0
    for i in range(n):
        base = filas[inicios["superficie"] + i]
        especie, variedad, ha = base[0], base[1], base[2]
        if not especie or not variedad:
            vacias += 1
            continue
        clave = clave_modelo(especie, variedad)
        registro = {"especie": especie, "variedad": variedad, "ha": num(ha, 3)}

        for bloque in CAB_CONSOLIDADO:
            fila = filas[inicios[bloque] + i]
            # El cruce se indexa por (especie, variedad), no por posicion: si
            # alguien reordena un bloque sin reordenar los otros, esto lo caza
            # en vez de mezclar los numeros de dos variedades.
            if norm(fila[0] or "") != norm(especie) or norm(fila[1] or "") != norm(variedad):
                sys.exit(
                    "El bloque '%s' no esta alineado en la fila %d: se esperaba %s / %s y vino %s / %s.\n"
                    "Las variedades tienen que ir en el mismo orden en los seis bloques."
                    % (bloque, inicios[bloque] + i + 1, especie, variedad, fila[0], fila[1]))
            nd = 0 if bloque in ("produccion", "ingresos", "costos", "ebitda") else 1
            valores = [num(fila[COL_TEMPORADA_0 - 1 + k], nd) for k in range(len(temporadas))]
            # Los costos vienen negativos en el libro; se guardan en positivo y
            # el signo queda en el nombre del campo, no en el dato.
            if bloque == "costos":
                valores = [None if v is None else abs(v) for v in valores]
            registro[bloque] = valores

        datos[clave] = registro

    if not datos:
        sys.exit(
            "El libro no trae ningun valor calculado. Pasa casi siempre cuando el archivo se genero\n"
            "con un script en vez de guardarse desde Excel: openpyxl lee el resultado que Excel deja\n"
            "cacheado, y si no esta, todas las celdas con formula se leen vacias.\n"
            "Solucion: abrir el .xlsx en Excel o LibreOffice y volver a guardarlo.")
    if vacias:
        print("  aviso: %d filas del bloque de superficie venian sin especie o variedad" % vacias)
    return temporadas, datos


# ── Inputs Generales ──────────────────────────────────────────────────────
# Cada dato se busca por su etiqueta en la columna B. Antes iban por numero de
# fila, que es justo lo que se corre cuando alguien agrega un supuesto: el tipo
# de cambio se leia de otra fila y nada avisaba, porque un numero donde se
# espera un numero no levanta sospecha.
ETIQUETAS = [
    ("anio_inicio", "Ano de inicio del modelo", 0, None),
    ("horizonte", "Horizonte de proyeccion", 0, None),
    ("tipo_cambio", "Tipo de cambio", 0, None),
    ("iva", "IVA", 0, 4),
    ("impuesto_renta", "Impuesto a la renta", 0, 4),
    ("apreciacion_tierra", "Apreciacion de la tierra", 0, 4),
    ("tasa_descuento", "Tasa de descuento", 0, 4),
    ("superficie_predio", "Superficie total del predio", 0, 2),
    ("superficie_tasacion", "Superficie plantada segun tasacion", 0, 2),
    ("superficie_modelada", "Superficie operacional modelada", 0, 2),
    ("valor_tierra_agua_clp", "Valor tierra y derechos de agua", 0, None),
    ("valor_tierra_ha_usd", "Valor tierra y agua por hectarea modelo", 0, 0),
    # Estas dos aparecen dos veces: primero en pesos y despues en dolares.
    ("valor_comercial_clp", "Valor comercial de tasacion", 0, None),
    ("valor_comercial_usd", "Valor comercial de tasacion", 1, 0),
    ("valor_liquidacion_clp", "Valor de liquidacion", 0, None),
    ("valor_liquidacion_usd", "Valor de liquidacion", 1, 0),
]

# Tabla de supuestos por variedad. La columna sigue siendo posicional, pero se
# comprueba contra su cabecera: si alguien inserta una columna, el script se
# detiene en vez de leer el precio donde estaba el rendimiento.
CAMPOS_VARIEDAD = [
    ("anio_plantacion", "E", None, "Año de plantacion"),
    ("unidad", "F", None, "Unidad de produccion"),
    ("rend_23_24", "G", 0, "Rendimiento 23-24"),
    ("rend_24_25", "H", 0, "Rendimiento 24-25"),
    ("rend_25_26", "I", 0, "Rendimiento 25-26"),
    ("rend_26_27", "J", 0, "Rendimiento 26-27"),
    ("rend_27_28", "K", 0, "Rendimiento 27-28"),
    ("rend_28_29", "L", 0, "Rendimiento 28-29"),
    ("rend_plena", "M", 0, "Rendimiento plena prod"),
    ("precio_export", "N", 2, "Precio exportacion"),
    ("precio_interno_clp", "O", 0, "Precio mercado interno"),
    ("pct_export", "P", 3, "Exportacion"),
    ("costo_fijo_ha", "Q", 0, "Costo fijo de produccion"),
    ("costo_cosecha_kg", "R", 3, "Costo de cosecha"),
    ("proceso_kg", "S", 3, "Proceso y embalaje"),
    ("otros_var_kg", "T", 3, "Otros costos variables"),
    ("gav_ha", "U", 0, "GAV"),
    ("capex_pct", "V", 3, "CapEx recurrente"),
]


# Busca la columna cuyo encabezado trae 'objetivo', partiendo de la letra
# esperada y ampliando hacia los lados si ahi no calza. Una columna insertada o
# borrada cerca corre el resto del bloque un lugar sin reordenarlo -es
# exactamente lo que paso en v5, que metio "Precio exportacion 27-28" entre el
# precio de exportacion y el precio interno y corrio doce columnas una casilla-,
# y una ventana chica lo sigue sin adivinar mas alla. Si nada calza ni cerca,
# no hay ambiguedad que resolver: se avisa y se para.
def col_con_encabezado(cabecera, idx, letra_base, objetivo, ventana=4):
    base = idx(letra_base)
    buscado = norm(objetivo)
    deltas = [0] + [d for paso in range(1, ventana + 1) for d in (paso, -paso)]
    for delta in deltas:
        i = base + delta
        if 0 <= i < len(cabecera):
            texto = norm(" ".join(str(cabecera[i] or "").split()))
            if buscado in texto:
                return i
    return None


def leer_inputs(ws):
    filas = list(ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=43, values_only=True))
    idx = lambda letra: openpyxl.utils.column_index_from_string(letra) - 1

    supuestos = {}
    for nombre, etiqueta, salto, nd in ETIQUETAS:
        i, visto = None, -1
        objetivo = norm(etiqueta)
        for k, f in enumerate(filas):
            if f[1] is not None and norm(f[1]) == objetivo:
                visto += 1
                if visto == salto:
                    i = k
                    break
        if i is None:
            sys.exit("No encontre el supuesto '%s' en la columna B de Inputs Generales" % etiqueta)
        supuestos[nombre] = num(filas[i][2], nd)

    # Seccion 4: la cabecera es la fila que tiene "Especie" en B y "Variedad" en C.
    i_cab = None
    for k, f in enumerate(filas):
        if f[1] and f[2] and norm(f[1]) == "especie" and norm(f[2]) == "variedad":
            i_cab = k
            break
    exigir(i_cab, "la cabecera Especie / Variedad", "Inputs Generales, seccion 4")

    cabecera = filas[i_cab]
    columnas = {}
    for nombre, letra, _, esperado in CAMPOS_VARIEDAD:
        i = col_con_encabezado(cabecera, idx, letra, esperado)
        if i is None:
            sys.exit(
                "No encuentro la columna de '%s' (se esperaba en %s o cerca) en la\n"
                "tabla de supuestos de Inputs Generales. En %s dice '%s'.\n"
                "Parece que se insertaron o borraron mas columnas de las que este\n"
                "script sabe seguir: revisa la hoja antes de seguir."
                % (esperado, letra, letra, cabecera[idx(letra)]))
        columnas[nombre] = i

    # Precio de exportacion con corte de temporada, agregado en v5: rige desde
    # una temporada en adelante y antes de esa temporada sigue el precio de
    # siempre. Es OPCIONAL -las versiones anteriores del libro no lo traen, y
    # una version futura podria volver a sacarlo- y se identifica por traer un
    # rango de dos anos en el encabezado (hoy "27-28"), no por su posicion: el
    # propio rango dice desde que temporada aplica, asi que si el corte se
    # mueve a otro ano el script lo sigue sin que haya que tocarlo.
    col_tardio = col_con_encabezado(cabecera, idx, "O", "exportacion")
    corte_tardio = None
    if col_tardio is not None:
        texto_tardio = str(cabecera[col_tardio] or "")
        m = re.search(r"(\d{2})\s*-\s*(\d{2})", texto_tardio)
        if m:
            corte_tardio = "20%s-20%s" % (m.group(1), m.group(2))
        else:
            col_tardio = None  # trae "exportacion" pero no un rango: no es esta columna

    por_variedad = {}
    for f in filas[i_cab + 1:]:
        especie, variedad = f[1], f[2]
        if not especie or not variedad:
            break                      # la tabla termina en la primera fila sin variedad
        reg = {}
        for nombre, letra, nd, _ in CAMPOS_VARIEDAD:
            v = f[columnas[nombre]]
            reg[nombre] = v if nd is None else num(v, nd)
        reg["precio_export_tardio"] = num(f[col_tardio], 2) if col_tardio is not None else None
        por_variedad[clave_modelo(especie, variedad)] = reg
    return supuestos, por_variedad, corte_tardio


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
    """Inventario de la tasacion, agrupado por variedad normalizada."""
    filas = list(ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=10, values_only=True))
    i_cab = None
    for k, f in enumerate(filas):
        if f[2] and norm(f[2]) == "variedad":
            i_cab = k
            break
    exigir(i_cab, "la cabecera con 'Variedad'", "Detalle Plantaciones")

    por_variedad, total = {}, 0.0
    for row in filas[i_cab + 1:]:
        _, especie, variedad, portainjerto, anio, ha, marco, plantas_ha, _, riego = row[:10]
        if not variedad:
            break                      # despues de la tabla vienen los totales
        if ha is None:
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
    """Produccion historica por variedad y numero de plantas."""
    filas = list(ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=9, values_only=True))
    i_cab = None
    for k, f in enumerate(filas):
        if f[0] and f[1] and norm(f[0]) == "especie" and norm(f[1]) == "variedad":
            i_cab = k
            break
    exigir(i_cab, "la cabecera Especie / Variedad", "Base Chada")

    out = {}
    # Indice de respaldo por nombre de variedad. La hoja escribe "Naranjas"
    # donde el modelo dice "Naranjos", y con la clave especie|variedad esas dos
    # filas no calzaban con nada: Cara Cara y Fukumoto quedaban sin historia sin
    # que nadie se enterara, porque una variedad sin historico igual se dibuja.
    # El nombre de variedad alcanza para desempatar mientras sea unico, y si
    # algun dia deja de serlo el respaldo se desactiva solo para ese nombre.
    por_variedad = {}
    for row in filas[i_cab + 1:]:
        especie, variedad, desde, hasta, ha, plantas, p23, p24, p25 = row[:9]
        if not especie or not variedad:
            break
        dato = {
            "anio_desde": desde, "anio_hasta": hasta,
            "ha_ficha": num(ha, 3), "plantas": num(plantas, 0),
            "prod_23_24": num(p23, 0), "prod_24_25": num(p24, 0), "prod_25_26": num(p25, 0),
        }
        out[norm(clave_modelo(especie, variedad))] = dato
        v = norm(variedad)
        por_variedad[v] = None if v in por_variedad else dato
    out["__por_variedad__"] = {k: v for k, v in por_variedad.items() if v}
    return out


# Fuente 2 agrupa en una fila lo que el modelo lleva en dos. Se declara
# explicito y no se adivina: las hectareas de la fila agrupada cuadran con la
# suma de las partes (19,84 = 12,18 + 7,66 y 2,53 = 1,41 + 1,12), que es lo que
# permite afirmar que son la misma cosa mirada con menos detalle.
FUENTE2_AGRUPA = {
    "santina": ["Santina", "Santina Macro Tunel"],
    "fukumoto-caracara": ["Cara Cara", "Fukumoto"],
}

# Cuantas temporadas de cosecha real trae la hoja, y como se llaman. La ultima
# es siempre 2025-2026: ver la verificacion en cruzar_cosechas().
TEMPORADAS_COSECHA = ["2023-2024", "2024-2025", "2025-2026"]

ANIO_COSECHA = re.compile(r"(?:cosecha|embalado)\s*(\d{4})", re.I)
CAJA_F2 = re.compile(r"(?:cja|caja)\s*([\d,.]+)", re.I)


def leer_fuente2(ws):
    """Cosecha real por variedad, de la hoja 'Fuente 2 Rendimientos'.

    La hoja son seis bloques apilados, uno por especie, cada uno con su unidad
    y su propio juego de temporadas: las cerezas se rotulan por el ano en que se
    cosechan (nov-dic) y la uva de mesa por el ano en que se embala (ene-abr),
    asi que la temporada 2023-2024 aparece como "Cosecha 2023" en un bloque y
    como "Embalado 2024" en el otro. Los ciruelos traen solo dos temporadas.

    El bloque se reconoce por la fila que rotula las temporadas, no por la
    palabra "Especie": el bloque de citricos la escribe distinto y con eso se
    perdia entero.
    """
    bloques = []
    for r in range(1, ws.max_row + 1):
        anios = {}
        for c in range(3, 8):
            m = ANIO_COSECHA.search(str(ws.cell(r, c).value or ""))
            if m:
                anios[c] = int(m.group(1))
        if len(anios) < 2:
            continue
        # La unidad va una fila mas arriba, al lado del nombre de la especie.
        arriba = " | ".join(str(ws.cell(r - 1, c).value or "") for c in range(2, 7))
        caja = CAJA_F2.search(arriba)
        en_cajas = bool(caja)
        filas = []
        rr = r + 1
        while rr <= ws.max_row:
            nombre = ws.cell(rr, 2).value
            if not nombre:
                break
            nombre = str(nombre).strip()
            if norm(nombre) == "total general":
                break
            filas.append((nombre, ws.cell(rr, 3).value,
                          [ws.cell(rr, c).value for c in sorted(anios)]))
            rr += 1
        if filas:
            bloques.append({
                "anios": [anios[c] for c in sorted(anios)],
                "en_cajas": en_cajas, "filas": filas, "fila": r,
            })

    if not bloques:
        raise SystemExit(
            "No se encontro ningun bloque en 'Fuente 2 Rendimientos'.\n"
            "Se buscan filas con dos o mas rotulos tipo 'Cosecha 2024' o\n"
            "'Embalado 2025' entre las columnas C y G. Si la hoja se reordeno,\n"
            "hay que ajustar leer_fuente2() en tools/modelo_to_json.py.")

    # Las temporadas se alinean por la derecha: la ultima columna de cada bloque
    # es 2025-2026, y de ahi hacia atras. No se supone -se verifica contra la
    # produccion 25/26 de la Ficha, en cruzar_cosechas()-.
    n = len(TEMPORADAS_COSECHA)
    salida = {}
    for b in bloques:
        ultimo = b["anios"][-1]
        for nombre, ha, valores in b["filas"]:
            serie = [None] * n
            for anio, v in zip(b["anios"], valores):
                i = n - 1 - (ultimo - anio)
                if 0 <= i < n:
                    serie[i] = v
            salida[norm(nombre)] = {
                "nombre": nombre, "ha": ha, "serie": serie,
                "en_cajas": b["en_cajas"],
            }
    return salida


def cruzar_cosechas(fuente2, variedades):
    """Pega la cosecha real a cada variedad del modelo y revisa que calce.

    Tres cosas se comprueban, y ninguna se arregla en silencio:
      - que la ultima temporada de Fuente 2 sea la misma produccion 25/26 que
        ya trae la Ficha, que es lo que confirma que las temporadas quedaron
        alineadas y no corridas un ano;
      - que la unidad del bloque coincida con la del modelo, porque un bloque
        en cajas leido como kilos da un rendimiento ocho veces menor;
      - que la superficie de la fila agrupada sea la suma de sus partes.
    """
    avisos = {"sin_cosecha": [], "desalineadas": [], "unidad_distinta": [],
              "difieren_de_ficha": [], "agrupadas": [], "rend_es_total": [],
              "repartidas_por_superficie": []}

    # Como se escribe de verdad cada variedad. Las claves de FUENTE2_AGRUPA van
    # sin tildes porque este archivo se lee en consolas que no siempre pueden
    # con ellas, pero lo que se muestra en el mapa tiene que salir del modelo:
    # "Santina Macro Tunel" escrito asi en pantalla es una falta de ortografia.
    como_se_escribe = {norm(r["variedad"]): r["variedad"] for r in variedades.values()}
    bonito = lambda nombre: como_se_escribe.get(norm(nombre), nombre)

    # Que fila de Fuente 2 le toca a cada variedad del modelo.
    de_variedad = {}
    for clave_f2, dato in fuente2.items():
        partes = FUENTE2_AGRUPA.get(clave_f2)
        if partes:
            for nombre in partes:
                de_variedad[norm(nombre)] = (dato, clave_f2)
        else:
            de_variedad[clave_f2] = (dato, None)

    variedades_por_nombre = {norm(r["variedad"]): r for r in variedades.values()}

    n = len(TEMPORADAS_COSECHA)
    for reg in variedades.values():
        par = de_variedad.get(norm(reg["variedad"]))
        if par is None:
            avisos["sin_cosecha"].append(reg["variedad"])
            reg["cosecha"] = None
            continue
        dato, agrupada = par
        factor = reg.get("kg_por_unidad") or 1.0
        if dato["en_cajas"] != (factor > 1):
            avisos["unidad_distinta"].append(
                "%s: Fuente 2 %s y el modelo %s"
                % (reg["variedad"], "en cajas" if dato["en_cajas"] else "en kilos",
                   "en cajas" if factor > 1 else "en kilos"))

        ha_fila = dato["ha"] or reg["ha"]
        kg_fila = [None if v is None else v * factor for v in dato["serie"]]

        # Una fila agrupada hay que repartirla entre sus partes: si las dos se
        # quedan con el total del par, cualquier suma lo cuenta dos veces.
        #
        # El reparto sale de la Ficha, que SI las lleva separadas -Cara Cara y
        # Fukumoto son 1,41 y 1,12 ha con cosechas muy distintas, y darles el
        # mismo rendimiento borraba justamente la diferencia entre los dos
        # cuarteles-. Fuente 2 sigue mandando en el total de cada temporada; la
        # Ficha solo dice como se parte. Cuando la Ficha no tiene con que
        # repartir esa temporada, se reparte por superficie y queda avisado.
        cuota, criterio = [1.0] * n, None
        if agrupada:
            partes = FUENTE2_AGRUPA[agrupada]
            hist = {norm(x): (variedades_por_nombre.get(norm(x)) or {}).get("historico") or {}
                    for x in partes}
            ha_parte = {norm(x): (variedades_por_nombre.get(norm(x)) or {}).get("ha") or 0.0
                        for x in partes}
            campos = ("prod_23_24", "prod_24_25", "prod_25_26")
            mio = norm(reg["variedad"])
            por_superficie = False
            for i in range(n):
                # El reparto se decide para el PAR, no para cada parte por su
                # cuenta: si una mira la Ficha y la otra cae a superficie, las
                # dos cuotas no suman uno y el total de la temporada se infla.
                # Una parte sin dato en la Ficha cuenta como cero, no como
                # faltante: el total del par ya esta explicado por las otras.
                trozos = {norm(x): (hist[norm(x)].get(campos[i]) or 0.0) for x in partes}
                total = sum(trozos.values())
                if total:
                    cuota[i] = trozos[mio] / total
                    criterio = criterio or "ficha"
                else:
                    ha_partes = sum(ha_parte.values())
                    cuota[i] = (ha_parte[mio] / ha_partes) if ha_partes else 0.0
                    por_superficie = True
            if por_superficie:
                criterio = "mixto" if criterio else "superficie"
                avisos["repartidas_por_superficie"].append(reg["variedad"])

        kg = [None if v is None else round(v * cuota[i]) for i, v in enumerate(kg_fila)]
        # La cosecha se divide por la superficie que la PRODUJO, que es la de la
        # hoja de rendimientos, no la del modelo. Antes de v6 eran la misma para
        # las variedades no agrupadas, pero v6 saco de la superficie modelada
        # dos cuarteles arrendados: Candy Hearts bajo a 12,50 ha y Sweet
        # Celebration a 18,73, y su cosecha historica -que salio del pano
        # entero, cuando todavia se operaba- se habria dividido por menos
        # hectareas de las que la generaron, inflando el rendimiento ~30%. La
        # cosecha real es un hecho del pasado y se mide contra el area de
        # entonces. En las agrupadas manda reg["ha"] -el kg ya viene repartido
        # por variedad, asi que la parte se divide por su propia area-.
        ha_propia = reg["ha"] if agrupada else (ha_fila or reg["ha"])
        rend = [None if v is None or not ha_propia else round(v / ha_propia) for v in kg]
        # El mismo rendimiento en la unidad del modelo: la uva de mesa se
        # negocia en cajas, no en kilos, y "22.834 kg/ha" no es un numero que
        # nadie use para hablar de un parron.
        rend_u = [None if v is None or not ha_propia else round(v / factor / ha_propia, 1)
                  for v in kg]

        # La ultima temporada tiene que ser la produccion 25/26 que ya teniamos.
        h = reg.get("historico") or {}
        ficha_2526 = h.get("prod_25_26")
        propio_2526 = None if kg_fila[n - 1] is None else kg_fila[n - 1] / factor
        if agrupada is None and ficha_2526 is not None and propio_2526 is not None:
            if abs(ficha_2526 - propio_2526) > max(1.0, 0.005 * abs(propio_2526)):
                avisos["desalineadas"].append(
                    "%s: Ficha 25/26 %s vs Fuente 2 %s"
                    % (reg["variedad"], round(ficha_2526), round(propio_2526)))

        # Donde Fuente 2 y la Ficha no dicen lo mismo en 23/24 o 24/25.
        difiere = [False] * n
        for i, campo in enumerate(("prod_23_24", "prod_24_25")):
            a, b = h.get(campo), None if dato["serie"][i] is None else dato["serie"][i]
            if a is not None and b is not None and abs(a - b) > max(1.0, 0.005 * abs(b)):
                difiere[i] = True
        if any(difiere) and agrupada is None:
            avisos["difieren_de_ficha"].append(reg["variedad"])

        if agrupada:
            avisos["agrupadas"].append("%s (con %s, reparto %s)" % (
                reg["variedad"],
                " + ".join(bonito(x) for x in FUENTE2_AGRUPA[agrupada]
                           if norm(x) != norm(reg["variedad"])),
                criterio or "superficie"))

        # ¿La celda rend_25_26 de 'Inputs Generales' trae un rendimiento o un
        # total? Con la cosecha real a mano se puede distinguir sin adivinar:
        # si el valor calza con los KILOS TOTALES de la temporada y no con los
        # kilos por hectarea, la celda lleva un total, y el modelo -que la
        # multiplica por la superficie- termina inflando la temporada entera
        # por un factor igual a las hectareas. No se corrige aca: se avisa.
        rend_libro = reg.get("rend_25_26")
        total_unid = propio_2526
        esperado = None if not ha_fila or total_unid is None else total_unid / ha_fila
        if (agrupada is None and rend_libro and total_unid and esperado
                and abs(rend_libro - total_unid) <= max(1.0, 0.005 * total_unid)
                and abs(rend_libro - esperado) > max(1.0, 0.05 * esperado)):
            ingreso_libro = (reg["ingresos"] or [None])[0]
            precio = reg.get("precio_efectivo") or 0
            avisos["rend_es_total"].append({
                "variedad": reg["variedad"],
                "especie": reg["especie"],
                "celda": round(rend_libro),
                "rendimiento_real": round(esperado),
                "factor": round(ha_fila, 2),
                "ingreso_modelado": None if ingreso_libro is None else round(ingreso_libro),
                "ingreso_implicado": round(total_unid * precio) if precio else None,
            })

        reg["cosecha"] = {
            "kg": kg,
            "rend_kg_ha": rend,
            "ha": round(ha_propia, 3) if ha_propia else None,
            "rend_u_ha": rend_u,
            "agrupada": (" + ".join(bonito(x) for x in FUENTE2_AGRUPA[agrupada])
                         if agrupada else None),
            "criterio_reparto": criterio,
            "difiere_de_ficha": difiere,
        }
    # Cada bloque de la hoja rotula sus temporadas a su manera -la cereza por el
    # ano en que se cosecha, la uva de mesa por el ano en que se embala-, asi
    # que las columnas se alinean por la derecha. Que la ultima coincida con la
    # produccion 25/26 que ya traia la Ficha es lo que demuestra que la
    # alineacion quedo bien. Si deja de coincidir, la serie entera esta corrida
    # un ano y el mapa mostraria la cosecha de una temporada rotulada como otra:
    # eso no es un aviso al pie, es motivo para no generar el archivo.
    if avisos["desalineadas"]:
        raise SystemExit(
            "Las temporadas de 'Fuente 2 Rendimientos' dejaron de calzar con la\n"
            "produccion 25/26 de la Ficha Tecnica ('Base Chada'). Las columnas se\n"
            "alinean por la derecha suponiendo que la ultima de cada bloque es la\n"
            "temporada 2025-2026; si se agrego una temporada nueva a la hoja, hay\n"
            "que actualizar TEMPORADAS_COSECHA en tools/modelo_to_json.py.\n\n"
            "No calzan:\n  " + "\n  ".join(avisos["desalineadas"][:12]))
    return avisos


def reportar_cambios(anterior, salida):
    """Que cambio respecto de la corrida anterior.

    Sin esto, actualizar el modelo es un acto de fe: el script dice OK y uno no
    sabe si entraron dos variedades nuevas, si el tipo de cambio se movio o si
    alguien borro media hoja sin querer. Comparar contra el JSON que ya estaba
    cuesta nada y convierte la actualizacion en algo que se puede revisar.
    """
    if not anterior:
        print("  (primera corrida: no hay con que comparar)")
        return

    antes = {clave_modelo(v["especie"], v["variedad"]): v for v in anterior.get("variedades", [])}
    ahora = {clave_modelo(v["especie"], v["variedad"]): v for v in salida["variedades"]}

    nuevas = [k for k in ahora if k not in antes]
    fuera = [k for k in antes if k not in ahora]
    cambio_ha = [(k, antes[k]["ha"], ahora[k]["ha"]) for k in ahora
                 if k in antes and abs((antes[k]["ha"] or 0) - (ahora[k]["ha"] or 0)) > 0.005]

    print("")
    print("  ── Cambios respecto de la corrida anterior ──")
    if not (nuevas or fuera or cambio_ha):
        print("    sin cambios en el listado de variedades ni en sus superficies")
    for k in nuevas:
        print("    + variedad nueva   %-34s %8.2f ha" % (k, ahora[k]["ha"] or 0))
    for k in fuera:
        print("    - variedad que sale %-33s %8.2f ha" % (k, antes[k]["ha"] or 0))
    for k, a, b in cambio_ha:
        print("    ~ superficie       %-34s %8.2f -> %.2f ha" % (k, a or 0, b or 0))

    for campo, etiqueta in (("tipo_cambio", "Tipo de cambio"),
                            ("superficie_modelada", "Superficie modelada"),
                            ("superficie_tasacion", "Superficie de tasacion"),
                            ("tasa_descuento", "Tasa de descuento")):
        a = (anterior.get("supuestos") or {}).get(campo)
        b = salida["supuestos"].get(campo)
        if a is not None and b is not None and abs(a - b) > 1e-9:
            print("    ~ supuesto         %-34s %s -> %s" % (etiqueta, a, b))

    if len(anterior.get("temporadas", [])) != len(salida["temporadas"]):
        print("    ~ horizonte        %d -> %d temporadas"
              % (len(anterior.get("temporadas", [])), len(salida["temporadas"])))

    for campo, etiqueta in (("ebitda", "EBITDA"), ("ingresos", "Ingresos"), ("costos", "Costos")):
        a = (anterior.get("totales") or {}).get(campo)
        b = salida["totales"][campo]
        if a and b and len(a) == len(b):
            i = min(3, len(b) - 1)
            if abs(a[i] - b[i]) > 0.5:
                print("    ~ %-16s plena produccion  %s -> %s US$"
                      % (etiqueta, format(round(a[i]), ",d"), format(round(b[i]), ",d")))


def procesar(esc, escribir_geo):
    """Lee un libro completo y deja su JSON. Devuelve la salida para cotejarla."""
    libro = RAIZ / "datos_fuente" / esc["libro"]
    if not libro.exists():
        raise SystemExit(
            "No esta el libro del escenario '%s':\n  %s\n\n"
            "Los libros van en datos_fuente/ (que no se versiona). Si el archivo\n"
            "cambio de nombre, hay que actualizar ESCENARIOS en\n"
            "tools/modelo_to_json.py." % (esc["id"], libro))
    print("")
    print("=" * 70)
    print("ESCENARIO %s  <-  %s" % (esc["nombre"], esc["libro"]))
    print("  %s" % esc["nota"])
    print("=" * 70)
    wb = abrir_libro(libro)

    temporadas, variedades = leer_consolidado(wb["Consolidado por variedad"])
    # El largo lo manda el libro, no una constante: si el modelo cambia de
    # horizonte, el JSON lo sigue sin que nadie tenga que tocar el script.
    N_TEMPORADAS = len(temporadas)
    supuestos, inputs_var, corte_precio_tardio = leer_inputs(wb["Inputs Generales"])
    # A que indice de temporada corresponde el corte del precio tardio -si el
    # libro trae uno-. Se busca por el nombre de la temporada, no se calcula a
    # partir del horizonte: si alguna temporada trae la "E" de estimada al
    # final (las de mas adelante la tienen) el corte real no la tiene, asi que
    # se compara sin ese sufijo.
    idx_corte_tardio = None
    if corte_precio_tardio:
        idx_corte_tardio = next(
            (k for k, t in enumerate(temporadas) if t.rstrip("E") == corte_precio_tardio), None)
    plantaciones, ha_tasacion = leer_plantaciones(wb["Detalle Plantaciones"])
    base = leer_base(wb["Base Chada"])
    fuente2 = leer_fuente2(wb["Fuente 2 Rendimientos"])

    faltantes = []
    for clave, reg in variedades.items():
        extra = inputs_var.get(clave)
        if extra is None:
            extra = next((v for k, v in inputs_var.items() if norm(k) == norm(clave)), None)
        if extra is None:
            faltantes.append(clave)
            # Campos vacios en vez de ausentes: el mapa lee estos nombres y una
            # variedad a medio definir tiene que dibujarse igual, no romper.
            for campo, _l, _n, _t in CAMPOS_VARIEDAD:
                reg.setdefault(campo, None)
        else:
            reg.update(extra)
        reg["historico"] = (base.get(norm(clave))
                            or base["__por_variedad__"].get(norm(reg["variedad"])))
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
        # Este control nacio por un error del libro v1: el bloque PRODUCCION
        # traia corridas una fila las cuatro variedades de Uva Vinifera, de modo
        # que cada una llevaba la produccion de la siguiente. Se detecta
        # despejando la produccion desde los ingresos y el precio efectivo.
        #
        # La prueba es POR TEMPORADA y gana la mayoria, no la primera. Una fila
        # corrida no calza en NINGUNA temporada -lleva la serie de otra
        # variedad-, mientras que un libro que usa el precio realmente obtenido
        # en la temporada en curso y el precio modelado de ahi en adelante no
        # calza en UNA sola. Mirando solo la primera temporada, como se hacia
        # antes, las dos cosas se ven iguales: en v3 eso marcaba como rotas
        # siete variedades de Uva de Mesa que estaban bien y les reemplazaba la
        # produccion 25/26 real por una despejada de un precio que no era el de
        # esa temporada. Peor que no avisar: corregir lo que estaba bien.
        #
        # reg.get y no reg[...]: una variedad agregada al Consolidado pero no a
        # la tabla de supuestos llega hasta aca sin estos campos, y reventar con
        # un KeyError no le dice a nadie que le falta una fila en otra hoja. Se
        # sigue adelante con lo que hay y la variedad queda listada en
        # inputs_faltantes, que se avisa al final.
        px = reg.get("pct_export")
        px = px if px is not None else 1
        interno = (reg.get("precio_interno_clp") or 0) / supuestos["tipo_cambio"]
        precio = (reg.get("precio_export") or 0) * px + interno * (1 - px)
        # precio_efectivo queda como el de siempre -el temprano-: es lo unico
        # que se expone en el diagnostico de consola, y para las variedades sin
        # precio tardio (todas antes de v5, y las que v5 no le puso el segundo
        # precio) el comportamiento no cambia en nada.
        reg["precio_efectivo"] = round(precio, 4) if precio else None

        # El precio con que se compara cada temporada. Si esta variedad tiene
        # un precio de exportacion tardio, rige desde el indice del corte en
        # adelante; si no, es el mismo precio en las 21 temporadas, como era
        # antes de que existiera esta columna.
        tardio_val = reg.get("precio_export_tardio")
        if tardio_val is not None and idx_corte_tardio is not None:
            precio_tardio = tardio_val * px + interno * (1 - px)
            precios = [precio_tardio if k >= idx_corte_tardio else precio for k in range(N_TEMPORADAS)]
        else:
            precios = [precio] * N_TEMPORADAS

        implicita = [None if not precios[k] else round(reg["ingresos"][k] / precios[k])
                    for k in range(N_TEMPORADAS)]

        # Temporadas con con que comparar: hace falta produccion e ingresos.
        comparables = [k for k in range(N_TEMPORADAS)
                       if precios[k] and reg["produccion"][k] and reg["ingresos"][k]]
        fuera = [k for k in comparables
                 if abs(reg["ingresos"][k] / reg["produccion"][k] - precios[k]) > 0.02 * precios[k]]
        reg["produccion_coherente"] = len(fuera) * 2 <= len(comparables)
        if reg["produccion_coherente"]:
            # Las temporadas sueltas con otro precio no se tocan: son dato del
            # libro. Se anotan para poder explicarlas si alguien pregunta por
            # que el ingreso por kilo de esa temporada no es el del modelo.
            reg["temporadas_otro_precio"] = [temporadas[k] for k in fuera]
        else:
            reg["temporadas_otro_precio"] = []
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

        # ── Economia unitaria ─────────────────────────────────────────────
        # Lo mismo que ya esta por hectarea, pero por kilo producido. El kilo
        # es la unidad en que se negocia la fruta, asi que es la unica forma de
        # comparar una cereza con una parra sin que la densidad de plantacion
        # se meta en el medio: dos variedades con el mismo costo/ha pueden
        # tener el doble de costo/kg si una rinde la mitad.
        #
        # Los kilos van convertidos por kg_por_unidad: la uva de mesa se modela
        # en cajas de 8,2 kg, y un US$/caja al lado de un US$/kg de cereza no
        # compara nada. Sin cosecha no hay denominador y el valor es None, no
        # cero: un cero diria "sale gratis" donde lo que pasa es que no hay con
        # que dividir.
        kg = [None if p is None else p * factor for p in reg["produccion"]]
        reg["kg"] = [None if k is None else round(k) for k in kg]
        por_kg = lambda serie: [None if not k else round((x or 0) / k, 4)
                                for x, k in zip(serie, kg)]
        reg["ingreso_kg"] = por_kg(reg["ingresos"])
        reg["costo_kg"] = por_kg(reg["costos"])
        # El margen por kilo es el EBITDA por kilo: lo que deja cada kilo
        # despues de costos. No es el margen sobre ventas -ese ya esta, y es
        # una razon sin unidad-, es plata por kilo.
        reg["ebitda_kg"] = por_kg(reg["ebitda"])

    # ── Cosecha real ──────────────────────────────────────────────────────
    # Va despues del bucle de arriba porque necesita kg_por_unidad y el
    # historico de la Ficha, que se arman ahi.
    avisos_cosecha = cruzar_cosechas(fuente2, variedades)

    # ── Cruce con los cuarteles del KMZ ───────────────────────────────────
    geo = json.loads((RAIZ / "geo_data.json").read_text(encoding="utf-8"))
    cuarteles_por_clave = {}
    aprox_por_clave = {}
    sin_modelo = []
    for f in geo["cuarteles"]["features"]:
        p = f["properties"]
        # Arrendado a terceros: fuera del analisis. No cruza con ninguna
        # variedad y su especie pasa a "Arrendado" para que en el mapa forme su
        # propia rama gris -como "Disponible"- en vez de colarse en la de la
        # variedad que tenia plantada. Se guarda el flag para que la ficha lo
        # diga, y la variedad real se conserva para poder nombrarla.
        if any(c in ARRENDADOS for c in p.get("cuarteles", [])):
            p["arrendado"] = True
            p["especie"] = ESPECIE_ARRENDADO
            p["modelo"] = []
            p["aprox"] = False
            continue
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

    # El cruce variedad-cuartel lo escribe solo el escenario que manda: es
    # geometria, no plata, y es identico en todos -se verifica despues-.
    if escribir_geo:
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
        # Kilos convertidos, no unidades del libro: sumar cajas de uva con
        # kilos de cereza daria un total que no significa nada.
        "kg": [round(x) for x in idx("kg")],
    }
    totales["ebitda_ha"] = [round(e / ha_total, 1) for e in totales["ebitda"]]
    totales["margen"] = [None if not i else round(e / i, 4)
                         for i, e in zip(totales["ingresos"], totales["ebitda"])]
    for campo, fuente in (("ingreso_kg", "ingresos"), ("costo_kg", "costos"), ("ebitda_kg", "ebitda")):
        totales[campo] = [None if not k else round(x / k, 4)
                          for x, k in zip(totales[fuente], totales["kg"])]

    por_especie = {}
    for reg in variedades.values():
        e = por_especie.setdefault(reg["especie"], {
            "especie": reg["especie"], "variedades": 0, "ha": 0.0,
            "produccion": [0.0] * N_TEMPORADAS, "kg": [0.0] * N_TEMPORADAS,
            "ingresos": [0.0] * N_TEMPORADAS,
            "costos": [0.0] * N_TEMPORADAS, "ebitda": [0.0] * N_TEMPORADAS,
        })
        e["variedades"] += 1
        e["ha"] = round(e["ha"] + reg["ha"], 3)
        for campo in ("produccion", "kg", "ingresos", "costos", "ebitda"):
            for i in range(N_TEMPORADAS):
                e[campo][i] += reg[campo][i] or 0
    for e in por_especie.values():
        for campo in ("produccion", "kg", "ingresos", "costos", "ebitda"):
            e[campo] = [round(x) for x in e[campo]]
        e["ebitda_ha"] = [round(x / e["ha"], 1) for x in e["ebitda"]]
        e["margen"] = [None if not i else round(x / i, 4) for i, x in zip(e["ingresos"], e["ebitda"])]
        for campo, fuente in (("ingreso_kg", "ingresos"), ("costo_kg", "costos"), ("ebitda_kg", "ebitda")):
            e[campo] = [None if not k else round(x / k, 4) for x, k in zip(e[fuente], e["kg"])]

    # ── Agregado de la cosecha real ───────────────────────────────────────
    # Los kilos ya vienen convertidos, asi que la suma significa algo. Las
    # hectareas del denominador son las de cada temporada CON dato: sumar sobre
    # las 292 ha completas cuando media hacienda todavia no entraba en
    # produccion daria un rendimiento que no es el de nadie.
    n_cos = len(TEMPORADAS_COSECHA)
    cosechas = {"temporadas": list(TEMPORADAS_COSECHA),
                "kg": [0] * n_cos, "ha": [0.0] * n_cos}
    for reg in variedades.values():
        c = reg.get("cosecha")
        if not c:
            continue
        for i in range(n_cos):
            if c["kg"][i] is None:
                continue
            cosechas["kg"][i] += c["kg"][i]
            # La misma area que produjo la cosecha, no la del modelo -por los
            # cuarteles arrendados difieren en Candy Hearts y Sweet Celebration-.
            cosechas["ha"][i] += c["ha"]
    cosechas["ha"] = [round(x, 2) for x in cosechas["ha"]]
    cosechas["rend_kg_ha"] = [None if not h else round(k / h)
                              for k, h in zip(cosechas["kg"], cosechas["ha"])]

    # ── Conciliacion de superficies ───────────────────────────────────────
    # El puente de la tasacion al modelo. Los tres numeros que Rolando usa para
    # explicar el predio, con el delta explicito entre cada par.
    ha_clemenules = sum(p["ha"] for lst in plantaciones.values() for p in lst
                        if norm(p.get("especie_tasacion") or "") == "clementinos"
                        and p["ha"] == 10.18)
    # Superficie que el modelo dejo de contar por los cuarteles arrendados. El
    # "antes de arrendar" se reconstruye sumandola de vuelta a la modelada, y
    # asi la vinifera arrancada sigue midiendose contra la superficie plantada
    # del predio y no se mezcla con el arriendo.
    ha_arrendados = round(sum(a["ha"] for a in ARRENDADOS.values()), 2)
    ha_plantada = round(supuestos["superficie_tasacion"] - ha_clemenules, 2)
    ha_antes_arrendar = round(supuestos["superficie_modelada"] + ha_arrendados, 2)
    conciliacion = [
        {"concepto": "Superficie plantada según tasación", "ha": supuestos["superficie_tasacion"],
         "nota": "Tasación Comercial N° 599-2026-SIMM, tablas pág. 15-17"},
        {"concepto": "Menos Clemenules (no productivo)", "ha": round(-ha_clemenules, 2),
         "nota": "10,18 ha plantadas en 1999, fuera de producción"},
        {"concepto": "Superficie plantada", "ha": ha_plantada,
         "nota": "Subtotal"},
        {"concepto": "Menos vinífera arrancada", "ha": round(ha_antes_arrendar - ha_plantada, 2),
         "nota": "Cabernet Sauvignon y Cabernet Franc arrancados"},
        {"concepto": "Superficie productiva del predio", "ha": ha_antes_arrendar,
         "nota": "Subtotal"},
        {"concepto": "Menos cuarteles arrendados", "ha": round(-ha_arrendados, 2),
         "nota": "5174 (Candy Hearts) y 5133 (Sweet Celebration), arrendados a terceros"},
        {"concepto": "Superficie productiva modelada", "ha": supuestos["superficie_modelada"],
         "nota": "Base de todo el modelo financiero"},
    ]

    salida = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": libro.name,
        "escenario": {"id": esc["id"], "nombre": esc["nombre"], "nota": esc["nota"],
                      "archivo": esc["salida"]},
        "escenarios": [{"id": e["id"], "nombre": e["nombre"], "nota": e["nota"],
                        "archivo": e["salida"]} for e in ESCENARIOS],
        "moneda": "US$",
        "temporadas": temporadas,
        "supuestos": supuestos,
        "conciliacion_superficie": conciliacion,
        "totales": totales,
        "cosechas": cosechas,
        "por_especie": sorted(por_especie.values(), key=lambda e: -e["ha"]),
        "variedades": sorted(variedades.values(), key=lambda r: (r["especie"], -r["ha"])),
        "avisos": {
            "produccion_incoherente": sorted(
                "%s / %s" % (r["especie"], r["variedad"])
                for r in variedades.values() if not r["produccion_coherente"]),
            "precio_distinto": sorted(
                "%s / %s (%s)" % (r["especie"], r["variedad"], ", ".join(r["temporadas_otro_precio"]))
                for r in variedades.values() if r.get("temporadas_otro_precio")),
            "variedades_sin_cuartel": sorted(r["variedad"] for r in variedades.values() if not r["cuarteles"]),
            "cuarteles_sin_modelo": sorted(set(sin_modelo)),
            "arrendados": ["%s (%s)" % (c, ARRENDADOS[c]["variedad"]) for c in sorted(ARRENDADOS)],
            "ha_detalle_plantaciones": ha_tasacion,
            "inputs_faltantes": faltantes,
            "cosecha": avisos_cosecha,
        },
    }

    destino = RAIZ / esc["salida"]
    anterior = None
    if destino.exists():
        try:
            anterior = json.loads(destino.read_text(encoding="utf-8"))
        except ValueError:
            pass
    destino.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("OK %s" % destino)
    print("  variedades=%d  ha=%s  temporadas=%d" % (len(variedades), ha_total, len(temporadas)))
    print("  cosecha real  %s" % "  ".join(
        "%s %s t" % (t, format(round(k / 1000), ",d"))
        for t, k in zip(cosechas["temporadas"], cosechas["kg"])))

    malas = avisos_cosecha["rend_es_total"]
    if malas:
        print("")
        print("  !! REVISAR EL LIBRO: 'Inputs Generales', columna Rendimiento 25/26")
        print("     Estas celdas traen los KILOS TOTALES de la temporada y no los")
        print("     kilos por hectarea. El modelo las multiplica por la superficie,")
        print("     asi que la temporada 2025-2026 queda inflada por ese factor.")
        for m in malas:
            print("       %-22s celda %-10s deberia ser %-8s (x%s ha)"
                  % (m["variedad"], format(m["celda"], ",d"),
                     format(m["rendimiento_real"], ",d"), m["factor"]))
            if m["ingreso_modelado"] is not None and m["ingreso_implicado"] is not None:
                print("         ingresos 25/26 modelados US$ %s  vs US$ %s implicados por la cosecha"
                      % (format(m["ingreso_modelado"], ",d"), format(m["ingreso_implicado"], ",d")))
        exceso = sum((m["ingreso_modelado"] or 0) - (m["ingreso_implicado"] or 0) for m in malas)
        print("     Exceso de ingresos en 2025-2026: US$ %s" % format(round(exceso), ",d"))
    print("  EBITDA %s: US$ %s  (%s US$/ha)" % (temporadas[0], format(totales["ebitda"][0], ",d"), totales["ebitda_ha"][0]))
    print("  EBITDA %s: US$ %s  (%s US$/ha)" % (temporadas[3], format(totales["ebitda"][3], ",d"), totales["ebitda_ha"][3]))
    for k, v in salida["avisos"].items():
        print("  %-26s %s" % (k, v))
    if faltantes:
        print("")
        print("  ATENCION: estas variedades estan en 'Consolidado por variedad' pero NO en la")
        print("  tabla de supuestos de 'Inputs Generales'. Se dibujan con los numeros que hay,")
        print("  pero sin precio, rendimiento ni costos unitarios:")
        for k in faltantes:
            print("    - %s" % k)
    reportar_cambios(anterior, salida)
    return salida


def cotejar_escenarios(salidas):
    """Los escenarios tienen que describir el mismo campo.

    El mapa dibuja una sola geometria, una sola leyenda y un solo arbol de
    especies, y los comparte entre escenarios. Si uno agregara una variedad,
    la sacara o le cambiara la superficie, al cambiar de escenario el mapa
    seguiria pintando el arbol del primero y los totales dejarian de cuadrar sin
    que nada lo dijera. Se compara y se detiene.
    """
    base_id, base = salidas[0]
    ref = {(v["especie"], v["variedad"]): v["ha"] for v in base["variedades"]}
    problemas = []
    for otro_id, otro in salidas[1:]:
        aca = {(v["especie"], v["variedad"]): v["ha"] for v in otro["variedades"]}
        for k in sorted(set(ref) - set(aca)):
            problemas.append("%s: falta %s / %s" % (otro_id, k[0], k[1]))
        for k in sorted(set(aca) - set(ref)):
            problemas.append("%s: sobra %s / %s" % (otro_id, k[0], k[1]))
        for k in sorted(set(ref) & set(aca)):
            if abs((ref[k] or 0) - (aca[k] or 0)) > 0.005:
                problemas.append("%s: %s / %s tiene %.2f ha y en %s tiene %.2f"
                                 % (otro_id, k[0], k[1], aca[k], base_id, ref[k]))
        if len(otro["temporadas"]) != len(base["temporadas"]):
            problemas.append("%s: %d temporadas y %s tiene %d"
                             % (otro_id, len(otro["temporadas"]), base_id, len(base["temporadas"])))
    if problemas:
        raise SystemExit(
            "Los escenarios no describen el mismo campo, y el mapa los dibuja\n"
            "sobre una sola geometria y una sola leyenda.\n\n  "
            + "\n  ".join(problemas[:20])
            + "\n\nHay que cuadrar los libros antes de publicar.")


def main():
    # Un libro suelto por linea de comandos sigue funcionando: se procesa como
    # el escenario que manda, que es lo que hacia este script antes.
    if len(sys.argv) > 1:
        esc = dict(ESCENARIOS[0])
        esc["libro"] = Path(sys.argv[1]).name
        procesar(esc, escribir_geo=True)
        return

    salidas = []
    for i, esc in enumerate(ESCENARIOS):
        salidas.append((esc["id"], procesar(esc, escribir_geo=(i == 0))))

    cotejar_escenarios(salidas)

    print("")
    print("=" * 70)
    print("COMPARACION ENTRE ESCENARIOS  (temporada de plena produccion)")
    print("=" * 70)
    base_id, base = salidas[0]
    i = min(3, len(base["temporadas"]) - 1)
    print("  %-14s %14s %14s %14s %14s" % ("escenario", "produccion kg", "ingresos", "costos", "EBITDA"))
    for esc_id, sal in salidas:
        esc_id = "escenario " + esc_id
        t = sal["totales"]
        print("  %-14s %14s %14s %14s %14s"
              % (esc_id, format(t["kg"][i], ",d"), format(t["ingresos"][i], ",d"),
                 format(t["costos"][i], ",d"), format(t["ebitda"][i], ",d")))
    t0 = base["totales"]
    for esc_id, sal in salidas[1:]:
        t = sal["totales"]
        print("  %-14s %13s%% %13s%% %13s%% %13s%%"
              % ("vs escen. " + base_id,
                 *["%+.1f" % ((t[c][i] / t0[c][i] - 1) * 100) if t0[c][i] else "s/d"
                   for c in ("kg", "ingresos", "costos", "ebitda")]))


if __name__ == "__main__":
    main()
