import streamlit as st
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="Tracking BOL02", layout="wide")
st.title("Tracking BOL02")

URL_BOL2_TRACKING = st.secrets["URL_BOL2_TRACKING"]

# ======================================================
# CARGA DE DATOS
# ======================================================
@st.cache_data(ttl=300)
def cargar_datos_desde_url(url):
    df = pd.read_csv(url)

    df = df.replace(
        ['', 'nan', 'NaN', 'None', 'N/A', 'n/a', '(en blanco)'],
        pd.NA
    )

    date_columns = ['ETD', 'SHIP_DATE', 'FECHA_INGRESO', 'FECHA_SOLICITADO']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col],
                errors="coerce",
                dayfirst=True
            )

    text_columns = [
        'ORIGEN', 'NP', 'NP_ACEPTADA', 'DESCRIPCION', 'MOD',
        'STATUS', 'CLIENTE', 'SOLICITADO', 'REFERENCIA', 'ESTADO'
    ]
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('nan', pd.NA)

    return df

# ======================================================
# FILTROS
# ======================================================
def preparar_datos(df):
    df = df.copy()
    for col in ['REFERENCIA', 'NP', 'CLIENTE']:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str).str.strip()
    return df

def filtrar_datos(df, referencia, np, cliente):
    if referencia:
        df = df[df['REFERENCIA'].str.contains(referencia, case=False, na=False)]
    if np:
        df = df[df['NP'].str.contains(np, case=False, na=False)]
    if cliente:
        df = df[df['CLIENTE'].str.contains(cliente, case=False, na=False)]
    return df

# ======================================================
# FORMATEO DE FECHAS (FIX DEFINITIVO)
# ======================================================
def formatear_fechas_df(df):
    df_display = df.copy()

    def format_fecha_ingreso(x):
        if pd.isnull(x):
            return "Pendiente"

        fecha = pd.to_datetime(x, errors="coerce")
        if pd.isnull(fecha):
            return "Pendiente"

        if fecha.date() == pd.Timestamp("1900-01-01").date():
            return "Pendiente"

        return fecha.strftime("%d/%m/%Y")

    for col in ['ETD', 'SHIP_DATE', 'FECHA_SOLICITADO']:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: pd.to_datetime(x).strftime("%d/%m/%Y") if pd.notnull(x) else ""
            )

    if 'FECHA_INGRESO' in df_display.columns:
        df_display['FECHA_INGRESO'] = df_display['FECHA_INGRESO'].apply(format_fecha_ingreso)

    return df_display

# ======================================================
# EXPORTACIONES
# ======================================================
def convertir_csv(df):
    return df.to_csv(index=False, encoding="utf-8-sig")

def convertir_xlsx(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultados")
    return output.getvalue()

# ======================================================
# APP
# ======================================================
def main():
    df = cargar_datos_desde_url(URL_BOL2_TRACKING)

    st.sidebar.header("📊 Información")
    st.sidebar.write(f"Total registros: {len(df)}")

    st.header("🔍 Búsqueda de Pedidos")
    col1, col2, col3 = st.columns(3)

    referencia = col1.text_input("Referencia")
    np = col2.text_input("NP")
    cliente = col3.text_input("Cliente")

    if st.button("🔎 Buscar", type="primary", use_container_width=True):
        if not any([referencia, np, cliente]):
            st.warning("Debes ingresar al menos un criterio")
            return

        df_filtrado = filtrar_datos(preparar_datos(df), referencia, np, cliente)

        if df_filtrado.empty:
            st.warning("No se encontraron resultados")
            return

        st.success(f"Se encontraron {len(df_filtrado)} registros")

        df_display = formatear_fechas_df(df_filtrado)

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        if len(df_filtrado) < len(df):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "📄 Descargar CSV",
                    convertir_csv(df_filtrado),
                    f"resultados_{timestamp}.csv",
                    "text/csv"
                )
            with col_dl2:
                st.download_button(
                    "📊 Descargar XLSX",
                    convertir_xlsx(df_display),
                    f"resultados_{timestamp}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    st.divider()
    st.caption("© 2026 Tracking GJ")

if __name__ == "__main__":
    main()
