#!/usr/bin/env python3
"""
valorador_catastral.py
-----------------------
Herramienta genérica de valoración inmobiliaria para cualquier vivienda en
España a partir de su referencia catastral.

Flujo:
  1. Consulta al Catastro oficial (Consulta_DNPRC) -> dato base: dirección,
     superficie, uso y año de construcción. NO es un valor de mercado.
  2. Intenta obtener una estimación de valor de mercado en cada una de varias
     fuentes gratuitas (bancos, portales inmobiliarios y tasadoras).
  3. Cada fuente que no devuelva un valor numérico fiable se marca como
     "no disponible" con el motivo, en vez de romper todo el proceso.
  4. Con los valores que sí se obtienen, calcula media, mediana, mínimo,
     máximo y número de fuentes.

Ninguna de las fuentes de mercado de abajo ofrece hoy una API pública que
devuelva una cifra solo con la referencia catastral: son formularios en
JavaScript (piden datos adicionales como nº de habitaciones, planta o
estado), o formularios de captación de contacto para tasadoras
profesionales. Por eso cada función de fuente es un punto de extensión
honesto: comprueba si el sitio es alcanzable y explica por qué no puede
extraer un valor automáticamente, en vez de inventar una cifra.

USO:
    python valorador_catastral.py 5550604VK2754N0001IW

Requisitos:
    pip install requests xmltodict
"""

import argparse
import statistics
import xml.etree.ElementTree as ET
import requests

CATASTRO_DNPRC = (
    "http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/"
    "OVCCallejero.asmx/Consulta_DNPRC"
)
CATASTRO_VALOR_REF_URL = "https://www.sedecatastro.gob.es/Accesos/SECAccvr.aspx"


def consulta_catastro(rc: str) -> dict:
    params = {"Provincia": "", "Municipio": "", "RC": rc}
    resp = requests.get(CATASTRO_DNPRC, params=params, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    def find_text(tag):
        for el in root.iter():
            if el.tag.endswith(tag):
                return el.text
        return None

    data = {
        "referencia_catastral": rc,
        "direccion": find_text("ldt") or find_text("dir"),
        "superficie_construida_m2": find_text("sfc"),
        "uso_predominante": find_text("luso"),
        "año_construccion": find_text("ant"),
        "clase_bien": find_text("cn"),
        "error": find_text("des") if find_text("cudnp") == "0" else None,
    }
    return data


def _comprobar_alcance(url: str) -> str | None:
    """Intenta alcanzar el sitio. Devuelve None si responde, o un motivo si falla."""
    try:
        requests.head(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        return None
    except requests.exceptions.RequestException as e:
        return f"sitio no alcanzable desde este entorno ({type(e).__name__})"


def _fuente_no_disponible(motivo: str) -> dict:
    return {"valor": None, "valor_min": None, "valor_max": None, "disponible": False, "motivo": motivo}


def consultar_bbva_valora(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "requiere introducir la dirección en un mapa interactivo (JS) y no ofrece "
        "API pública documentada; el simulador está ligado a la contratación de hipoteca"
    )
    return _fuente_no_disponible(motivo)


def consultar_kutxabank(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "simulador ligado al proceso de solicitud hipotecaria; pide datos personales "
        "antes de mostrar una cifra"
    )
    return _fuente_no_disponible(motivo)


def consultar_unicaja(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "simulador de tasación ligado a la gestión de hipoteca; requiere contacto "
        "comercial para obtener un valor"
    )
    return _fuente_no_disponible(motivo)


def consultar_idealista_tasacion(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "formulario multi-paso en JS que pide datos no disponibles en el Catastro "
        "(habitaciones, planta, estado, ascensor) y email/teléfono para el informe"
    )
    return _fuente_no_disponible(motivo)


def consultar_fotocasa_tasacion(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "formulario multi-paso en JS; el resultado se envía por email tras dejar "
        "datos de contacto, no hay API pública"
    )
    return _fuente_no_disponible(motivo)


def consultar_cbre(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "es una tasadora profesional: el 'simulador' es un formulario de solicitud "
        "de presupuesto/cita, no un valor automático instantáneo"
    )
    return _fuente_no_disponible(motivo)


def consultar_gesvalt(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "tasadora homologada: la tasación requiere visita técnica y encargo formal, "
        "no ofrece cifra automática"
    )
    return _fuente_no_disponible(motivo)


def consultar_sotasa(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "tasadora homologada (grupo Sociedad de Tasación): la tasación requiere "
        "visita técnica y encargo formal, no ofrece cifra automática"
    )
    return _fuente_no_disponible(motivo)


def consultar_housfy(rc: str, direccion: str, url: str) -> dict:
    error_red = _comprobar_alcance(url)
    motivo = error_red or (
        "tasación previa gratuita, pero pide registro/datos de contacto antes de "
        "entregar el informe con la cifra"
    )
    return _fuente_no_disponible(motivo)


# Cada entrada: función de consulta, nombre para mostrar, URL del simulador.
FUENTES_MERCADO = [
    (consultar_bbva_valora, "BBVA Valora", "https://www.bbva.es/personas/hipotecas/valora-tu-vivienda.html"),
    (consultar_kutxabank, "Kutxabank (simulador valor vivienda)", "https://www.kutxabank.es/w2/es/particulares/hipotecas/simulador-tasacion/"),
    (consultar_unicaja, "Unicaja (simulador de tasación)", "https://www.unicajabanco.es/es/particulares/hipotecas"),
    (consultar_idealista_tasacion, "Idealista (tasación online)", "https://tasaciones.idealista.com/"),
    (consultar_fotocasa_tasacion, "Fotocasa (tasación online)", "https://www.fotocasa.es/tasacion/"),
    (consultar_cbre, "CBRE Valoraciones y Tasaciones", "https://www.cbre.es/services/valuation-advisory"),
    (consultar_gesvalt, "Gesvalt (simulador de tasación)", "https://www.gesvalt.es/"),
    (consultar_sotasa, "Sotasa (simulador de tasación)", "https://www.sotasa.es/"),
    (consultar_housfy, "Housfy (tasación previa)", "https://www.housfy.com/tasacion-vivienda"),
]


def consultar_todas_las_fuentes(rc: str, direccion: str) -> list[dict]:
    resultados = []
    for fn, nombre, url in FUENTES_MERCADO:
        r = fn(rc, direccion, url)
        r["nombre"] = nombre
        r["url"] = url
        resultados.append(r)
    return resultados


def calcular_estadisticas(resultados: list[dict]) -> dict:
    valores = [r["valor"] for r in resultados if r.get("valor") is not None]
    if not valores:
        return {"media": None, "mediana": None, "minimo": None, "maximo": None, "n_fuentes": 0}
    return {
        "media": round(statistics.mean(valores), 2),
        "mediana": round(statistics.median(valores), 2),
        "minimo": min(valores),
        "maximo": max(valores),
        "n_fuentes": len(valores),
    }


def main():
    parser = argparse.ArgumentParser(description="Valorador genérico a partir de referencia catastral")
    parser.add_argument("referencia", help="Referencia catastral, ej. 5550604VK2754N0001IW")
    args = parser.parse_args()

    print(f"\n== Datos oficiales del Catastro para {args.referencia} ==")
    try:
        datos = consulta_catastro(args.referencia)
        for k, v in datos.items():
            print(f"  {k}: {v}")
        direccion = datos.get("direccion")
    except Exception as e:
        print(f"  [!] No se pudo consultar el Catastro: {e}")
        direccion = None

    print(f"\n== Valoraciones de mercado ({len(FUENTES_MERCADO)} fuentes) ==")
    resultados = consultar_todas_las_fuentes(args.referencia, direccion)
    for r in resultados:
        if r["disponible"]:
            if r["valor"] is not None:
                cifra = f"{r['valor']} €"
            else:
                cifra = f"{r['valor_min']}-{r['valor_max']} €"
            print(f"  {r['nombre']:<38} {cifra}")
        else:
            print(f"  {r['nombre']:<38} no disponible ({r['motivo']})")
            print(f"    -> consulta manual: {r['url']}")

    stats = calcular_estadisticas(resultados)
    print("\n== Resumen ==")
    if stats["n_fuentes"] > 0:
        print(f"  Media:   {stats['media']} €")
        print(f"  Mediana: {stats['mediana']} €")
        print(f"  Rango:   {stats['minimo']} € - {stats['maximo']} €")
        print(f"  Fuentes con dato: {stats['n_fuentes']} / {len(FUENTES_MERCADO)}")
    else:
        print("  Ninguna fuente de mercado devolvió un valor automático.")
        print(f"  Fuentes con dato: 0 / {len(FUENTES_MERCADO)}")
        print("  Consulta manual (10s) del valor de referencia fiscal del Catastro:")
        print(f"  {CATASTRO_VALOR_REF_URL}")
        print("  Para un valor real, revisa los enlaces de consulta manual listados arriba.")


if __name__ == "__main__":
    main()
