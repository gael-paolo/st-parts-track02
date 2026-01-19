import streamlit as st
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="Tracking BOL02", layout="wide")
st.title("Tracking BOL02")

URL_BOL2_TRACKING = st.secrets["URL_BOL2_TRACKING"]

# ======================================================
# CARGA DE DATOS (cache invalidado por versión)
# ======================================================
@st.cache_data(ttl=300)
def cargar_datos_desde_url(url, version="v3"):
    df = pd.read_csv(url)

    df = df.replace(
        ['', 'nan', 'NaN', 'None', 'N/A', 'n/a', '(en blanco)'],
        pd.NA
    )

    date_columns = ['ETD', 'SHIP_DATE', 'FECHA_INGRESO', 'FECHA_SOLICITADO']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    text_columns = [
        'ORIGEN', 'NP', 'NP_ACEPTADA', 'DESCRIPCION', 'MOD',
        'STATUS', 'CLIENTE', 'SOLICITADO', 'REFERENCIA', 'ESTADO'
    ]
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('nan', pd.NA)

    return df

# ======================================================
# PREPARACIÓN Y FILTRO
# ======================================================
def preparar_datos(df):
    df_clean = df.copy()
    for col in ['REFERENCIA', 'NP', 'CLIENTE']:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna('').astype(str).str.strip()
    return df_clean

def filtrar_datos(df, referencia, np, cliente):
    if referencia:
        df = df[df['REFERENCIA'].str.contains(referencia, case=False, na=False)]
    if np:
        df = df[df['NP'].str.contains(np, case=False, na=False)]
    if cliente:
        df = df[df['CLIENTE'].str.contains(cliente, case=False, na=False)]
    return df

# ======================================================
# FORMATEO DE FECHAS
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
    with st.spinner("Cargando datos..."):
        df = cargar_datos_desde_url(URL_BOL2_TRACKING, version="v3")

    if df.empty:
        st.error("No se pudieron cargar los datos.")
        return

    st.sidebar.header("📊 Información")
    st.sidebar.write(f"Total de registros: {len(df)}")
    st.sidebar.write(f"Referencias únicas: {df['REFERENCIA'].nunique()}")
    st.sidebar.write(f"NPs únicos: {df['NP'].nunique()}")
    st.sidebar.write(f"Clientes únicos: {df['CLIENTE'].nunique()}")

    st.header("🔍 Búsqueda de Pedidos")
    col1, col2, col3 = st.columns(3)

    referencia = col1.text_input("Referencia")
    np = col2.text_input("NP")
    cliente = col3.text_input("Cliente")

    buscar = st.button("🔎 Buscar", type="primary", use_container_width=True)

    if buscar:
        if not any([referencia.strip(), np.strip(), cliente.strip()]):
            st.warning("Debes ingresar al menos un criterio de búsqueda")
            st.session_state.mostrar_resultados = False
        else:
            df_filtrado = filtrar_datos(
                preparar_datos(df),
                referencia.strip(),
                np.strip(),
                cliente.strip()
            )

            if df_filtrado.empty:
                st.warning("No se encontraron resultados")
                st.session_state.mostrar_resultados = False
            else:
                st.session_state.resultados = df_filtrado
                st.session_state.mostrar_resultados = True
                st.success(f"Se encontraron {len(df_filtrado)} registros")

    if st.session_state.get("mostrar_resultados", False):
        resultados = st.session_state.resultados
        resultados_display = formatear_fechas_df(resultados)

        st.header("📋 Resultados")
        st.dataframe(
            resultados_display,
            use_container_width=True,
            hide_index=True
        )

        if 0 < len(resultados) < len(df):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            col_dl1, col_dl2 = st.columns(2)

            with col_dl1:
                st.download_button(
                    "📄 Descargar CSV",
                    convertir_csv(resultados),
                    f"resultados_{timestamp}.csv",
                    "text/csv"
                )

            with col_dl2:
                st.download_button(
                    "📊 Descargar XLSX",
                    convertir_xlsx(resultados_display),
                    f"resultados_{timestamp}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    st.divider()
    st.caption("© 2026 Tracking GJ")
    st.caption(f"Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

if __name__ == "__main__":
    main()
