# -*- coding: utf-8 -*-
"""Genera el grafico de EBITDA por hectarea y variedad como SVG.

Sale de modelo_data.json, asi que se regenera solo cuando cambie el modelo.

Decisiones de diseno, por si alguien las quiere discutir:

  DOS COLORES, NO UNA RAMPA. El largo de la barra ya dice cuanto; pintar
  ademas cada barra segun su valor gastaria el canal de color repitiendo lo
  mismo. El color aqui dice UNA cosa que el largo no dice de un vistazo: de
  que lado del cero esta. Azul suma, rojo resta; son los dos polos del par
  divergente documentado.

  ORDENADO DE MAYOR A MENOR, no alfabetico ni por superficie. La pregunta que
  contesta el grafico es cual rinde mas por hectarea.

  LA SUPERFICIE VA AL LADO. Sin ella, Sweet Favors (1,5 ha) y Autumn Crisp
  (38,1 ha) parecen decisiones del mismo tamano, y no lo son.

  LINEA DEL PROMEDIO PONDERADO. Da la referencia contra la que cada variedad
  se mide; sin ella, "9.320 US$/ha" es un numero sin escala.
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "modelo_data.json"
SALIDA = RAIZ / "salidas" / "ebitda_ha_por_variedad.svg"

# Polos del par divergente documentado (los mismos del mapa).
POS = "#2a78d6"
NEG = "#d03b3b"
INK = "#1A2733"
TXT2 = "#6D7C86"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

FILA = 21
MARGEN_SUP = 92
MARGEN_INF = 56
X_NOMBRE = 20
X_TRAMA_0 = 188
X_TRAMA_1 = 648
X_VALOR = 742
X_HA = 800
ANCHO = 820


def miles(x, dec=0):
    """Formato chileno: punto para miles, coma para decimales."""
    s = ("%%.%df" % dec) % abs(x)
    ent, _, frac = s.partition(".")
    ent = "{:,}".format(int(ent)).replace(",", ".")
    out = ent + ("," + frac if frac else "")
    return ("−" if x < 0 else "") + out


def paso_lindo(amplitud):
    import math
    decada = 10 ** math.floor(math.log10(amplitud / 5))
    for m in (1, 2, 2.5, 5, 10):
        if amplitud / (m * decada) <= 5:
            return m * decada
    return decada * 10


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main():
    d = json.loads(MODELO.read_text(encoding="utf-8"))
    # Plena produccion: la temporada en que el modelo se estabiliza y deja de
    # depender de en que ano entro cada plantacion.
    t = 0
    for i in range(len(d["temporadas"]) - 1):
        if any(abs((d["totales"][c][i] or 0) - (d["totales"][c][i + 1] or 0)) > 0.5
               for c in ("ingresos", "costos", "ebitda")):
            t = i + 1
    temporada = d["temporadas"][t]

    filas = sorted(d["variedades"], key=lambda v: -(v["ebitda_ha"][t] or 0))
    valores = [v["ebitda_ha"][t] or 0 for v in filas]
    promedio = d["totales"]["ebitda_ha"][t]

    bajo, alto = min(min(valores), 0), max(valores)
    paso = paso_lindo(alto - bajo)
    import math
    dom0 = math.floor(bajo / paso) * paso
    dom1 = math.ceil(alto / paso) * paso
    escala = lambda x: X_TRAMA_0 + (x - dom0) / (dom1 - dom0) * (X_TRAMA_1 - X_TRAMA_0)
    x_cero = escala(0)

    alto_svg = MARGEN_SUP + len(filas) * FILA + MARGEN_INF
    o = []
    a = o.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
      'font-family="Fira Sans, Segoe UI, Helvetica, Arial, sans-serif">'
      % (ANCHO, alto_svg, ANCHO, alto_svg))
    a('<rect width="%d" height="%d" fill="#FFFFFF"/>' % (ANCHO, alto_svg))

    a('<text x="%d" y="34" font-size="17" font-weight="600" fill="%s">EBITDA por hectárea, por variedad</text>'
      % (X_NOMBRE, INK))
    a('<text x="%d" y="54" font-size="11.5" fill="%s">Hacienda Chada: Huelquén · temporada %s, plena producción · '
      '%s ha modeladas</text>' % (X_NOMBRE, TXT2, esc(temporada), miles(d["totales"]["ha"], 2)))

    # Leyenda de los dos polos: el color dice de que lado del cero, nada mas.
    a('<rect x="%d" y="64" width="9" height="9" rx="2" fill="%s"/>' % (X_NOMBRE, POS))
    a('<text x="%d" y="72.5" font-size="10.5" fill="%s">Aporta</text>' % (X_NOMBRE + 14, TXT2))
    a('<rect x="%d" y="64" width="9" height="9" rx="2" fill="%s"/>' % (X_NOMBRE + 68, NEG))
    a('<text x="%d" y="72.5" font-size="10.5" fill="%s">Resta</text>' % (X_NOMBRE + 82, TXT2))

    a('<text x="%d" y="72.5" font-size="9.5" font-weight="600" fill="%s" text-anchor="end" '
      'letter-spacing="0.5">US$/ha</text>' % (X_VALOR, MUTED))
    a('<text x="%d" y="72.5" font-size="9.5" font-weight="600" fill="%s" text-anchor="end" '
      'letter-spacing="0.5">ha</text>' % (X_HA, MUTED))

    y0 = MARGEN_SUP
    y1 = y0 + len(filas) * FILA

    # Grilla: recesiva, por detras de las barras.
    x = dom0
    while x <= dom1 + 1:
        px = escala(x)
        a('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1"/>'
          % (px, y0 - 6, px, y1, GRID))
        a('<text x="%.1f" y="%d" font-size="10" fill="%s" text-anchor="middle">%s</text>'
          % (px, y1 + 18, MUTED, miles(x / 1000) + "k"))
        x += paso

    for i, v in enumerate(filas):
        val = v["ebitda_ha"][t] or 0
        y = y0 + i * FILA
        cy = y + FILA / 2
        px = escala(val)
        x_ini, ancho_barra = (x_cero, px - x_cero) if val >= 0 else (px, x_cero - px)
        a('<rect x="%.1f" y="%.1f" width="%.1f" height="13" rx="2.5" fill="%s"/>'
          % (x_ini, cy - 6.5, max(ancho_barra, 1.2), POS if val >= 0 else NEG))
        a('<text x="%d" y="%.1f" font-size="11" fill="%s">%s</text>'
          % (X_NOMBRE, cy + 3.8, INK, esc(v["variedad"])))
        a('<text x="%d" y="%.1f" font-size="11" fill="%s" text-anchor="end" font-weight="500">%s</text>'
          % (X_VALOR, cy + 3.8, INK if val >= 0 else NEG, miles(val)))
        a('<text x="%d" y="%.1f" font-size="10.5" fill="%s" text-anchor="end">%s</text>'
          % (X_HA, cy + 3.8, MUTED, miles(v["ha"], 1)))

    # Cero: la referencia que da sentido al color.
    a('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1.5"/>'
      % (x_cero, y0 - 6, x_cero, y1, INK))

    # Promedio ponderado del predio.
    px = escala(promedio)
    a('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1" stroke-dasharray="3 3"/>'
      % (px, y0 - 6, px, y1, TXT2))
    a('<text x="%.1f" y="%d" font-size="10" fill="%s" text-anchor="middle">promedio %s</text>'
      % (px, y0 - 12, TXT2, miles(promedio)))

    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1"/>'
      % (X_TRAMA_0, y1, X_TRAMA_1, y1, AXIS))
    a('<text x="%d" y="%d" font-size="10" fill="%s">Fuente: %s · EBITDA sobre superficie modelada de cada variedad. '
      'El color indica sólo el signo; el largo, la magnitud.</text>'
      % (X_NOMBRE, y1 + 42, MUTED, esc(d["source"])))
    a('</svg>')

    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text("\n".join(o), encoding="utf-8")
    print("OK %s" % SALIDA)
    print("  temporada %s · %d variedades · promedio %s US$/ha" % (temporada, len(filas), miles(promedio)))
    print("  mejor  %-22s %8s US$/ha" % (filas[0]["variedad"], miles(filas[0]["ebitda_ha"][t])))
    print("  peor   %-22s %8s US$/ha" % (filas[-1]["variedad"], miles(filas[-1]["ebitda_ha"][t])))


if __name__ == "__main__":
    main()
