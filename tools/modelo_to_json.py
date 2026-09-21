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
    for _, letra, _, esperado in CAMPOS_VARIEDAD:
        texto = norm(" ".join(str(cabecera[idx(letra)] or "").split()))
        if norm(esperado) not in texto:
            sys.exit(
                "La columna %s de la tabla de supuestos dice '%s' y se esperaba '%s'.\n"
                "Parece que se insertaron o movieron columnas: revisa la hoja antes de seguir."
                % (letra, cabecera[idx(letra)], esperado))

    por_variedad = {}
    for f in filas[i_cab + 1:]:
        especie, variedad = f[1], f[2]
        if not especie or not variedad:
            break                      # la tabla termina en la primera fila sin variedad
        reg = {}
        for nombre, letra, nd, _ in CAMPOS_VARIEDAD:
            v = f[idx(letra)]
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
    for row in filas[i_cab + 1:]:
        especie, variedad, desde, hasta, ha, plantas, p23, p24, p25 = row[:9]
        if not especie or not variedad:
            break
        out[norm(clave_modelo(especie, variedad))] = {
            "anio_desde": desde, "anio_hasta": hasta,
            "ha_ficha": num(ha, 3), "plantas": num(plantas, 0),
            "prod_23_24": num(p23, 0), "prod_24_25": num(p24, 0), "prod_25_26": num(p25, 0),
        }
    return out


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


def main():
    libro = Path(sys.argv[1]) if len(sys.argv) > 1 else LIBRO
    wb = abrir_libro(libro)

    temporadas, variedades = leer_consolidado(wb["Consolidado por variedad"])
    # El largo lo manda el libro, no una constante: si el modelo cambia de
    # horizonte, el JSON lo sigue sin que nadie tenga que tocar el script.
    N_TEMPORADAS = len(temporadas)
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
            # Campos vacios en vez de ausentes: el mapa lee estos nombres y una
            # variedad a medio definir tiene que dibujarse igual, no romper.
            for campo, _l, _n, _t in CAMPOS_VARIEDAD:
                reg.setdefault(campo, None)
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
        # reg.get y no reg[...]: una variedad agregada al Consolidado pero no a
        # la tabla de supuestos llega hasta aca sin estos campos, y reventar con
        # un KeyError no le dice a nadie que le falta una fila en otra hoja. Se
        # sigue adelante con lo que hay y la variedad queda listada en
        # inputs_faltantes, que se avisa al final.
        px = reg.get("pct_export")
        px = px if px is not None else 1
        precio = (reg.get("precio_export") or 0) * px             + (reg.get("precio_interno_clp") or 0) / supuestos["tipo_cambio"] * (1 - px)
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
    anterior = None
    if destino.exists():
        try:
            anterior = json.loads(destino.read_text(encoding="utf-8"))
        except ValueError:
            pass
    destino.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("OK %s" % destino)
    print("  variedades=%d  ha=%s  temporadas=%d" % (len(variedades), ha_total, len(temporadas)))
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


if __name__ == "__main__":
    main()
