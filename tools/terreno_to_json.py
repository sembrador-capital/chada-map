# -*- coding: utf-8 -*-
"""Calcula pendiente, exposicion y elevacion de cada cuartel desde el DEM.

Descarga los tiles Terrain-RGB de Mapbox que cubren el predio, los arma en una
sola grilla de elevacion, calcula la pendiente por el metodo de Horn y resume
cada poligono del KMZ. Escribe el resultado dentro de geo_data.json.

Decisiones que cambian el numero, explicitas:

  ZOOM 14 (~7,9 m/px a esta latitud). El tile z15 existe, pero el dato de
  origen en la zona ronda los 30 m: bajar a 4 m/px no agrega informacion,
  solo interpola, y la pendiente sale mas suave de lo que es.

  PASO 2. La ventana de Horn no toma pixeles contiguos sino de dos en dos, asi
  la base del gradiente queda en ~32 m, del orden de la resolucion real del
  DEM. Con pixeles contiguos la pendiente se calcula sobre una interpolacion y
  aparece ruido que no esta en el terreno.

  La pendiente se informa en PORCENTAJE (desnivel sobre distancia horizontal),
  que es como se habla en campo, no en grados. 100% son 45 grados.

Mercator es conforme, asi que la escala local es la misma en x y en y: una
sola resolucion de celda sirve para ambos ejes.
"""
import io
import json
import math
import re
import os
import sys
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
GEO = RAIZ / "geo_data.json"
ZOOM = 14
PASO = 2
TILE = 256
MARGEN_TILES = 1
FUENTES = [
    "https://api.mapbox.com/v4/mapbox.terrain-rgb/{z}/{x}/{y}.pngraw",
    "https://api.mapbox.com/v4/mapbox.mapbox-terrain-dem-v1/{z}/{x}/{y}.pngraw",
]
RUMBOS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]

# Clases de pendiente con las que se habla de un cuartel frutal.
CLASES = [
    (2, "Plano"), (5, "Suave"), (10, "Moderada"),
    (15, "Fuerte"), (25, "Muy fuerte"), (float("inf"), "Escarpada"),
]


def token():
    t = os.environ.get("MAPBOX_TOKEN")
    if t:
        return t
    # Una sola copia del token en el repo: la del mapa.
    m = re.search(r"pk\.ey[\w\-.]+", (RAIZ / "index.html").read_text(encoding="utf-8"))
    if not m:
        sys.exit("No encontre el token de Mapbox: define MAPBOX_TOKEN o dejalo en index.html")
    return m.group(0)


def lonlat_a_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    return x, y


def descargar(z, x, y, tk, sesion):
    for plantilla in FUENTES:
        url = plantilla.format(z=z, x=x, y=y)
        r = sesion.get(url, params={"access_token": tk}, timeout=30)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        if r.status_code in (401, 403):
            sys.exit("Mapbox rechazo el token (%d) en %s" % (r.status_code, url))
    return None


def grilla_elevacion(bbox, tk):
    """Mosaico de elevacion que cubre el bbox, con margen de un tile."""
    x0f, y1f = lonlat_a_tile(bbox[0], bbox[3], ZOOM)     # noroeste
    x1f, y0f = lonlat_a_tile(bbox[2], bbox[1], ZOOM)     # sureste
    tx0, tx1 = int(math.floor(x0f)) - MARGEN_TILES, int(math.floor(x1f)) + MARGEN_TILES
    ty0, ty1 = int(math.floor(y1f)) - MARGEN_TILES, int(math.floor(y0f)) + MARGEN_TILES

    ancho, alto = (tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE
    mosaico = np.full((alto, ancho, 3), np.nan, dtype=np.float64)

    sesion = requests.Session()
    faltantes = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            img = descargar(ZOOM, tx, ty, tk, sesion)
            if img is None:
                faltantes += 1
                continue
            a = np.asarray(img, dtype=np.float64)
            if a.shape[0] != TILE:                       # por si viniera @2x
                img = img.resize((TILE, TILE), Image.BILINEAR)
                a = np.asarray(img, dtype=np.float64)
            fy, fx = (ty - ty0) * TILE, (tx - tx0) * TILE
            mosaico[fy:fy + TILE, fx:fx + TILE] = a

    if faltantes:
        print("  aviso: %d tiles sin respuesta" % faltantes)

    # Codificacion Mapbox: altura = -10000 + (R*65536 + G*256 + B) * 0,1
    elev = -10000.0 + (mosaico[:, :, 0] * 65536.0 + mosaico[:, :, 1] * 256.0 + mosaico[:, :, 2]) * 0.1
    return elev, tx0, ty0


def pendiente_y_exposicion(elev, lat_media):
    """Horn 3x3 con paso PASO. Devuelve (pendiente %, exposicion en grados)."""
    res = 156543.03392 * math.cos(math.radians(lat_media)) / (2 ** ZOOM)   # m/px
    base = 8.0 * res * PASO
    p = PASO
    z = elev

    # a b c / d e f / g h i, con las filas creciendo hacia el SUR.
    a, b, c = z[:-2 * p, :-2 * p], z[:-2 * p, p:-p], z[:-2 * p, 2 * p:]
    d, f    = z[p:-p,    :-2 * p], z[p:-p,    2 * p:]
    g, h, i = z[2 * p:,  :-2 * p], z[2 * p:,  p:-p], z[2 * p:,  2 * p:]

    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / base          # positivo: sube al este
    dzdy = ((a + 2 * b + c) - (g + 2 * h + i)) / base          # positivo: sube al norte

    pend = np.hypot(dzdx, dzdy) * 100.0
    # Exposicion: hacia donde MIRA la ladera, o sea cuesta abajo. Grados desde
    # el norte, en sentido horario.
    expo = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360.0) % 360.0

    # Se vuelve al tamano original rellenando el borde, para que los indices de
    # pixel sigan valiendo para las tres grillas.
    pend_full = np.full_like(z, np.nan)
    expo_full = np.full_like(z, np.nan)
    pend_full[p:-p, p:-p] = pend
    expo_full[p:-p, p:-p] = expo
    return pend_full, expo_full


def anillos(feature):
    geom = feature["geometry"]
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def mascara(poligonos, tx0, ty0, ventana):
    """Rasteriza el poligono en la ventana dada. Los anillos interiores restan."""
    x0, y0, w, h = ventana
    img = Image.new("L", (w, h), 0)
    dib = ImageDraw.Draw(img)
    for rings in poligonos:
        for k, ring in enumerate(rings):
            pts = []
            for lon, lat in ring:
                fx, fy = lonlat_a_tile(lon, lat, ZOOM)
                pts.append(((fx - tx0) * TILE - x0, (fy - ty0) * TILE - y0))
            if len(pts) >= 3:
                dib.polygon(pts, fill=0 if k else 1)
    return np.asarray(img, dtype=bool)


def clase(p):
    for limite, nombre in CLASES:
        if p < limite:
            return nombre
    return CLASES[-1][1]


def main():
    tk = token()
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    bbox = geo["bbox"]
    lat_media = (bbox[1] + bbox[3]) / 2.0

    print("Descargando DEM z%d..." % ZOOM)
    elev, tx0, ty0 = grilla_elevacion(bbox, tk)
    if np.all(np.isnan(elev)):
        sys.exit("No se pudo armar la grilla de elevacion")
    pend, expo = pendiente_y_exposicion(elev, lat_media)
    res = 156543.03392 * math.cos(math.radians(lat_media)) / (2 ** ZOOM)
    print("  grilla %dx%d px · %.2f m/px · base del gradiente %.1f m"
          % (elev.shape[1], elev.shape[0], res, 2 * PASO * res))

    alto, ancho = elev.shape
    sin_pixeles = []
    for f in geo["cuarteles"]["features"]:
        polis = anillos(f)
        xs, ys = [], []
        for rings in polis:
            for lon, lat in rings[0]:
                fx, fy = lonlat_a_tile(lon, lat, ZOOM)
                xs.append((fx - tx0) * TILE); ys.append((fy - ty0) * TILE)
        x0, x1 = max(0, int(min(xs)) - 1), min(ancho, int(max(xs)) + 2)
        y0, y1 = max(0, int(min(ys)) - 1), min(alto, int(max(ys)) + 2)
        if x1 <= x0 or y1 <= y0:
            sin_pixeles.append(f["properties"]["nombre"]); continue

        m = mascara(polis, tx0, ty0, (x0, y0, x1 - x0, y1 - y0))
        ep = elev[y0:y1, x0:x1]; pp = pend[y0:y1, x0:x1]; xp = expo[y0:y1, x0:x1]
        val = m & ~np.isnan(pp)

        # Un cuartel chico puede no atrapar ningun centro de pixel. En vez de
        # dejarlo sin dato se toma el pixel de su centroide: es el mismo DEM,
        # solo que con una muestra.
        if val.sum() == 0:
            cx, cy = f["properties"]["centro"]
            fx, fy = lonlat_a_tile(cx, cy, ZOOM)
            px, py = int((fx - tx0) * TILE), int((fy - ty0) * TILE)
            if not (0 <= px < ancho and 0 <= py < alto) or np.isnan(pend[py, px]):
                sin_pixeles.append(f["properties"]["nombre"]); continue
            muestras_p = np.array([pend[py, px]]); muestras_e = np.array([elev[py, px]])
            muestras_x = np.array([expo[py, px]]); n = 0
        else:
            muestras_p, muestras_e, muestras_x = pp[val], ep[val], xp[val]
            n = int(val.sum())

        # La exposicion es circular: promediarla como numero daria norte donde
        # hay este y oeste. Se promedian vectores unitarios ponderados por la
        # pendiente, que es lo que le da sentido a una orientacion.
        rad = np.radians(muestras_x)
        peso = np.clip(muestras_p, 0, None)
        sx, sy = float(np.sum(np.sin(rad) * peso)), float(np.sum(np.cos(rad) * peso))
        if sx == 0 and sy == 0:
            rumbo, expo_grados = None, None
        else:
            expo_grados = round((math.degrees(math.atan2(sx, sy)) + 360) % 360, 1)
            rumbo = RUMBOS[int((expo_grados + 22.5) % 360 // 45)]

        media = float(np.mean(muestras_p))
        p = f["properties"]
        p["pendiente"] = round(media, 1)
        p["pendiente_p90"] = round(float(np.percentile(muestras_p, 90)), 1)
        p["pendiente_clase"] = clase(media)
        p["elev"] = round(float(np.mean(muestras_e)))
        p["elev_min"] = round(float(np.min(muestras_e)))
        p["elev_max"] = round(float(np.max(muestras_e)))
        p["exposicion"] = rumbo
        p["exposicion_grados"] = expo_grados
        p["dem_px"] = n

    feats = [f["properties"] for f in geo["cuarteles"]["features"] if "pendiente" in f["properties"]]
    geo["terreno"] = {
        "fuente": "Mapbox Terrain-RGB",
        "zoom": ZOOM,
        "resolucion_m": round(res, 2),
        "base_gradiente_m": round(2 * PASO * res, 1),
        "metodo": "Horn 3x3, pendiente en % (desnivel/distancia horizontal)",
        "cuarteles_con_dato": len(feats),
        "pendiente_min": round(min(p["pendiente"] for p in feats), 1),
        "pendiente_max": round(max(p["pendiente"] for p in feats), 1),
        "elev_min": min(p["elev_min"] for p in feats),
        "elev_max": max(p["elev_max"] for p in feats),
    }

    GEO.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK %s" % GEO)
    print("  cuarteles con dato: %d de %d" % (len(feats), len(geo["cuarteles"]["features"])))
    print("  pendiente %.1f%% a %.1f%%  ·  elevacion %d a %d m"
          % (geo["terreno"]["pendiente_min"], geo["terreno"]["pendiente_max"],
             geo["terreno"]["elev_min"], geo["terreno"]["elev_max"]))
    if sin_pixeles:
        print("  sin dato: %s" % sin_pixeles)

    reparto = {}
    for p in feats:
        reparto[p["pendiente_clase"]] = reparto.get(p["pendiente_clase"], 0) + 1
    for _, nombre in CLASES:
        if nombre in reparto:
            print("    %-12s %3d cuarteles" % (nombre, reparto[nombre]))


if __name__ == "__main__":
    main()
