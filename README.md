# Hacienda Chada: Huelquén — Mapa interactivo

Mapa de cuarteles del predio cruzado con el modelo financiero: especie y
variedad, rendimiento, ingresos, costos y EBITDA por hectárea. Misma estructura
y mismo sistema de diseño que [ketcal-map](https://github.com/sembrador-capital/ketcal-map)
y el mapa de San Gerardo: los tres predios comparten producto, así que comparten
chrome, tipografía, paleta de marca y convención de datos.

Es una sola página estática. No hay build, ni dependencias instalables, ni
backend: `index.html` pide dos JSON por `fetch` y dibuja sobre Mapbox GL.

---

## La superficie: 311,65 → 301,47 → 292,23 ha

Los tres números que explican el predio, y el puente entre ellos:

| Concepto | ha | Fuente |
|---|---:|---|
| Superficie plantada según tasación | 311,65 | Tasación Comercial N° 599-2026-SIMM, pág. 15-17 |
| − Clemenules (no productivo) | −10,18 | Plantado en 1999, fuera de producción |
| **Superficie plantada** | **301,47** | |
| − Vinífera arrancada | −9,24 | Cabernet Sauvignon y Cabernet Franc |
| **Superficie productiva modelada** | **292,23** | Base de todo el modelo financiero |

**292,23 ha es la superficie de referencia de todo el mapa.** El KMZ no aporta
hectáreas y el código no las calcula: un contorno dibujado a mano no es una
medición, y mezclarlo con la tasación haría que los totales del mapa y los del
modelo no cuadren. El KMZ aporta geometría e identidad de cuartel; el modelo
aporta las hectáreas y la plata.

El KMZ sí dibuja los siete cuarteles que el modelo excluye —los arranques de
vinífera y el paño de Clemenules—, agrupados como `Disponible`. Se pintan en
gris y la ficha dice por qué no tienen contraparte: son parte de las 311,65 ha
de tasación, no de las 292,23 modeladas.

---

## Qué muestra

Tres modos, con la misma leyenda-árbol para encender y apagar cualquier rama.

**Vista general** — identidad. Colorea por especie (siete tonos) o por variedad
(el tono de su especie, escalonado en luminosidad). El mapa se lee primero por
especie y después por variedad.

**Producción** — rendimiento en kg/ha por temporada, rampa secuencial.

**Financiero** — EBITDA/ha, ingresos/ha, costos/ha o margen EBITDA, por
temporada. EBITDA y margen usan una escala divergente en torno a cero: rojo bajo
cero, azul sobre cero.

En Producción y Financiero se abre el panel **Modelo**, con:

- los KPI de la temporada, sobre lo que esté encendido en la leyenda;
- un gráfico con dos vistas: la serie 2025-2046 de ingresos, costos y EBITDA, y
  el ranking de EBITDA/ha por variedad, con los mismos cortes y colores que el
  mapa;
- la tabla por variedad, ordenable, que además es la lectura alternativa
  obligatoria para los colores que no alcanzan 3:1 de contraste;
- la conciliación de superficie y los avisos de calidad de datos.

La ficha del cuartel —al pasar el cursor, clic para fijarla— trae especie,
variedad, superficie del modelo, rendimiento, ingresos, costos, EBITDA y margen
de la temporada elegida, más año de plantación, portainjerto, marco y plantas/ha
de la tasación. En los cuarteles mixtos desglosa cada variedad con su cuartel y
su EBITDA/ha.

---

## Hallazgos sobre los datos

Dos cosas que el cruce dejó a la vista. Ninguna se corrige en silencio: las dos
salen en el panel y en la ficha del cuartel.

**1. El bloque PRODUCCIÓN de Uva Vinífera está corrido una fila.** En
`Consolidado por variedad`, la fila de Cabernet Franc lleva la producción de
Cabernet Sauvignon, la de Sauvignon la de Carmenere, la de Carmenere la de Petit
Verdot, y la de Petit Verdot carga el total de la especie. Sin corregir, el mapa
pondría Cabernet Sauvignon en 74 kg/ha en plena producción.

Ingresos, costos y EBITDA **no** están afectados: cuadran con ha × rendimiento
de `Inputs Generales` en las cuatro variedades, así que el error es sólo de ese
bloque y no toca la plata. El pipeline lo detecta despejando la producción desde
los ingresos y el precio efectivo, compara contra el libro, y donde no cuadra
usa la serie despejada. Las otras 29 variedades calzan dentro del 2%.

**2. Dos variedades del modelo no tienen polígono en el KMZ:** `Red Globe`
(2,94 ha) y `Lapins Injerto` (0,46 ha). Suman en los totales del modelo pero no
se pueden pintar, así que el mapa encendido al 100% muestra 288,83 de las 292,23
ha — el 99%. Si aparecen en una versión futura del KMZ, se cruzan solas por el
nombre.

Hay además **un cruce aproximado**: el cuartel 8205 va rotulado `Cheery Moon` en
el KMZ y el modelo no tiene esa variedad; tiene `Cheery Treat Injerto.`, que en
la tasación figura plantada en 2023 sobre portainjerto «Maxma 14 - Ch Moon». Se
cruzan como el mismo bloque y el cuartel queda marcado en su ficha. Es el único
de los 174.

---

## Estructura

```
index.html                      La aplicación completa: chrome, estilos y lógica.
geo_data.json                   Geometría e identidad de cuartel. Derivado, no se edita.
modelo_data.json                Superficie, producción, ingresos, costos y EBITDA.
Hacienda Chada Huelquen.kmz     Fuente geográfica.
tools/kml_to_geojson.py         KMZ → geo_data.json.
tools/modelo_to_json.py         Modelo financiero → modelo_data.json (y cruce al KMZ).
datos_fuente/                   El .xlsx del modelo. Ignorado por git.
```

### Regenerar

El orden importa: `modelo_to_json.py` lee `geo_data.json` y le escribe encima el
cruce de cada cuartel contra el modelo.

```bash
python tools/kml_to_geojson.py && python tools/modelo_to_json.py
```

`kml_to_geojson.py` sólo usa stdlib. `modelo_to_json.py` necesita `openpyxl`.

El libro trae 8.338 nombres definidos y al menos uno apunta a `#N/A`, lo que hace
que openpyxl se niegue a abrirlo; el script reescribe una copia sin el bloque
`<definedNames>` antes de leer y deja el resto intacto.

### Cómo se lee el KMZ

Viene ordenado como `Folder(especie) > Folder(variedad) > Placemark`, y el nombre
del placemark tiene la forma `<variedades> — <cuarteles>`:

- `Santina — 5220` → variedad `Santina`, cuartel `5220`.
- `Santina — 5221 (Macrotúnel)` → el paréntesis es un atributo del cuartel, no
  parte del código: sale del nombre y queda en `nota`. El macrotúnel es una
  variedad aparte en el modelo —otro precio, otro CapEx—, así que esa nota es la
  que decide el cruce.
- `Cheery Glow / Cheery Treat / Cheery Moon / Santina — 8203 / 8204 / 8205 / 8206`
  → cuartel mixto. Las dos listas van en paralelo: la variedad *i* corresponde al
  cuartel *i*.

### Cómo se pinta un cuartel mixto

El mapa pinta una celda por polígono, pero un cuartel mixto lleva varias
variedades. El valor que se pinta es el promedio de esas variedades ponderado por
**la superficie que el modelo les asigna** —nunca por el área del polígono—. El
margen no se promedia como razón: se recompone como EBITDA sobre ingresos, que es
lo que significa. La ficha desglosa cada variedad por separado.

### La llave del cruce

El **código de cuartel** (`5218-A`, `8203`, …) para lo geográfico, y el par
**(especie, variedad)** para lo financiero. `uid` es un correlativo del orden del
KMZ y cambia si el KMZ se reordena: no sirve como llave entre fuentes.

---

## Notas técnicas

- **Mapbox GL JS 3.4**, estilos `satellite-v9` y `light-v11`. **Chart.js 4.4**
  para el gráfico. El token de Mapbox es público (`pk.*`), está pensado para
  vivir en el cliente y es el mismo de los otros dos mapas.
- **Colores en un solo lugar.** Fuera del bloque `:root` no hay literales de
  color en CSS, y en JS se leen de esos mismos tokens.
- **Marca y dato no comparten tokens.** El chrome usa la paleta Sembrador; las
  escalas de dato son propias y están validadas con el validador de paletas
  (seis chequeos, simulación de daltonismo Machado-Oliveira-Fernandes):
  - las cuatro rampas —los dos brazos del divergente de EBITDA, el secuencial de
    costos y el de ingresos/rendimiento— pasan los cuatro chequeos ordinales;
  - las tres series del gráfico pasan los seis chequeos en pares
    todos-contra-todos;
  - las siete ranuras de especie pasan en pares **adyacentes**. En pares
    todos-contra-todos —que es lo que exige un mapa, donde cualquier par de
    polígonos puede quedar vecino— siete colores no pasan, y ninguna
    reordenación los salva: el tope del método son tres. La reserva es el
    encoding secundario, que este mapa trae completo: etiqueta de cuartel sobre
    el polígono, ficha con especie y variedad escritas, leyenda con el nombre
    junto al color, filtro por rama y la tabla del panel.
- **Las variedades no reciben tonos nuevos:** toman el de su especie y se
  escalonan en luminosidad. Con más de cinco variedades en una especie los pasos
  quedan bajo el ΔL de 0,06 que pide una rampa ordinal; ahí el color deja de
  bastar por sí solo y carga el mismo encoding secundario.
- **Sin modo oscuro**, igual que Ketcal y San Gerardo.
- Cambiar de base descarta fuentes y capas: el remontaje va colgado de
  `style.load`. Con `styledata` no alcanza, se emite antes de que el estilo esté
  listo y `addSource` falla.
- El relleno del encuadre se calcula contra el ancho real del mapa. Con el panel
  abierto el mapa baja a ~700 px y un relleno fijo de 300 px se comía más de la
  mitad: ahí Mapbox deja de encuadrar.
