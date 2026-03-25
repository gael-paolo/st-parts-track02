import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

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

# =========================
# BOTONES DE MODO
# =========================
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Buscar por Referencia"):
        st.session_state.modo_busqueda = "REFERENCE"

with col2:
    if st.button("Buscar por ATENTION_INVOICE"):
        st.session_state.modo_busqueda = "ATENTION_INVOICE"

with col3:
    if st.button("Buscar por NP"):
        st.session_state.modo_busqueda = "NP"

campo = st.session_state.modo_busqueda

# =========================
# URLS
# =========================
URL_SUPPLY = st.secrets["URL_SUPPLY"]
URL_REFRESH = st.secrets["URL_REFRESH"]

# =========================
# FUNCIONES
# =========================
@st.cache_data
def cargar_datos(url):
    df = pd.read_csv(url)

    df["REFERENCE"] = df["REFERENCE"].astype(str)
    df["INVOICE"] = df["INVOICE"].replace(["", "(en blanco)", "No Invoice"], pd.NA)

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
    df["INVOICE"] = df["INVOICE"].replace(["", "(en blanco)", "No Invoice"], pd.NA)

    df["ENTRY_DATE"] = pd.to_datetime(df["ENTRY_DATE"], errors="coerce")
    df.loc[df["ENTRY_DATE"] == pd.Timestamp("1900-01-01"), "ENTRY_DATE"] = pd.NaT

    cond_air = df["VIA"] == "AIR"
    cond_invoice = df["INVOICE"].notna()

    df["ETA_LP"] = pd.NaT

    df.loc[cond_air & cond_invoice & df["SHIP_DATE"].notna(), "ETA_LP"] = df["SHIP_DATE"] + pd.Timedelta(days=30)
    df.loc[cond_air & ~cond_invoice & df["ETD"].notna(), "ETA_LP"] = df["ETD"] + pd.Timedelta(days=45)
    df.loc[~cond_air & cond_invoice & df["SHIP_DATE"].notna(), "ETA_LP"] = df["SHIP_DATE"] + pd.Timedelta(days=50)
    df.loc[~cond_air & ~cond_invoice & df["ETD"].notna(), "ETA_LP"] = df["ETD"] + pd.Timedelta(days=50)

    now = pd.Timestamp.now()

    condiciones = [
        (df["STATUS"].isin(["C", "U"])),
        (df["STATUS"] == "Pending"),
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
            df1 = cargar_datos(URL_SUPPLY)

            if 'CHANNEL' in df1.columns:
                df1 = df1[
                    (df1['CHANNEL'] == 'BOL02') &
                    (df1['DATE_SOLICITED'].notna()) &
                    (df1['DATE_SOLICITED'] >= pd.Timestamp('2026-01-01'))]

            df2 = cargar_datos(URL_REFRESH)

            df = pd.concat([df2, df1], ignore_index=True)

            if campo in df.columns:
                df_filtrado = df[df[campo]
                                 .astype(str)
                                 .str.strip()
                                 .str.upper()
                                 == valor.strip().upper()].copy()
            else:
                df_filtrado = pd.DataFrame()

            if not df_filtrado.empty:
                df_filtrado = validar_estado_pedidos(df_filtrado)

                # Guardar resultado en sesión
                st.session_state.df_resultado = df_filtrado.copy()
            else:
                st.session_state.df_resultado = None

        except Exception as e:
            st.error(f"Error: {e}")

# =========================
# DISPLAY
# =========================
if st.session_state.df_resultado is not None:

    df_display = st.session_state.df_resultado.copy()
    df_display["ETA_LP"] = df_display["ETA_LP"].dt.strftime("%Y/%m/%d")

    st.subheader(f"Resultados para {campo}: {valor}")

    excel_data = convertir_a_excel(st.session_state.df_resultado)

    st.download_button(
        label="Descargar Excel",
        data=excel_data,
        file_name="tracking_pedidos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )