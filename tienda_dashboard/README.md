# Dashboard Red de Tiendas (Streamlit)

App que lee tu Excel (hojas **JUN** y **LAST**) desde OneDrive, calcula
estadísticas y genera alertas automáticas. Se actualiza sola cada vez que
editas el Excel en OneDrive (caché de 15 min, o botón "Actualizar ahora").

## Estructura del proyecto

```
tienda_dashboard/
├── app.py                     # Dashboard (4 pestañas: Resumen, Tiendas, Histórico, Alertas)
├── data_loader.py             # Descarga y limpia el Excel (JUN y LAST)
├── alerts.py                  # Reglas de negocio para las alertas
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── secrets.toml.example   # Plantilla del link de OneDrive
└── data/
    └── Book.xlsx              # Copia local de respaldo (opcional, para pruebas)
```

---

## Paso 1 — Generar el link de descarga directa de OneDrive

1. Abre OneDrive (onedrive.com) y ubica tu archivo Excel.
2. Clic derecho → **Compartir** → cambia el permiso a **"Cualquier persona
   con el vínculo puede ver"** (no hace falta que puedan editar).
3. Copia el link generado. Se verá algo así:
   `https://1drv.ms/x/s!AbCdEfGhIjKlMnOp...`
4. **Opción simple (recomendada):** pega ese link tal cual en
   `ONEDRIVE_URL` — el `data_loader.py` ya sabe resolver los links cortos
   `1drv.ms` porque siguen la redirección automáticamente.
5. **Si usas OneDrive de empresa (SharePoint)** el link se verá como
   `https://tuempresa-my.sharepoint.com/:x:/g/personal/.../Book.xlsx?...`
   — en ese caso el loader agrega automáticamente `&download=1` al final.

> ⚠️ Importante: cualquier persona con el link puede descargar el archivo
> (no requiere login). Si el contenido es muy sensible, la alternativa más
> segura es Microsoft Graph API con login — lo podemos armar después si
> hace falta, pero implica registrar una app en Azure AD y manejar tokens.

---

## Paso 2 — Subir el proyecto a GitHub

```bash
cd tienda_dashboard
git init
git add .
git commit -m "Dashboard inicial de tiendas"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/tienda-dashboard.git
git push -u origin main
```

El `.gitignore` ya excluye `data/Book.xlsx` y `.streamlit/secrets.toml`
para que **nunca subas tu Excel real ni tu link privado a GitHub**.

---

## Paso 3 — Desplegar en Streamlit Community Cloud

1. Entra a [share.streamlit.io](https://share.streamlit.io) con tu cuenta
   de GitHub.
2. Clic en **"New app"** → elige tu repo `tienda-dashboard`, branch `main`,
   archivo principal `app.py`.
3. Antes de darle "Deploy", ve a **"Advanced settings" → Secrets** y pega:
   ```toml
   ONEDRIVE_URL = "https://1drv.ms/x/s!TU_LINK_AQUI"
   ```
4. Deploy. En 1-2 minutos tendrás la URL pública de tu dashboard.

Cada vez que actualices el Excel en OneDrive, la app lo reflejará solo
(máximo 15 minutos de retraso por el caché, o al instante si le das
**"🔄 Actualizar ahora"** en la barra lateral).

---

## Probar en tu computador antes de desplegar (opcional)

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edita .streamlit/secrets.toml con tu link real
streamlit run app.py
```

Si no configuras `secrets.toml`, la app usa automáticamente el archivo
local `data/Book.xlsx` como respaldo — útil para probar sin depender de
internet.

---

## Clasificación de rendimiento con SCOREF

La hoja `JUN` puede incluir la columna `SCOREF`. El dashboard la convierte a número y clasifica cada tienda así:

| Rango de SCOREF | Clasificación | Uso recomendado |
|---|---|---|
| Mayor a 3 | Mejor tienda | Identificar prácticas y tiendas referentes |
| De 0 a 3 | Tienda buena | Mantener seguimiento normal |
| De -3 a menos de 0 | En observación | Revisar tendencia y plan de mejora |
| Menor a -3 | En alerta | Priorizar diagnóstico y acción correctiva |

La pestaña **Alertas** muestra primero las tiendas con SCOREF menor a -3 y conserva las alertas existentes de caída de ventas, caída de contribución, batting bajo, renta/ventas baja y estado operativo crítico. Los filtros de plaza y de clasificación SCOREF aplican a todo el dashboard.

## Ajustar las alertas

Los umbrales están al inicio de `alerts.py`:

```python
BATTING_BAJO = 0.5          # %Batting por debajo de esto = alerta
CAIDA_VENTAS_PCT = -0.10    # caída >= 10% vs mes anterior
CAIDA_MARGEN_PCT = -0.15    # caída >= 15% en contribución
RENTA_BAJA_PCT = 0.05       # renta/ventas por debajo de 5%
ESTADOS_CRITICOS = ["OBRA", "FIRMADA"]
```

Cámbialos según tu criterio de negocio y vuelve a desplegar (git push).

**Nota sobre %Batting:** en tu archivo actual, 672 de 770 tiendas tienen
`%Batting = 0`. El loader trata esos casos como "sin dato" y los excluye
de la alerta (en vez de marcarlos como "batting malo"), para no generar
falsos positivos. Si en tu negocio 0 sí significa algo distinto, avísame
y ajustamos la regla.

---

## Próximos pasos posibles

- **API REST real** (además del dashboard): se puede agregar un backend
  con FastAPI que exponga `/tiendas`, `/alertas`, etc. en JSON, por si
  quieres consumir los datos desde otra app (Power BI, otro dashboard, etc.).
- **Notificaciones automáticas** de alertas por correo/WhatsApp/Slack
  cuando aparezcan nuevas alertas críticas.
- **Autenticación** para que solo tu equipo vea el dashboard (Streamlit
  Cloud lo soporta con "viewer restrictions" en el plan pago, o con
  `streamlit-authenticator` en el gratuito).
- Integrar las hojas PTM (zonas de expansión) y EOD (encuestas) más
  adelante si las vuelves a necesitar — el código ya estaba armado, solo
  se quitó del dashboard actual.
