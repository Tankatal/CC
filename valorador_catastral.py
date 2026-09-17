#!/usr/bin/env python3
"""
valorador_catastral.py
-----------------------
Automatiza el proceso: referencia catastral -> datos descriptivos oficiales
+ (opcional) valoraciones de mercado de varias fuentes -> valor medio estimado.

USO BÁSICO (solo datos oficiales del Catastro, sin claves de API):
    python valorador_catastral.py 5550604VK2754N0001IW

CON FUENTES DE MERCADO (si te das de alta en alguna):
    python valorador_catastral.py 5550604VK2754N0001IW --tinsa-key TU_CLAVE
    python valorador_catastral.py 5550604VK2754N0001IW --catastrogps-key TU_CLAVE

Requisitos:
    pip install requests xmltodict
"""

import argparse
import sys
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


def tinsa_valoracion(rc: str, api_key: str):
    return None


def catastrogps_valoracion(rc: str, api_key: str):
    return None


def calcular_valor_medio(valores):
    valores = [v for v in valores if v]
    if not valores:
        return {"valor_medio": None, "n_fuentes": 0}
    return {
        "valor_medio": round(sum(valores) / len(valores), 2),
        "valor_min": min(valores),
        "valor_max": max(valores),
        "n_fuentes": len(valores),
    }


def main():
    parser = argparse.ArgumentParser(description="Valorador a partir de referencia catastral")
    parser.add_argument("referencia", help="Referencia catastral, ej. 5550604VK2754N0001IW")
    parser.add_argument("--tinsa-key", default=None)
    parser.add_argument("--catastrogps-key", default=None)
    args = parser.parse_args()

    print(f"\n== Datos oficiales del Catastro para {args.referencia} ==")
    try:
        datos = consulta_catastro(args.referencia)
        for k, v in datos.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"  [!] No se pudo consultar el Catastro: {e}")
        datos = {}

    valores_mercado = []

    if args.tinsa_key:
        v = tinsa_valoracion(args.referencia, args.tinsa_key)
        if v:
            print(f"\nTinsa Digital AVM: {v} €")
            valores_mercado.append(v)

    if args.catastrogps_key:
        v = catastrogps_valoracion(args.referencia, args.catastrogps_key)
        if v:
            print(f"\nCatastroGPS mercado: {v}")

    resultado = calcular_valor_medio(valores_mercado)
    print("\n== Resumen ==")
    if resultado["valor_medio"]:
        print(f"  Valor medio estimado: {resultado['valor_medio']} € (de {resultado['n_fuentes']} fuente(s))")
    else:
        print("  No hay valores de mercado automáticos todavía.")
        print("  Consulta manual (10s) del valor de referencia fiscal:")
        print(f"  {CATASTRO_VALOR_REF_URL}")
        print("  Para automatizar el valor de MERCADO real, contrata acceso a Tinsa Digital, CASAFARI o idealista/data y pásame la API key.")


if __name__ == "__main__":
    main()
