import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import time

# =========================
# CONFIGURACIÓN
# =========================
st.set_page_config(page_title="Tracking Orders BOL02", layout="wide")

st.title("Tracking Orders BOL02 ~ Nissan Parts")
st.header("Consulta Pedidos Reservados")

# =========================
# SESSION STATE
# =========================
if "modo_busqueda" not in st.session_state:
    st.session_state.modo_busqueda = "REFERENCE"

if "df_resultado" not in st.session_state:
    st.session_state.df_resultado = None

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# =========================
# BOTONES DE CONTROL
# =========================
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("Buscar por Referencia"):
        st.session_state.modo_busqueda = "REFERENCE"

with col2:
    if st.button("Buscar por ATENTION_INVOICE"):
        st.session_state.modo_busqueda = "ATENTION_INVOICE"

with col3:
    if st.button("Buscar por NP"):
        st.session_state.modo_busqueda = "NP"

with col4:
    if st.button("🔄 Refrescar datos"):
        st.cache_data.clear()
        st.session_state.last_refresh = time.time()
        st.success("Cache limpiado. Se recargarán datos nuevos.")

campo = st.session_state.modo_busqueda

# =========================
# URLS
# =========================
URL_SUPPLY = st.secrets["URL_SUPPLY"]
URL_REFRESH = st.secrets["URL_REFRESH"]

# =========================
# FUNCIONES
# =========================
@st.cache_data(ttl=300)
def cargar_datos(url, refresh_key):
    df = pd.read_csv(
        url,
        dtype=str,
        sep=",",
        engine="python",
        on_bad_lines="warn"
    )

    # Normalización
    for col in ["REFERENCE", "ATENTION_INVOICE", "NP", "INVOICE"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.upper()
                .replace(["", "NAN", "NONE"], pd.NA)
            )

    # Fechas
    fechas = ["DATE_SOLICITED", "SHIP_DATE", "ARRIVAL_DATE", "ENTRY_DATE", "ETD", "ATENTION_DATE"]
    for c in fechas:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    columnas_finales = [
        'TYPE', 'VIA', 'SOLICITED', 'REFERENCE', 'CLIENT', 'NP',
        'NP_ACCEPTED', 'DATE_SOLICITED', 'DESCRIPTION', 'STATUS',
        'INVOICE', 'ETD', 'SHIP_DATE', 'ARRIVAL_DATE', 'ENTRY_DATE',
        'ATENTION_INVOICE', 'ATENTION_DATE', 'QTY', 'CHANNEL'
    ]

    columnas_existentes = [c for c in columnas_finales if c in df.columns]

    return df[columnas_existentes]


def validar_estado_pedidos(df):
    for col in ["VIA", "STATUS", "INVOICE"]:
        if col not in df.columns:
            df[col] = pd.NA

    df["STATUS"] = df["STATUS"].fillna("")
    df["INVOICE"] = df["INVOICE"].replace(["", "(EN BLANCO)", "NO INVOICE"], pd.NA)

    df["ENTRY_DATE"] = pd.to_datetime(df["ENTRY_DATE"], errors="coerce")
    df.loc[df["ENTRY_DATE"] == pd.Timestamp("1900-01-01"), "ENTRY_DATE"] = pd.NaT

    # =========================
    # CÁLCULO ETA_LP
    # =========================
    df["ETA_LP"] = pd.NaT

    # 🔴 Regla prioritaria: VIA = NSC → vacío
    cond_nsc = df["VIA"] == "NSC"
    
    cond_air = df["VIA"] == "AIR"
    cond_invoice = df["INVOICE"].notna()

    # Cálculos normales SOLO si no es NSC
    df.loc[~cond_nsc & cond_air & cond_invoice & df["SHIP_DATE"].notna(), "ETA_LP"] = df["SHIP_DATE"] + pd.Timedelta(days=30)
    df.loc[~cond_nsc & cond_air & ~cond_invoice & df["ETD"].notna(), "ETA_LP"] = df["ETD"] + pd.Timedelta(days=45)
    df.loc[~cond_nsc & ~cond_air & cond_invoice & df["SHIP_DATE"].notna(), "ETA_LP"] = df["SHIP_DATE"] + pd.Timedelta(days=50)
    df.loc[~cond_nsc & ~cond_air & ~cond_invoice & df["ETD"].notna(), "ETA_LP"] = df["ETD"] + pd.Timedelta(days=50)

    now = pd.Timestamp.now()

    condiciones = [
        (df["STATUS"].isin(["C", "U"])),
        (df["STATUS"] == "PENDING"),
        (df["ATENTION_DATE"].notna()),
        (df["ENTRY_DATE"].notna()),
        (df["ARRIVAL_DATE"].notna()),
        (df["ARRIVAL_DATE"].isna() & df["ETA_LP"].notna() & (df["ETA_LP"] < now) & df["INVOICE"].isna()),
        (df["ARRIVAL_DATE"].isna() & df["ETA_LP"].notna() & (df["ETA_LP"] < now) & df["INVOICE"].notna()),
        (df["INVOICE"].isna() & (df["STATUS"] == "B/O")),
        (df["ARRIVAL_DATE"].isna() & df["INVOICE"].notna())
    ]

    resultados = [
        "Cancelado y no será atendido.",
        "Pendiente de Colocar al Proveedor",
        "Pedido enviado a destino",
        "Pieza ingresada y lista para disposición",
        "La Pieza ha arribado al almacén.",
        "Pedido sin Atención y Retrasado",
        "Pedido Retrasado en tránsito",
        "Estado en Back Order, posible retraso.",
        "La Pieza se encuentra en tránsito."
    ]

    df["ANALISIS"] = np.select(condiciones, resultados, default="Sin información suficiente.")

    return df


def convertir_a_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()


# =========================
# INPUT
# =========================
valor = st.text_input(f"Ingrese {campo}:")
buscar = st.button("Buscar")

# =========================
# PROCESAMIENTO
# =========================
if buscar and valor:
    with st.spinner("Procesando..."):
        try:
            refresh_key = st.session_state.last_refresh

            df1 = cargar_datos(URL_SUPPLY, refresh_key)
            df2 = cargar_datos(URL_REFRESH, refresh_key)

            if 'CHANNEL' in df1.columns:
                df1 = df1[
                    (df1['CHANNEL'] == 'BOL02') &
                    (df1['DATE_SOLICITED'].notna()) &
                    (df1['DATE_SOLICITED'] >= pd.Timestamp('2025-01-01'))
                ]

            df = pd.concat([df2, df1], ignore_index=True)

            if campo in df.columns:
                df_filtrado = df[
                    df[campo]
                    .astype(str)
                    .str.contains(valor.strip(), case=False, na=False)
                ].copy()
            else:
                st.error(f"La columna {campo} no existe")
                df_filtrado = pd.DataFrame()

            st.write("Filas encontradas:", df_filtrado.shape[0])

            if not df_filtrado.empty:
                df_filtrado = validar_estado_pedidos(df_filtrado)
                st.session_state.df_resultado = df_filtrado
            else:
                st.session_state.df_resultado = None
                st.warning("No se encontraron resultados")

        except Exception as e:
            st.error(f"Error: {e}")

# =========================
# DISPLAY
# =========================
if st.session_state.df_resultado is not None:

    df_display = st.session_state.df_resultado.copy()

    if "ETA_LP" in df_display.columns:
        df_display["ETA_LP"] = df_display["ETA_LP"].dt.strftime("%Y/%m/%d")

    st.subheader(f"Resultados para {campo}: {valor}")

    st.dataframe(df_display.head(50), use_container_width=True)

    excel_data = convertir_a_excel(st.session_state.df_resultado)

    st.download_button(
        label="Descargar Excel",
        data=excel_data,
        file_name="tracking_pedidos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )