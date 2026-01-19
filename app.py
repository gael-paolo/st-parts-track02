import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Tracking BOL02", layout="wide")

st.title("Tracking BOL02")

URL_BOL2_TRACKING = st.secrets["URL_BOL2_TRACKING"]

@st.cache_data(ttl=300)
def cargar_datos_desde_url(url):
    try:
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
                    errors='coerce',
                    dayfirst=True
                )
                if col == 'FECHA_INGRESO':
                    df[col] = df[col].apply(
                        lambda x: pd.NaT if pd.isnull(x) or x == pd.Timestamp("1900-01-01") else x
                    )

        text_columns = [
            'ORIGEN', 'NP', 'NP_ACEPTADA', 'DESCRIPCION', 'MOD', 'STATUS',
            'CLIENTE', 'SOLICITADO', 'REFERENCIA', 'ESTADO'
        ]
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace('nan', pd.NA)

        return df

    except Exception as e:
        st.error(f"Error al cargar los datos desde la URL: {e}")
        return pd.DataFrame()

def preparar_datos(df):
    df_clean = df.copy()
    search_cols = ['REFERENCIA', 'NP', 'CLIENTE']
    for col in search_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna('').astype(str).str.strip()
    return df_clean

def filtrar_datos(df, referencia=None, np=None, cliente=None):
    df_filtrado = df.copy()

    if referencia and referencia.strip():
        df_filtrado = df_filtrado[
            df_filtrado['REFERENCIA'].str.contains(referencia.strip(), case=False, na=False)
        ]

    if np and np.strip():
        df_filtrado = df_filtrado[
            df_filtrado['NP'].str.contains(np.strip(), case=False, na=False)
        ]

    if cliente and cliente.strip():
        df_filtrado = df_filtrado[
            df_filtrado['CLIENTE'].str.contains(cliente.strip(), case=False, na=False)
        ]

    return df_filtrado

def convertir_a_csv(df):
    return df.to_csv(index=False, encoding='utf-8-sig')

def formatear_fechas_df(df):
    df_display = df.copy()

    date_columns = ['ETD', 'SHIP_DATE', 'FECHA_INGRESO', 'FECHA_SOLICITADO']
    for col in date_columns:
        if col in df_display.columns:
            if col == 'FECHA_INGRESO':
                df_display[col] = df_display[col].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else 'Pendiente'
                )
            else:
                df_display[col] = df_display[col].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else ''
                )

    return df_display

def main():
    with st.spinner("Cargando datos desde la URL..."):
        df = cargar_datos_desde_url(URL_BOL2_TRACKING)

    if df.empty:
        st.error("No se pudieron cargar los datos.")
        return

    st.sidebar.header("📊 Información")
    st.sidebar.write(f"**Total de registros:** {len(df):,}")
    st.sidebar.write(f"**Referencias únicas:** {df['REFERENCIA'].nunique()}")
    st.sidebar.write(f"**NPs únicos:** {df['NP'].nunique()}")
    st.sidebar.write(f"**Clientes únicos:** {df['CLIENTE'].nunique()}")

    if 'ESTADO' in df.columns:
        st.sidebar.subheader("📈 Distribución por Estado")
        for estado, count in df['ESTADO'].value_counts().head(5).items():
            st.sidebar.write(f"• {estado}: {count}")

    st.header("🔍 Búsqueda de Pedidos")
    col1, col2, col3 = st.columns(3)

    with col1:
        referencia_input = st.text_input("Referencia")
    with col2:
        np_input = st.text_input("NP")
    with col3:
        cliente_input = st.text_input("Cliente")

    buscar_btn = st.button("🔎 Buscar", type="primary", use_container_width=True)

    if buscar_btn:
        if not any([referencia_input.strip(), np_input.strip(), cliente_input.strip()]):
            st.warning("Debes ingresar al menos un criterio de búsqueda")
            st.session_state.mostrar_resultados = False
        else:
            df_clean = preparar_datos(df)
            resultados = filtrar_datos(df_clean, referencia_input, np_input, cliente_input)
            if not resultados.empty:
                st.session_state.resultados_filtrados = resultados
                st.session_state.mostrar_resultados = True
                st.success(f"Se encontraron {len(resultados)} registros")
            else:
                st.warning("No se encontraron resultados")
                st.session_state.mostrar_resultados = False

    if st.session_state.get("mostrar_resultados", False):
        resultados = st.session_state["resultados_filtrados"]

        st.header("📋 Resultados")
        resultados_display = formatear_fechas_df(resultados)

        st.dataframe(
            resultados_display,
            use_container_width=True,
            hide_index=True
        )

        if 0 < len(resultados) < len(df):
            csv_data = convertir_a_csv(resultados)
            filename = f"resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            st.download_button(
                "📄 Descargar CSV",
                data=csv_data,
                file_name=filename,
                mime="text/csv"
            )

    st.sidebar.divider()
    st.sidebar.info(
        "• Usa al menos un filtro\n"
        "• Búsqueda no sensible a mayúsculas\n"
        "• No se permite descargar el dataset completo"
    )

    st.divider()
    st.caption("© 2026 Tracking GJ")
    st.caption(f"Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
