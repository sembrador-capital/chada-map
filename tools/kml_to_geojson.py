# -*- coding: utf-8 -*-
"""Convierte el KMZ de Hacienda Chada (Huelquen) en geo_data.json.

El KMZ viene ordenado como Folder(especie) > Folder(variedad) > Placemark(poligono).
El nombre del placemark tiene la forma "<variedades> - <cuarteles>", separados por
un guion largo. Cuando el cuartel es mixto, ambos lados traen varios valores
separados por "/" y se mantienen en paralelo.

El KMZ aporta geometria e identidad de cuartel, y nada mas: NO se emite ninguna
superficie derivada del poligono. Las hectareas del predio son las del modelo
financiero (292,23 ha productivas), que vienen de la ficha tecnica y la
tasacion. El area del poligono se calcula solo para ponderar el centroide, que
es donde se ancla la etiqueta del cuartel.
"""
import datetime
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

KML_NS = "{http://www.opengis.net/kml/2.2}"
DASH = re.compile(r"\s+[–—]\s+")


def tag(el):
    return el.tag.split("}")[-1]


def child_text(el, name):
    node = el.find(KML_NS + name)
    return node.text.strip() if node is not None and node.text else ""


def ring_coords(text):
    pts = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) >= 2:
            pts.append([round(float(parts[0]), 7), round(float(parts[1]), 7)])
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def polygons(placemark):
    """Devuelve una lista de poligonos: cada uno [anillo_exterior, *interiores]."""
    out = []
    for poly in placemark.iter(KML_NS + "Polygon"):
        rings = []
        outer = poly.find(KML_NS + "outerBoundaryIs/" + KML_NS + "LinearRing/" + KML_NS + "coordinates")
        if outer is None or not outer.text:
            continue
        rings.append(ring_coords(outer.text))
        for inner in poly.findall(KML_NS + "innerBoundaryIs/" + KML_NS + "LinearRing/" + KML_NS + "coordinates"):
            if inner.text:
                rings.append(ring_coords(inner.text))
        out.append(rings)
    return out


def ring_area_m2(ring, lat0):
    """Area planar aproximada proyectando lon/lat a metros locales."""
    mx = 111320.0 * math.cos(math.radians(lat0))
    my = 110540.0
    acc = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0] * mx, ring[i][1] * my
        x2, y2 = ring[i + 1][0] * mx, ring[i + 1][1] * my
        acc += x1 * y2 - x2 * y1
    return abs(acc) / 2.0


def centroide(polys):
    """Centroide ponderado por el area de cada poligono.

    El area se usa solo como peso: no sale de esta funcion ni llega al JSON.
    """
    lats = [pt[1] for rings in polys for ring in rings for pt in ring]
    lat0 = sum(lats) / len(lats)
    area = 0.0
    cx = cy = 0.0
    for rings in polys:
        neto = ring_area_m2(rings[0], lat0) - sum(ring_area_m2(r, lat0) for r in rings[1:])
        area += neto
        ring = rings[0]
        cx += sum(p[0] for p in ring[:-1]) / (len(ring) - 1) * neto
        cy += sum(p[1] for p in ring[:-1]) / (len(ring) - 1) * neto
    if area > 0:
        cx, cy = cx / area, cy / area
    else:
        ring = polys[0][0]
        cx = sum(p[0] for p in ring) / len(ring)
        cy = lat0
    return [round(cx, 6), round(cy, 6)]


def split_name(name, folder_variedad):
    """Separa el nombre en (variedades, cuarteles, nota)."""
    parts = DASH.split(name, 1)
    izq = parts[0].strip()
    der = parts[1].strip() if len(parts) > 1 else ""

    variedades = [v.strip() for v in izq.split("/") if v.strip()]
    if not variedades:
        variedades = [folder_variedad]

    # El sufijo entre parentesis es un atributo del cuartel, no parte del codigo.
    nota = ""
    m = re.search(r"\(([^)]*)\)\s*$", der)
    if m:
        nota = m.group(1).strip()
        der = der[: m.start()].strip()

    cuarteles = [c.strip() for c in der.split("/") if c.strip()]
    return variedades, cuarteles, nota


def rings_of(feature):
    geom = feature["geometry"]
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poly in polys:
        for ring in poly:
            yield ring


def main():
    root_dir = Path(__file__).resolve().parent.parent
    default = root_dir / "Hacienda Chada Huelquen.kmz"
    kmz = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    with zipfile.ZipFile(kmz) as z:
        kml_name = next(n for n in z.namelist() if n.lower().endswith(".kml"))
        doc = ET.fromstring(z.read(kml_name))

    features = []
    seq = [0]

    def walk(node, especie, variedad):
        for el in node:
            t = tag(el)
            if t == "Folder":
                nombre = child_text(el, "name")
                if especie is None and nombre.startswith("HCH"):
                    walk(el, None, None)        # carpeta raiz del predio
                elif especie is None:
                    walk(el, nombre, None)      # carpeta de especie
                else:
                    walk(el, especie, nombre)   # carpeta de variedad
            elif t == "Placemark":
                polys = polygons(el)
                if not polys:
                    continue
                seq[0] += 1
                nombre = child_text(el, "name")
                variedades, cuarteles, nota = split_name(nombre, variedad or "")
                centro = centroide(polys)
                features.append({
                    "type": "Feature",
                    "id": seq[0],
                    "properties": {
                        "uid": "C%03d" % seq[0],
                        "nombre": nombre,
                        "especie": especie or "Sin especie",
                        "variedad": variedad or (variedades[0] if variedades else "Sin variedad"),
                        "variedades": variedades,
                        "cuartel": " / ".join(cuarteles) if cuarteles else "s/c",
                        "cuarteles": cuarteles,
                        "mixto": len(variedades) > 1,
                        "nota": nota,
                        "centro": centro,
                    },
                    "geometry": {
                        "type": "MultiPolygon" if len(polys) > 1 else "Polygon",
                        "coordinates": polys if len(polys) > 1 else polys[0],
                    },
                })

    document = doc.find(KML_NS + "Document")
    walk(document if document is not None else doc, None, None)

    pts = [p for f in features for ring in rings_of(f) for p in ring]
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    bbox = [round(min(lons), 6), round(min(lats), 6), round(max(lons), 6), round(max(lats), 6)]

    # Conteos de cuarteles, sin superficie: las hectareas las pone el modelo.
    por_especie = {}
    for f in features:
        p = f["properties"]
        esp = por_especie.setdefault(p["especie"], {"especie": p["especie"], "cuarteles": 0, "variedades": {}})
        esp["cuarteles"] += 1
        var = esp["variedades"].setdefault(p["variedad"], {"variedad": p["variedad"], "cuarteles": 0})
        var["cuarteles"] += 1

    resumen = []
    for esp in sorted(por_especie.values(), key=lambda e: -e["cuarteles"]):
        esp["variedades"] = sorted(esp["variedades"].values(), key=lambda v: -v["cuarteles"])
        resumen.append(esp)

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": kmz.name,
        "farm": {"name": "Hacienda Chada: Huelquen", "operador": "Sembrador Capital"},
        "bbox": bbox,
        "center": [round((bbox[0] + bbox[2]) / 2, 6), round((bbox[1] + bbox[3]) / 2, 6)],
        "totales": {
            "cuarteles": len(features),
            "especies": len(resumen),
            "variedades": sum(len(e["variedades"]) for e in resumen),
        },
        "por_especie": resumen,
        "cuarteles": {"type": "FeatureCollection", "features": features},
    }

    dest = root_dir / "geo_data.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK %s  cuarteles=%d" % (dest, len(features)))
    for e in resumen:
        print("  %-16s %4d cuarteles  %d variedades" % (e["especie"], e["cuarteles"], len(e["variedades"])))


if __name__ == "__main__":
    main()
