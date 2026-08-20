"""
Dashboard de Streamlit: rendimiento y alertas de la red de tiendas.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

import data_loader as dl
import alerts as al

st.set_page_config(page_title="OXXO | Red de tiendas", layout="wide", page_icon="🛒")

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] { background: #f7f8fa; }
    [data-testid="stSidebar"] { background: #17365d; }
    [data-testid="stSidebar"] * { color: white !important; }
    .brand { background: #d71920; color: white; padding: 16px 22px; border-radius: 10px;
             margin-bottom: 20px; font-size: 25px; font-weight: 800; letter-spacing: .4px; }
    .section { border-left: 5px solid #d71920; padding-left: 12px; margin: 12px 0 8px; }
    .legend { padding: 12px 16px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;
              margin: 8px 0 18px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="brand">OXXO · Centro de rendimiento de tiendas</div>', unsafe_allow_html=True)
st.sidebar.title("Control de red")
st.sidebar.caption("Datos conectados desde OneDrive")

if st.sidebar.button("Actualizar datos"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption(f"Última carga: {dl.last_update_label()} (caché ~15 min)")

try:
    df_tiendas = dl.load_tiendas()
    df_historico = dl.load_historico()
except Exception as e:
    st.error(f"No se pudo cargar el Excel: {e}")
    st.stop()

if "SCOREF" in df_tiendas.columns:
    df_tiendas["clasificacion_scoref"] = df_tiendas["SCOREF"].apply(al.clasificar_scoref)
else:
    df_tiendas["SCOREF"] = pd.NA
    df_tiendas["clasificacion_scoref"] = "Sin SCOREF"

plazas = ["Todas"] + sorted(df_tiendas["PLAZA 2026"].dropna().unique().tolist())
plaza_sel = st.sidebar.selectbox("Filtrar por plaza", plazas)
df_t = df_tiendas if plaza_sel == "Todas" else df_tiendas[df_tiendas["PLAZA 2026"] == plaza_sel]
crs_filtradas = set(df_t["CR"])
df_h = df_historico if plaza_sel == "Todas" else df_historico[df_historico["CR"].isin(crs_filtradas)]

segmentos = ["Todos"] + [x for x in ["Mejor tienda", "Tienda buena", "En observación", "En alerta", "Sin SCOREF"] if x in df_t["clasificacion_scoref"].unique()]
segmento_sel = st.sidebar.selectbox("Filtrar por SCOREF", segmentos)
if segmento_sel != "Todos":
    df_t = df_t[df_t["clasificacion_scoref"] == segmento_sel]
    df_h = df_h[df_h["CR"].isin(set(df_t["CR"]))]

abiertas = df_t[df_t["ESTADO"].eq("ABIERTA")]

with st.sidebar.expander("Guía de SCOREF", expanded=True):
    st.markdown("**> 3** · Mejor tienda  \\n**0 a 3** · Tienda buena  \\n**-3 a < 0** · En observación  \\n**< -3** · En alerta")

tab_resumen, tab_tiendas, tab_historico, tab_alertas = st.tabs(
    ["Resumen", "Tiendas", "Histórico", "Alertas"]
)

with tab_resumen:
    st.markdown('<div class="section"><h3>Resumen ejecutivo</h3></div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tiendas abiertas", f"{len(abiertas):,}")
    c2.metric("Ventas último mes", f"${abiertas['VENTAS OUM'].sum():,.0f}")
    c3.metric("Tráfico mensual", f"{abiertas['TRAFICO UM'].sum():,.0f}")
    c4.metric("SCOREF promedio", f"{df_t['SCOREF'].mean():.2f}" if df_t['SCOREF'].notna().any() else "Sin dato")
    c5.metric("Tiendas en alerta", f"{(df_t['SCOREF'] < al.SCOREF_ALERTA).sum():,}")

    st.markdown(
        '<div class="legend"><b>Lectura rápida:</b> SCOREF mayor a 3 representa el mejor desempeño; entre 0 y 3 son tiendas buenas; de -3 a menos de 0 requieren observación; menor a -3 son tiendas en alerta.</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Distribución por SCOREF**")
        score_count = df_t["clasificacion_scoref"].value_counts().rename_axis("Clasificación").reset_index(name="Tiendas")
        fig = px.bar(score_count, x="Clasificación", y="Tiendas", color="Clasificación",
                     color_discrete_map={"Mejor tienda": "#17823b", "Tienda buena": "#58a55c", "En observación": "#f3a712", "En alerta": "#d71920", "Sin SCOREF": "#7b8794"})
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("**Ventas por plaza**")
        ventas_plaza = abiertas.groupby("PLAZA 2026", as_index=False)["VENTAS OUM"].sum()
        st.plotly_chart(px.bar(ventas_plaza, x="PLAZA 2026", y="VENTAS OUM", color="PLAZA 2026"), use_container_width=True)

    st.markdown("**Tiendas que requieren atención inmediata**")
    criticas = df_t[df_t["SCOREF"] < al.SCOREF_ALERTA].copy().sort_values("SCOREF")
    cols = ["CR", "NAME", "PLAZA 2026", "VENTAS OUM", "SCOREF", "clasificacion_scoref"]
    st.dataframe(criticas[[c for c in cols if c in criticas.columns]].head(10), use_container_width=True, hide_index=True)

with tab_tiendas:
    st.markdown('<div class="section"><h3>Rendimiento por tienda</h3></div>', unsafe_allow_html=True)
    cols_show = ["CR", "NAME", "PLAZA 2026", "MUNICIPIO", "ESTADO", "SCOREF", "clasificacion_scoref", "GENERADOR", "TRAFICO UM", "TICKET UM", "VENTAS OUM", "CONTRIBUCION UM", "MARGEN UM", "MARGEN_%_UM", "RENTA UM", "%Batting"]
    cols_show = [c for c in cols_show if c in df_t.columns]
    st.dataframe(df_t[cols_show].sort_values("SCOREF", ascending=False, na_position="last"), use_container_width=True, height=500, hide_index=True)
    st.markdown("**Relación entre tráfico, ticket y ventas**")
    st.plotly_chart(px.scatter(abiertas, x="TRAFICO UM", y="TICKET UM", size="VENTAS OUM", color="clasificacion_scoref", hover_name="NAME"), use_container_width=True)

with tab_historico:
    st.markdown('<div class="section"><h3>Evolución mensual</h3></div>', unsafe_allow_html=True)
    metrica = st.radio("Métrica", ["Ventas 6 Months", "Contribucion 6 Months"], horizontal=True)
    evol = df_h.groupby("Mes Año", as_index=False)[metrica].sum()
    st.plotly_chart(px.line(evol, x="Mes Año", y=metrica, markers=True), use_container_width=True)
    evol_seg = df_h.groupby(["Mes Año", "Segmento 2025"], as_index=False)[metrica].sum()
    st.plotly_chart(px.line(evol_seg, x="Mes Año", y=metrica, color="Segmento 2025", markers=True), use_container_width=True)
    tiendas_unicas = sorted(df_h["Tienda"].dropna().unique().tolist())
    tienda_sel = st.selectbox("Ver histórico de una tienda", ["-"] + tiendas_unicas)
    if tienda_sel != "-":
        st.plotly_chart(px.line(df_h[df_h["Tienda"] == tienda_sel], x="Mes Año", y=metrica, markers=True, title=tienda_sel), use_container_width=True)

with tab_alertas:
    st.markdown('<div class="section"><h3>Centro de alertas</h3></div>', unsafe_allow_html=True)
    st.caption("Prioriza las tiendas con SCOREF crítico y las variaciones negativas de ventas, contribución, batting, renta u operación.")
    resumen = al.resumen_alertas(df_t, df_h)
    total_alertas = sum(len(v) for v in resumen.values())
    c1, c2 = st.columns(2)
    c1.metric("Alertas activas", f"{total_alertas:,}")
    c2.metric("SCOREF crítico", f"{len(resumen['SCOREF en alerta']):,}")
    for nombre, df_alerta in resumen.items():
        with st.expander(f"{nombre} · {len(df_alerta)}", expanded=(nombre == "SCOREF en alerta" and len(df_alerta) > 0)):
            if df_alerta.empty:
                st.success("Sin alertas en esta categoría.")
            else:
                st.dataframe(df_alerta, use_container_width=True, hide_index=True)
