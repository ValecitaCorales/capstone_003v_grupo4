import json
import datetime
import logging
import oracledb
from .database import get_connection, close_connection

# Configuración de logging para el seguimiento y depuración
logging.basicConfig(level=logging.INFO)


#verificar conexion con la BD al llamar a funciones del crud
def with_connection(func):
    """Decorator para manejar la conexión a la base de datos."""
    def wrapper(*args, **kwargs):
        connection = get_connection()
        if not connection:
            logging.error("No se pudo establecer la conexión con la base de datos.")
            return None
        try:
            result = func(connection, *args, **kwargs)
            connection.commit()
            return result
        except Exception as e:
            logging.error(f"Error en la función {func.__name__}: {e}")
            connection.rollback()
        finally:
            close_connection(connection)
    return wrapper


# formatea fecha a formato DDMMMYYYY
def format_date(date_str):
    """Convierte una fecha en cualquier formato válido (incluido datetime con tiempo) a 'DD/MM/YYYY'."""
    # Formatos de fecha conocidos, incluido formato con hora
    formatos_validos = [
        "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d",
        "%d %b %Y", "%d %B %Y", "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %I:%M %p",
        "%d %b %Y %H:%M:%S", "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S %Z"
    ]

    for fmt in formatos_validos:
        try:
            # Intentamos parsear la fecha
            date_obj = datetime.datetime.strptime(date_str, fmt)
            # Retornamos en formato 'DD/MM/YYYY'
            return date_obj.strftime("%d/%m/%Y")
        except ValueError:
            continue

    # Si ninguno de los formatos funciona, levantamos un error
    raise ValueError(f"Formato de fecha inválido para '{date_str}'. Use un formato válido como 'DD/MM/YYYY'.")


# CREA nuevos registros en facturas emitidas o recibidas
@with_connection
def create_invoice(connection, data, table_name):
    """Insertar una nueva factura en la tabla especificada."""
    cursor = connection.cursor()
    invoice_json = json.dumps(data)
    insert_query = f"INSERT INTO {table_name} (invoice_data) VALUES (:invoice_data)"
    cursor.execute(insert_query, invoice_data=invoice_json)

    if table_name == 'invoices_issued':
        cursor.callproc('pkg_issued.main')
    elif table_name == 'invoices_received':
        cursor.callproc('pkg_received.main')
    
    logging.info(f"Factura insertada correctamente en {table_name}.")
    cursor.close()


# CREA nuevos registros en boletas fisicas
@with_connection
def create_physical_tickets(connection, data):
    """Insertar datos en la tabla physical_tickets."""
    cursor = connection.cursor()
    data_to_insert = data.to_dict(orient='records')
    insert_sql = """
    INSERT INTO physical_tickets (
        folio, neto, iva, total, dte, fecha, rut_vendedor, sucursal
    ) VALUES (
        :numero_documento, :monto_neto, :monto_impuestos, :monto_total, :codigo_tributario, to_date(:fecha_emision, 'YYYYMMDD'), :vendedor, :sucursal
    )
    """
    #:folio, :neto, :iva, :total, :dte, to_date(:fecha, 'YYYYMMDD'), :vendedor, :sucursal
    #:Nº Documento, :Monto Neto Documento, :Monto Impuestos Documento, :Monto Documento, :Código Tributario, to_date(:Fecha Emisión, 'YYYYMMDD'), :Vendedor, :Sucursal
    cursor.executemany(insert_sql, data_to_insert)
    logging.info(f"{cursor.rowcount} registros insertados en physical_tickets.")
    cursor.close()


# CREA nuevos registros en boletas electronicas
@with_connection
def create_electronic_tickets(connection, data):
    """Insertar datos en la tabla electronic_tickets."""
    cursor = connection.cursor()
    data_to_insert = data.to_dict(orient='records')
    insert_sql = """
    INSERT INTO electronic_tickets (
        tipo, tipo_documento, folio, razon_social_receptor, fecha_publicacion,
        emision, monto_neto, monto_exento, monto_iva, monto_total, fecha_sii, estado_sii
    ) VALUES (
        :tipo, 
        :tipo_documento, 
        :folio, 
        :razon_social_receptor,
        to_date(:publicacion,'YYYYMMDD'), 
        to_date(:fecha_emision,'YYYYMMDD'), 
        :monto_neto, 
        :monto_exento, 
        :monto_impuestos, 
        :monto_total, 
        to_date(:fecha_sii,'YYYYMMDD'), 
        :estado_sii
    )
    """
    cursor.executemany(insert_sql, data_to_insert)
    logging.info(f"{cursor.rowcount} registros insertados en electronic_tickets.")
    cursor.close()


# LEE registro de validaciones en log
@with_connection
def read_log(connection):
    """Leer todas las facturas desde la tabla invoice_audit_log."""
    cursor = connection.cursor()
    select_query = "SELECT ISSUER_NAME, PROCESS, INVOICE_ID, ISSUE_DATE, VALIDATION_MESSAGE FROM invoice_audit_log"
    cursor.execute(select_query)
    rows = cursor.fetchall()
    invoices = [
        {"ISSUER_NAME": row[0],"PROCESS": row[1], "INVOICE_ID": row[2], "ISSUE_DATE": row[3], "VALIDATION_MESSAGE": row[4]} 
        for row in rows
    ]
    cursor.close()
    return invoices


# LEE campos validados segun funcionabilidad
@with_connection
def read_select_invoice(connection, doc_number, functionalitie):
    """Leer una factura o documento específico desde la base de datos según la funcionalidad."""
    cursor = connection.cursor()
    # Consultas y campos por funcionalidad
    queries = {
        1: ("flat_invoices_received", "invoice_number", [
            'subtotal', 'tax', 'total', 'pay_method', 'issuer_name', 'issuer_rut', 'invoice_number'
        ]),
        2: ("flat_invoices_issued", "invoice_number", [
            'subtotal', 'tax', 'total', 'pay_method', 'issuer_rut', 'invoice_number', 'invoice_type', 'buyer_name', 'buyer_rut'
        ]),
        3: ("physical_tickets", "folio", [
            'folio', 'neto', 'iva', 'total', 'fecha', 'rut_vendedor', 'sucursal'
        ]),
        4: ("electronic_tickets", "folio", [
            'tipo_documento', 'folio', 'emision', 'monto_neto', 'monto_exento', 'monto_iva', 'monto_total'
        ])
    }
    query, id_field, fields = queries.get(functionalitie, (None, None, None))
    
    if not query:
        logging.error("Funcionalidad no reconocida.")
        cursor.close()
        return []
    
    select_query = f"SELECT {', '.join(fields)} FROM {query} WHERE {id_field} = :doc_number"
    cursor.execute(select_query, doc_number=doc_number)
    #print(select_query)
    rows = cursor.fetchall()
    invoices = [dict(zip(fields, row)) for row in rows]
    cursor.close()
    return invoices


# ACTUALIZA campos validados segun funcionabilidad
@with_connection
def update_selected_invoice(connection, invoice_number, updated_fields, functionalitie):
    """Actualizar campos específicos de una factura existente."""
    cursor = connection.cursor()
    table_info = {
        1: ("flat_invoices_received", "invoice_number", [
            'subtotal', 'tax', 'total', 'pay_method', 'issuer_name', 'issuer_rut', 'invoice_number'
        ]),
        2: ("flat_invoices_issued", "invoice_number", [
            'subtotal', 'tax', 'total', 'pay_method', 'issuer_rut', 'invoice_number', 'invoice_type', 'buyer_name', 'buyer_rut'
        ]),
        3: ("physical_tickets", "folio", [
            'folio', 'neto', 'iva', 'total', 'fecha', 'rut_vendedor', 'sucursal'
        ]),
        4: ("electronic_tickets", "folio", [
            'tipo_documento', 'folio', 'emision', 'monto_neto', 'monto_exento', 'monto_iva', 'monto_total'
        ])
    }
    table_info = table_info.get(functionalitie)
    if not table_info:
        logging.error("Funcionalidad no reconocida.")
        cursor.close()
        return

    table_name, id_field, valid_fields = table_info
    fields_to_update = {k: v for k, v in updated_fields.items() if k in valid_fields}

    if not fields_to_update:
        logging.warning("No hay campos válidos para actualizar.")
        cursor.close()
        return

    # Convertir campos de fecha y especificar el formato de fecha en la consulta SQL
    date_fields = ['fecha', 'emision']
    for date_field in date_fields:
        if date_field in fields_to_update:
            fields_to_update[date_field] = format_date(fields_to_update[date_field])
            fields_to_update[date_field] = f"TO_DATE(:{date_field}, 'DD/MM/YYYY')"

    # Construir cláusula SET, manejando fechas con TO_DATE
    set_clause = ', '.join([
        f"{field} = {fields_to_update[field]}" if field in date_fields else f"{field} = :{field}" 
        for field in fields_to_update.keys()
    ])
    
    # Eliminar TO_DATE para los parámetros de fecha en el diccionario params
    params = {k: v for k, v in fields_to_update.items() if k not in date_fields}
    params.update({date_field: format_date(updated_fields[date_field]) for date_field in date_fields if date_field in updated_fields})

    params[id_field] = invoice_number
    update_query = f"UPDATE {table_name} SET {set_clause} WHERE {id_field} = :{id_field}"

    cursor.execute(update_query, params)
    logging.info(f"Registro actualizado en {table_name}.")

    logging.info(functionalitie)
    #llamando a auditoria
    if functionalitie == 1:
        cursor.callproc('pkg_received.audit_invoice_received')
    elif functionalitie == 2:
        cursor.callproc('pkg_issued.audit_invoice_issued')
    elif functionalitie in [3,4]:
        logging.info(f"Documentos validados previamente.")
    else:
        logging.info(f"funcionabilidad no definida.")

    cursor.close()


# ELIMINA registros segun funcionabilidad
@with_connection
def delete_invoice(connection, functionalitie, invoice_number):
    """Eliminar una factura o boleta según funcionalidad."""
    cursor = connection.cursor()
    delete_queries = {
        1: "DELETE FROM flat_invoices_received WHERE invoice_number = :invoice_number",
        2: "DELETE FROM flat_invoices_issued WHERE invoice_number = :invoice_number",
        3: "DELETE FROM physical_tickets WHERE folio = :invoice_number",
        4: "DELETE FROM electronic_tickets WHERE folio = :invoice_number"
    }
    delete_query = delete_queries.get(functionalitie, None)

    if not delete_query:
        logging.error("Funcionalidad no reconocida para eliminación.")
        cursor.close()
        return

    cursor.execute(delete_query, invoice_number=invoice_number)
    logging.info(f"Registro eliminado en funcionalidad {functionalitie}.")

    insert_sql = "DELETE FROM invoice_audit_log WHERE invoice_ID = :invoice_number"
    cursor.execute(insert_sql, invoice_number=invoice_number)
    logging.info(f"{cursor.rowcount} registros insertados en electronic_tickets.")
  

    """Llama a la función FN_LOG_DEPURATION y verifica el resultado."""
    try:
        # Llama a la función y espera un resultado de tipo NUMBER
        result = cursor.callfunc('PKG_LOG_DEPURATION.FN_LOG_DEPURATION', oracledb.NUMBER, [invoice_number])
        
        # Verifica el resultado
        if result == 0:
            logging.info(f"Depuración exitosa para la factura {invoice_number}.")
        else:
            logging.error(f"Error en depuración para la factura {invoice_number}: Resultado inesperado ({result}).")
    
    except oracledb.Error as e:
        # Captura errores de Oracle y los muestra en el log
        logging.error(f"Error al ejecutar FN_LOG_DEPURATION para la factura {invoice_number}: {e}")
    except Exception as e:
        # Captura cualquier otro error y los muestra en el log
        logging.error(f"Error inesperado al ejecutar FN_LOG_DEPURATION para la factura {invoice_number}: {e}")

    cursor.close()
