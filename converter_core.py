#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Núcleo de conversión de formato Gabmap a Diatech
Funciones adaptadas para trabajar con archivos en memoria
"""

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

def parse_kml_from_bytes(kml_bytes):
    """
    Extrae coordenadas y códigos de localidades del archivo KML (desde bytes)
    Solo extrae puntos (Point), ignora polígonos (Polygon) que son para límites
    Retorna: dict {nombre_localidad: {'lat': float, 'lon': float, 'code': str}}
    """
    tree = ET.parse(io.BytesIO(kml_bytes))
    root = tree.getroot()
    
    # Namespace de KML
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    localidades = {}
    
    # Buscar todos los Placemarks
    for placemark in root.findall('.//kml:Placemark', ns):
        # Verificar si es un polígono (límites) o un punto (localidad)
        polygon = placemark.find('.//kml:Polygon', ns)
        if polygon is not None:
            # Es un polígono, saltarlo (se usa para límites, no para localidades)
            continue
        
        # Buscar Point (localidades)
        point = placemark.find('.//kml:Point', ns)
        if point is None:
            # Si no es Point ni Polygon, intentar buscar coordenadas directamente
            pass
        
        name_elem = placemark.find('kml:name', ns)
        desc_elem = placemark.find('kml:description', ns)
        coords_elem = placemark.find('.//kml:coordinates', ns)
        
        if name_elem is not None and coords_elem is not None:
            nombre = name_elem.text.strip() if name_elem.text else ""
            descripcion = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
            
            # Coordenadas: longitud,latitud,altitud
            coords_str = coords_elem.text.strip()
            if coords_str:
                # Si hay múltiples coordenadas (polígono), tomar solo la primera
                # Si es un punto, solo habrá una coordenada
                first_coord = coords_str.split()[0] if ' ' in coords_str else coords_str
                parts = first_coord.split(',')
                if len(parts) >= 2:
                    try:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        
                        localidades[nombre] = {
                            'lat': lat,
                            'lon': lon,
                            'code': descripcion
                        }
                    except ValueError:
                        # Si no se puede convertir a float, saltar
                        continue
    
    return localidades

def read_dialec_txt_from_bytes(txt_bytes):
    """
    Lee el archivo dialec.txt de Gabmap (desde bytes)
    Retorna: (conceptos, datos) donde datos es dict {nombre_localidad: [variantes]}
    """
    conceptos = []
    datos = {}
    
    # Intentar diferentes codificaciones
    encodings_to_try = ['utf-8-sig', 'utf-16', 'utf-8', 'latin-1', 'cp1252']
    
    for enc in encodings_to_try:
        try:
            txt_str = txt_bytes.decode(enc)
            lines = txt_str.splitlines()
            
            # Primera línea: conceptos léxicos
            if lines:
                conceptos = lines[0].strip().split('\t')
                # La primera columna puede estar vacía, eliminarla si es necesario
                if conceptos and not conceptos[0].strip():
                    conceptos = conceptos[1:]
            
            # Resto de líneas: datos por localidad
            for line in lines[1:]:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    nombre_localidad = parts[0].strip()
                    variantes = parts[1:]  # Todas las variantes
                    
                    # Ajustar si hay desajuste de columnas
                    if len(variantes) > len(conceptos):
                        variantes = variantes[:len(conceptos)]
                    elif len(variantes) < len(conceptos):
                        variantes.extend([''] * (len(conceptos) - len(variantes)))
                    
                    datos[nombre_localidad] = variantes
            
            return conceptos, datos
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    # Si todas las codificaciones fallan, intentar con errores ignorados
    txt_str = txt_bytes.decode('utf-8', errors='ignore')
    lines = txt_str.splitlines()
    
    if lines:
        conceptos = lines[0].strip().split('\t')
        if conceptos and not conceptos[0].strip():
            conceptos = conceptos[1:]
    
    for line in lines[1:]:
        parts = line.strip().split('\t')
        if len(parts) >= 2:
            nombre_localidad = parts[0].strip()
            variantes = parts[1:]
            if len(variantes) > len(conceptos):
                variantes = variantes[:len(conceptos)]
            elif len(variantes) < len(conceptos):
                variantes.extend([''] * (len(conceptos) - len(variantes)))
            datos[nombre_localidad] = variantes
    
    return conceptos, datos

def normalize_name(name):
    """Normaliza nombres para comparación (minúsculas, sin espacios extra)"""
    return name.lower().strip()

def create_diatech_csv_bytes(conceptos, datos, localidades_kml, txt_filename):
    """
    Crea el contenido del archivo dialec.csv en formato Diatech (como bytes)
    Retorna: bytes del archivo CSV
    """
    # Crear diccionario normalizado para búsqueda
    localidades_normalizadas = {}
    for nombre, info in localidades_kml.items():
        localidades_normalizadas[normalize_name(nombre)] = (nombre, info)
    
    # Preparar encabezados con coordenadas
    encabezados = ['']  # Primera columna vacía para conceptos
    
    # Obtener lista de localidades en orden de aparición en datos
    nombres_localidades = list(datos.keys())
    
    for nombre_localidad in nombres_localidades:
        nombre_norm = normalize_name(nombre_localidad)
        
        if nombre_norm in localidades_normalizadas:
            nombre_original, info = localidades_normalizadas[nombre_norm]
            lat = info['lat']
            lon = info['lon']
            # Formato: "Municipio, Departamento[Latitud,Longitud]"
            # Si no tenemos departamento, usar solo el nombre
            encabezado = f'"{nombre_original}[{lat},{lon}]"'
        else:
            # Si no encontramos coordenadas, usar solo el nombre
            encabezado = f'"{nombre_localidad}"'
        
        encabezados.append(encabezado)
    
    # Escribir CSV a bytes (formato exacto de Diatech)
    output = io.BytesIO()
    output.write('""'.encode('utf-8'))
    output.write(';'.encode('utf-8'))
    output.write(';'.join(encabezados[1:]).encode('utf-8'))
    output.write('\r\n'.encode('utf-8'))
    
    # Escribir datos: cada concepto es una fila
    for i, concepto in enumerate(conceptos):
        # Primera columna: concepto SIN espacio inicial (formato nativo Diatech)
        output.write(f'"{concepto}";'.encode('utf-8'))
        
        # Resto de columnas: variantes
        for j, nombre_localidad in enumerate(nombres_localidades):
            if nombre_localidad in datos and i < len(datos[nombre_localidad]):
                variante = datos[nombre_localidad][i]
                if variante:
                    output.write(f'"{variante}"'.encode('utf-8'))
                else:
                    output.write('""'.encode('utf-8'))
            else:
                output.write('""'.encode('utf-8'))
            
            # Agregar punto y coma excepto en la última columna
            if j < len(nombres_localidades) - 1:
                output.write(';'.encode('utf-8'))
        
        output.write('\r\n'.encode('utf-8'))
    
    return output.getvalue()

def extract_country_boundaries_bytes(kml_bytes, kml_filename):
    """
    Extrae límites geográficos (polígonos) del archivo KML (desde bytes)
    Retorna: bytes del archivo CSV de boundaries, o None si no hay polígonos
    """
    tree = ET.parse(io.BytesIO(kml_bytes))
    root = tree.getroot()
    
    # Namespace de KML
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    # Buscar polígonos en el KML
    polygons = root.findall('.//kml:Polygon', ns)
    
    if polygons:
        # Extraer coordenadas del primer polígono encontrado
        coords_elem = polygons[0].find('.//kml:coordinates', ns)
        
        if coords_elem is not None and coords_elem.text:
            coords_str = coords_elem.text.strip()
            # Las coordenadas están separadas por espacios
            coord_pairs = coords_str.split()
            
            output = io.BytesIO()
            # Escribir manualmente para controlar formato exacto
            for coord_pair in coord_pairs:
                parts = coord_pair.split(',')
                if len(parts) >= 2:
                    lon = parts[0].strip()
                    lat = parts[1].strip()
                    # Formato: "longitud";"latitud" (usar CRLF como en archivos nativos)
                    output.write(f'"{lon}";"{lat}"\r\n'.encode('utf-8'))
            
            return output.getvalue()
    
    return None

def convert_gabmap_to_diatech(txt_bytes, kml_bytes, txt_filename, kml_filename):
    """
    Función principal de conversión
    Retorna: (csv_bytes, boundaries_bytes, stats)
    donde stats es un dict con estadísticas
    """
    # Leer archivos
    conceptos, datos = read_dialec_txt_from_bytes(txt_bytes)
    localidades_kml = parse_kml_from_bytes(kml_bytes)
    
    # Crear CSV principal
    csv_bytes = create_diatech_csv_bytes(conceptos, datos, localidades_kml, txt_filename)
    
    # Extraer boundaries
    boundaries_bytes = extract_country_boundaries_bytes(kml_bytes, kml_filename)
    
    # Calcular estadísticas
    nombres_txt = set(normalize_name(n) for n in datos.keys())
    nombres_kml = set(normalize_name(n) for n in localidades_kml.keys())
    coincidencias = nombres_txt & nombres_kml
    faltantes = nombres_txt - nombres_kml
    
    stats = {
        'conceptos': len(conceptos),
        'localidades': len(datos),
        'localidades_con_coordenadas': len(localidades_kml),
        'coincidencias': len(coincidencias),
        'faltantes': len(faltantes),
        'faltantes_lista': sorted(list(faltantes))[:10]  # Primeros 10
    }
    
    return csv_bytes, boundaries_bytes, stats

# ============================================================================
# FUNCIONES DE CONVERSIÓN INVERSA: Diatech → Gabmap
# ============================================================================

def read_diatech_csv_from_bytes(csv_bytes):
    """
    Lee el archivo dialec.csv de Diatech (desde bytes)
    Retorna: (conceptos, datos, localidades) donde:
    - conceptos: lista de conceptos léxicos
    - datos: dict {nombre_localidad: [variantes]}
    - localidades: dict {nombre_localidad: {'lat': float, 'lon': float}}
    """
    import csv
    
    csv_str = csv_bytes.decode('utf-8')
    lines = csv_str.splitlines()
    
    conceptos = []
    datos = {}
    localidades = {}
    
    if not lines:
        return conceptos, datos, localidades
    
    # Leer encabezado (primera línea)
    reader = csv.reader(io.StringIO(lines[0]), delimiter=';', quotechar='"')
    header = next(reader)
    
    # Extraer nombres de localidades y coordenadas del encabezado
    nombres_localidades = []
    for i, col in enumerate(header[1:], start=1):  # Saltar primera columna vacía
        # Formato: "Nombre[lat,lon]" o "Nombre, Departamento[lat,lon]"
        # Permitir espacios opcionales después de la coma en coordenadas
        match = re.match(r'^"?(.+?)\[([0-9.-]+)\s*,\s*([0-9.-]+)\]"?$', col)
        if match:
            nombre_completo = match.group(1).strip('"')
            lat = float(match.group(2))
            lon = float(match.group(3))
            
            # Extraer solo el nombre del municipio (antes de la coma si hay departamento)
            # IMPORTANTE: En Gabmap, el TXT solo debe tener el nombre, sin coordenadas
            nombre = nombre_completo.split(',')[0].strip()
            nombres_localidades.append(nombre)
            
            localidades[nombre] = {
                'lat': lat,
                'lon': lon
            }
        else:
            # Si no tiene coordenadas, usar el nombre tal cual (sin coordenadas)
            nombre = col.strip('"')
            # Asegurar que no tenga coordenadas en el nombre
            if '[' in nombre and ']' in nombre:
                # Si por alguna razón tiene coordenadas, extraer solo el nombre
                nombre = nombre.split('[')[0].strip()
            nombres_localidades.append(nombre)
            localidades[nombre] = {'lat': None, 'lon': None}
    
    # Leer datos (resto de líneas)
    for line in lines[1:]:
        reader = csv.reader(io.StringIO(line), delimiter=';', quotechar='"')
        row = next(reader)
        
        if not row:
            continue
        
        # Primera columna: concepto (puede tener espacio inicial)
        concepto = row[0].strip().strip('"').strip()
        if not concepto:
            continue
        
        conceptos.append(concepto)
        
        # Resto de columnas: variantes por localidad
        for i, variante in enumerate(row[1:], start=0):
            if i < len(nombres_localidades):
                nombre_localidad = nombres_localidades[i]
                if nombre_localidad not in datos:
                    datos[nombre_localidad] = []
                
                # Asegurar que la lista tenga el tamaño correcto
                while len(datos[nombre_localidad]) < len(conceptos):
                    datos[nombre_localidad].append('')
                
                # Agregar variante (sin comillas)
                variante_limpia = variante.strip('"').strip()
                datos[nombre_localidad][len(conceptos) - 1] = variante_limpia
    
    return conceptos, datos, localidades

def create_gabmap_txt_bytes(conceptos, datos):
    """
    Crea el contenido del archivo dialec.txt en formato Gabmap (como bytes)
    Formato: localidades x conceptos (transpuesto)
    Retorna: bytes del archivo TXT
    """
    output = io.BytesIO()
    
    # Primera línea: conceptos (separados por tabulaciones)
    conceptos_line = '\t'.join(conceptos)
    output.write(conceptos_line.encode('utf-8'))
    output.write('\r\n'.encode('utf-8'))
    
    # Resto de líneas: localidad + variantes
    for nombre_localidad in sorted(datos.keys()):
        variantes = datos[nombre_localidad]
        # Asegurar que tenga el mismo número de variantes que conceptos
        while len(variantes) < len(conceptos):
            variantes.append('')
        
        # Primera columna: nombre de localidad (SIN coordenadas)
        # Asegurar que no tenga coordenadas en el nombre (formato Gabmap)
        nombre_limpio = nombre_localidad
        if '[' in nombre_limpio and ']' in nombre_limpio:
            # Si tiene coordenadas, extraer solo el nombre
            nombre_limpio = nombre_limpio.split('[')[0].strip()
            # También quitar departamento si existe (antes de la coma)
            nombre_limpio = nombre_limpio.split(',')[0].strip()
        
        line = nombre_limpio
        # Resto: variantes separadas por tabulaciones
        line += '\t' + '\t'.join(variantes)
        output.write(line.encode('utf-8'))
        output.write('\r\n'.encode('utf-8'))
    
    return output.getvalue()

def create_kml_bytes(localidades, boundaries_bytes=None):
    """
    Crea el contenido del archivo KML con placemarks de localidades
    Retorna: bytes del archivo KML
    """
    # Crear estructura KML
    kml_root = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    document = ET.SubElement(kml_root, 'Document')
    
    # Agregar placemarks para cada localidad
    for nombre, info in localidades.items():
        placemark = ET.SubElement(document, 'Placemark')
        name_elem = ET.SubElement(placemark, 'name')
        name_elem.text = nombre
        
        if info.get('lat') is not None and info.get('lon') is not None:
            point = ET.SubElement(placemark, 'Point')
            coordinates = ET.SubElement(point, 'coordinates')
            # Formato KML: lon,lat,altitud
            coordinates.text = f"{info['lon']},{info['lat']},0"
    
    # Agregar polígono de límites si existe
    if boundaries_bytes:
        boundaries_str = boundaries_bytes.decode('utf-8')
        lines = boundaries_str.strip().splitlines()
        
        if lines:
            placemark = ET.SubElement(document, 'Placemark')
            name_elem = ET.SubElement(placemark, 'name')
            name_elem.text = 'Boundaries'
            
            polygon = ET.SubElement(placemark, 'Polygon')
            outer_boundary = ET.SubElement(polygon, 'outerBoundaryIs')
            linear_ring = ET.SubElement(outer_boundary, 'LinearRing')
            coordinates = ET.SubElement(linear_ring, 'coordinates')
            
            # Convertir boundaries CSV a formato KML
            coords_list = []
            for line in lines:
                parts = line.strip().split(';')
                if len(parts) >= 2:
                    lon = parts[0].strip('"')
                    lat = parts[1].strip('"')
                    coords_list.append(f"{lon},{lat},0")
            
            coordinates.text = ' '.join(coords_list)
    
    # Convertir a bytes
    try:
        ET.indent(kml_root, space='  ')
    except AttributeError:
        # ET.indent no disponible en Python < 3.9
        pass
    kml_str = ET.tostring(kml_root, encoding='utf-8', xml_declaration=True)
    return kml_str

def convert_diatech_to_gabmap(csv_bytes, boundaries_bytes, csv_filename):
    """
    Función principal de conversión inversa (Diatech → Gabmap)
    Retorna: (txt_bytes, kml_bytes, stats)
    donde stats es un dict con estadísticas
    """
    # Leer CSV de Diatech
    conceptos, datos, localidades = read_diatech_csv_from_bytes(csv_bytes)
    
    # Crear TXT de Gabmap (transponer)
    txt_bytes = create_gabmap_txt_bytes(conceptos, datos)
    
    # Crear KML
    kml_bytes = create_kml_bytes(localidades, boundaries_bytes)
    
    # Calcular estadísticas
    localidades_con_coords = sum(1 for info in localidades.values() 
                                 if info.get('lat') is not None and info.get('lon') is not None)
    
    stats = {
        'conceptos': len(conceptos),
        'localidades': len(datos),
        'localidades_con_coordenadas': localidades_con_coords
    }
    
    return txt_bytes, kml_bytes, stats

