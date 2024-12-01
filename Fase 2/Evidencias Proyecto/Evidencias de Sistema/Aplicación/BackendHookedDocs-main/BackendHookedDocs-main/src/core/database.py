import oracledb
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configuración de la base de datos
DB_CONFIG = {
    "username": os.getenv("DB_USERNAME"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "sid": os.getenv("DB_SID")
}

def get_connection():
    """
    Crear y devolver una conexión a la base de datos.
    """
    try:
        dsn = f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['sid']}"
        connection = oracledb.connect(
            user=DB_CONFIG['username'],
            password=DB_CONFIG['password'],
            dsn=dsn
        )
        return connection
    except oracledb.DatabaseError as e:
        print(f"Error al conectarse a la base de datos: {e}")
        raise e

def close_connection(connection):
    """
    Cerrar la conexión a la base de datos.
    """
    if connection:
        connection.close()
