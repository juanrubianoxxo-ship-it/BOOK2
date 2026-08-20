"""
alerts.py
---------
Reglas de negocio para generar alertas a partir de los datos de tiendas.
Cada función devuelve un DataFrame con las tiendas que disparan la alerta
más una columna 'motivo' explicando por qué.

Los umbrales (thresholds) están como constantes al inicio del archivo para
que sea fácil ajustarlos sin tocar la lógica.
"""

import pandas as pd

# ---- Umbrales configurables ----
BATTING_BAJO = 0.5          # %Batting por debajo de esto = alerta
CAIDA_VENTAS_PCT = -0.10    # caída >= 10% vs mes anterior = alerta
CAIDA_MARGEN_PCT = -0.15    # caída >= 15% en margen = alerta
RENTA_BAJA_PCT = 0.05       # renta/ventas por debajo de 5% = alerta de rentabilidad baja
ESTADOS_CRITICOS = ["OBRA", "FIRMADA"]  # tiendas que aún no operan
SCOREF_ALERTA = -3       # menor a esto = tienda en alerta
SCOREF_OBSERVACION = 0   # de -3 a menos de 0 = requiere seguimiento
SCOREF_BUENA = 3         # de 0 a 3 = tienda buena; mayor a 3 = mejor tienda


def clasificar_scoref(score) -> str:
    """Clasifica el rendimiento de una tienda según SCOREF."""
    if pd.isna(score):
        return "Sin SCOREF"
    if score > SCOREF_BUENA:
        return "Mejor tienda"
    if score >= SCOREF_OBSERVACION:
        return "Tienda buena"
    if score >= SCOREF_ALERTA:
        return "En observación"
    return "En alerta"


def alertas_scoref(df_tiendas: pd.DataFrame) -> pd.DataFrame:
    """Devuelve tiendas con SCOREF menor a -3, priorizadas por menor score."""
    if "SCOREF" not in df_tiendas.columns:
        return pd.DataFrame(columns=["CR", "NAME", "PLAZA 2026", "SCOREF", "clasificacion", "motivo"])
    sub = df_tiendas[df_tiendas["SCOREF"] < SCOREF_ALERTA].copy()
    sub["clasificacion"] = sub["SCOREF"].apply(clasificar_scoref)
    sub["motivo"] = sub["SCOREF"].apply(
        lambda v: f"SCOREF crítico ({v:.2f}), menor a {SCOREF_ALERTA}"
    )
    cols = ["CR", "NAME", "PLAZA 2026", "ESTADO", "VENTAS OUM", "SCOREF", "clasificacion", "motivo"]
    return sub[[c for c in cols if c in sub.columns]].sort_values("SCOREF")


def alertas_batting_bajo(df_tiendas: pd.DataFrame) -> pd.DataFrame:
    # Nota: muchas tiendas tienen %Batting = 0, que interpretamos como
    # "sin dato" (no aplica) en vez de "batting malo", para no inflar la
    # alerta con tiendas que simplemente no tienen esta métrica cargada.
    sub = df_tiendas[
        df_tiendas["ESTADO"].eq("ABIERTA")
        & (df_tiendas["%Batting"] > 0)
        & (df_tiendas["%Batting"] < BATTING_BAJO)
    ].copy()
    sub["motivo"] = sub["%Batting"].apply(
        lambda v: f"%Batting bajo ({v:.0%}), por debajo de {BATTING_BAJO:.0%}"
    )
    cols = ["CR", "NAME", "PLAZA 2026", "%Batting", "GENERADOR", "motivo"]
    return sub[[c for c in cols if c in sub.columns]].sort_values("%Batting")


def alertas_renta_baja(df_tiendas: pd.DataFrame) -> pd.DataFrame:
    sub = df_tiendas[df_tiendas["ESTADO"].eq("ABIERTA")].copy()
    sub["renta_sobre_ventas"] = sub["RENTA UM"] / sub["VENTAS OUM"]
    sub = sub[sub["renta_sobre_ventas"] < RENTA_BAJA_PCT]
    sub["motivo"] = sub["renta_sobre_ventas"].apply(
        lambda v: f"Renta/Ventas baja ({v:.1%}), por debajo de {RENTA_BAJA_PCT:.0%}"
    )
    cols = ["CR", "NAME", "PLAZA 2026", "RENTA UM", "VENTAS OUM", "renta_sobre_ventas", "motivo"]
    return sub[[c for c in cols if c in sub.columns]].sort_values("renta_sobre_ventas")


def alertas_estado_critico(df_tiendas: pd.DataFrame) -> pd.DataFrame:
    sub = df_tiendas[df_tiendas["ESTADO"].isin(ESTADOS_CRITICOS)].copy()
    sub["motivo"] = sub["ESTADO"].apply(lambda e: f"Tienda en estado '{e}', aún no operativa")
    cols = ["CR", "NAME", "PLAZA 2026", "ESTADO", "TIE26", "motivo"]
    return sub[[c for c in cols if c in sub.columns]]


def alertas_tendencia(df_historico: pd.DataFrame, metrica: str = "Ventas 6 Months") -> pd.DataFrame:
    """
    Compara el último mes disponible contra el mes anterior, por tienda,
    y marca caídas relevantes en ventas o contribución.
    """
    umbral = CAIDA_VENTAS_PCT if metrica == "Ventas 6 Months" else CAIDA_MARGEN_PCT

    df = df_historico.sort_values(["CR", "Mes Año"]).copy()
    df["mes_anterior_valor"] = df.groupby("CR")[metrica].shift(1)
    df["variacion_pct"] = (df[metrica] - df["mes_anterior_valor"]) / df["mes_anterior_valor"]

    ultimo_mes = df["Mes Año"].max()
    sub = df[(df["Mes Año"] == ultimo_mes) & (df["variacion_pct"] <= umbral)].copy()
    sub["motivo"] = sub["variacion_pct"].apply(
        lambda v: f"{metrica} cayó {v:.1%} vs. mes anterior"
    )
    cols = ["CR", "Tienda", "Mes Año", metrica, "mes_anterior_valor", "variacion_pct", "motivo"]
    return sub[[c for c in cols if c in sub.columns]].sort_values("variacion_pct")


def resumen_alertas(df_tiendas: pd.DataFrame, df_historico: pd.DataFrame) -> dict:
    """Arma todas las alertas y devuelve un diccionario {nombre: DataFrame}."""
    return {
        "SCOREF en alerta": alertas_scoref(df_tiendas),
        "Ventas cayendo": alertas_tendencia(df_historico, "Ventas 6 Months"),
        "Contribución cayendo": alertas_tendencia(df_historico, "Contribucion 6 Months"),
        "%Batting bajo": alertas_batting_bajo(df_tiendas),
        "Renta/Ventas baja": alertas_renta_baja(df_tiendas),
        "Estado crítico (obra/firmada)": alertas_estado_critico(df_tiendas),
    }
