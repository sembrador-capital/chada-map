# -*- coding: utf-8 -*-
"""Cruza el plano de suelos de Hacienda Chada con los cuarteles del KMZ.

El plano ("PLANO DE TIPOS DE SUELOS POR SECTORES", Hacienda Chada S.A.) es un
PDF vectorial de una pagina, sin georreferenciar: sus sectores de suelo estan
dibujados como areas de color y la simbologia describe cada color por textura y
profundidad. No trae coordenadas.

El puente son los CODIGOS DE CUARTEL. El plano rotula sus panos con el mismo
numero que el KMZ en una parte de los casos, y esos pares comunes bastan para
ajustar una transformacion afin de la hoja a lon/lat por minimos cuadrados. El
ajuste descarta iterativamente los pares cuyo residuo se pasa de 2,5 veces la
mediana: el plano es de otra epoca -rotula Thompson Seedless y Flame- y varios
panos se redibujaron, asi que un codigo que sobrevivio no garantiza que el pano
sea el mismo.

Con la transformacion en mano, cada cuartel del KMZ se rasteriza sobre el plano
renderizado y se cuenta de que color es cada pixel que cae dentro. El resultado
es la MEZCLA de tipos de suelo del cuartel, no una etiqueta unica: un cuartel
puede cruzar dos sectores y decir lo contrario seria inventar precision.

Lo que este script NO hace: no convierte el plano en analisis de laboratorio. La
simbologia describe textura y profundidad por estratos; no hay densidad
aparente, ni retencion de humedad, ni infiltracion, ni granulometria. Eso es
otro documento.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pdfplumber
from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
GEO = RAIZ / "geo_data.json"
PLANO = RAIZ / "datos_fuente" / "Plano Chada Suelos.pdf"
DPI = 600
TOLERANCIA_COLOR = 30          # distancia maxima por canal para aceptar un color
CORTE_RESIDUO = 2.5            # veces la mediana, para descartar pares de control

# ── Simbologia del plano ───────────────────────────────────────────────────
# Colores muestreados del propio PDF y textos transcritos de la simbologia.
# El orden es el del plano (columna izquierda y despues la derecha).
SIMBOLOGIA = [
    ("S1",  "#80bf80", "Arcilloso profundo",
     "0 a 20 cm franco arcilloso; 20 cm a 150 cm arcilloso", 20, "franco arcilloso", "sin piedras"),
    ("S2",  "#80ffff", "Arcilloso con piedras angulares",
     "0 a 20 cm franco arcilloso; 20 cm a 150 cm arcilloso con piedras angulares", 20, "franco arcilloso", "piedras angulares"),
    ("S3",  "#ffbf80", "Arcilloso con escasas piedras",
     "0 a 30 cm franco arcilloso; 30 cm a 150 cm arcilloso con escasa presencia de piedras", 30, "franco arcilloso", "escasas piedras"),
    ("S4",  "#80ff80", "Arcilloso con piedras angulares (30 cm)",
     "0 a 30 cm franco arcilloso; 30 cm a 150 cm arcilloso con piedras angulares", 30, "franco arcilloso", "piedras angulares"),
    ("S5",  "#bf80bf", "Contrastes de piedra",
     "0 a 40 cm franco arcilloso; 40 cm a 150 cm contrastes de piedra", 40, "franco arcilloso", "contrastes de piedra"),
    ("S6",  "#ff80ff", "Franco limoso sobre arenoso",
     "0 a 70 cm franco limoso; 70 cm a 150 cm arenoso arcilloso, algunas piedras", 70, "franco limoso", "algunas piedras"),
    ("S7",  "#8080ff", "Franco arcilloso con piedras",
     "0 a 50 cm franco arcilloso; 50 cm a 150 cm con presencia de piedras", 50, "franco arcilloso", "presencia de piedras"),
    ("S8",  "#fefe80", "Franco sobre franco arcilloso",
     "0 a 25 cm franco; 20 cm a 70 cm franco arcilloso", 25, "franco", "sin piedras"),
    ("S9",  "#ff8080", "Franco con incrustaciones de piedra",
     "0 a 40 cm franco; 40 cm a 160 cm franco arcilloso e incrustaciones de piedras", 40, "franco", "incrustaciones"),
    ("S10", "#bfbf80", "Franco profundo",
     "0 a 50 cm franco; 50 cm a 160 cm franco arcilloso", 50, "franco", "sin piedras"),
]
# Escala de pedregosidad, de menos a mas estorbo para raiz y maquinaria.
PEDREGOSIDAD = ["sin piedras", "escasas piedras", "algunas piedras",
                "presencia de piedras", "incrustaciones", "piedras angulares",
                "contrastes de piedra"]

CODIGO = re.compile(r"^\d{4}(-\d+)?[A-Z]?$")


def hex_a_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def puntos_de_control(pg, geo):
    """Pares (codigo, punto en la hoja, punto en lon/lat) sin ambiguedad."""
    plano = {}
    for w in pg.extract_words(x_tolerance=0.6, y_tolerance=0.4):
        t = w["text"].strip()
        if CODIGO.match(t):
            plano.setdefault(t, []).append(((w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2))

    kmz = {}
    for f in geo["cuarteles"]["features"]:
        cs = f["properties"]["cuarteles"]
        if len(cs) == 1:               # solo cuarteles simples: el centroide es suyo
            kmz.setdefault(cs[0], []).append(f["properties"]["centro"])

    pares = []
    for c in sorted(set(plano) & set(kmz)):
        if len(plano[c]) == 1 and len(kmz[c]) == 1:
            pares.append((c, plano[c][0], kmz[c][0]))
    return pares


def ajustar_afin(pares):
    """Afin hoja -> lon/lat por minimos cuadrados, descartando atipicos."""
    A = np.array([[px, py, 1.0] for _, (px, py), _ in pares])
    lon = np.array([g[0] for _, _, g in pares])
    lat = np.array([g[1] for _, _, g in pares])
    lat_media = float(np.mean(lat))
    idx = np.arange(len(pares))

    for _ in range(6):
        cl, *_ = np.linalg.lstsq(A[idx], lon[idx], rcond=None)
        ca, *_ = np.linalg.lstsq(A[idx], lat[idx], rcond=None)
        err = np.hypot((A @ cl - lon) * 111320 * math.cos(math.radians(lat_media)),
                       (A @ ca - lat) * 110540)
        corte = np.median(err[idx]) * CORTE_RESIDUO
        nuevo = np.array([i for i in idx if err[i] <= corte])
        if len(nuevo) == len(idx) or len(nuevo) < 4:
            break
        idx = nuevo

    descartados = [pares[i][0] for i in range(len(pares)) if i not in idx]
    calidad = {
        "puntos_totales": len(pares),
        "puntos_usados": int(len(idx)),
        "descartados": descartados,
        "error_medio_m": round(float(err[idx].mean()), 1),
        "error_mediano_m": round(float(np.median(err[idx])), 1),
        "error_max_m": round(float(err[idx].max()), 1),
    }
    # Inversa: de lon/lat a la hoja, que es la direccion que se usa despues.
    M = np.array([[cl[0], cl[1]], [ca[0], ca[1]]])
    t = np.array([cl[2], ca[2]])
    Minv = np.linalg.inv(M)
    return (lambda lo, la: Minv @ (np.array([lo, la]) - t)), calidad


def clasificar_imagen(im):
    """Cada pixel al color de simbologia mas cercano, o 255 si no es ninguno."""
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    clases = np.full(a.shape[:2], 255, dtype=np.uint8)
    mejor = np.full(a.shape[:2], TOLERANCIA_COLOR + 1, dtype=np.int16)
    for i, (_, hx, *_rest) in enumerate(SIMBOLOGIA):
        d = np.max(np.abs(a - np.array(hex_a_rgb(hx), dtype=np.int16)), axis=2)
        mask = d < mejor
        clases[mask] = i
        mejor[mask] = d[mask]
    clases[mejor > TOLERANCIA_COLOR] = 255
    return clases


def anillos(feature):
    g = feature["geometry"]
    return [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]


def main():
    plano = Path(sys.argv[1]) if len(sys.argv) > 1 else PLANO
    if not plano.exists():
        sys.exit("No encuentro el plano en %s" % plano)

    geo = json.loads(GEO.read_text(encoding="utf-8"))
    pdf = pdfplumber.open(str(plano))
    pg = pdf.pages[0]

    pares = puntos_de_control(pg, geo)
    if len(pares) < 4:
        sys.exit("Solo %d codigos comunes entre plano y KMZ: no alcanza para georreferenciar" % len(pares))
    a_hoja, calidad = ajustar_afin(pares)
    print("Georreferenciacion: %d de %d puntos · error mediano %.0f m (max %.0f m)"
          % (calidad["puntos_usados"], calidad["puntos_totales"],
             calidad["error_mediano_m"], calidad["error_max_m"]))
    if calidad["descartados"]:
        print("  descartados: %s" % ", ".join(calidad["descartados"]))

    print("Renderizando el plano a %d dpi..." % DPI)
    im = pg.to_image(resolution=DPI).original
    escala = DPI / 72.0
    x0, y0 = pg.bbox[0], pg.bbox[1]
    a_pixel = lambda hx, hy: ((hx - x0) * escala, (hy - y0) * escala)
    clases = clasificar_imagen(im)
    alto, ancho = clases.shape

    # Escala real del plano, en metros por pixel, a partir de la afin.
    p0 = a_hoja(geo["center"][0], geo["center"][1])
    lon_por_pt = abs(np.linalg.norm(np.array(a_hoja(geo["center"][0] + 0.001, geo["center"][1])) - p0))
    m_por_px = (0.001 * 111320 * math.cos(math.radians(geo["center"][1]))) / max(lon_por_pt, 1e-9) / escala
    print("  imagen %dx%d px · %.2f m/px" % (ancho, alto, m_por_px))

    sin_dato, ambiguos = [], []
    for f in geo["cuarteles"]["features"]:
        pts = []
        for rings in anillos(f):
            for lon, lat in rings[0]:
                pts.append(a_pixel(*a_hoja(lon, lat)))
        xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
        bx0, bx1 = max(0, int(min(xs)) - 1), min(ancho, int(max(xs)) + 2)
        by0, by1 = max(0, int(min(ys)) - 1), min(alto, int(max(ys)) + 2)
        prop = f["properties"]
        if bx1 <= bx0 or by1 <= by0:
            sin_dato.append(prop["nombre"]); prop["suelo"] = None; continue

        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        dib = ImageDraw.Draw(mask)
        for rings in anillos(f):
            for k, ring in enumerate(rings):
                poly = [a_pixel(*a_hoja(lon, lat)) for lon, lat in ring]
                poly = [(x - bx0, y - by0) for x, y in poly]
                if len(poly) >= 3:
                    dib.polygon(poly, fill=0 if k else 1)
        m = np.asarray(mask, dtype=bool)
        sub = clases[by0:by1, bx0:bx1]
        val = sub[m & (sub != 255)]
        if val.size == 0:
            sin_dato.append(prop["nombre"]); prop["suelo"] = None; continue

        cuenta = np.bincount(val, minlength=len(SIMBOLOGIA))
        total = int(cuenta.sum())
        orden = np.argsort(-cuenta)
        mezcla = [{"clase": SIMBOLOGIA[i][0], "pct": round(float(cuenta[i]) / total, 3)}
                  for i in orden if cuenta[i] > 0]
        dom = SIMBOLOGIA[int(orden[0])]
        pct = float(cuenta[orden[0]]) / total
        if pct < 0.6:
            ambiguos.append(prop["cuartel"])
        prop["suelo"] = {
            "clase": dom[0], "nombre": dom[2], "descripcion": dom[3],
            "prof_cm": dom[4], "textura": dom[5], "pedregosidad": dom[6],
            "pct": round(pct, 3), "mezcla": mezcla, "px": total,
            "cobertura": round(float(val.size) / max(int(m.sum()), 1), 3),
        }

    con = [f["properties"] for f in geo["cuarteles"]["features"] if f["properties"].get("suelo")]
    reparto = {}
    for p in con:
        reparto[p["suelo"]["clase"]] = reparto.get(p["suelo"]["clase"], 0) + 1

    geo["suelos"] = {
        "fuente": "Plano de tipos de suelos por sectores · Hacienda Chada S.A.",
        "metodo": "Afin por codigos de cuartel comunes; clasificacion por color sobre el plano renderizado",
        "dpi": DPI,
        "m_por_px": round(m_por_px, 2),
        "georreferencia": calidad,
        "simbologia": [{"clase": c, "color": hx, "nombre": n, "descripcion": d,
                        "prof_cm": pr, "textura": tx, "pedregosidad": pe}
                       for c, hx, n, d, pr, tx, pe in SIMBOLOGIA],
        "pedregosidad_orden": PEDREGOSIDAD,
        "cuarteles_con_dato": len(con),
        "cuarteles_ambiguos": sorted(set(ambiguos)),
    }

    GEO.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK %s" % GEO)
    print("  cuarteles con suelo: %d de %d · %.1f m/px"
          % (len(con), len(geo["cuarteles"]["features"]), m_por_px))
    for c, _, n, *_r in SIMBOLOGIA:
        if reparto.get(c):
            print("    %-4s %-40s %3d cuarteles" % (c, n, reparto[c]))
    if ambiguos:
        print("  mezcla sin clase dominante (<60%%): %d cuarteles" % len(set(ambiguos)))
    if sin_dato:
        print("  sin cobertura del plano: %d cuarteles" % len(sin_dato))


if __name__ == "__main__":
    main()
