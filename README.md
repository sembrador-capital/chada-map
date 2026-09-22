# Hacienda Chada: Huelquén — Mapa interactivo

Mapa de cuarteles del predio cruzado con el modelo financiero: especie y
variedad, rendimiento, ingresos, costos y EBITDA por hectárea. Misma estructura
y mismo sistema de diseño que [ketcal-map](https://github.com/sembrador-capital/ketcal-map)
y el mapa de San Gerardo: los tres predios comparten producto, así que comparten
chrome, tipografía, paleta de marca y convención de datos.

Es una sola página estática. No hay build, ni dependencias instalables, ni
backend: `index.html` pide dos JSON por `fetch` y dibuja sobre Mapbox GL. Las
capas de terreno y suelo viven dentro de `geo_data.json`.

---

## La superficie: 311,65 → 292,23 → 284,02 ha

Los tres números que explican el predio, y el puente entre ellos:

| Concepto | ha | Fuente |
|---|---:|---|
| Superficie plantada según tasación | 311,65 | Tasación Comercial N° 599-2026-SIMM, pág. 15-17 |
| − Clemenules (no productivo) | −10,18 | Plantado en 1999, fuera de producción |
| **Superficie plantada** | **301,47** | |
| − Vinífera arrancada | −9,24 | Cabernet Sauvignon y Cabernet Franc |
| **Superficie productiva del predio** | **292,23** | |
| − Cuarteles arrendados | −8,21 | 5174 (Candy Hearts) y 5133 (Sweet Celebration) |
| **Superficie productiva modelada** | **284,02** | Base de todo el modelo financiero |

**284,02 ha es la superficie de referencia de todo el mapa.** El KMZ no aporta
hectáreas y el código no las calcula: un contorno dibujado a mano no es una
medición, y mezclarlo con la tasación haría que los totales del mapa y los del
modelo no cuadren. El KMZ aporta geometría e identidad de cuartel; el modelo
aporta las hectáreas y la plata.

El KMZ sí dibuja los siete cuarteles que el modelo excluye —los arranques de
vinífera y el paño de Clemenules—, agrupados como `Disponible`. Se pintan en
gris y la ficha dice por qué no tienen contraparte: son parte de las 311,65 ha
de tasación, no de las 284,02 modeladas.

**Dos cuarteles están arrendados a terceros** —el 5174 (Candy Hearts, 3,80 ha) y
el 5133 (Sweet Celebration, 4,41 ha)—. El negocio no los explota, así que desde
v6 el modelo dejó de contar su superficie: es el último escalón, de 292,23 a
284,02 ha. En el mapa van en su propia rama gris, `Arrendado`, aparte de
`Disponible`, y no entran en ningún total ni en el filtro de EBITDA. El KMZ los
sigue dibujando con su variedad —la ficha la nombra— pero pintados en gris para
que se vea que están fuera del análisis. Se configuran en la tabla `ARRENDADOS`
de `tools/modelo_to_json.py`: si cambia qué se arrienda, se edita solo eso.

---

## El terreno: un campo con cerros

La mitad del predio está en pendiente, y eso explica buena parte del resto. La
vinífera son 94 paños pequeños siguiendo la curva de nivel a **538 m de media y
25,8% de pendiente**; la uva de mesa está en el plano del valle, a **436 m y
5,1%**. El campo va de **397 a 611 m**.

| Especie | Pendiente media | Elevación media |
|---|---:|---:|
| Uva vinífera | 25,8% | 538 m |
| Naranjos | 17,6% | 532 m |
| Clementinas | 13,1% | 540 m |
| Paltos | 9,7% | 544 m |
| Cerezos | 7,3% | 460 m |
| Uva de mesa | 5,1% | 436 m |
| Ciruelos | 4,4% | 443 m |

88 de los 174 cuarteles están sobre 15% de pendiente — el umbral donde cambia la
maquinaria que entra.

La pendiente **se calcula, no se estima**: `tools/terreno_to_json.py` baja los
tiles Terrain-RGB de Mapbox que cubren el predio, arma la grilla de elevación y
resume cada polígono. Tres decisiones que cambian el número, todas explícitas en
el script:

- **Zoom 14** (~7,9 m/px). El tile z15 existe, pero el dato de origen en la zona
  ronda los 30 m: bajar a 4 m/px no agrega información, sólo interpola, y la
  pendiente sale más suave de lo que es.
- **Ventana de Horn con paso 2**, o sea una base de gradiente de ~32 m, del orden
  de la resolución real del DEM. Con píxeles contiguos la pendiente se calcularía
  sobre una interpolación y aparecería ruido que no está en el terreno.
- **Porcentaje, no grados** — desnivel sobre distancia horizontal, como se habla
  en campo. 100% son 45°.

Control independiente: comparando el resultado de Horn contra desnivel sobre
ancho equivalente del cuartel, los paños planos dan 2,0–2,5% por ambos caminos y
los empinados quedan en el mismo rango de 33–48%.

La **exposición** se promedia como vector unitario ponderado por la pendiente, no
como número: promediar 350° y 10° aritméticamente daría sur donde hay norte.

En el mapa, el relieve va en dos interruptores separados dentro de *Vista*:
**sombreado del cerro** (encendido, bajo los polígonos para no ensuciar el color
del cuartel) y **relieve 3D** (apagado por defecto: al inclinar la cámara los
cuarteles del fondo se aplastan y las etiquetas se amontonan).

---

## Los suelos: un plano de papel, cruzado

El *Plano de tipos de suelos por sectores* de Hacienda Chada S.A. es un PDF
vectorial de una página, **sin georreferenciar**: los sectores están dibujados
como áreas de color y la simbología describe cada color por textura y
profundidad, en dos estratos. No trae coordenadas.

El puente son los **códigos de cuartel**. El plano rotula sus paños con el mismo
número que el KMZ en 20 casos, y con esos pares se ajusta una transformación afín
de la hoja a lon/lat por mínimos cuadrados. El ajuste descarta los pares cuyo
residuo se pasa de 2,5 veces la mediana —el plano es de otra época, rotula
Thompson Seedless y Flame, y varios paños se redibujaron— y converge con **16 de
20 puntos y un residuo mediano de 24 m** (máximo 50 m). Con eso, cada cuartel del
KMZ se rasteriza sobre el plano y se cuenta de qué color es cada píxel adentro:
**0,88 m/px**, los 174 cuarteles con dato.

El resultado es la **mezcla** de tipos de suelo del cuartel, no una etiqueta
única. Un cuartel puede cruzar dos sectores, y decir lo contrario sería inventar
precisión: 2 cuarteles (`5144` y `5165-B`) quedan sin tipo dominante y su ficha
lo dice.

### El cruce se valida solo

La pendiente y la especie **no** entran en la clasificación de suelo, así que
sirven de control independiente. Y calzan:

| Especie | Tipos de suelo | Pendiente media |
|---|---|---:|
| Uva vinífera (94) | S3: 66 · S1: 28 — sólo los dos arcillosos | 25,8% |
| Uva de mesa (47) | repartida en los 10 tipos del valle | 5,1% |

Los suelos arcillosos del plano caen enteros sobre el cerro, y los francos y
limosos sobre el plano del valle. Nada de eso se le dijo al algoritmo.

| Tipo | Descripción | Cuarteles | Pendiente media |
|---|---|---:|---:|
| S3 | 0-30 franco arcilloso; 30-150 arcilloso con escasas piedras | 81 | 22,7% |
| S1 | 0-20 franco arcilloso; 20-150 arcilloso | 33 | 22,8% |
| S4 | 0-30 franco arcilloso; 30-150 arcilloso con piedras angulares | 13 | 8,5% |
| S8 | 0-25 franco; 20-70 franco arcilloso | 11 | 3,6% |
| S2 | 0-20 franco arcilloso; 20-150 arcilloso con piedras angulares | 9 | 14,0% |
| S9 | 0-40 franco; 40-160 franco arcilloso e incrustaciones | 9 | 2,9% |
| S6 | 0-70 franco limoso; 70-150 arenoso arcilloso | 7 | 3,3% |
| S5 | 0-40 franco arcilloso; 40-150 contrastes de piedra | 4 | 3,0% |
| S10 | 0-50 franco; 50-160 franco arcilloso | 4 | 3,4% |
| S7 | 0-50 franco arcilloso; 50-150 con presencia de piedras | 3 | 4,0% |

### Lo que el plano no es

**No es un análisis físico de laboratorio.** La simbología describe textura y
profundidad por estratos, que es información de calicata leída a ojo. No hay
densidad aparente, ni retención de humedad, ni velocidad de infiltración, ni
granulometría, ni pH, ni materia orgánica. Si aparece el estudio de suelos con
las calicatas, se cruza por cuartel igual que todo lo demás.

En el mapa, el modo **Suelos** usa **los colores del plano original**, no una
paleta nuestra: quien conoce el papel reconoce el mapa. Esa paleta viene heredada
del documento y no pasó por el validador; la reserva es la misma de siempre —
leyenda con el nombre al lado del color, ficha con la descripción completa,
etiqueta de cuartel y filtro por rama.

---

## Qué muestra

Cuatro pestañas, con la misma leyenda-árbol para encender y apagar cualquier rama.

**Vista general** — identidad. Colorea por especie (siete tonos) o por variedad
(el tono de su especie, escalonado en luminosidad y con un giro corto de tono).
El mapa se lee primero por especie y después por variedad. En *Vista ▸ Escrito
sobre el cuartel* se puede cambiar la etiqueta del polígono de código de cuartel
a **nombre de variedad**, que es lo que permite leer el predio por variedad sin
tener que ir al color; la variedad entra antes en zoom y con letra más grande,
porque «Sweet Celebration» a 9 px no se lee, se adivina.

**Producción** — se abre por dos caras, en una subpestaña.

*Proyectada (modelo)* es el rendimiento en kg/ha que el modelo asume, por
temporada. *Cosecha real* es lo que el campo efectivamente dio, de la hoja
**Fuente 2 Rendimientos**: tres temporadas, 2023/24, 2024/25 y 2025/26. Las dos
usan **la misma escala** —mismos cortes, mismos colores—, que es lo que permite
saltar de una a otra y ver de inmediato dónde la proyección le pide al campo más
de lo que ha dado.

La hoja mide por variedad, así que cada cuartel recibe el rendimiento de la suya;
un cuartel mixto recompone el suyo con los kilos de sus variedades sobre sus
hectáreas, no promediando rendimientos. La barra de métricas agrega un punto de
comparación permanente: qué porcentaje de la plena producción del modelo
representa la temporada que se está mirando (2025/26 va en 71,9%), y el gráfico
del panel marca esa plena producción con una línea de referencia. En 2024/25 el
campo la superó.

Dos detalles de la fuente, ambos visibles en el mapa:

- Las hectáreas del denominador son las que **tenían cosecha registrada** esa
  temporada, no la superficie total del predio. En 2023/24 buena parte del campo todavía
  no entraba en producción (271,28 ha), y dividir por el total daría un
  rendimiento que no es el de ningún cuartel.
- Fuente 2 lleva en una sola fila **Santina con Santina Macro Túnel** y **Cara
  Cara con Fukumoto** —sus hectáreas cuadran con la suma de las partes, que es
  lo que permite afirmar que son la misma cosa con menos detalle—. La **Ficha
  Técnica sí las separa**, así que el total de cada temporada, que lo sigue
  poniendo Fuente 2, se reparte con las proporciones de la Ficha. Por eso Cara
  Cara y Fukumoto salen distintos en el mapa —21.092 y 37.604 kg/ha en
  2025-2026— en vez de pintados del mismo color por ser vecinos en una planilla.
  El reparto se decide para el par completo y no para cada parte por su lado: si
  una mirara la Ficha y la otra cayera a superficie, las cuotas no sumarían uno
  y el total de la temporada se inflaría. Van marcadas con `*` en la tabla.

### Un solo modelo, con lugar para más

Producción y Financiero muestran **la última versión del modelo financiero**
(`Financial_Model_Hacienda_Chada_v6.xlsx`). En plena producción (2028-2029) deja
un EBITDA de **+US$ 916.776** sobre ingresos de US$ 6,81 M y costos de US$ 5,55 M.
El EBITDA total casi no se movió desde v5 (+US$ 915.146) —los dos cuarteles que
v6 saca por arriendo eran chicos y de margen parejo—, pero la superficie
modelada bajó de 292,23 a 284,02 ha. El salto grande de rentabilidad había sido
antes: v3 cerraba en −US$ 93.775, v4 en +US$ 111.833, y v4→v5 sumó casi todo el
EBITDA (ingresos +12,5% con costos planos) por el precio de exportación
escalonado —ver el hallazgo más abajo—.

La maquinaria para comparar dos modelos lado a lado sigue en pie pero apagada:
la lista `ESCENARIOS` de `tools/modelo_to_json.py` tiene una sola entrada, y el
mapa esconde el selector y la tabla comparativa cuando hay menos de dos. Para
volver a comparar basta agregar ahí la entrada del otro libro —id, nombre,
archivo de salida y nota— y correr el script; `index.html` no se toca.

### Qué superficie gana plata

Financiero y Producción traen un filtro por signo del EBITDA: **Todas ·
EBITDA + · EBITDA −**. En plena producción (2028-2029) las variedades con
EBITDA/ha positivo suman **193,47 ha de las 284,02**, el 68% del predio,
repartidas en 59 de los 174 paños. El resto —90,55 ha— pierde plata. Las dos
mitades suman exactamente el predio, que es la comprobación de que nada se
pierde ni se cuenta dos veces.

El signo cambia con la temporada, así que el filtro se vuelve a evaluar al
cambiarla: 68,03 ha en 2025-2026, 141,51 en 2026-2027, **190,23** en 2027-2028 y
193,47 de ahí en adelante. El salto de 2026-2027 a 2027-2028 —de 142 a 190 ha—
es el precio de exportación escalonado que el modelo aplica a la Uva de Mesa
desde 2027-2028: varias variedades cruzan a rentables ahí.

**El filtro es por variedad del modelo, no por rama de la leyenda.** Es la
diferencia entre que el total cuadre y que no: el número que se quiere
reproducir sale de la tabla del modelo, que es por variedad, y las ramas del KMZ
no calzan una a una con ella. «Cerezos / Mixtos» es **una** fila de la leyenda
con ocho variedades dentro, de las que sólo algunas ganan plata; decidiendo por
rama en vez de por variedad, esas hectáreas se perdían y el total no cuadraba
con la tabla del modelo.

Como el tamiz es por variedad y el mapa pinta paños, hay **cinco cuarteles que
llevan variedades de los dos signos** —`8201 / 8202-A` tiene Lapins (+2.055
US$/ha) y Royal Dawn (−5.092)—. El paño es uno solo y no se puede partir:
aparece, porque tiene algo que mostrar, y se pinta con el valor del cuartel
completo, que puede salir rojo dentro de un filtro de positivos. La ficha de
esos cinco lo dice con nombre y apellido.

El filtro de rentabilidad y el de la leyenda son **independientes y se
componen**: se puede pedir las positivas y después apagar Cerezos. La cabecera
de la leyenda declara los dos, y «Todo» sigue siendo la salida de cualquiera de
ellos.

El control está en **Financiero y en Producción** —las dos pestañas donde la
pregunta tiene sentido— y lo que deja puesto vale en todas: filtrar y pasar a
Suelos muestra qué suelo tienen justamente los paños que ganan plata. El cruce
más útil es con *Cosecha real*: las 193,5 ha rentables cosecharon 17.330 kg/ha
en 2025/26 contra los 24.258 que el modelo les pide en plena producción, un
**71,4%** —prácticamente lo mismo que el 72,9% del predio completo—. Con v3, las
130,5 ha rentables de entonces estaban bastante más cerca de su meta que el
predio (82,7% contra 71,9%); desde v4 esa ventaja desaparece, porque el conjunto
de variedades rentables se ensanchó y ya no es sólo el núcleo más eficiente.

El filtro mira **siempre el EBITDA del modelo**, no el de la temporada
cosechada: en *Cosecha real* el selector de temporada muestra otro eje de
tiempo, así que tanto el botón como la cabecera de la leyenda escriben contra
qué temporada se está evaluando («EBITDA + en 2028-2029»).

### La superficie que muestra la ficha

La ficha del cuartel da dos hectáreas y son cosas distintas:

- **la del modelo**, que es la de la **variedad completa** —Candy Hearts son
  16,30 ha repartidas en varios cuarteles—;
- **la del paño**, `ha_kmz`, que es el área dibujada de **ese** polígono: el
  cuartel 5174 mide 3,99 ha.

Antes sólo estaba la primera y se leía como si el paño que uno estaba tocando
midiera las 16,30. La segunda va justo debajo, rotulada «ha dibujadas» y en
gris, para que se vea que son dos cosas.

`ha_kmz` es lo **único** que el mapa deriva del contorno del KMZ, y **no entra en
ningún cálculo**: ni en totales, ni en promedios ponderados, ni en escalas de
color, ni en repartos. La razón está a la vista: sumar los 174 paños da
**330,81 ha** contra las 284,02 del modelo. Un contorno dibujado a mano no es
una medición, y mezclarlo con la tasación descuadraría todo.

### Cajas o kilos, según lo que se esté mirando

El modelo lleva la uva de mesa en **cajas de 8,2 kg** —que es como se embala, se
vende y se habla de un parrón— y todo lo demás en kilos. «22.834 kg/ha» no es un
número que nadie use para describir un cuartel de Sweet Globe.

La regla es la misma en toda la pestaña: **mientras lo que está a la vista
comparta unidad se habla en la suya, y si hay mezcla se cae a kilos**, porque
cajas y kilos no se suman ni caben en una misma escala de color. Con todo el
predio encendido el mapa va en kg/ha; apagando el resto —o con un «solo» sobre
Uva de mesa— la escala, la barra de métricas y el ranking pasan enteros a
cajas/ha, con sus propios cortes redondos (1.000 · 2.000 · 3.000 · 4.000) y no
los de kilos divididos por 8,2, que no caerían en ninguna parte reconocible.

La **ficha de un cuartel siempre habla en la unidad del modelo**, haya o no
mezcla en el resto de la pantalla: ningún paño comparte cajas con kilos —la uva
de mesa no convive con otra especie en el mismo cuartel—, así que su unidad
nunca es ambigua. En las tablas la unidad va en la fila y no en cada celda: una
etiqueta `cj` junto al nombre de la variedad, porque repetirla en tres columnas
por treinta y tres filas es ruido. Las columnas se **ordenan por el equivalente
en kilos** para que el ranking siga siendo físico: ordenadas por el número
mostrado, 4.645 cajas quedarían sobre 13.825 kilos sin que eso signifique nada.

**Financiero** — dos familias de métricas, y el modo entero sigue a la que se
elija: la barra de métricas, la tabla del panel y el ranking por variedad hablan
todos en la misma unidad, porque dos denominadores en la misma pantalla obligan
a leer la etiqueta de cada número antes de poder comparar dos.

- *Por hectárea*: EBITDA/ha, ingresos/ha, costos/ha o margen EBITDA sobre ventas.
- *Por kilo producido*: margen/kg, ingresos/kg y costos/kg.

El kilo es la unidad en que se negocia la fruta, así que es la única forma de
comparar una cereza con una parra sin que la densidad de plantación se meta en
el medio: dos variedades con el mismo costo/ha pueden tener el doble de
costo/kg si una rinde la mitad. Los kilos van siempre convertidos —la uva de
mesa se modela en cajas de 8,2 kg—, y donde no hay cosecha no hay denominador:
el valor queda vacío y no en cero, porque un cero diría «sale gratis» donde lo
que pasa es que no hay con qué dividir.

Las razones **no se promedian, se recomponen**. Un cuartel mixto lleva varias
variedades: el promedio ponderado por hectárea de dos US$/kg no es el costo de
ningún kilo, porque la variedad que más rinde aporta más kilos al total, no más
hectáreas. Cada razón declara su numerador y su denominador y cada uno se suma
por su lado. Con eso, el agregado del mapa con todo encendido reproduce exacto
los totales del modelo: 5.584.758 kg, 1,2121 de ingreso, 1,0409 de costo y
0,1084 de margen por kilo en plena producción.

EBITDA, margen sobre ventas y margen/kg usan una escala divergente en torno a
cero: rojo bajo cero, azul sobre cero.

**Suelos** — se abre por dos caras, en una subpestaña. *Tipo de suelo (físico)*
trae lo que dice el plano de la hacienda: el tipo, con su simbología, o la
profundidad del primer horizonte en una rampa ordinal propia. *Terreno* trae lo
que dice el relieve: pendiente o elevación, desde el DEM. Son el mismo cuartel
mirado de dos maneras, no dos pestañas del predio, y ninguna de las dos cambia
con la temporada.

### Un solo número por cosa

Cuando el árbol de la leyenda tiene ramas apagadas, el titular deja de ser la
superficie del predio, y eso tiene que verse: la barra de métricas pasa de decir
«292,2 · Hectáreas» a «279,4 · de 292,2 ha · 96%», la cabecera de la leyenda
avisa cuántas ramas están apagadas y el botón «Todo» se destaca como salida. Sin
eso, un filtro puesto sin querer sólo se manifiesta como un total que no cuadra.

Las hectáreas de la tabla del panel salen de las mismas ramas encendidas que la
barra de métricas. Contarlas desde los polígonos dejaba fuera las 3,4 ha de las
dos variedades sin paño dibujado, y la misma pantalla mostraba 280,62 arriba y
284,02 al lado.

Los dos JSON se piden con `cache: 'no-cache'`. La respuesta sigue siendo un 304
barato mientras el archivo no cambie, pero sin eso el navegador servía los datos
de la corrida anterior y no había manera de notarlo desde la pantalla: los
números seguían siendo coherentes entre sí, sólo que viejos.

### Encontrar una variedad en el mapa

La leyenda lista cuarenta ramas y varios nombres se repiten entre especies. Leer
«Santina» y no saber a qué parte del cerro apunta era el hueco más grande que
tenía: al pasar el cursor por una fila, **sus cuarteles se resaltan en el mapa**
con un contorno grueso, y el botón **«solo»** que aparece en la fila la deja
sola encendida —y la vuelve a soltar si ya lo estaba—. Apagar treinta y dos
variedades a mano para poder mirar una era el camino largo del mismo viaje.

El buscador tiene dos niveles de calce. El exacto dispara solo, mientras se
escribe, que es lo que pasa al elegir una sugerencia de la lista; el aproximado
—prefijo de código o de variedad— espera a `Enter`. Antes el mapa volaba en cada
tecla: escribir «5218» hacía tres viajes, uno por cada dígito a partir del
segundo, y ninguno al cuartel buscado.

Hay atajos, listados en *Vista ▸ Atajos*: `1`–`4` cambian de pestaña, `D` abre y
cierra el panel, `L` la leyenda, `F` encuadra el predio y `Esc` suelta la ficha.
No disparan cuando el foco está en un campo de texto.

### Cada pantalla muestra lo suyo

La regla es que nada se diga dos veces. Los números de cabecera viven en la barra
de métricas y no se repiten en el panel; la identidad del cuartel vive en la
cabecera de la ficha y no se repite en su cuerpo.

**La ficha del cuartel** —al pasar el cursor, clic para fijarla— trae la cabecera
con especie, cuartel y variedad, y debajo **sólo el bloque del modo activo**:
superficie y plantación en Vista general, rendimiento en Producción, ingresos y
margen en Financiero, pendiente y exposición en Terreno, tipo y textura en
Suelos. Antes apilaba los cinco bloques en todos los modos y llenaba media
pantalla con datos que nadie había pedido.

**El panel arranca cerrado.** Lo primero que se viene a ver es el mapa, y 392 px
de tablas encima de eso es una respuesta antes de que nadie haya hecho la
pregunta. Se abre con el asa de la derecha, con el botón *Datos* de la barra de
controles o con la tecla `D`.

**El panel** acompaña a las cuatro pestañas y trae dos cosas: un gráfico y una
tabla, los dos del modo activo: hectáreas por especie en Vista general, la serie
por temporada y el ranking por variedad en Producción y Financiero, el reparto
por clase de pendiente o por tipo de suelo en Suelos. El ranking grafica **la
métrica que está pintando el mapa**, no una fija: si el selector dice «Costos /
kg», mirar un ranking de EBITDA/ha al lado obliga a cambiar de pregunta entre
una mitad de la pantalla y la otra.

Los repartos de terreno y suelo se cuentan en **cuarteles**, no en hectáreas: el
DEM y el plano clasifican polígonos, y repartir las hectáreas de una variedad
entre sus cuarteles exigiría un supuesto de superficie que no tenemos. La conciliación de superficie y los avisos de calidad quedan en una
sección plegada. La tabla es además la lectura alternativa obligatoria para los
colores que no alcanzan 3:1 de contraste.

**Sólo se ofrecen las temporadas hasta plena producción** (2025-2026 a
2028-2029). De ahí en adelante las diecisiete restantes repiten exactamente el
mismo número, y ofrecerlas en un selector hacía creer que había algo que mirar.
El corte no está escrito a mano: se calcula comparando los totales temporada
contra temporada.

Los dos gráficos son de barras. La vista por temporada era una curva de
veintiún puntos que se aplanaba en el cuarto —diecisiete temporadas de línea
recta para decir que el modelo asume plena producción—; en barras agrupadas y
sólo con las temporadas que cambian se ve de una cuánto sube el EBITDA y cuánto
de los ingresos se lleva el costo. El rango del eje se calcula en vez de
dejárselo al automático: con pasos gruesos, un EBITDA de −0,17 M arrastraba el
eje hasta −2 M y dejaba en blanco un quinto del gráfico. Y el paso calculado es
el que manda: `maxTicksLimit` lo pisa y deja que Chart.js invente el suyo, que
en el ranking por kilo salía con cortes como −0,80 y −0,35.

### La barra de controles cabía en una fila y se partía igual

La barra flotante de controles se partía en dos filas —con «Vista» sola abajo—
por ancha que fuera la ventana. La causa no era el contenido: es un elemento
absoluto con `left:50%` y sin `right`, y en ese caso el ancho disponible que el
navegador usa para el «shrink-to-fit» es lo que va del 50% al borde derecho, o
sea **media ventana**. Con 1.098 px de pantalla la barra se topaba en 549 px
aunque su contenido midiera 780. Se arregla con `width:max-content` y un
`max-width` que recién frena cuando de verdad no cabe. De paso se acortaron los
rótulos que sobraban —«Proyectada (modelo)» cuando arriba ya dice VER— y el
`<select>` de temporada, cuyo ancho lo manda su opción más larga.

### El chrome se acomoda midiendo, no adivinando

Dos barras flotan sobre el mapa y las dos se encimaban con algo cuando el ancho
útil bajaba. La de controles envuelve en dos filas y se montaba sobre el panel
de leyenda; la de métricas vive arriba a la derecha y, con el panel abierto,
tapaba media pestaña de «Suelos». En vez de un umbral en píxeles —que se queda
corto o sobra según el modo, porque cada uno trae distintos controles y
distintos rótulos— se miden las cajas y se mueve sólo la que de verdad se pisa.
Para que la medición valga, las tres barras dejaron de animar su posición: el
mapa ya cedía el ancho de una sola vez, así que animar el chrome hacía que el
mapa saltara y las barras llegaran 200 ms después, y peor, que se midiera la
posición vieja a mitad de la animación.

Por lo mismo, el relleno del encuadre mide **cuánto tapa el panel** en vez de
suponerlo. Bajo 1180 px el panel deja de quitarle ancho al mapa y se monta
encima: el canvas sigue midiendo lo mismo, así que «Ver todo el predio»
encuadraba contra un ancho que en pantalla no existe y dejaba el tercio oriente
—los cerezos del cerro— escondido detrás del panel.

---

## Hallazgos sobre los datos

Cuatro cosas que el cruce dejó a la vista. Ninguna se corrige en silencio: todas
salen en el panel y, donde corresponde, en la ficha del cuartel.

**Los dos primeros ya están corregidos en el libro v3, y el tercero es de v5.**
Se dejan escritos porque los controles que los detectaron siguen corriendo en
cada actualización, y porque explican por qué existen.

**0d. v5 agregó una columna en medio de la tabla de supuestos, y el script la
seguía a ciegas por posición.** `Inputs Generales` inserta *Precio exportación
27-28→* entre el precio de exportación y el precio de mercado interno, corriendo
doce columnas un lugar —costo fijo, costo de cosecha, GAV, todo lo que venía
después—. El lector validaba cada columna contra su encabezado y por eso frenó
solo, con el mensaje puesto para eso: *"La columna O... dice 'Precio
exportación 27-28→'... parece que se insertaron o movieron columnas"*. Sin esa
guarda habría leído el costo de cosecha donde estaba el costo fijo, y ningún
número se habría visto raro —cada columna corrida seguía siendo un número del
mismo orden de magnitud que la de al lado—.

Se resolvió en dos partes. Primero, el lector de esa tabla dejó de fijarse solo
en la letra de columna: si el encabezado esperado no está ahí, busca en las
columnas vecinas antes de rendirse, así que una columna insertada o borrada no
vuelve a parar el script. Segundo, el precio nuevo es real —Uva de Mesa cobra
más por kilo de exportación desde 2027-2028— y hay que usarlo: el chequeo de
coherencia de producción ahora compara cada temporada contra el precio que le
corresponde (el de antes del corte o el de después), no contra un precio único
para las 21 temporadas. Sin este segundo paso, 11 variedades de Uva de Mesa
habrían salido "incoherentes" desde 2027-2028 en adelante —19 de 21
temporadas— y su producción real se habría reemplazado por una despejada de un
precio que dejó de regir, el mismo error que ya se había cometido y corregido
con v3. El corte de temporada no está escrito a mano: se lee del propio
encabezado («27-28» ⟶ busca "2027-2028" en la lista de temporadas), así que si
el corte se mueve a otro año el script lo sigue sin que haya que tocarlo.

**0. La celda de rendimiento 25/26 de la vinífera traía un total, no un
rendimiento** *(resuelto en v3)*. En `Inputs Generales`, la columna *Rendimiento 25/26* de Cabernet
Sauvignon marca **46.622**, que es exactamente el total de kilos cosechados esa
temporada según Fuente 2 —el rendimiento real es 1.225 kg/ha—. Cabernet Franc
tiene el mismo problema: 3.987 contra 1.133. El modelo multiplica esa celda por
la superficie, así que la temporada 2025-2026 queda inflada por un factor igual a
las hectáreas: **US$ 457.206 de ingresos de más**, casi todo de Cabernet
Sauvignon (US$ 466.833 modelados contra US$ 12.271 que implica la cosecha real).
Sobre un EBITDA 25/26 de −167.712, no es un detalle.

Se detecta sin adivinar, comparando contra la cosecha real: si la celda calza con
los **kilos totales** de la temporada y no con los kilos por hectárea, lleva un
total. El mapa no la corrige —muestra el libro tal cual— y deja la cosecha real
al lado, en *Producción ▸ Cosecha real*.

**0c. `Base Chada` escribe «Naranjas» donde el modelo dice «Naranjos».** El
historico se buscaba por la clave `especie|variedad`, así que esas dos filas no
calzaban con nada y **Cara Cara y Fukumoto quedaban sin historia** sin que se
notara, porque una variedad sin histórico igual se dibuja. Ahora, cuando la
clave completa falla, se busca por nombre de variedad mientras sea único. Eso
además es lo que permite separar los dos naranjos en la cosecha real.

**0b. Las dos fuentes de historia no dicen lo mismo.** `Fuente 2 Rendimientos` y
la Ficha Técnica —que es la que alimenta `Base Chada` y, por ahí, el modelo—
coinciden **exactamente** en 2025/26, en las 33 variedades. En 2023/24 y 2024/25
difieren en 19 de 33, algunas por mucho: Lapins 24/25 da 109.950 kg según la
Ficha y 406.772 según Fuente 2. El mapa pinta Fuente 2, que es la hoja cuyas
hectáreas suman las 292,23 ha que el predio operaba antes de arrendar (la Ficha suma 301,01: es anterior al
arranque de la vinífera). La coincidencia exacta en 25/26 es además lo que
confirma que las temporadas quedaron alineadas y no corridas un año, porque cada
bloque de la hoja rotula distinto —la cereza por el año en que se cosecha, la uva
de mesa por el año en que se embala—; el extractor lo verifica variedad por
variedad y aborta si deja de calzar.

**1. El bloque PRODUCCIÓN de Uva Vinífera estaba corrido una fila**
*(resuelto en v3: el precio implicado ahora calza en las 20 temporadas)*. En
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
(2,94 ha) y `Lapins Injerto` (0,46 ha). Aparecen igual en el árbol de la leyenda,
en cursiva y con el punto hueco, y suman en los totales: por eso el mapa
encendido entero dice 284,02 ha y no 280,62. Lo que no pueden es pintarse, porque
no hay polígono que pintar; al hacerles clic en la tabla el mapa lo dice en vez
de quedarse quieto. Si aparecen en una versión futura del KMZ, se cruzan solas
por el nombre.

**3. Cinco códigos de cuartel aparecen en más de un polígono.** En `8201` y
`8209` es a propósito —vienen partidos en A y B—, pero `5127`, `5137` y `5213`
son paños distintos con el mismo rótulo, y `5213` además cubre dos variedades
(Cara Cara y Fukumoto). El buscador los desempata con el ID interno y el panel
lo anota.

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
tools/modelo_to_json.py         Modelos financieros → un JSON por escenario (y cruce al KMZ).
tools/terreno_to_json.py        DEM de Mapbox → pendiente, exposición y elevación por cuartel.
tools/suelos_to_json.py         Plano de suelos (PDF) → tipo de suelo por cuartel.
datos_fuente/                   Los .xlsx de los modelos y el PDF del plano. Ignorado por git.
```

### Cuando llegue un modelo financiero nuevo

Es lo que va a pasar seguido, y cada vez trae un nombre de archivo distinto
—`v3`, `v4`, `v5`—: alguien edita el Excel y lo manda con la versión siguiente
en el nombre. El procedimiento son tres pasos.

```bash
# 1. dejar el libro nuevo en datos_fuente/, con su propio nombre versionado
cp "<el archivo que llegó>.xlsx" datos_fuente/Financial_Model_Hacienda_Chada_v6.xlsx
```

```python
# 2. apuntar ESCENARIOS al archivo nuevo, en tools/modelo_to_json.py
{"id": "v6", "nombre": "v6", "libro": "Financial_Model_Hacienda_Chada_v6.xlsx",
 "salida": "modelo_data.json", "nota": "Última versión del modelo financiero."},
```

```bash
# 3. releer los modelos y volver a cruzarlos contra los cuarteles
python tools/modelo_to_json.py
```

El libro viejo se puede dejar en `datos_fuente/` —no se sube a git— o borrarlo;
no lo lee nadie una vez que `ESCENARIOS` deja de apuntarlo.

El script lee **todos los escenarios** en una corrida y termina con la tabla
comparativa, así que no hay que acordarse de correrlo dos veces. Los nombres de
archivo y los rótulos viven en la lista `ESCENARIOS`, al principio de
`tools/modelo_to_json.py`:

```python
ESCENARIOS = [
    {"id": "v6", "nombre": "v6", "libro": "Financial_Model_Hacienda_Chada_v6.xlsx",
     "salida": "modelo_data.json", "nota": "Última versión del modelo financiero."},
]
```

**Para agregar un tercer escenario** basta una entrada más ahí y el libro en
`datos_fuente/`: el mapa arma los botones leyendo esa lista desde el JSON, así
que no hay que tocar `index.html`. El primero de la lista manda —es el que
escribe el cruce en `geo_data.json` y contra el que se comparan los demás—, y si
un JSON de escenario no está publicado el mapa sigue andando con los que sí, con
un aviso: un escenario que falta es una opción menos, no una pantalla en blanco.

**No hay que correr los otros tres.** `modelo_to_json.py` reescribe el JSON de
cada escenario y actualiza el cruce dentro de `geo_data.json` sin tocar la
geometría, el terreno ni el suelo. Los otros scripts sólo se corren si cambia
el KMZ o el plano — y en ese caso el orden importa, porque
`kml_to_geojson.py` reconstruye `geo_data.json` desde cero.

**Lo que el script informa al terminar**, que es lo que hay que leer antes de
dar la actualización por buena:

- las variedades que entraron, las que salieron y las que cambiaron de
  superficie, comparando contra la corrida anterior;
- los supuestos que se movieron (tipo de cambio, superficies, tasa de
  descuento) y si cambió el horizonte de temporadas;
- cómo quedaron ingresos, costos y EBITDA en plena producción, antes y después;
- las variedades del modelo que no tienen cuartel dibujado y los cuarteles que
  quedaron sin contraparte — o sea, los nombres que dejaron de calzar;
- y, al final, producción, ingresos, costos y EBITDA de **cada escenario** en
  plena producción, con la variación de cada uno contra el primero.

**Nada se lee por número de fila.** Cada bloque se busca por su título, la
cantidad de variedades sale de contar entre la cabecera y el total, y las
temporadas de contar columnas. Agregar una variedad, insertar un supuesto o
alargar el horizonte no rompe nada. Lo que sí está atado a la posición son las
columnas de la tabla de supuestos, y por eso se validan contra su cabecera: si
alguien inserta una columna, el script se detiene en vez de leer el precio donde
estaba el rendimiento.

**Los tres avisos que aparecen cuando algo no calza**, todos con nombre y
apellido en vez de un traceback:

| Si pasa esto | El script dice |
|---|---|
| Se agregó una variedad a un bloque y no a los otros cinco | En qué fila se desalineó, qué esperaba y qué encontró |
| Se agregó al Consolidado pero no a la tabla de supuestos | Cuál variedad; la dibuja igual con los números que hay, sin precio ni rendimiento |
| Se movieron columnas en la tabla de supuestos | Qué columna, qué decía y qué se esperaba |
| El libro llegó sin valores calculados | Que hay que abrirlo en Excel y volver a guardarlo |
| Falta el .xlsx de un escenario | Cuál, dónde lo buscó y dónde se configura el nombre |
| Dos escenarios no describen el mismo campo | Qué variedad sobra, falta o cambió de hectáreas, y en cuál |

Ese último caso vale la pena explicarlo: el script lee el resultado que Excel
deja **cacheado** en el archivo, porque no evalúa fórmulas. Un `.xlsx` guardado
por un script en vez de por Excel viene sin esa caché y todas las celdas con
fórmula se leen vacías. Si el libro llega así, el script lo dice en vez de
escribir un JSON lleno de ceros.

### Regenerar

El orden importa. `kml_to_geojson.py` reescribe `geo_data.json` desde cero, y los
otros tres le agregan encima: `modelo_to_json.py` el cruce de cada cuartel contra
el modelo, `terreno_to_json.py` la pendiente, la exposición y la elevación, y
`suelos_to_json.py` el tipo de suelo. Correr el primero solo deja el mapa sin
esas capas.

```bash
python tools/kml_to_geojson.py && python tools/modelo_to_json.py && python tools/terreno_to_json.py && python tools/suelos_to_json.py
```

`kml_to_geojson.py` sólo usa stdlib. `modelo_to_json.py` necesita `openpyxl`;
`terreno_to_json.py` necesita `numpy`, `Pillow` y `requests`, y toma el token de
Mapbox de `MAPBOX_TOKEN` o, si no está, del propio `index.html`.
`suelos_to_json.py` necesita `numpy`, `Pillow` y `pdfplumber`.

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
  - las seis rampas —los dos brazos del divergente de EBITDA, el secuencial de
    costos, el de ingresos/rendimiento, el de pendiente y el de elevación— pasan
    los cuatro chequeos ordinales;
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
