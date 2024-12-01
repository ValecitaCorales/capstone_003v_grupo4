import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import json
import os
import sys
import ttkthemes
from plyer import notification
from PIL import Image, ImageTk

route = os.path.abspath(__file__)
index_route = route.find("BackendHookedDocs")
local_path = route[:index_route + len("BackendHookedDocs")]
global_route = os.path.join(local_path, "src")

sys.path.append(global_route)

from src.etl.physical_tickets import main as fun_pt
from src.etl.electronic_tickets import main as fun_et
from src.etl.invoices_issued import main as fun_ii
from src.etl.invoices_received import main as fun_ir
from src.core.crud import read_select_invoice, update_selected_invoice, delete_invoice, read_log

class HookedDocsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HookedDocs - Herramienta de Depuración")
        #icon_path = os.path.join(local_path, "assets", "icon.ico")
        #self.root.iconbitmap(icon_path)

        # Cargar configuraciones previas si existen
        self.config_data = self.load_config()

        # Aplicar tema visual
        self.style = ttkthemes.ThemedStyle(self.root)
        self.available_themes = self.style.theme_names()
        self.current_theme = self.config_data.get("theme", "breeze")  # Cargar tema del config o usar "breeze" por defecto
        self.style.set_theme(self.current_theme)

        # Crear la barra de menú
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        # Crear un menú de configuración
        config_menu = tk.Menu(menu_bar, tearoff=0)
        config_menu.add_command(label="Configuración de Carpetas", command=self.config_folders)
        config_menu.add_command(label="Seleccionar Tema", command=self.select_theme_window)
        menu_bar.add_cascade(label="Configuración", menu=config_menu)

        # Crear el Notebook para las pestañas de funcionalidades
        notebook = ttk.Notebook(self.root)
        notebook.pack(expand=True, fill='both')

        # Pestaña para cada funcionalidad
        self.facturas_recibidas_tab = self.add_tab(notebook, "Facturas Recibidas", 1)
        self.facturas_emitidas_tab = self.add_tab(notebook, "Facturas Emitidas", 2)
        self.boletas_fisicas_tab = self.add_tab(notebook, "Boletas Físicas", 3)
        self.boletas_electronicas_tab = self.add_tab(notebook, "Boletas Electrónicas", 4)
        self.logs_tab = self.add_logs_tab(notebook)

        # Cargar configuraciones previas si existen
        self.config_data = self.load_config()

        # Variables para guardar rutas de carpetas
        self.facturas_recibidas_path = self.config_data.get("Facturas Recibidas", "")
        self.facturas_emitidas_path = self.config_data.get("Facturas Emitidas", "")
        self.boletas_fisicas_path = self.config_data.get("Boletas Físicas", "")
        self.boletas_electronicas_path = self.config_data.get("Boletas Electrónicas", "")

        # Variable para almacenar el tipo de documento actual
        self.current_document_type = None
        self.current_functionality_number = None

        # Verificar errores pendientes al iniciar
        self.check_pending_errors()

    def add_tab(self, notebook, title, functionality_number):
        # Crear un Frame para la pestaña
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)

        # Botón que ejecuta el proceso específico de cada pestaña
        process_button = ttk.Button(frame, text=f"Procesar {title}", command=lambda: self.process_documents(title))
        process_button.pack(pady=10)

        # Botón para actualizar facturas o boletas
        update_button = ttk.Button(frame, text=f"Actualizar {title}", command=lambda: self.open_update_window(title, functionality_number))
        update_button.pack(pady=10)

        # Botón para eliminar facturas o boletas
        delete_button = ttk.Button(frame, text=f"Eliminar {title}", command=lambda: self.delete_document(title, functionality_number))
        delete_button.pack(pady=10)

        return frame
    
    def add_logs_tab(self, notebook):
        # Crear un Frame para la pestaña de logs
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Auditoría DTE's")

        # Tabla para mostrar los logs
        self.logs_tree = ttk.Treeview(frame, columns=("ISSUER_NAME", "PROCESS", "INVOICE_ID", "VALIDATION_MESSAGE"), show="headings")
        self.logs_tree.heading("ISSUER_NAME", text="Nombre del Emisor")
        self.logs_tree.heading("PROCESS", text="Proceso DTE")
        self.logs_tree.heading("INVOICE_ID", text="Nº DTE")
        self.logs_tree.heading("VALIDATION_MESSAGE", text="Mensaje de Error")
        
        # Ajustar el tamaño de cada columna para mejorar la visualización
        self.logs_tree.column("ISSUER_NAME", width=150)
        self.logs_tree.column("PROCESS", width=120)
        self.logs_tree.column("INVOICE_ID", width=70)
        self.logs_tree.column("VALIDATION_MESSAGE", width=400)

        self.logs_tree.pack(expand=True, fill='both', padx=10, pady=10)

        # Cargar los logs al iniciar
        self.load_logs()

        return frame

    def load_logs(self):
        # Limpiar la tabla antes de cargar nuevos datos
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)

        # Leer los logs desde la base de datos
        logs = read_log()
        for log in logs:
            # Insertar cada log en la tabla con sus valores correspondientes
            self.logs_tree.insert("", "end", values=(log["ISSUER_NAME"], log["PROCESS"], log["INVOICE_ID"], log["VALIDATION_MESSAGE"]))

    def check_pending_errors(self):
        # Verificar si hay errores pendientes
        logs = read_log()
        if logs:
            messagebox.showwarning("DTE's con errores", f"Hay {len(logs)} DTE's con errores de lectura, favor revisar la ventana Auditoría DTE's.")

    def config_folders(self):
        # Ventana de configuración para seleccionar carpetas
        config_window = tk.Toplevel(self.root)
        config_window.title("Configuración de Carpetas")
        config_window.geometry("630x250")

        self.entries = {}

        # Lista de funcionalidades para crear la configuración de cada carpeta
        functionalities = ["Facturas Recibidas", "Facturas Emitidas", "Boletas Físicas", "Boletas Electrónicas"]

        for index, func in enumerate(functionalities):
            label = ttk.Label(config_window, text=f"{func}:")
            label.grid(row=index, column=0, padx=10, pady=5, sticky="w")

            entry = ttk.Entry(config_window, width=40)
            entry.grid(row=index, column=1, padx=10, pady=5)
            self.entries[func] = entry

            # Cargar valores previos si existen o asignar un valor vacío
            entry.insert(0, self.config_data.get(func, ""))

            button = ttk.Button(config_window, text="Seleccionar", command=lambda e=entry, key=func: self.select_folder(e, key))
            button.grid(row=index, column=2, padx=10, pady=5)

        # Botón para guardar configuraciones
        save_button = ttk.Button(config_window, text="Guardar", command=self.save_config)
        save_button.grid(row=len(functionalities), column=1, pady=20)

    def select_folder(self, entry, key):
        # Abrir diálogo para seleccionar la carpeta
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            entry.delete(0, tk.END)
            entry.insert(0, folder_selected)
            # Actualizar el valor en config_data
            self.config_data[key] = folder_selected

    def save_config(self):
        # Recopilar datos de las entradas y guardarlos en un archivo JSON
        self.config_data.update({
            "Facturas Recibidas": self.entries["Facturas Recibidas"].get(),
            "Facturas Emitidas": self.entries["Facturas Emitidas"].get(),
            "Boletas Físicas": self.entries["Boletas Físicas"].get(),
            "Boletas Electrónicas": self.entries["Boletas Electrónicas"].get(),
            "theme": self.current_theme
        })

        # Guardar la configuración en el archivo JSON
        with open("config.json", "w") as config_file:
            json.dump(self.config_data, config_file, indent=4)

        # Actualizar las rutas de carpetas en las variables correspondientes
        self.facturas_recibidas_path = self.config_data.get("Facturas Recibidas", "")
        self.facturas_emitidas_path = self.config_data.get("Facturas Emitidas", "")
        self.boletas_fisicas_path = self.config_data.get("Boletas Físicas", "")
        self.boletas_electronicas_path = self.config_data.get("Boletas Electrónicas", "")

        messagebox.showinfo("Guardado", "Las configuraciones se han guardado correctamente.")

    def load_config(self):
        # Cargar configuraciones previas si existe el archivo config.json
        if os.path.exists("config.json"):
            with open("config.json", "r") as config_file:
                return json.load(config_file)
        return {}

    def select_theme_window(self):
        # Ventana para seleccionar el tema
        theme_window = tk.Toplevel(self.root)
        theme_window.title("Seleccionar Tema Visual")
        theme_window.geometry("400x200")

        theme_label = ttk.Label(theme_window, text="Seleccione un tema:")
        theme_label.pack(pady=10)

        theme_combobox = ttk.Combobox(theme_window, values=self.available_themes)
        theme_combobox.set(self.current_theme)
        theme_combobox.pack(pady=10)

        apply_button = ttk.Button(theme_window, text="Aplicar", command=lambda: self.apply_theme(theme_combobox.get()))
        apply_button.pack(pady=10)

    def apply_theme(self, theme_name):
        if theme_name in self.available_themes:
            self.style.set_theme(theme_name)
            self.current_theme = theme_name
            self.config_data["theme"] = theme_name  # Guardar el tema actual en la configuración
            self.save_config()  # Guardar la configuración actualizada
            messagebox.showinfo("Tema Aplicado", f"Tema '{theme_name}' aplicado exitosamente.")
        else:
            messagebox.showwarning("Error", f"El tema '{theme_name}' no está disponible.")

    def open_update_window(self, document_type, functionality_number):
        self.current_document_type = document_type
        self.current_functionality_number = functionality_number
        update_window = tk.Toplevel(self.root)
        update_window.title(f"Actualizar {document_type}")
        update_window.geometry("600x650")

        search_label = ttk.Label(update_window, text="Número de Factura o Boleta:")
        search_label.pack(pady=5)

        search_entry = ttk.Entry(update_window)
        search_entry.pack(pady=5)

        search_button = ttk.Button(update_window, text="Buscar", command=lambda: self.search_invoice(search_entry))
        search_button.pack(pady=5)

        self.invoice_data_entries = {}

        # Definir los campos específicos según la funcionalidad
        fields = []
        if functionality_number == 1:  # Facturas Recibidas
            fields = ["Número Factura", "Nombre Proveedor", "RUT Proveedor", "Subtotal", "IVA", "Total", "Método de Pago"]
        elif functionality_number == 2:  # Facturas Emitidas
            fields = ["Número Factura", "Nombre Comprador", "RUT Comprador", "RUT Proveedor", "Tipo de Factura", "Subtotal", "IVA", "Total", "Método de Pago"]
        elif functionality_number == 3:  # Boletas Físicas
            fields = ["Folio", "RUT Vendedor", "Sucursal", "Fecha", "Neto", "IVA", "Total"]
        elif functionality_number == 4:  # Boletas Electrónicas
            fields = ["Folio", "Tipo Documento", "Emisión", "Monto Neto", "Monto Exento", "Monto IVA", "Monto Total"]

        for field in fields:
            label = ttk.Label(update_window, text=field)
            label.pack(pady=2)

            entry = ttk.Entry(update_window, width=50)
            entry.pack(pady=2)
            self.invoice_data_entries[field] = entry

        update_button = ttk.Button(update_window, text="Actualizar", command=self.update_invoice)
        update_button.pack(pady=20)

    def run_etl_process(self, path, etl_function, document_type):
        # Validar si hay archivos en la carpeta antes de comenzar
        if not os.listdir(path):
            # Mostrar mensaje si no hay archivos para procesar
            messagebox.showinfo("Sin Archivos", f"No hay archivos en la carpeta {document_type} para procesar.")
            return

        # Notificar al usuario que se ha iniciado el procesamiento de archivos
        notification.notify(
            title="Procesamiento Iniciado",
            message=f"Se ha iniciado el procesamiento de {document_type}.",
            timeout=5
        )

        # Mostrar mensaje mientras se realiza el procesamiento
        try:
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Procesando")
            progress_label = ttk.Label(progress_window, text=f"Procesando {document_type} en la carpeta: {path}")
            progress_label.pack(pady=10)

            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill='x')
            progress_bar.start()

            self.root.update()

            # Ejecutar la función de procesamiento (ETL)
            processed_count = etl_function(path)  # Suponiendo que esta función devuelve la cantidad de archivos procesados

            progress_bar.stop()
            progress_window.destroy()

            # Mostrar el mensaje de éxito con la cantidad de archivos procesados
            messagebox.showinfo("Éxito", f"{document_type} procesadas exitosamente. Total de archivos procesados: {processed_count}")

            # Mostrar la notificación del sistema
            notification.notify(
                title="Proceso Completado",
                message=f"Procesamiento de {document_type} realizado con éxito.",
                timeout=5 
            )

            self.load_logs()
            self.check_pending_errors()
        except Exception as e:
            print(f"Error al procesar {document_type}: {e}")
            messagebox.showerror("Error", f"Ocurrió un error al procesar {document_type}:{str(e)}")

    def process_documents(self, document_type):
        path = None
        etl_function = None

        if document_type == "Facturas Recibidas":
            path = self.facturas_recibidas_path
            etl_function = fun_ir
        elif document_type == "Facturas Emitidas":
            path = self.facturas_emitidas_path
            etl_function = fun_ii
        elif document_type == "Boletas Físicas":
            path = self.boletas_fisicas_path
            etl_function = fun_pt
        elif document_type == "Boletas Electrónicas":
            path = self.boletas_electronicas_path
            etl_function = fun_et

        if not path:
            messagebox.showwarning("Advertencia", f"La carpeta para {document_type} no está configurada.")
            return

        self.run_etl_process(path, etl_function, document_type)

    def search_invoice(self, search_entry):
        invoice_number = search_entry.get()
        if not invoice_number:
            messagebox.showwarning("Advertencia", "Ingrese el número de factura o boleta a buscar.")
            return

        try:
            # Buscar la factura o boleta en la BD
            invoices = read_select_invoice(invoice_number, self.current_functionality_number)
            if invoices:
                # Tomar el primer resultado (asumiendo que hay solo uno)
                invoice_data = invoices[0]

                # Crear un mapeo entre los nombres de los campos de la GUI y las claves del diccionario
                if self.current_functionality_number == 1:
                    key_mapping = {
                        'Número Factura': 'invoice_number',
                        'Nombre Proveedor': 'issuer_name',
                        'RUT Proveedor': 'issuer_rut',
                        'Subtotal': 'subtotal',
                        'IVA': 'tax',
                        'Total': 'total',
                        'Método de Pago': 'pay_method'
                    }
                elif self.current_functionality_number == 2:
                    key_mapping = {
                        'Número Factura': 'invoice_number',
                        'Nombre Comprador': 'buyer_name',
                        'RUT Comprador': 'buyer_rut',
                        'RUT Proveedor': 'issuer_rut',
                        'Tipo de Factura': 'invoice_type',
                        'Subtotal': 'subtotal',
                        'IVA': 'tax',
                        'Total': 'total',
                        'Método de Pago': 'pay_method'
                    }
                elif self.current_functionality_number == 3:
                    key_mapping = {
                        'Folio': 'folio',
                        'Neto': 'neto',
                        'IVA': 'iva',
                        'Total': 'total',
                        'Fecha': 'fecha',
                        'RUT Vendedor': 'rut_vendedor',
                        'Sucursal': 'sucursal'  
                    }
                elif self.current_functionality_number == 4:
                    key_mapping = {
                        'Tipo Documento': 'tipo_documento',
                        'Folio': 'folio',
                        'Emisión': 'emision',
                        'Monto Neto': 'monto_neto',
                        'Monto Exento': 'monto_exento',
                        'Monto IVA': 'monto_iva',
                        'Monto Total': 'monto_total'
                    }
                else:
                    key_mapping = {}

                # Rellenar los campos con los datos de la factura o boleta
                for gui_field_name, entry in self.invoice_data_entries.items():
                    entry.delete(0, tk.END)
                    # Obtener la clave correspondiente en el diccionario invoice_data
                    data_key = key_mapping.get(gui_field_name)
                    if data_key:
                        value = invoice_data.get(data_key, "")
                    else:
                        value = ""
                        
                    # Asegurarse de que value es una cadena y no None
                    if value is None:
                        value = ""
                    else:
                        value = str(value)
                    entry.insert(0, value)
            else:
                messagebox.showinfo("Información", "Documento no encontrado.")
                self.clear_invoice_entries()
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al buscar el documento: {str(e)}")
            self.clear_invoice_entries()

    def clear_invoice_entries(self):
        # Limpiar todos los campos de entrada en el formulario
        for entry in self.invoice_data_entries.values():
            entry.delete(0, tk.END)

    def update_invoice(self):
        # Obtener los datos actualizados desde la interfaz gráfica
        updated_data = {key.lower().replace(" ", "_"): entry.get() for key, entry in self.invoice_data_entries.items()}

        # Mapeo de claves ajustado para coincidir con updated_data
        if self.current_functionality_number == 1:
            key_mapping = {
                'número_factura': 'invoice_number',
                'nombre_proveedor': 'issuer_name',
                'rut_proveedor': 'issuer_rut',
                'subtotal': 'subtotal',
                'iva': 'tax',
                'total': 'total',
                'método_de_pago': 'pay_method'
            }
        elif self.current_functionality_number == 2:
            key_mapping = {
                'número_factura': 'invoice_number',
                'nombre_comprador': 'buyer_name',
                'rut_comprador': 'buyer_rut',
                'rut_proveedor': 'issuer_rut',
                'tipo_de_factura': 'invoice_type',
                'subtotal': 'subtotal',
                'iva': 'tax',
                'total': 'total',
                'método_de_pago': 'pay_method'
            }
        elif self.current_functionality_number == 3:
            # mapeo para boletas físicas
            key_mapping = {
                'folio': 'folio',
                'neto': 'neto',
                'iva': 'iva',
                'total': 'total',
                'fecha': 'fecha',
                'rut_vendedor': 'rut_vendedor',
                'sucursal': 'sucursal'
            }
        elif self.current_functionality_number == 4:
            # mapeo para boletas electrónicas
            key_mapping = {
                'tipo_documento': 'tipo_documento',
                'folio': 'folio',
                'emisión': 'emision',
                'monto_neto': 'monto_neto',
                'monto_exento': 'monto_exento',
                'monto_iva': 'monto_iva',
                'monto_total': 'monto_total'
            }
        else:
            messagebox.showerror("Error", "Funcionalidad no reconocida.")
            return

        # Aplicar el mapeo a los datos actualizados
        updated_data_mapped = {key_mapping.get(k, k): v for k, v in updated_data.items()}

        # Obtener el número de factura o folio
        if self.current_functionality_number in [1, 2]:
            invoice_number = updated_data_mapped.get('invoice_number')
        elif self.current_functionality_number == 3:
            invoice_number = updated_data_mapped.get('folio')
        elif self.current_functionality_number == 4:
            invoice_number = updated_data_mapped.get('folio')
        else:
            messagebox.showerror("Error", "Funcionalidad no reconocida.")
            return

        if not invoice_number:
            messagebox.showwarning("Advertencia", "El número de factura o folio no está especificado.")
            return

        try:
            # Actualizar la factura o boleta en la BD
            update_selected_invoice(invoice_number, updated_data_mapped, self.current_functionality_number)
            messagebox.showinfo("Éxito", "Documento actualizado correctamente.")
            self.clear_invoice_entries()
            self.load_logs() 
        except ValueError as ve:
            messagebox.showerror("Error", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al actualizar el documento: {str(e)}")

    def delete_document(self, document_type, functionality_number):
        delete_window = tk.Toplevel(self.root)
        delete_window.title(f"Eliminar {document_type}")
        delete_window.geometry("300x150")

        delete_label = ttk.Label(delete_window, text="Número de Factura o Boleta a eliminar:")
        delete_label.pack(pady=5)

        delete_entry = ttk.Entry(delete_window)
        delete_entry.pack(pady=5)

        # Cambiar el botón para que pase delete_entry como objeto
        delete_button = ttk.Button(delete_window, text="Eliminar", command=lambda: self.perform_delete(functionality_number, delete_entry))
        delete_button.pack(pady=10)

    def perform_delete(self, functionality_number, delete_entry):
        # Obtener el valor del campo de entrada
        invoice_number = delete_entry.get()
        if not invoice_number:
            messagebox.showwarning("Advertencia", "Ingrese el número de factura o boleta a eliminar.")
            return

        try:
            # Eliminar la factura o boleta en la BD
            delete_invoice(functionality_number, invoice_number)
            messagebox.showinfo("Éxito", "Documento eliminado correctamente.")
            # Limpiar el campo de entrada del número de DTE
            delete_entry.delete(0, tk.END)
            self.load_logs()  # Actualizar los logs después de eliminar
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al eliminar el documento: {str(e)}")


if __name__ == "__main__":
    # Crear la ventana de splash
    splash_root = tk.Tk()
    splash_root.overrideredirect(True)  # Quitar la barra de título

    # Obtener el tamaño de la pantalla y la imagen del splash
    screen_width = splash_root.winfo_screenwidth()
    screen_height = splash_root.winfo_screenheight()
    splash_image = Image.open("assets/splash.png")
    splash_photo = ImageTk.PhotoImage(splash_image)

    # Obtener el tamaño de la imagen del splash
    splash_width = splash_photo.width()
    splash_height = splash_photo.height()

    # Calcular la posición x e y para centrar el splash
    splash_x = int((screen_width / 2) - (splash_width / 2))
    splash_y = int((screen_height / 2) - (splash_height / 2))

    # Establecer la geometría de la ventana de splash centrada
    splash_root.geometry(f"{splash_width}x{splash_height}+{splash_x}+{splash_y}")

    # Crear un label para mostrar la imagen
    splash_label = tk.Label(splash_root, image=splash_photo)
    splash_label.pack()

    # Mostrar la ventana de splash durante 3 segundos
    splash_root.after(3000, splash_root.destroy)
    splash_root.mainloop()

    # Luego de cerrar el splash, iniciar la aplicación principal
    root = tk.Tk()

    # Obtener el tamaño de la pantalla y el tamaño de la ventana principal
    root.update_idletasks()  # Asegurarse de que la ventana principal está actualizada
    main_width = 800
    main_height = 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Calcular la posición x e y para centrar la ventana principal
    main_x = int((screen_width / 2) - (main_width / 2))
    main_y = int((screen_height / 2) - (main_height / 2))

    # Establecer la geometría de la ventana principal centrada
    root.geometry(f"{main_width}x{main_height}+{main_x}+{main_y}")

    # Crear la instancia de la aplicación principal
    app = HookedDocsApp(root)
    root.mainloop()

