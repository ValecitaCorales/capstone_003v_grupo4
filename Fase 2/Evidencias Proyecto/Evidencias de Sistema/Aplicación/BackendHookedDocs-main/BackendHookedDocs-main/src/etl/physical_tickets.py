import os
import sys
import shutil
import pandas as pd
from src.core.crud import *

# Configuración de rutas para agregar el directorio src al path de Python
route = os.path.abspath(__file__)
index_route = route.find("BackendHookedDocs")
local_path = route[:index_route + len("BackendHookedDocs")]
global_route = os.path.join(local_path, "src")

sys.path.append(global_route)

def extract(tickets_path):
    """
    Extrae los datos de cada archivo Excel en la carpeta especificada.
    
    Parámetros:
    - tickets_path: Ruta de la carpeta que contiene los archivos de Excel.
    
    Retorna:
    - Una lista de tuplas (dataframe, archivo) con los datos extraídos y el nombre del archivo.
    """
    extracted_data = []

    for file in os.listdir(tickets_path):
        if file.endswith(".xls") or file.endswith(".xlsx"):
            file_path = os.path.join(tickets_path, file)
            try:
                # Leer archivo Excel
                data = pd.read_excel(file_path)
                extracted_data.append((data, file_path))
            except Exception as e:
                print(f"Error al leer el archivo {file_path}: {e}")

    return extracted_data

def transform(data):

    data = data[data['EFECTIVO'] != 0]

    # Renombrar columnas para evitar caracteres especiales
    column_mapping = {
        'Nº Documento': 'numero_documento',
        'Fecha Emisión': 'fecha_emision',
        'Código Tributario': 'codigo_tributario',
        'Monto Neto Documento': 'monto_neto',
        'Monto Impuestos Documento': 'monto_impuestos',
        'Monto Documento': 'monto_total',
        'Vendedor': 'vendedor',
        'Sucursal': 'sucursal'
    }
    data.rename(columns=column_mapping, inplace=True)
    
    # Seleccionar solo las columnas requeridas
    required_columns = list(column_mapping.values())
    data = data[[col for col in required_columns if col in data.columns]]

    # Eliminar filas con valores nulos
    data.dropna(inplace=True)

    # Convertir la columna 'fecha_emision' al formato deseado
    if 'fecha_emision' in data.columns:
        data['fecha_emision'] = pd.to_datetime(data['fecha_emision']).dt.strftime('%Y%m%d')
    
    return data


def load(data):
    """
    Carga los datos procesados en una base de datos (actualmente solo muestra los datos).
    
    Parámetros:
    - data: El DataFrame con los datos procesados de la factura.
    """
    print (data.head())
    create_physical_tickets(data)

def move_to_processed(file_path, base_path):
    """
    Mueve el archivo procesado a una carpeta llamada "PROCESADOS".
    
    Parámetros:
    - file_path: Ruta del archivo a mover.
    - base_path: Ruta base donde se encuentra la carpeta "PROCESADOS".
    """
    processed_folder = os.path.join(base_path, "PROCESADOS")

    if not os.path.exists(processed_folder):
        os.makedirs(processed_folder)

    shutil.move(file_path, processed_folder)

def main(physical_tickets_path):
    """
    Función principal que coordina las etapas de extracción, transformación y carga de datos.
    """
    
    # Etapa de extracción: leer todos los archivos Excel de la carpeta
    extracted_data_list = extract(physical_tickets_path)
    processed_count = 0  # Inicializa el contador

    for data, file_path in extracted_data_list:
        # Etapa de transformación: normaliza el DataFrame
        data_final = transform(data)

        # Etapa de carga: inserta o muestra los datos en la base de datos
        load(data_final)

        # Mover el archivo a la carpeta "PROCESADOS" después de procesarlo
        move_to_processed(file_path, physical_tickets_path)
        processed_count += 1  # Incrementa el contador por cada archivo movido

    return processed_count
