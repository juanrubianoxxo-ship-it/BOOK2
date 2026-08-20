"""
data_loader.py
--------------
Descarga el archivo Excel (desde un link de OneDrive o desde disco local),
lo parsea en DataFrames limpios y expone funciones cacheadas para usar en
la app de Streamlit.

Cómo funciona la conexión con OneDrive:
- En Streamlit Secrets (st.secrets) guardas ONEDRIVE_URL con el link de
  "compartir" convertido a descarga directa (ver README.md para el paso a paso).
- Cada vez que la app se abre o se refresca, se vuelve a descargar el
  archivo. Usamos st.cache_data con un TTL corto (por defecto 15 minutos)
  para no descargar en cada click, pero sí reflejar cambios recientes.
- Si no hay ONEDRIVE_URL configurado, se usa un archivo local
  (útil para desarrollo/pruebas).

Solo se procesan las hojas JUN (rendimiento actual por tienda) y LAST
(histórico mensual de ventas/contribución).
"""

import io
import os
import re
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

LOCAL_FALLBACK_PATH = os.path.join(os.path.dirname(__file__), "data", "Book.xlsx")
CACHE_TTL_SECONDS = 15 * 60  # 15 minutos


def _onedrive_share_to_direct(url: str) -> str:
    """
    Convierte un link de "compartir" de OneDrive personal
    (onedrive.live.com/... o 1drv.ms/...) en un link de descarga directa.
    Si el link ya es de descarga directa (contiene 'download=1' o es
    de SharePoint con '?download=1'), lo deja igual.
    """
    if not url:
        return url

    # Links cortos 1drv.ms se resuelven solos al hacer la petición (redirect),
    # así que los dejamos pasar tal cual.
    if "1drv.ms" in url:
        return url

    # Links largos onedrive.live.com: forzamos descarga directa
    if "onedrive.live.com" in url and "download=1" not in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}download=1"

    # Links de SharePoint/OneDrive for Business: agregar download=1
    if "sharepoint.com" in url and "download=1" not in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}download=1"

    return url


def _download_excel_bytes(url: str) -> bytes:
    direct_url = _onedrive_share_to_direct(url)
    headers = {
        # Algunos tenants de SharePoint bloquean peticiones sin un
        # User-Agent que parezca de navegador.
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(direct_url, headers=headers, allow_redirects=True, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise ConnectionError(
            f"No se pudo descargar el archivo desde OneDrive/SharePoint: {e}. "
            "Verifica que el link siga activo y que el permiso sea "
            "'Cualquier persona con el vínculo'."
        ) from e

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        raise ValueError(
            "El link devolvió una página HTML en vez del archivo Excel (esto pasa "
            "cuando SharePoint pide iniciar sesión o el link cambió). Prueba abrir "
            "el link en una ventana de incógnito: si te pide login, hay que "
            "regenerar el link como público, o usar Microsoft Graph API. "
            f"Content-Type recibido: {content_type or 'desconocido'}."
        )
    if len(resp.content) < 1000:
        raise ValueError(
            "El archivo descargado es sospechosamente pequeño "
            f"({len(resp.content)} bytes) — probablemente no es el Excel real. "
            "Revisa el link."
        )
    return resp.content


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Descargando y procesando el Excel...")
def load_workbook_bytes() -> bytes:
    """Devuelve los bytes del Excel, desde OneDrive si hay secret configurado,
    o desde el archivo local de respaldo."""
    onedrive_url = st.secrets.get("ONEDRIVE_URL", "https://femcom-my.sharepoint.com/:x:/g/personal/juan_rubiano_oxxo_com/IQBBFO2BfMQHRbOUDYjE0DD7Afy4zh6B1pszFdTkjDrERug?e=aJF7vL") if hasattr(st, "secrets") else ""
    if onedrive_url:
        return _download_excel_bytes(onedrive_url)
    if os.path.exists(LOCAL_FALLBACK_PATH):
        with open(LOCAL_FALLBACK_PATH, "rb") as f:
            return f.read()
    raise FileNotFoundError(
        "No se encontró ONEDRIVE_URL en st.secrets ni un archivo local en "
        f"{LOCAL_FALLBACK_PATH}. Configura uno de los dos (ver README.md)."
    )


def _clean_money(series: pd.Series) -> pd.Series:
    """Convierte columnas tipo '$ 220.531' (texto) a float."""
    return (
        series.astype(str)
        .str.replace(r"[^\d,.\-]", "", regex=True)
        .str.replace(".", "", regex=False)  # separador de miles
        .str.replace(",", ".", regex=False)  # decimal si lo hubiera
        .replace("", None)
        .astype(float)
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_tiendas() -> pd.DataFrame:
    """Hoja JUN: foto actual de cada tienda (rendimiento)."""
    raw = load_workbook_bytes()
    df = pd.read_excel(io.BytesIO(raw), sheet_name="JUN", header=0)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df["CR"].notna()].copy()

    numeric_cols = [
        "AREA", "VT", "ET", "TRAFICO UM", "TRAFICO U6M", "TICKET UM",
        "TICKET U6M", "VENTAS OUM", "VENTAS OU6M", "CONTRIBUCION UM",
        "CONTRIBUCION U6M", "MARGEN UM", "MARGEN U6M", "RENTA UM",
        "RENTA U6M", "%Batting", "SCOREF", "COSTO M2", "PTH",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "FECHA APE" in df.columns:
        df["FECHA APE"] = pd.to_datetime(df["FECHA APE"], errors="coerce")

    # Margen sobre ventas, para tener un % comparable entre tiendas
    if {"MARGEN UM", "VENTAS OUM"}.issubset(df.columns):
        df["MARGEN_%_UM"] = (df["MARGEN UM"] / df["VENTAS OUM"]).replace(
            [float("inf"), float("-inf")], None
        )

    return df.reset_index(drop=True)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_historico() -> pd.DataFrame:
    """Hoja LAST: histórico mensual de ventas/contribución por tienda."""
    raw = load_workbook_bytes()
    df = pd.read_excel(io.BytesIO(raw), sheet_name="LAST", header=0)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df["CR"].notna()].copy()

    df["Mes Año"] = pd.to_datetime(df["Mes Año"], errors="coerce")
    df["Ventas 6 Months"] = _clean_money(df["Ventas 6 Months"])
    df["Contribucion 6 Months"] = pd.to_numeric(
        df["Contribucion 6 Months"], errors="coerce"
    )
    df["Modelo Eco"] = pd.to_numeric(df["Modelo Eco"], errors="coerce")

    return df.dropna(subset=["Mes Año"]).reset_index(drop=True)


def last_update_label() -> str:
    """Etiqueta legible de cuándo se descargó el archivo por última vez
    (aprox., basada en el TTL de caché)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
