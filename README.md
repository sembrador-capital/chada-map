# Hacienda Chada: Huelquén — Mapa interactivo

Mapa de cuarteles del predio, por especie y variedad. Misma estructura y mismo
sistema de diseño que [ketcal-map](https://github.com/sembrador-capital/ketcal-map)
y el mapa de San Gerardo: los tres predios comparten producto, así que comparten
chrome, tipografía, paleta de marca y convención de datos.

Es una sola página estática. No hay build, ni dependencias instalables, ni
backend: `index.html` pide `geo_data.json` por `fetch` y dibuja sobre Mapbox GL.

---

## Qué muestra hoy

| | |
|---|---|
| Cuarteles | 174 |
| Superficie | 330,86 ha |
| Especies | 8 |
| Variedades | 26 |

Por especie:

| Especie | Cuarteles | ha | Variedades |
|---|---:|---:|---:|
| Uva de mesa | 47 | 169,80 | 10 |
| Cerezos | 19 | 57,98 | 4 |
| Uva vinífera | 94 | 54,47 | 4 |
| Disponible | 7 | 28,70 | 3 |
| Ciruelos | 2 | 13,27 | 1 |
| Paltos | 2 | 3,05 | 1 |
| Naranjos | 2 | 2,51 | 2 |
| Clementinas | 1 | 1,09 | 1 |

`Disponible` no es una especie: son los cuarteles arrancados o no productivos que
el KMZ agrupa aparte. Se mantiene como categoría propia, en gris, porque es
superficie del predio y esconderla haría que los totales no cuadren.

---

## Cómo se usa

- **Colorear por** — especie (8 colores) o variedad (26). La leyenda se repinta
  junto con el mapa: si el mapa está por especie, los puntos de variedad toman
  el color de su especie, para no prometer una distinción que el mapa no hace.
- **Leyenda** — árbol especie → variedad. Un clic en cualquier fila la enciende o
  apaga; el caret sólo pliega la rama. `Todo` / `Nada` para la selección
  completa. Las métricas de arriba a la derecha siempre se refieren a lo que
  está visible, no al predio entero.
- **Vista** — interruptores de relleno, contorno, etiquetas, panel de leyenda y
  barra de métricas; base satelital o clara; y `Ver todo el predio` para
  reencuadrar.
- **Hover** — ficha con especie, variedad, cuartel, superficie e ID interno. En
  los cuarteles mixtos se abre el detalle variedad ↔ cuartel.
- **Clic** — fija la ficha. Clic fuera o `Esc` la suelta.
- **Buscar cuartel** — por código o por `código — variedad`. Vuela al cuartel,
  lo enciende si estaba apagado y deja la ficha fijada.

---

## Estructura

```
index.html                      La aplicación completa: chrome, estilos y lógica.
geo_data.json                   Único archivo de datos. Derivado, no se edita a mano.
Hacienda Chada Huelquen.kmz     Fuente original del predio.
tools/kml_to_geojson.py         KMZ → geo_data.json.
```

### Regenerar los datos

Sólo stdlib de Python, sin dependencias:

```bash
python tools/kml_to_geojson.py
```

Toma el KMZ de la raíz y reescribe `geo_data.json`. Para otro archivo, se pasa la
ruta como argumento.

### Cómo se lee el KMZ

El KMZ viene ordenado como `Folder(especie) > Folder(variedad) > Placemark`, y el
nombre del placemark tiene la forma `<variedades> — <cuarteles>`:

- `Santina — 5220` → variedad `Santina`, cuartel `5220`.
- `Santina — 5221 (Macrotúnel)` → el paréntesis es un atributo del cuartel, no
  parte del código: sale del nombre y queda en `nota`.
- `Cheery Glow / Cheery Treat / Cheery Moon / Santina — 8203 / 8204 / 8205 / 8206`
  → cuartel mixto. Las dos listas van en paralelo y se guardan así: la variedad
  *i* corresponde al cuartel *i*. La ficha del mapa los muestra emparejados.

La superficie no viene en el KMZ: se calcula del polígono, proyectando lon/lat a
metros locales. Es una aproximación planar, suficiente a la escala de un cuartel,
pero **no reemplaza la superficie de la tasación ni la del catastro**. Cuando
llegue la base de datos con las hectáreas oficiales, el cruce manda sobre esto.

### Formato de `geo_data.json`

```jsonc
{
  "generated_at": "…", "source": "…",
  "bbox": [lon_min, lat_min, lon_max, lat_max],
  "center": [lon, lat],
  "totales": { "cuarteles": 174, "ha": 330.86, "especies": 8, "variedades": 26 },
  "por_especie": [ { "especie": "…", "cuarteles": 47, "ha": 169.8,
                     "variedades": [ { "variedad": "…", "cuarteles": 10, "ha": 38.063 } ] } ],
  "cuarteles": {
    "type": "FeatureCollection",
    "features": [ { "id": 1, "properties": {
        "uid": "C001",            // id estable, la llave para cruzar otras bases
        "nombre": "…",            // nombre crudo del placemark
        "especie": "…", "variedad": "…",
        "variedades": ["…"],      // desglose del cuartel mixto
        "cuartel": "5218-A",      // código, o los códigos unidos por " / "
        "cuarteles": ["5218-A"],
        "mixto": false, "nota": "",
        "ha": 6.42, "centro": [lon, lat]
    } } ]
  }
}
```

La llave para cruzar producción, costos o análisis es el **código de cuartel**
(`cuartel` / `cuarteles`), no `uid`: `uid` es un correlativo del orden del KMZ y
cambia si el KMZ se reordena.

---

## Pendiente

Las pestañas `Producción` y `Financiero` están en la barra, deshabilitadas. Se
muestran a propósito: la hoja de ruta es parte de la información, y una pestaña
que aparece de la nada más adelante desorienta más que una que se anuncia.

1. **Producción** — cruzar las bases de plantación y cosecha contra el código de
   cuartel: año de plantación, superficie oficial, portainjerto, marco, kg/ha por
   temporada.
2. **Financiero** — proyecciones del modelo de Chada: producciones, ingresos,
   costos y EBITDA, por cuartel y por especie.

---

## Notas técnicas

- **Mapbox GL JS 3.4**, estilos `satellite-v9` y `light-v11`. El token es público
  y está restringido por dominio; vive en `index.html` igual que en los otros dos
  mapas.
- **Paleta**. El chrome usa los colores de marca Sembrador; las especies tienen
  escala propia porque necesitan ocho colores separables sobre satelital. Cada
  variedad se deriva del color de su especie abriendo el tono en abanico y
  alternando la luminosidad: el mapa se lee primero por especie y recién después
  por variedad. El abanico se estrecha cuando hay pocas variedades, para no
  invadir el territorio de la especie vecina.
- **Colores en un solo lugar.** Fuera del bloque `:root` no hay literales de
  color en CSS. En JS los colores se leen de esos mismos tokens.
- Cambiar de base descarta fuentes y capas: el remontaje va colgado de
  `style.load`. Con `styledata` no alcanza, se emite antes de que el estilo esté
  listo y `addSource` falla.
