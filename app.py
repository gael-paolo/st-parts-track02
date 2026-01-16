import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# Configuración inicial
st.set_page_config(page_title="Tracking BOL02", layout="wide")

# Título
st.title("Tracking BOL02")

# URL desde secrets (como en la otra app)
URL_BOL2_TRACKING = st.secrets["URL_BOL2_TRACKING"]

# Función para cargar datos desde URL
@st.cache_data(ttl=300)  # Cache por 5 minutos
def cargar_datos_desde_url(url):

    try:
        df = pd.read_csv(url)
        
        df = df.replace(['', 'nan', 'NaN', 'None', 'N/A', 'n/a', '(en blanco)'], pd.NA)
        
        date_columns = ['ETD', 'SHIP_DATE', 'FECHA_INGRESO', 'FECHA_SOLICITADO']

        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                
                if col == 'FECHA_INGRESO':
                    df[col] = df[col].apply(
                        lambda x: pd.NaT if pd.isnull(x) or x == pd.Timestamp("1900-01-01") else x
                    )
        
        text_columns = ['ORIGEN', 'NP', 'NP_ACEPTADA', 'DESCRIPCION', 'MOD', 'STATUS', 
                       'CLIENTE', 'SOLICITADO', 'REFERENCIA', 'ESTADO']

        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        df = df.replace('nan', pd.NA)
        
        return df
        
    except Exception as e:
        st.error(f"Error al cargar los datos desde la URL: {e}")
        return pd.DataFrame()

def preparar_datos(df):

    df_clean = df.copy()
    
    search_cols = ['REFERENCIA', 'NP', 'CLIENTE']
    for col in search_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna('')
            df_clean[col] = df_clean[col].astype(str).str.strip()
    
    return df_clean

def filtrar_datos(df, referencia=None, np=None, cliente=None):

    df_filtrado = df.copy()
    
    if referencia and referencia.strip():
        df_filtrado = df_filtrado[
            df_filtrado['REFERENCIA'].str.contains(referencia.strip(), case=False, na=False)]
    
    if np and np.strip():
        df_filtrado = df_filtrado[
            df_filtrado['NP'].str.contains(np.strip(), case=False, na=False)]
    
    if cliente and cliente.strip():
        df_filtrado = df_filtrado[
            df_filtrado['CLIENTE'].str.contains(cliente.strip(), case=False, na=False)]
    
    return df_filtrado


def convertir_a_csv(df):
    return df.to_csv(index=False, encoding='utf-8-sig')

def formatear_fechas_df(df):

    df_display = df.copy()
    
    date_columns = ['ETD', 'SHIP_DATE', 'FECHA_INGRESO', 'FECHA_SOLICITADO']
    for col in date_columns:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
    
    return df_display


def main():
    with st.spinner("Cargando datos desde la URL..."):
        df = cargar_datos_desde_url(URL_BOL2_TRACKING)
    
    if df.empty:
        st.error("No se pudieron cargar los datos. Verifica la URL en los secrets.")
        return
    
    st.sidebar.header("📊 Información del Dataset")
    st.sidebar.write(f"**Total de registros:** {len(df):,}")
    st.sidebar.write(f"**Referencias únicas:** {df['REFERENCIA'].nunique()}")
    st.sidebar.write(f"**NPs únicos:** {df['NP'].nunique()}")
    st.sidebar.write(f"**Clientes únicos:** {df['CLIENTE'].nunique()}")
    
    if 'ESTADO' in df.columns:
        estado_counts = df['ESTADO'].value_counts()
        st.sidebar.subheader("📈 Distribución por Estado")
        for estado, count in estado_counts.head(5).items():
            st.sidebar.write(f"• {estado}: {count}")
    
    with st.expander("🔍 Vista previa del dataset completo (primeros 10 registros)"):
        df_preview = formatear_fechas_df(df.head(10))
        st.dataframe(df_preview)
        st.caption(f"Mostrando 10 de {len(df)} registros totales")
    
    st.header("🔍 Búsqueda de Pedidos")
    st.markdown("Usa al menos uno de los siguientes filtros para buscar:")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        referencia_input = st.text_input(
            "**Referencia:**", 
            placeholder="Ej: NI1025M",
            help="Busca por número de referencia")
    
    with col2:
        np_input = st.text_input(
            "**NP (Número de Parte):**", 
            placeholder="Ej: 110445RB0A",
            help="Busca por número de parte")
    
    with col3:
        cliente_input = st.text_input(
            "**Cliente:**", 
            placeholder="Ej: Sin Cliente",
            help="Busca por nombre de cliente")
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        buscar_btn = st.button(
            "🔎 **Buscar Pedidos**", 
            type="primary", 
            use_container_width=True,
            help="Click para ejecutar la búsqueda con los filtros ingresados")
    
    if buscar_btn:

        inputs = [referencia_input, np_input, cliente_input]
        valores_ingresados = [val for val in inputs if val and val.strip()]
        
        if not valores_ingresados:
            st.warning("⚠️ **Debes ingresar al menos un criterio de búsqueda**")
            st.info("Por favor, completa al menos uno de los campos: Referencia, NP o Cliente")
            
            if 'resultados_filtrados' in st.session_state:
                del st.session_state.resultados_filtrados
            if 'mostrar_resultados' in st.session_state:
                st.session_state.mostrar_resultados = False
        else:
            with st.spinner("🔍 Buscando en los datos..."):

                df_clean = preparar_datos(df)
                resultados = filtrar_datos(df_clean, referencia_input, np_input, cliente_input)
                
                if len(resultados) > 0:
                    st.session_state.resultados_filtrados = resultados
                    st.session_state.mostrar_resultados = True
                    st.success(f"✅ **Se encontraron {len(resultados)} registro(s)**")
                else:
                    st.warning("❌ **No se encontraron resultados con los criterios especificados**")
                    st.session_state.mostrar_resultados = False
    
    if 'mostrar_resultados' in st.session_state and st.session_state.mostrar_resultados:
        if 'resultados_filtrados' in st.session_state and st.session_state.resultados_filtrados is not None:
            resultados = st.session_state.resultados_filtrados
            
            st.header("📋 Resultados de la Búsqueda")
            
            st.subheader("📊 Estadísticas de Resultados")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total de Registros", len(resultados))
            
            with col2:
                estados_unicos = resultados['ESTADO'].nunique()
                st.metric("Estados Únicos", estados_unicos)
            
            with col3:
                nps_unicos = resultados['NP'].nunique()
                st.metric("NPs Únicos", nps_unicos)
            
            with col4:
                referencias_unicas = resultados['REFERENCIA'].nunique()
                st.metric("Referencias Únicas", referencias_unicas)
            
            st.subheader("📝 Detalles de los Pedidos")
            resultados_display = formatear_fechas_df(resultados)
            
            column_config = {}
            date_columns = ['ETD', 'SHIP_DATE', 'FECHA_INGRESO', 'FECHA_SOLICITADO']
            for col in date_columns:
                if col in resultados_display.columns:
                    column_config[col] = st.column_config.TextColumn(
                        col,
                        help="Fecha en formato DD/MM/YYYY")
            
            st.dataframe(
                resultados_display,
                use_container_width=True,
                hide_index=True,
                column_config=column_config)
            
            st.divider()
            st.subheader("📥 Descargar Resultados")
            
            if len(resultados) > 0 and len(resultados) < len(df):
                csv_data = convertir_a_csv(resultados)                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"resultados_busqueda_{timestamp}.csv"
                
                col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
                with col_dl2:
                    st.download_button(
                        label="📄 **Descargar como CSV**",
                        data=csv_data,
                        file_name=filename,
                        mime="text/csv",
                        help=f"Descargar {len(resultados)} registro(s) en formato CSV",
                        use_container_width=True,
                        type="secondary")
                
                with st.expander("📊 Información de la descarga"):
                    st.write(f"**Registros a descargar:** {len(resultados)}")
                    st.write(f"**Columnas incluidas:** {len(resultados.columns)}")
                    st.write("**Lista de columnas:**")
                    for col in resultados.columns:
                        st.write(f"• {col}")
                    
                    st.write(f"**Tamaño estimado:** {(len(csv_data) / 1024):.2f} KB")
                    
            elif len(resultados) == len(df):
                st.warning("""
                ⚠️ **No se permite descargar el dataset completo**
                
                Por políticas de seguridad, solo puedes descargar resultados de búsquedas específicas.
                Por favor, refina tu búsqueda usando los filtros disponibles.
                """)
            else:
                st.info("No hay resultados para descargar.")
    
    st.sidebar.divider()
    st.sidebar.header("ℹ️ Instrucciones de Uso")
    st.sidebar.info("""
    **Cómo buscar:**
    1. Usa al menos uno de los campos de búsqueda
    2. Los campos son combinables
    3. Búsqueda no sensible a mayúsculas
    
    **Restricciones:**
    • No se permiten búsquedas vacías
    • No se puede descargar el dataset completo
    
    **Campos disponibles:**
    • REFERENCIA: Código único del pedido
    • NP: Número de Parte
    • CLIENTE: Nombre del cliente
    """)
    
    # Footer
    st.divider()
    col_footer1, col_footer2, col_footer3 = st.columns([1, 2, 1])
    with col_footer2:
        st.caption("© 2026 Tracking GJ")
        st.caption(f"Última actualización de datos: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        st.caption("Aplicación desarrollada para consulta de tracking de pedidos")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
        st.info("Por favor, recarga la página o contacta al administrador.")