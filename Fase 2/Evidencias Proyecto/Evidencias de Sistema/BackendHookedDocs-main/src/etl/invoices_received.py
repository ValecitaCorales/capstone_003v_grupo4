import pdfplumber
import re
import os
import sys
import shutil
import unicodedata

# Configuración de rutas para agregar el directorio src al path de Python
route = os.path.abspath(__file__)
index_route = route.find("BackendHookedDocs")
local_path = route[:index_route + len("BackendHookedDocs")]
global_route = os.path.join(local_path, "src")

sys.path.append(global_route)

from core.crud import create_invoice

def extract(path_invoices):
    """
    Extrae el texto de facturas en formato PDF utilizando pdfplumber.
    
    Parámetros:
    - path_invoices: Ruta de la carpeta que contiene los archivos de facturas.
    """
    processed_count = 0  # Inicializa el contador

    for file in os.listdir(path_invoices):
        if file.endswith(".pdf"):
            file_path = os.path.join(path_invoices, file)
            try:
                # Utiliza pdfplumber para extraer el texto del PDF
                with pdfplumber.open(file_path) as pdf:
                    extracted_text = ''
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_text += page_text + '\n'

                # Procesar el archivo PDF según el proveedor
                data = transform(extracted_text)
                load(data)

                # Mover archivo a la carpeta "PROCESADOS" después de procesarlo
                move_to_processed(file_path, path_invoices)
                processed_count += 1  # Incrementa el contador tras mover el archivo
            except Exception as e:
                print(f"Error al procesar el archivo {file}: {e}")

    return processed_count  # Retorna el número de archivos procesados

def transform(extracted_text):
    """
    Transforma el texto extraído y extrae los datos estructurados según el proveedor.
    
    Parámetros:
    - extracted_text: El texto extraído del PDF de la factura.

    Retorna:
    - Un diccionario con los datos estructurados de la factura.
    """
    transformed_text = extracted_text.upper()

    # Verificar el proveedor
    if "PROFESSIONAL FISHING SPA" in transformed_text:
        return transform_professional_fishing(transformed_text)
    elif "MI TIENDA SPA" in transformed_text:
        return transform_mi_tienda(transformed_text)
    elif "76.214.117-5" in transformed_text:
        return transform_rapala(transformed_text)
    else:
        raise ValueError("Proveedor no reconocido en el documento.")


def remove_accents(input_str):
    """
    Elimina los acentos del texto para facilitar las coincidencias en las expresiones regulares.
    """
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return ''.join([c for c in nfkd_form if not unicodedata.combining(c)])

def transform_professional_fishing(text):
    """
    Extrae los datos de la factura de PROFESSIONAL FISHING SPA.

    Parámetros:
    - text: Texto extraído de la factura.

    Retorna:
    - Un diccionario con los datos estructurados.
    """
    # Eliminar acentos y convertir a mayúsculas
    text = remove_accents(text)
    text = text.upper()

    # Inicializar el diccionario de datos
    data = {
        "invoice_number": None,
        "issue_date": None,
        "pay_method": None,
        "items": [],
        "subtotal": None,
        "tax": None,
        "total": None,
        "issuer": {
            "name": "PROFESSIONAL FISHING SPA",
            "rut": None,
            "address": None,
            "email": None,
            "phone": None
        }
    }

    months = {
        'ENERO': '01',
        'FEBRERO': '02',
        'MARZO': '03',
        'ABRIL': '04',
        'MAYO': '05',
        'JUNIO': '06',
        'JULIO': '07',
        'AGOSTO': '08',
        'SEPTIEMBRE': '09',
        'OCTUBRE': '10',
        'NOVIEMBRE': '11',
        'DICIEMBRE': '12'
    }

    def parse_int(num_str):
        return int(num_str.replace('.', '').replace(',', '').strip())

    def parse_float(num_str):
        return float(num_str.replace('.', '').replace(',', '.').strip())

    # Dividir el texto en líneas para facilitar el procesamiento
    lines = text.split('\n')

    # Añadir una lista para rastrear los ítems procesados
    processed_items = set()

    # Procesar líneas
    for i, line in enumerate(lines):
        line = line.strip()

        # Extracción del RUT del emisor
        if 'R.U.T' in line and data["issuer"]["rut"] is None:
            rut_match = re.search(r'R\.U\.T\:?\s*([\d\.\-]+)', line)
            if rut_match:
                data["issuer"]["rut"] = rut_match.group(1).replace('.', '').replace('-', '').strip()

        # Extracción de la dirección del emisor
        if line.startswith('DIRECCION:') and 'COMUNA:' not in line:
            data["issuer"]["address"] = line.split(':',1)[1].strip()

        # Extracción del email del emisor
        if 'EMAIL:' in line:
            email_match = re.search(r'EMAIL:\s*(\S+@\S+)', line)
            if email_match:
                data["issuer"]["email"] = email_match.group(1).strip()

        # Extracción del teléfono del emisor
        if 'TELEFONO(S):' in line:
            phone_match = re.search(r'TELEFONO\(S\):\s*([^\n]+)', line)
            if phone_match:
                data["issuer"]["phone"] = phone_match.group(1).replace(' ', '').strip()

        # Extracción del número de factura
        if line.startswith('N°') or line.startswith('Nº') or line.startswith('NO'):
            invoice_number_match = re.search(r'NO?\s*(\d+)', line)
            if invoice_number_match and data["invoice_number"] is None:
                data["invoice_number"] = invoice_number_match.group(1).strip()

        # Extracción de la fecha de emisión
        if 'FECHA EMISION' in line and data["issue_date"] is None:
            issue_date_match = re.search(r'FECHA EMISION:\s*(\d{1,2})\s+DE\s+(\w+)\s+DE\s+(\d{4})', line)
            if issue_date_match:
                day = issue_date_match.group(1).zfill(2)
                month_name = issue_date_match.group(2).upper()
                year = issue_date_match.group(3)
                month = months.get(month_name, '00')
                data["issue_date"] = f"{day}{month}{year}"

        # Extracción del método de pago
        if 'FORMA PAGO:' in line and data["pay_method"] is None:
            pay_method_match = re.search(r'FORMA PAGO:\s*(.+)', line)
            if pay_method_match:
                data["pay_method"] = pay_method_match.group(1).strip()

        # Extracción de los ítems
        if 'CODIGO DESCRIPCION' in line:
            # Los ítems empiezan en la siguiente línea
            items_start = i + 1
            # Encontrar el final de los ítems
            for j in range(items_start, len(lines)):
                if 'N° LINEAS' in lines[j] or 'Nº LINEAS' in lines[j] or 'NO LINEAS' in lines[j]:
                    items_end = j
                    break
            else:
                items_end = len(lines)
            # Procesar los ítems
            for item_line in lines[items_start:items_end]:
                item_line = item_line.strip()
                if not item_line:
                    continue
                # Verificar si ya hemos procesado este ítem
                if item_line in processed_items:
                    continue
                else:
                    processed_items.add(item_line)
                # Expresión regular para extraer los detalles del ítem
                line_regex = r'(?P<code>\S+)\s+(?P<description>.+?)\s+(?P<quantity>\d+)\s+(?P<unit_price>[\d.,]+)(?:\s+(?P<discount>[\d.,]+)\s*%)?\s*(AFECTO|EXENTO)?\s+(?P<total_price>[\d.,]+)'
                line_match = re.match(line_regex, item_line)
                if line_match:
                    code = line_match.group('code')
                    description = line_match.group('description')
                    quantity = line_match.group('quantity')
                    unit_price = line_match.group('unit_price')
                    discount = line_match.group('discount') or '0'
                    total_price = line_match.group('total_price')
                    item = {
                        'quantity': int(quantity),
                        'sku': code.strip(),
                        'description': description.strip(),
                        'unit_price': parse_int(unit_price),
                        'discount': parse_float(discount),
                        'subtotal': parse_int(total_price)
                    }
                    data["items"].append(item)

    # Extracción del subtotal (Monto neto)
    subtotal_match = re.search(r'MONTO NETO:\s*\$\s*([\d.,]+)', text)
    if subtotal_match:
        data['subtotal'] = parse_int(subtotal_match.group(1))

    # Extracción del IVA
    tax_match = re.search(r'IVA\s*\(19%\):\s*\$\s*([\d.,]+)', text)
    if tax_match:
        data['tax'] = parse_int(tax_match.group(1))

    # Extracción del total
    total_match = re.search(r'TOTAL:\s*\$\s*([\d.,]+)', text)
    if total_match:
        data['total'] = parse_int(total_match.group(1))

    return data

def transform_mi_tienda(text):
    """
    Extrae los datos de la factura de MI TIENDA SPA.
    
    Parámetros:
    - text: Texto extraído de la factura.
    
    Retorna:
    - Un diccionario con los datos estructurados.
    """
    # Eliminar acentos y convertir a mayúsculas
    text = remove_accents(text)
    text = text.upper()

    data = {
        "invoice_number": None,
        "issue_date": None,
        "pay_method": None,
        "items": [],
        "subtotal": None,
        "tax": None,
        "total": None,
        "issuer": {
            "name": "MI TIENDA SPA",
            "rut": None,
            "address": None,
            "email": None,
            "phone": None
        }
    }

    # Dividir el texto en líneas para facilitar el procesamiento
    lines = text.split('\n')

    # Procesar líneas
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Extracción del RUT del emisor
        if 'RUT:' in line and data['issuer']['rut'] is None and 'SENOR' not in line:
            rut_match = re.search(r'RUT:\s*([\d\.\-Kk]+)', line)
            if rut_match:
                data["issuer"]["rut"] = rut_match.group(1).replace('.', '').replace('-', '').strip()

        # Extracción de la dirección del emisor
        if line.startswith('AV '):
            data['issuer']['address'] = line.strip()

        # Extracción del email del emisor
        if 'MAIL:' in line:
            email_match = re.search(r'MAIL:\s*(\S+@\S+)', line)
            if email_match:
                data['issuer']['email'] = email_match.group(1).strip()

        # Extracción del teléfono del emisor
        if ('TELEFONO:' in line or 'TELEFONO:+' in line) and data['issuer']['phone'] is None and 'SENOR' not in line:
            phone_match = re.search(r'TELEFONO:\s*([^\n]+)', line)
            if phone_match:
                data["issuer"]["phone"] = phone_match.group(1).replace(' ', '').strip()

        # Extracción del número de factura
        if ('N°' in line or 'Nº' in line or 'NO ' in line) and data['invoice_number'] is None:
            invoice_number_match = re.search(r'N[O°º\s]*\s*(\d+)', line)
            if invoice_number_match:
                data["invoice_number"] = invoice_number_match.group(1).strip()

        # Extracción de la fecha de emisión
        if 'FECHA EMISION:' in line and data['issue_date'] is None:
            issue_date_match = re.search(r'FECHA EMISION:\s*(\d{2}/\d{2}/\d{4})', line)
            if issue_date_match:
                date_str = issue_date_match.group(1)
                day, month, year = date_str.split('/')
                data["issue_date"] = day + month + year

        # Extracción del método de pago
        if 'FORMA DE PAGO:' in line and data['pay_method'] is None:
            pay_method_match = re.search(r'FORMA DE PAGO:\s*(.*)', line)
            if pay_method_match:
                pay_method = pay_method_match.group(1).strip()
                # Verificar si el método de pago continúa en la siguiente línea
                if not pay_method and i + 1 < len(lines):
                    i += 1
                    pay_method = lines[i].strip()
                data['pay_method'] = pay_method

        # Extracción de los ítems
        if 'CANTIDAD SKU ITEM VALOR UNITARIO % DESCT. SUBTOTAL' in line:
            # Los ítems empiezan en la siguiente línea
            items_start = i + 1
            # Encontrar el final de los ítems
            for j in range(items_start, len(lines)):
                if 'NOTA:' in lines[j].upper() or 'SON:' in lines[j].upper() or '_____' in lines[j]:
                    items_end = j
                    break
            else:
                items_end = len(lines)
            # Unir líneas de ítems considerando descripciones en múltiples líneas
            item_lines = []
            current_item_lines = []
            for k in range(items_start, items_end):
                item_line = lines[k].strip()
                if not item_line:
                    continue
                # Verificar si es el inicio de un nuevo ítem
                if re.match(r'^\d+\s+\S+', item_line):
                    if current_item_lines:
                        current_item = ' '.join(current_item_lines)
                        item_lines.append(current_item)
                        current_item_lines = []
                    current_item_lines.append(item_line)
                else:
                    # Línea de continuación de descripción
                    current_item_lines.append(item_line)
            # Agregar el último ítem
            if current_item_lines:
                current_item = ' '.join(current_item_lines)
                item_lines.append(current_item)
            # Procesar cada ítem
            for item_line in item_lines:
                # Expresión regular para extraer los campos
                item_regex = r'^(?P<quantity>\d+)\s+(?P<sku>\S+)\s+(?P<description>.+?)\s+\$\s*(?P<unit_price>[\d.,]+)\s+(?P<discount>[\d.,]+)\s*%\s+\$\s*(?P<subtotal>[\d.,]+)(?:\s+.*)?$'
                item_match = re.match(item_regex, item_line)
                if item_match:
                    quantity = int(item_match.group('quantity'))
                    sku = item_match.group('sku').strip()
                    description = item_match.group('description').strip()
                    unit_price = float(item_match.group('unit_price').replace('.', '').strip())
                    discount = float(item_match.group('discount').replace(',', '.').strip())
                    subtotal = float(item_match.group('subtotal').replace('.', '').strip())
                    item = {
                        "quantity": quantity,
                        "sku": sku,
                        "description": description,
                        "unit_price": unit_price,
                        "discount": discount,
                        "subtotal": subtotal
                    }
                    data["items"].append(item)
                else:
                    print(f"No se pudo procesar la línea de ítem: {item_line}")
            # Saltar a la línea después de los ítems
            i = items_end - 1  # -1 porque el bucle incrementará i
        # Extracción del subtotal
        if ('NETO ($)' in line or 'NETO($)' in line) and data['subtotal'] is None:
            subtotal_match = re.search(r'NETO\s*\(\$\)\s*\$\s*([\d.,]+)', line)
            if subtotal_match:
                data["subtotal"] = int(subtotal_match.group(1).replace('.', '').replace(',', '').strip())

        # Extracción del IVA
        if ('I.V.A. 19%' in line or 'IVA 19%' in line) and data['tax'] is None:
            tax_match = re.search(r'I\.?V\.?A\.?\s*19%\s*\$\s*([\d.,]+)', line)
            if tax_match:
                data["tax"] = int(tax_match.group(1).replace('.', '').replace(',', '').strip())

        # Extracción del total
        if ('TOTAL ($)' in line or 'TOTAL($)' in line) and data['total'] is None:
            total_match = re.search(r'TOTAL\s*\(\$\)\s*\$\s*([\d.,]+)', line)
            if total_match:
                data["total"] = int(total_match.group(1).replace('.', '').replace(',', '').strip())

        i += 1

    return data
def transform_rapala(text):
    """
    Extrae los datos de la factura de RAPALA.
    
    Parámetros:
    - text: Texto extraído de la factura.
    
    Retorna:
    - Un diccionario con los datos estructurados.
    """
    # Convertir el texto a mayúsculas
    text = text.upper()

    # Diccionario de reemplazos para normalizar el texto
    replacements = {
        'Á': 'A', 
        'É': 'E', 
        'Í': 'I', 
        'Ó': 'O', 
        'Ú': 'U',
        'N*': 'N°', 
        'N?': 'N°', 
        'S.I.1': 'S.I.I.',
        '#$': '#',
        # Añadir más reemplazos si es necesario
    }

    # Aplica los reemplazos al texto
    for old, new in replacements.items():
        text = text.replace(old, new)

    data = {
        "invoice_number": None,
        "issue_date": None,
        "pay_method": None,
        "items": [],
        "subtotal": None,
        "tax": None,
        "total": None,
        "issuer": {
            "name": "RAPALA",
            "rut": None,
            "address": "EL ROBRE 731, RECOLETA, SANTIAGO",
            "email": None,
            "phone": "+56224017467"
        }
    }

    months = {
        'ENERO': '01',
        'FEBRERO': '02',
        'MARZO': '03',
        'ABRIL': '04',
        'MAYO': '05',
        'JUNIO': '06',
        'JULIO': '07',
        'AGOSTO': '08',
        'SEPTIEMBRE': '09',
        'OCTUBRE': '10',
        'NOVIEMBRE': '11',
        'DICIEMBRE': '12'
    }

    def parse_int(num_str):
        return int(num_str.replace('.', '').replace(',', '').strip())

    def parse_float(num_str):
        return float(num_str.replace('.', '').replace(',', '.').strip())

    # Extraer RUT del emisor
    rut_match = re.search(r'R\.U\.T\.?:\s*([\d\.\-]+)', text)
    if rut_match:
        data["issuer"]["rut"] = rut_match.group(1).replace('.', '').replace('-', '')

    # Extraer el número de factura
    invoice_number_match = re.search(r'N[°º]?\s*(\d+)', text)
    if invoice_number_match:
        data["invoice_number"] = invoice_number_match.group(1)

    # Extraer fecha de emisión
    issue_date_match = re.search(r'FECHA EMISION\s*:\s*(\d{1,2})\s*-\s*(\w+)\s+DE\s+(\d{4})', text)
    if issue_date_match:
        day = issue_date_match.group(1).zfill(2)
        month_name = issue_date_match.group(2).upper()
        year = issue_date_match.group(3)
        month = months.get(month_name, '00')
        data["issue_date"] = f"{day}{month}{year}"

    # Extraer método de pago
    pay_method_match = re.search(r'PAGO\s*:\s*(.+)', text)
    if pay_method_match:
        data["pay_method"] = pay_method_match.group(1).strip()

    # Extraer ítems
    items_section_match = re.search(
        r'CODIGO DESCRIPCION CANTIDAD.*?\n(.*?)(?:DOCUMENTO REFERENCIA|NETO|SON:)', 
        text, 
        re.DOTALL
    )
    if items_section_match:
        items_text = items_section_match.group(1).strip()
        item_lines = items_text.split('\n')
        line_regex = r'(?P<code>\S+)\s+(?P<description>.+?)\s+(?P<quantity>\d+)\s+\w+\s+(?P<unit_price>[\d.,]+)\s+(?P<discount>[\d.,]+)\s*%\s+(?P<desc_amount>[\d.,]+)\s+(?P<total_price>[\d.,]+)'
        for line in item_lines:
            line = line.strip()
            if not line:
                continue
            line_match = re.match(line_regex, line)
            if line_match:
                code = line_match.group('code')
                description = line_match.group('description')
                quantity = line_match.group('quantity')
                unit_price = line_match.group('unit_price')
                discount = line_match.group('discount')
                total_price = line_match.group('total_price')
                # Build the item dict
                item = {
                    'quantity': int(quantity),
                    'sku': code.strip(),
                    'description': description.strip(),
                    'unit_price': parse_float(unit_price),
                    'discount': parse_float(discount),
                    'subtotal': parse_float(total_price)
                }
                data["items"].append(item)
            else:
                print(f"No match for line: {line}")

    # Extraer el subtotal
    subtotal_match = re.search(r'NETO\s*([\d.,]+)', text)
    if subtotal_match:
        data['subtotal'] = parse_int(subtotal_match.group(1))

    # Extraer el IVA
    tax_match = re.search(r'I\.V\.A\. 19%\s*([\d.,]+)', text)
    if tax_match:
        data['tax'] = parse_int(tax_match.group(1))

    # Extraer el total
    total_match = re.search(r'TOTAL\s*([\d.,]+)', text)
    if total_match:
        data['total'] = parse_int(total_match.group(1))

    return data

def load(data):
    """
    Carga los datos procesados en la base de datos.
    
    Parámetros:
    - data: El diccionario con los datos procesados de la factura.
    """
    # Ejemplo de carga de datos en la base de datos (crear una nueva factura)
    create_invoice(data, 'invoices_received')
    
def move_to_processed(file_path, path_invoices):
    """
    Mueve el archivo procesado a la carpeta "PROCESADOS".
    
    Parámetros:
    - file_path: Ruta del archivo procesado.
    - path_invoices: Ruta de la carpeta que contiene los archivos de facturas.
    """
    processed_folder = os.path.join(path_invoices, "PROCESADOS")
    if not os.path.exists(processed_folder):
        os.makedirs(processed_folder)

    # Mover el archivo a la carpeta "PROCESADOS"
    processed_path = os.path.join(processed_folder, os.path.basename(file_path))
    shutil.move(file_path, processed_path)

    print(f"Archivo {file_path} movido a {processed_path}")

def main(invoices_received_path):
    """
    Función principal que coordina las etapas de extracción, transformación y carga de datos.
    
    Parámetros:
    - invoices_received_path: Ruta de la carpeta que contiene los archivos de facturas.
    Retorna el número de archivos procesados
    """
    
    processed_count = extract(invoices_received_path)
    return processed_count
    