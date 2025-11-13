#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicación Streamlit para conversión bidireccional Gabmap ↔ Diatech
"""

import streamlit as st
import zipfile
import io
from pathlib import Path
from converter_core import convert_gabmap_to_diatech, convert_diatech_to_gabmap

# Configuración de la página
st.set_page_config(
    page_title="Conversor Gabmap ↔ Diatech",
    page_icon="🗺️",
    layout="wide"
)

# Título y descripción
st.title("🗺️ Conversor Gabmap ↔ Diatech")
st.markdown("""
Convierte tus archivos entre formato **Gabmap** (`.txt` + `.kml`) y formato **Diatech** (`.csv` + `boundaries/`).
""")

# Inicializar estado de sesión
if 'conversion_done' not in st.session_state:
    st.session_state.conversion_done = False
if 'conversion_direction' not in st.session_state:
    st.session_state.conversion_direction = 'gabmap_to_diatech'

# Selector de dirección de conversión
st.header("📋 Seleccionar Dirección de Conversión")

conversion_direction = st.radio(
    "¿Qué conversión deseas realizar?",
    options=['gabmap_to_diatech', 'diatech_to_gabmap'],
    format_func=lambda x: {
        'gabmap_to_diatech': '🔄 Gabmap → Diatech',
        'diatech_to_gabmap': '🔄 Diatech → Gabmap'
    }[x],
    horizontal=True
)

st.session_state.conversion_direction = conversion_direction

# Sección de carga de archivos según la dirección
st.header("📤 Cargar Archivos")

if conversion_direction == 'gabmap_to_diatech':
    st.markdown("""
    ### 📋 Instrucciones (Gabmap → Diatech):
    1. Sube tu archivo `.txt` con los datos lingüísticos
    2. Sube tu archivo `.kml` con las coordenadas geográficas
    3. Haz clic en "Convertir"
    4. Descarga el archivo ZIP con los resultados
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        txt_file = st.file_uploader(
            "Archivo TXT (datos lingüísticos)",
            type=['txt'],
            help="Archivo tabulado con conceptos y variantes por localidad"
        )
    
    with col2:
        kml_file = st.file_uploader(
            "Archivo KML (coordenadas geográficas)",
            type=['kml'],
            help="Archivo KML con placemarks de localidades y polígonos de límites"
        )
    
    # Validación y conversión
    if txt_file and kml_file:
        st.success("✅ Ambos archivos cargados correctamente")
        
        # Mostrar información de los archivos
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**TXT:** {txt_file.name} ({txt_file.size:,} bytes)")
        with col2:
            st.info(f"**KML:** {kml_file.name} ({kml_file.size:,} bytes)")
        
        # Botón de conversión
        if st.button("🔄 Convertir a formato Diatech", type="primary", use_container_width=True):
            with st.spinner("Procesando archivos..."):
                try:
                    # Leer archivos
                    txt_bytes = txt_file.read()
                    kml_bytes = kml_file.read()
                    
                    # Convertir
                    csv_bytes, boundaries_bytes, stats = convert_gabmap_to_diatech(
                        txt_bytes, kml_bytes, txt_file.name, kml_file.name
                    )
                    
                    # Crear ZIP
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        # Agregar CSV principal
                        csv_filename = Path(txt_file.name).stem + '.csv'
                        zipf.writestr(csv_filename, csv_bytes)
                        
                        # Agregar boundaries si existe
                        if boundaries_bytes:
                            boundaries_filename = Path(kml_file.name).stem + '.csv'
                            zipf.writestr(f'boundaries/{boundaries_filename}', boundaries_bytes)
                    
                    zip_buffer.seek(0)
                    
                    # Guardar en sesión
                    st.session_state.zip_data = zip_buffer.getvalue()
                    st.session_state.stats = stats
                    st.session_state.conversion_done = True
                    st.session_state.output_files = {
                        'csv': csv_filename,
                        'boundaries': boundaries_filename if boundaries_bytes else None
                    }
                    st.session_state.zip_filename = Path(txt_file.name).stem + '-diatech.zip'
                    
                    st.success("✅ Conversión completada exitosamente!")
                    
                except Exception as e:
                    st.error(f"❌ Error durante la conversión: {str(e)}")
                    st.exception(e)
                    st.session_state.conversion_done = False

else:  # diatech_to_gabmap
    st.markdown("""
    ### 📋 Instrucciones (Diatech → Gabmap):
    Puedes subir el archivo ZIP completo o los archivos por separado.
    """)
    
    # Opción de método de carga
    upload_method = st.radio(
        "Método de carga:",
        options=['zip', 'separados'],
        format_func=lambda x: {
            'zip': '📦 Subir ZIP completo',
            'separados': '📄 Subir archivos por separado'
        }[x],
        horizontal=True
    )
    
    csv_bytes = None
    boundaries_bytes = None
    csv_filename = None
    
    if upload_method == 'zip':
        zip_file = st.file_uploader(
            "Archivo ZIP de Diatech",
            type=['zip'],
            help="ZIP que contiene el CSV principal y opcionalmente boundaries/archivo.csv"
        )
        
        if zip_file:
            try:
                # Leer y extraer archivos del ZIP
                zip_bytes = zip_file.read()
                zip_io = io.BytesIO(zip_bytes)
                
                with zipfile.ZipFile(zip_io, 'r') as zipf:
                    # Buscar archivo CSV principal (no en boundaries/)
                    csv_found = False
                    boundaries_found = False
                    
                    for name in zipf.namelist():
                        # Ignorar directorios
                        if name.endswith('/'):
                            continue
                        
                        # Buscar archivo de boundaries
                        if 'boundaries/' in name.lower() and name.endswith('.csv'):
                            boundaries_bytes = zipf.read(name)
                            boundaries_found = True
                            continue
                        
                        # Buscar CSV principal (no en boundaries/)
                        if name.endswith('.csv') and not csv_found:
                            csv_bytes = zipf.read(name)
                            csv_filename = Path(name).name
                            csv_found = True
                    
                    if not csv_found:
                        st.error("❌ No se encontró archivo CSV en el ZIP")
                    else:
                        st.success("✅ ZIP cargado correctamente")
                        st.info(f"**CSV:** {csv_filename} encontrado")
                        if boundaries_found:
                            st.info("**Boundaries:** Encontrado en el ZIP")
                        else:
                            st.info("**Boundaries:** No encontrado (opcional)")
                            
            except Exception as e:
                st.error(f"❌ Error al leer el ZIP: {str(e)}")
                zip_file = None
    
    else:  # separados
        csv_file = st.file_uploader(
            "Archivo CSV (datos lingüísticos)",
            type=['csv'],
            help="Archivo CSV en formato Diatech con conceptos y variantes por localidad"
        )
        
        boundaries_file = st.file_uploader(
            "Archivo CSV de Boundaries (opcional)",
            type=['csv'],
            help="Archivo CSV con límites geográficos (boundaries)"
        )
        
        if csv_file:
            csv_bytes = csv_file.read()
            csv_filename = csv_file.name
            st.success("✅ Archivo CSV cargado correctamente")
            st.info(f"**CSV:** {csv_file.name} ({csv_file.size:,} bytes)")
            
            if boundaries_file:
                boundaries_bytes = boundaries_file.read()
                st.info(f"**Boundaries:** {boundaries_file.name} ({boundaries_file.size:,} bytes)")
            else:
                st.info("**Boundaries:** No se proporcionó (opcional)")
    
    # Botón de conversión (si hay CSV)
    if csv_bytes:
        if st.button("🔄 Convertir a formato Gabmap", type="primary", use_container_width=True):
            with st.spinner("Procesando archivos..."):
                try:
                    # Convertir
                    txt_bytes, kml_bytes, stats = convert_diatech_to_gabmap(
                        csv_bytes, boundaries_bytes, csv_filename or 'dialec.csv'
                    )
                    
                    # Crear ZIP
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        # Agregar TXT principal
                        txt_filename = Path(csv_filename or 'dialec.csv').stem + '.txt'
                        zipf.writestr(txt_filename, txt_bytes)
                        
                        # Agregar KML
                        kml_filename = Path(csv_filename or 'dialec.csv').stem + '.kml'
                        zipf.writestr(kml_filename, kml_bytes)
                    
                    zip_buffer.seek(0)
                    
                    # Guardar en sesión
                    st.session_state.zip_data = zip_buffer.getvalue()
                    st.session_state.stats = stats
                    st.session_state.conversion_done = True
                    st.session_state.output_files = {
                        'txt': txt_filename,
                        'kml': kml_filename
                    }
                    st.session_state.zip_filename = Path(csv_filename or 'dialec.csv').stem + '-gabmap.zip'
                    
                    st.success("✅ Conversión completada exitosamente!")
                    
                except Exception as e:
                    st.error(f"❌ Error durante la conversión: {str(e)}")
                    st.exception(e)
                    st.session_state.conversion_done = False

# Mostrar resultados si la conversión fue exitosa
if st.session_state.get('conversion_done', False):
    st.header("📊 Resultados")
    
    # Estadísticas
    stats = st.session_state.get('stats', {})
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Conceptos léxicos", stats.get('conceptos', 0))
    with col2:
        st.metric("Localidades", stats.get('localidades', 0))
    with col3:
        st.metric("Con coordenadas", stats.get('localidades_con_coordenadas', 0))
    
    # Advertencias si hay localidades sin coordenadas (solo para Gabmap → Diatech)
    if st.session_state.conversion_direction == 'gabmap_to_diatech' and stats.get('faltantes', 0) > 0:
        st.warning(f"⚠️ {stats['faltantes']} localidades no tienen coordenadas en el KML")
        if stats.get('faltantes_lista'):
            with st.expander("Ver localidades sin coordenadas"):
                for nombre in stats['faltantes_lista']:
                    st.text(f"  • {nombre}")
    
    # Descarga del ZIP
    st.header("📥 Descargar Resultados")
    
    st.download_button(
        label="⬇️ Descargar archivo ZIP",
        data=st.session_state.zip_data,
        file_name=st.session_state.zip_filename,
        mime="application/zip",
        type="primary",
        use_container_width=True
    )
    
    # Información del contenido
    output_files = st.session_state.get('output_files', {})
    if st.session_state.conversion_direction == 'gabmap_to_diatech':
        st.info(f"""
        **Contenido del ZIP:**
        - `{output_files.get('csv', 'N/A')}` - Archivo principal con datos lingüísticos
        {f"- `boundaries/{output_files.get('boundaries', 'N/A')}` - Límites geográficos" if output_files.get('boundaries') else "- (No se encontraron polígonos de límites en el KML)"}
        """)
    else:
        st.info(f"""
        **Contenido del ZIP:**
        - `{output_files.get('txt', 'N/A')}` - Archivo principal con datos lingüísticos
        - `{output_files.get('kml', 'N/A')}` - Archivo con coordenadas geográficas
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>Conversor Gabmap ↔ Diatech</p>
</div>
""", unsafe_allow_html=True)
