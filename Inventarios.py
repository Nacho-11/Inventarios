import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font, simpledialog
from datetime import datetime, timedelta
import sqlite3
import os
import sys
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import json
import webbrowser
from pathlib import Path

# Constantes
ML_A_OZ = 0.033814  # 1 ml = 0.033814 oz
OZ_A_ML = 29.5735   # 1 oz = 29.5735 ml
VERSION = "1.2.0"

def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller"""
    try:
        # PyInstaller crea una carpeta temporal y almacena la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    return os.path.join(base_path, relative_path)

class ToolTip:
    """Clase para crear tooltips personalizados"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        """Muestra el tooltip"""
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, background="#ffffe0", 
                        relief="solid", borderwidth=1, font=('Segoe UI', 9))
        label.pack()

    def hide_tooltip(self, event=None):
        """Oculta el tooltip"""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class LicorDB:
    def __init__(self, db_name='inventario_licores.db'):
        try:
            # Crear directorio en Documents para persistencia
            data_dir = Path.home() / "Documents" / "InventarioLicores"
            data_dir.mkdir(exist_ok=True, parents=True)
        
            db_path = data_dir / db_name
            print(f"Base de datos ubicada en: {db_path}")  # Para verificar la ruta
        
            self.conn = sqlite3.connect(str(db_path))
            self.create_tables()
            self.create_admin_user()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo inicializar la base de datos: {str(e)}")
            raise
        
    def drop_tables(self):
        """Elimina las tablas existentes (solo para desarrollo)"""
        tables = ['movimientos', 'productos', 'usuarios', 'locales']
        cursor = self.conn.cursor()
        for table in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
            except sqlite3.Error as e:
                print(f"No se pudo eliminar la tabla {table}: {e}")
        self.conn.commit()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Tabla de locales
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS locales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            direccion TEXT,
            telefono TEXT,
            activo INTEGER DEFAULT 1
        )
        ''')
        
        # Tabla de usuarios
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL,  -- 'admin', 'gerente', 'empleado'
            local_id INTEGER,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (local_id) REFERENCES locales (id)
        )
        ''')
        
        # Tabla de productos (con local_id)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            marca TEXT NOT NULL,
            tipo TEXT NOT NULL,
            densidad REAL NOT NULL,
            capacidad_ml REAL NOT NULL,
            peso_envase REAL NOT NULL,
            activo INTEGER DEFAULT 1,
            botellas_completas INTEGER DEFAULT 0,
            minimo_inventario REAL DEFAULT 0.2,
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (local_id) REFERENCES locales (id)
        )
        ''')
        
        # Tabla de movimientos
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,  -- 'entrada', 'salida', 'ajuste'
            cantidad_ml REAL NOT NULL,
            peso_bruto REAL,
            notas TEXT,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos (id),
            FOREIGN KEY (user_id) REFERENCES usuarios (id)
        )
        ''')
        
        self.conn.commit()
    
    def create_admin_user(self):
        """Crea el usuario administrador por defecto si no existe"""
        cursor = self.conn.cursor()
        
        # Verificar si ya existe un admin
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        if cursor.fetchone() is None:
            # Crear local por defecto si no existe
            cursor.execute("SELECT id FROM locales WHERE nombre = 'Local Principal'")
            local = cursor.fetchone()
            
            if local is None:
                cursor.execute("INSERT INTO locales (nombre) VALUES ('Local Principal')")
                local_id = cursor.lastrowid
            else:
                local_id = local[0]
            
            # Crear usuario admin
            cursor.execute(
                "INSERT INTO usuarios (username, password, nombre, rol, local_id) VALUES (?, ?, ?, ?, ?)",
                ('admin', 'admin123', 'Administrador', 'admin', local_id)
            )
            self.conn.commit()
    
    def execute_query(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor
    
    def fetch_all(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def fetch_one(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    
    def close(self):
        self.conn.close()

class LoginWindow:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        
        # Configurar icono
        try:
            self.root.iconbitmap(resource_path('Icon.ico'))
        except Exception as e:
            print(f"Error al cargar icono: {e}")
            # Opcional: Puedes cargar un icono por defecto alternativo aquí
        
        self.root.title("Login - Inventario Licores")
        self.root.geometry("400x300")
        
        # Estilo
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Logo/título
        ttk.Label(main_frame, text="Inventario Licores", font=('Helvetica', 16, 'bold')).pack(pady=10)
        
        # Campos de login
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(pady=20)
        
        ttk.Label(form_frame, text="Usuario:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.entry_username = ttk.Entry(form_frame)
        self.entry_username.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="Contraseña:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.entry_password = ttk.Entry(form_frame, show="*")
        self.entry_password.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="Local:").grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.combo_local = ttk.Combobox(form_frame, state='readonly')
        self.combo_local.grid(row=2, column=1, padx=5, pady=5)
        
        # Cargar locales disponibles
        self.cargar_locales()
        
        # Botón de login
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Ingresar", command=self.validar_login).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Salir", command=self.root.quit).pack(side='left', padx=5)
        
        # Centrar ventana
        self.root.eval('tk::PlaceWindow . center')
        
        # Configurar tecla Enter para login
        self.root.bind('<Return>', lambda event: self.validar_login())
    
    def cargar_locales(self):
        """Carga los locales disponibles en el combobox"""
        locales = self.db.fetch_all("SELECT id, nombre FROM locales WHERE activo = 1 ORDER BY nombre")
        self.locales_data = {f"{l[1]} (ID: {l[0]})": l[0] for l in locales}
        self.combo_local['values'] = list(self.locales_data.keys())
        if locales:
            self.combo_local.current(0)
    
    def validar_login(self):
        """Valida las credenciales del usuario"""
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        local_str = self.combo_local.get()
        
        if not username or not password or not local_str:
            messagebox.showerror("Error", "Todos los campos son obligatorios")
            return
        
        try:
            local_id = self.locales_data[local_str]
        except:
            messagebox.showerror("Error", "Seleccione un local válido")
            return
        
        # Verificar credenciales
        query = """
        SELECT id, nombre, rol 
        FROM usuarios 
        WHERE username = ? AND password = ? AND (local_id = ? OR rol = 'admin') AND activo = 1
        """
        usuario = self.db.fetch_one(query, (username, password, local_id))
        
        if usuario:
            user_id, nombre, rol = usuario
            self.root.destroy()  # Cierra la ventana de login
            
            # Abre la aplicación principal con los datos del usuario y local
            root_main = tk.Tk()
            root_main.geometry("1000x600")
            app = InventarioApp(root_main, self.db, user_id, nombre, rol, local_id)
            root_main.mainloop()
        else:
            messagebox.showerror("Error", "Credenciales incorrectas o no tiene acceso a este local")

class Producto:
    """Clase para representar un producto (licor)"""
    def __init__(self, id, nombre, marca, tipo, densidad, capacidad_ml, peso_envase, activo=True, botellas_completas=0):
        self.id = id
        self.nombre = nombre
        self.marca = marca
        self.tipo = tipo
        self.densidad = densidad
        self.capacidad_ml = capacidad_ml
        self.peso_envase = peso_envase
        self.activo = activo
        self.botellas_completas = botellas_completas
    
    def calcular_peso_licor(self, volumen_ml):
        return round(volumen_ml * self.densidad, 2)
    
    def calcular_volumen(self, peso_total):
        return (peso_total - self.peso_envase) / self.densidad

class InventarioApp:
    def __init__(self, root, db, user_id, user_name, user_role, local_id):
        self.root = root
        """Inicializador de la clase"""
        self.db = db
        self.user_id = user_id
        self.user_name = user_name
        self.user_role = user_role
        self.local_id = local_id
        self.pages = {}  # Diccionario para almacenar páginas
        
        # Configurar el icono de la ventana principal
        try:
            self.root.iconbitmap(resource_path('Icon.ico'))
        except Exception as e:
            print(f"No se pudo cargar el icono: {e}")
    
        # Obtener nombre del local
        local_nombre = self.db.fetch_one("SELECT nombre FROM locales WHERE id = ?", (local_id,))[0]
        self.local_nombre = local_nombre
    
        # Configuración de estilos
        self.colors = {
            'primary': '#3498db',
            'secondary': '#7f8c8d',
            'success': '#2ecc71',
            'danger': '#e74c3c',
            'warning': '#f39c12',
            'background': '#f5f5f5'
        }
        
        self.font_title = ('Segoe UI', 12, 'bold')
        self.font_text = ('Segoe UI', 10)
        self.font_small = ('Segoe UI', 8)
        
        # Cargar configuración
        self.config = self.cargar_configuracion()
        self.nombre_empresa = self.config.get('nombre_empresa', 'Mi Bar')
        
        # Configurar interfaz
        self.setup_ui()
        
        # Cargar datos iniciales
        self.cargar_productos()
        self.actualizar_lista_productos()
        self.actualizar_inventario()

    def cargar_configuracion(self):
        """Carga la configuración desde archivo JSON"""
        config_file = 'config.json'
        defaults = {'nombre_empresa': 'Mi Bar'}
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
            return defaults
        except Exception as e:
            print(f"Error cargando configuración: {e}")
            return defaults
    
    def guardar_configuracion(self):
        """Guarda la configuración en archivo JSON"""
        try:
            with open('config.json', 'w') as f:
                json.dump({'nombre_empresa': self.nombre_empresa}, f, indent=4)
        except Exception as e:
            print(f"Error guardando configuración: {e}")
    
    def setup_ui(self):
        """Configura la interfaz principal"""
        self.root.title(f"Inventario Licores - {self.nombre_empresa} - {self.local_nombre}")
        
        # Configurar estilo
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configurar colores
        self.style.configure('.', background=self.colors['background'])
        self.style.configure('TFrame', background=self.colors['background'])
        self.style.configure('TLabel', background=self.colors['background'], font=self.font_text)
        self.style.configure('TButton', font=self.font_text)
        self.style.configure('Treeview', font=self.font_text, rowheight=25)
        self.style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        
        # Frame principal
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill='both', expand=True)
        
        # Barra de navegación
        self.setup_navigation()
        
        # Área de contenido
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        # Crear páginas
        self.create_pages()
        self.show_page('inventario')
    
    def setup_navigation(self):
        """Configura la barra de navegación lateral"""
        self.nav_frame = ttk.Frame(self.main_frame, width=200)
        self.nav_frame.pack(side='left', fill='y', padx=5, pady=5)
        
        # Logo y nombre
        logo_frame = ttk.Frame(self.nav_frame)
        logo_frame.pack(pady=10)
        
        self.lbl_nombre_empresa = ttk.Label(
            logo_frame, 
            text=self.nombre_empresa,
            font=('Helvetica', 12, 'bold')
        )
        self.lbl_nombre_empresa.pack()
        
        ttk.Label(logo_frame, text=f"v{VERSION}").pack()
        ttk.Label(logo_frame, text=f"Local: {self.local_nombre}").pack()
        ttk.Label(logo_frame, text=f"Usuario: {self.user_name}").pack()
        
        # Botón para editar nombre
        if self.user_role == 'admin':
            ttk.Button(
                logo_frame,
                text="✏️ Editar nombre",
                command=self.editar_nombre_empresa
            ).pack(pady=10)
        
        # Botones de navegación
        nav_buttons = [
            ('📊 Inventario', 'inventario'),
            ('📦 Productos', 'productos'),
            ('🔄 Movimientos', 'movimientos'),
            ('📈 Reportes', 'reportes'),
            ('ℹ️ Acerca de', 'about')
        ]
        
        for text, page in nav_buttons:
            ttk.Button(
                self.nav_frame,
                text=text,
                command=lambda p=page: self.show_page(p)
            ).pack(fill='x', padx=5, pady=2)
        
        # Botones de administración solo para admin
        if self.user_role == 'admin':
            ttk.Button(
                self.nav_frame,
                text="🏬 Locales",
                command=lambda: self.show_page('admin_locales')
            ).pack(fill='x', padx=5, pady=2)
            
            ttk.Button(
                self.nav_frame,
                text="👥 Usuarios",
                command=lambda: self.show_page('admin_usuarios')
            ).pack(fill='x', padx=5, pady=2)
        
        # Botón de salir
        ttk.Button(
            self.nav_frame,
            text="🚪 Salir",
            command=self.on_close
        ).pack(side='bottom', fill='x', padx=5, pady=10)
    
    def editar_nombre_empresa(self):
        """Permite editar el nombre del establecimiento"""
        nuevo_nombre = simpledialog.askstring(
            "Editar nombre",
            "Ingrese el nuevo nombre:",
            initialvalue=self.nombre_empresa
        )
        
        if nuevo_nombre and nuevo_nombre != self.nombre_empresa:
            self.nombre_empresa = nuevo_nombre
            self.actualizar_interfaz()
            self.guardar_configuracion()
            messagebox.showinfo("Éxito", "Nombre actualizado correctamente")
    
    def actualizar_interfaz(self):
        """Actualiza los elementos de la interfaz con el nuevo nombre"""
        self.root.title(f"Inventario Licores - {self.nombre_empresa} - {self.local_nombre}")
        self.lbl_nombre_empresa.config(text=self.nombre_empresa)
        
        # Actualizar página "Acerca de" si existe
        if 'about' in self.pages:
            for widget in self.pages['about'].winfo_children():
                if isinstance(widget, ttk.LabelFrame) and "Acerca de" in widget.cget('text'):
                    widget.config(text=f"Acerca de {self.nombre_empresa}")
    
    def create_pages(self):
        """Crea todas las páginas de la aplicación"""
        self.create_inventario_page()
        self.create_productos_page()
        self.create_movimientos_page()
        self.create_reportes_page()
        self.create_about_page()
        
        if self.user_role == 'admin':
            self.create_admin_locales_page()
            self.create_admin_usuarios_page()
    
    def create_inventario_page(self):
        """Crea la página de inventario con diseño mejorado"""
        self.pages['inventario'] = ttk.Frame(self.content_frame)
        
        # Frame superior (gráfico y resumen)
        top_frame = ttk.LabelFrame(self.pages['inventario'], text="Resumen de Inventario")
        top_frame.pack(fill='x', pady=(0, 10))
        
        # Gráfico de niveles
        self.fig, self.ax = plt.subplots(figsize=(8, 4), dpi=100)
        self.fig.patch.set_facecolor(self.colors['background'])
        self.ax.set_facecolor(self.colors['background'])
        self.canvas = FigureCanvasTkAgg(self.fig, master=top_frame)
        self.canvas.get_tk_widget().pack(side='left', fill='both', expand=True, padx=10, pady=10)
        
        # Resumen rápido
        summary_frame = ttk.Frame(top_frame)
        summary_frame.pack(side='right', fill='y', padx=10, pady=10)
        
        ttk.Label(summary_frame, text="Estadísticas", font=self.font_title).pack(pady=5)
        
        self.lbl_total_productos = ttk.Label(summary_frame, text="Productos: 0", font=self.font_text)
        self.lbl_total_productos.pack(anchor='w', pady=2)
        
        self.lbl_botellas_completas = ttk.Label(summary_frame, text="Botellas completas: 0", font=self.font_text)
        self.lbl_botellas_completas.pack(anchor='w', pady=2)
        
        self.lbl_bajos_inventario = ttk.Label(summary_frame, text="Productos bajos: 0", 
                                            foreground=self.colors['danger'], font=self.font_text)
        self.lbl_bajos_inventario.pack(anchor='w', pady=2)
        
        # Frame de lista de inventario
        inv_frame = ttk.LabelFrame(self.pages['inventario'], text="Inventario Actual")
        inv_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Treeview de inventario
        self.tree_inventario = ttk.Treeview(inv_frame, columns=('nombre', 'marca', 'tipo', 'disponible', 'botellas', 'estado'), 
                                           show='headings')
        
        # Configurar columnas
        columns = [
            ('nombre', 'Nombre', 150),
            ('marca', 'Marca', 120),
            ('tipo', 'Tipo', 100),
            ('disponible', 'Disponible', 150),
            ('botellas', 'Bot. Completas', 80),
            ('estado', 'Estado', 80)
        ]
        
        for col_id, col_text, width in columns:
            self.tree_inventario.heading(col_id, text=col_text)
            self.tree_inventario.column(col_id, width=width, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(inv_frame, orient='vertical', command=self.tree_inventario.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree_inventario.configure(yscrollcommand=scrollbar.set)
        self.tree_inventario.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        
        # Configurar tags para colores
        self.tree_inventario.tag_configure('bajo', foreground=self.colors['danger'])
        self.tree_inventario.tag_configure('ok', foreground=self.colors['success'])
        
        # Frame de controles
        ctrl_frame = ttk.LabelFrame(self.pages['inventario'], text="Acciones Rápidas")
        ctrl_frame.pack(fill='x', pady=(0, 10))
        
        # Controles de registro de peso
        ttk.Label(ctrl_frame, text="Peso total (g):", font=self.font_text).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.entry_peso = ttk.Entry(ctrl_frame, font=self.font_text, width=10)
        self.entry_peso.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ToolTip(self.entry_peso, "Ingrese el peso total medido en gramos")
        
        self.btn_registrar = ttk.Button(ctrl_frame, text="Registrar Peso", command=self.registrar_peso)
        self.btn_registrar.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.btn_registrar, "Registrar el peso actual del producto seleccionado")
        
        btn_auto_vacio = ttk.Button(ctrl_frame, text="Peso Vacío", command=self.auto_completar_peso_vacio)
        btn_auto_vacio.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(btn_auto_vacio, "Autocompletar con el peso del envase vacío")
        
        btn_agregar_botella = ttk.Button(ctrl_frame, text="+ Botella Completa", 
                                        command=self.agregar_botella_completa)
        btn_agregar_botella.grid(row=0, column=4, padx=5, pady=5)
        ToolTip(btn_agregar_botella, "Agregar una botella completa al inventario")
        
        btn_quitar_botella = ttk.Button(ctrl_frame, text="- Botella Completa", 
                                       command=self.quitar_botella_completa)
        btn_quitar_botella.grid(row=0, column=5, padx=5, pady=5)
        ToolTip(btn_quitar_botella, "Quitar una botella completa del inventario")
        
        # Detalles del producto
        self.details_frame = ttk.LabelFrame(self.pages['inventario'], text="Detalles del Producto")
        self.details_frame.pack(fill='x', pady=(0, 10))
        
        self.lbl_detalles = ttk.Label(self.details_frame, text="Seleccione un producto para ver detalles", 
                                    font=self.font_text, wraplength=800)
        self.lbl_detalles.pack(fill='x', padx=10, pady=10)
        
        # Barra de progreso
        self.progress_frame = ttk.Frame(self.pages['inventario'])
        self.progress_frame.pack(fill='x', pady=(0, 10))
        
        self.canvas_progreso = tk.Canvas(self.progress_frame, height=25, bg='white', highlightthickness=0)
        self.canvas_progreso.pack(fill='x')
        
        # Configurar evento de selección
        self.tree_inventario.bind('<<TreeviewSelect>>', self.mostrar_detalles_producto)
    
    def create_productos_page(self):
        """Crea la página de gestión de productos"""
        self.pages['productos'] = ttk.Frame(self.content_frame)
        
        # Frame de formulario
        form_frame = ttk.LabelFrame(self.pages['productos'], text="Agregar/Editar Producto")
        form_frame.pack(fill='x', padx=10, pady=10)
        
        # Campos del formulario
        ttk.Label(form_frame, text="Nombre:", font=self.font_text).grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.entry_prod_nombre = ttk.Entry(form_frame, font=self.font_text)
        self.entry_prod_nombre.grid(row=0, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Marca:", font=self.font_text).grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.entry_prod_marca = ttk.Entry(form_frame, font=self.font_text)
        self.entry_prod_marca.grid(row=1, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Tipo:", font=self.font_text).grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.combo_prod_tipo = ttk.Combobox(form_frame, values=[
            'Whisky', 'Vodka', 'Ron', 'Ginebra', 'Tequila', 'Brandy',
            'Coñac', 'Pisco', 'Vino', 'Cerveza', 'Licor', 'Crema'
        ], font=self.font_text, state='readonly')
        self.combo_prod_tipo.grid(row=2, column=1, sticky='we', padx=5, pady=5)
        self.combo_prod_tipo.bind("<<ComboboxSelected>>", self.actualizar_densidad_por_tipo)
        
        # Diccionario de densidades
        self.densidades_licores = {
            'Whisky': 0.94,
            'Vodka': 0.953,
            'Ron': 0.95,
            'Ginebra': 0.949,
            'Tequila': 0.93,
            'Brandy': 0.96,
            'Coñac': 0.965,
            'Pisco': 0.94,
            'Vino': 0.99,
            'Cerveza': 1.01,
            'Licor': 1.02,
            'Crema': 1.03
        }
        
        ttk.Label(form_frame, text="Densidad (g/ml):", font=self.font_text).grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.entry_prod_densidad = ttk.Entry(form_frame, font=self.font_text)
        self.entry_prod_densidad.grid(row=3, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Capacidad (ml):", font=self.font_text).grid(row=4, column=0, sticky='e', padx=5, pady=5)
        self.entry_prod_capacidad = ttk.Entry(form_frame, font=self.font_text)
        self.entry_prod_capacidad.grid(row=4, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Peso envase (g):", font=self.font_text).grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.entry_prod_peso_envase = ttk.Entry(form_frame, font=self.font_text)
        self.entry_prod_peso_envase.grid(row=5, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Mínimo inventario (%):", font=self.font_text).grid(row=6, column=0, sticky='e', padx=5, pady=5)
        self.entry_prod_minimo = ttk.Entry(form_frame, font=self.font_text)
        self.entry_prod_minimo.insert(0, "20")
        self.entry_prod_minimo.grid(row=6, column=1, sticky='we', padx=5, pady=5)
        
        # Botones de acción
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=7, columnspan=2, pady=10)
        
        self.btn_guardar_producto = ttk.Button(btn_frame, text="Guardar", command=self.guardar_producto)
        self.btn_guardar_producto.pack(side='left', padx=5)
        
        self.btn_limpiar_form = ttk.Button(btn_frame, text="Limpiar", command=self.limpiar_formulario_producto)
        self.btn_limpiar_form.pack(side='left', padx=5)
        
        self.btn_eliminar_producto = ttk.Button(btn_frame, text="Eliminar", command=self.eliminar_producto)
        self.btn_eliminar_producto.pack(side='left', padx=5)
        
        # Lista de productos
        list_frame = ttk.LabelFrame(self.pages['productos'], text="Lista de Productos")
        list_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        self.tree_productos = ttk.Treeview(list_frame, columns=('id', 'nombre', 'marca', 'tipo', 'botellas', 'estado'), 
                                          show='headings')
        
        # Configurar columnas
        columns = [
            ('id', 'ID', 50),
            ('nombre', 'Nombre', 150),
            ('marca', 'Marca', 120),
            ('tipo', 'Tipo', 100),
            ('botellas', 'Bot. Completas', 80),
            ('estado', 'Estado', 80)
        ]
        
        for col_id, col_text, width in columns:
            self.tree_productos.heading(col_id, text=col_text)
            self.tree_productos.column(col_id, width=width, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree_productos.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree_productos.configure(yscrollcommand=scrollbar.set)
        self.tree_productos.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        
        # Evento de selección
        self.tree_productos.bind('<<TreeviewSelect>>', self.cargar_producto_seleccionado)
    
    def create_movimientos_page(self):
        """Crea la página de movimientos"""
        self.pages['movimientos'] = ttk.Frame(self.content_frame)
        
        # Frame de filtros
        ctrl_frame = ttk.LabelFrame(self.pages['movimientos'], text="Filtrar Movimientos")
        ctrl_frame.pack(fill='x', padx=10, pady=10)
        
        # Filtros
        ttk.Label(ctrl_frame, text="Producto:", font=self.font_text).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.combo_filtro_producto = ttk.Combobox(ctrl_frame, state='readonly', font=self.font_text)
        self.combo_filtro_producto.grid(row=0, column=1, padx=5, pady=5, sticky='we')
        self.combo_filtro_producto.bind('<<ComboboxSelected>>', self.filtrar_movimientos)
        
        ttk.Label(ctrl_frame, text="Tipo:", font=self.font_text).grid(row=0, column=2, padx=5, pady=5, sticky='e')
        self.combo_filtro_tipo = ttk.Combobox(ctrl_frame, values=['Todos', 'entrada', 'salida', 'ajuste'], 
                                             state='readonly', font=self.font_text)
        self.combo_filtro_tipo.set('Todos')
        self.combo_filtro_tipo.grid(row=0, column=3, padx=5, pady=5, sticky='we')
        self.combo_filtro_tipo.bind('<<ComboboxSelected>>', self.filtrar_movimientos)
        
        ttk.Label(ctrl_frame, text="Desde:", font=self.font_text).grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.entry_filtro_desde = ttk.Entry(ctrl_frame, font=self.font_text, width=10)
        self.entry_filtro_desde.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        
        ttk.Label(ctrl_frame, text="Hasta:", font=self.font_text).grid(row=1, column=2, padx=5, pady=5, sticky='e')
        self.entry_filtro_hasta = ttk.Entry(ctrl_frame, font=self.font_text, width=10)
        self.entry_filtro_hasta.grid(row=1, column=3, padx=5, pady=5, sticky='w')
        
        btn_filtrar = ttk.Button(ctrl_frame, text="Aplicar Filtros", command=self.filtrar_movimientos)
        btn_filtrar.grid(row=1, column=4, padx=5, pady=5)
        
        btn_exportar = ttk.Button(ctrl_frame, text="Exportar a Excel", command=self.exportar_movimientos_excel)
        btn_exportar.grid(row=1, column=5, padx=5, pady=5)
        
        # Lista de movimientos
        list_frame = ttk.LabelFrame(self.pages['movimientos'], text="Movimientos Registrados")
        list_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        self.tree_movimientos = ttk.Treeview(list_frame, columns=('fecha', 'producto', 'tipo', 'cantidad', 'notas', 'usuario'), 
                                           show='headings')
        
        # Configurar columnas
        columns = [
            ('fecha', 'Fecha', 150),
            ('producto', 'Producto', 150),
            ('tipo', 'Tipo', 80),
            ('cantidad', 'Cantidad (ml)', 100),
            ('notas', 'Notas', 250),
            ('usuario', 'Usuario', 100)
        ]
        
        for col_id, col_text, width in columns:
            self.tree_movimientos.heading(col_id, text=col_text)
            self.tree_movimientos.column(col_id, width=width, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree_movimientos.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree_movimientos.configure(yscrollcommand=scrollbar.set)
        self.tree_movimientos.pack(side='left', fill='both', expand=True, padx=5, pady=5)
    
    def create_reportes_page(self):
        """Crea la página de reportes"""
        self.pages['reportes'] = ttk.Frame(self.content_frame)
        
        # Frame de gráficos
        graph_frame = ttk.LabelFrame(self.pages['reportes'], text="Reporte de Consumo")
        graph_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Gráfico de consumo
        self.fig_reportes, self.ax_reportes = plt.subplots(figsize=(10, 6), dpi=100)
        self.fig_reportes.patch.set_facecolor(self.colors['background'])
        self.ax_reportes.set_facecolor(self.colors['background'])
        self.canvas_reportes = FigureCanvasTkAgg(self.fig_reportes, master=graph_frame)
        self.canvas_reportes.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        
        # Frame de controles
        ctrl_frame = ttk.LabelFrame(self.pages['reportes'], text="Opciones de Reporte")
        ctrl_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        # Controles de reporte
        ttk.Label(ctrl_frame, text="Producto:", font=self.font_text).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.combo_reporte_producto = ttk.Combobox(ctrl_frame, state='readonly', font=self.font_text)
        self.combo_reporte_producto.grid(row=0, column=1, padx=5, pady=5, sticky='we')
        
        ttk.Label(ctrl_frame, text="Período:", font=self.font_text).grid(row=0, column=2, padx=5, pady=5, sticky='e')
        self.combo_reporte_periodo = ttk.Combobox(ctrl_frame, values=['7 días', '15 días', '30 días', '60 días', '90 días'], 
                                                state='readonly', font=self.font_text)
        self.combo_reporte_periodo.set('30 días')
        self.combo_reporte_periodo.grid(row=0, column=3, padx=5, pady=5, sticky='we')
        
        btn_generar_reporte = ttk.Button(ctrl_frame, text="Generar Reporte", command=self.generar_reporte_consumo)
        btn_generar_reporte.grid(row=0, column=4, padx=5, pady=5)
        
        btn_exportar_reporte = ttk.Button(ctrl_frame, text="Exportar Gráfico", command=self.exportar_grafico)
        btn_exportar_reporte.grid(row=0, column=5, padx=5, pady=5)
    
    def create_about_page(self):
        """Crea la página 'Acerca de'"""
        self.pages['about'] = ttk.Frame(self.content_frame)
        
        about_frame = ttk.LabelFrame(self.pages['about'], text=f"Acerca de {self.nombre_empresa}")
        about_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        title_frame = ttk.Frame(about_frame)
        title_frame.pack(pady=20)
        
        ttk.Label(title_frame, text=f"{self.nombre_empresa}", 
                 font=('Segoe UI', 24, 'bold'), 
                 foreground=self.colors['primary']).pack()
        
        ttk.Label(title_frame, text=f"Versión {VERSION}", 
                 font=self.font_text, 
                 foreground=self.colors['secondary']).pack()
        
        # Descripción
        desc_frame = ttk.Frame(about_frame)
        desc_frame.pack(fill='x', pady=10, padx=20)
        
        features = [
            ("📦", "Gestión completa de inventario de licores"),
            ("📊", "Reportes y estadísticas detalladas"),
            ("📝", "Registro de movimientos y transacciones"),
            ("🔔", "Alertas de inventario bajo"),
            ("📱", "Interfaz intuitiva y fácil de uso")
        ]
        
        for icon, text in features:
            frame = ttk.Frame(desc_frame)
            frame.pack(fill='x', pady=2)
            ttk.Label(frame, text=icon, font=('Segoe UI', 12)).pack(side='left', padx=5)
            ttk.Label(frame, text=text, font=self.font_text).pack(side='left')
        
        # Créditos
        credits_frame = ttk.Frame(about_frame)
        credits_frame.pack(fill='x', pady=20)
        
        ttk.Label(credits_frame, 
                 text="Desarrollado por [Ignacio y Gabriel]\n\n© 2025 Todos los derechos reservados",
                 font=self.font_small,
                 justify='center').pack()
        
        # Botones de acción
        btn_frame = ttk.Frame(about_frame)
        btn_frame.pack(pady=20)
        
        btn_manual = ttk.Button(btn_frame, text="📘 Manual de Usuario", command=self.abrir_manual)
        btn_manual.pack(side='left', padx=10)
        
        btn_soporte = ttk.Button(btn_frame, text="🛠️ Soporte Técnico", command=self.abrir_soporte)
        btn_soporte.pack(side='left', padx=10)
        
        btn_actualizaciones = ttk.Button(btn_frame, text="🔄 Ver Actualizaciones", command=self.ver_actualizaciones)
        btn_actualizaciones.pack(side='left', padx=10)
    
    def create_admin_locales_page(self):
        """Crea la página de administración de locales (solo para admin)"""
        self.pages['admin_locales'] = ttk.Frame(self.content_frame)
        
        # Frame de formulario
        form_frame = ttk.LabelFrame(self.pages['admin_locales'], text="Agregar/Editar Local")
        form_frame.pack(fill='x', padx=10, pady=10)
        
        # Campos del formulario
        ttk.Label(form_frame, text="Nombre:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_local_nombre = ttk.Entry(form_frame)
        self.entry_local_nombre.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="Dirección:", font=self.font_text).grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.entry_local_direccion = ttk.Entry(form_frame, font=self.font_text)
        self.entry_local_direccion.grid(row=1, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Teléfono:", font=self.font_text).grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.entry_local_telefono = ttk.Entry(form_frame, font=self.font_text)
        self.entry_local_telefono.grid(row=2, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Estado:", font=self.font_text).grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.combo_local_activo = ttk.Combobox(form_frame, values=['Activo', 'Inactivo'], state='readonly', font=self.font_text)
        self.combo_local_activo.set('Activo')
        self.combo_local_activo.grid(row=3, column=1, sticky='we', padx=5, pady=5)
        
        # Botones de acción
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=4, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Guardar", command=self.guardar_local).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Limpiar", command=self.limpiar_formulario_local).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Eliminar", command=self.eliminar_local).pack(side='left', padx=5)
        
        # Lista de locales
        list_frame = ttk.LabelFrame(self.pages['admin_locales'], text="Lista de Locales")
        list_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        columns = ('id', 'nombre', 'direccion', 'telefono', 'estado')
        self.tree_locales = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        # Configurar columnas
        self.tree_locales.heading('id', text='ID')
        self.tree_locales.column('id', width=50, anchor='center')
        self.tree_locales.heading('nombre', text='Nombre')
        self.tree_locales.column('nombre', width=150)
        self.tree_locales.heading('direccion', text='Dirección')
        self.tree_locales.column('direccion', width=200)
        self.tree_locales.heading('telefono', text='Teléfono')
        self.tree_locales.column('telefono', width=100)
        self.tree_locales.heading('estado', text='Estado')
        self.tree_locales.column('estado', width=80, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree_locales.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree_locales.configure(yscrollcommand=scrollbar.set)
        self.tree_locales.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        
        # Evento de selección
        self.tree_locales.bind('<<TreeviewSelect>>', self.cargar_local_seleccionado)
        
        # Cargar datos iniciales
        self.actualizar_lista_locales()
    
    def create_admin_usuarios_page(self):
        """Crea la página de administración de usuarios (solo para admin)"""
        self.pages['admin_usuarios'] = ttk.Frame(self.content_frame)
        
        # Frame de formulario
        form_frame = ttk.LabelFrame(self.pages['admin_usuarios'], text="Agregar/Editar Usuario")
        form_frame.pack(fill='x', padx=10, pady=10)
        
        # Campos del formulario
        ttk.Label(form_frame, text="Usuario:", font=self.font_text).grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.entry_usuario_username = ttk.Entry(form_frame, font=self.font_text)
        self.entry_usuario_username.grid(row=0, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Contraseña:", font=self.font_text).grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.entry_usuario_password = ttk.Entry(form_frame, font=self.font_text)
        self.entry_usuario_password.grid(row=1, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Nombre:", font=self.font_text).grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.entry_usuario_nombre = ttk.Entry(form_frame, font=self.font_text)
        self.entry_usuario_nombre.grid(row=2, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Rol:", font=self.font_text).grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.combo_usuario_rol = ttk.Combobox(form_frame, values=['admin', 'gerente', 'empleado'], 
                                            state='readonly', font=self.font_text)
        self.combo_usuario_rol.grid(row=3, column=1, sticky='we', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Local:", font=self.font_text).grid(row=4, column=0, sticky='e', padx=5, pady=5)
        self.combo_usuario_local = ttk.Combobox(form_frame, state='readonly', font=self.font_text)
        self.combo_usuario_local.grid(row=4, column=1, sticky='we', padx=5, pady=5)
        self.cargar_locales_usuarios()
        
        ttk.Label(form_frame, text="Estado:", font=self.font_text).grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.combo_usuario_activo = ttk.Combobox(form_frame, values=['Activo', 'Inactivo'], 
                                               state='readonly', font=self.font_text)
        self.combo_usuario_activo.set('Activo')
        self.combo_usuario_activo.grid(row=5, column=1, sticky='we', padx=5, pady=5)
        
        # Botones de acción
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=6, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Guardar", command=self.guardar_usuario).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Limpiar", command=self.limpiar_formulario_usuario).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Eliminar", command=self.eliminar_usuario).pack(side='left', padx=5)
        
        # Lista de usuarios
        list_frame = ttk.LabelFrame(self.pages['admin_usuarios'], text="Lista de Usuarios")
        list_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        columns = ('id', 'username', 'nombre', 'rol', 'local', 'estado')
        self.tree_usuarios = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        # Configurar columnas
        self.tree_usuarios.heading('id', text='ID')
        self.tree_usuarios.column('id', width=50, anchor='center')
        self.tree_usuarios.heading('username', text='Usuario')
        self.tree_usuarios.column('username', width=100)
        self.tree_usuarios.heading('nombre', text='Nombre')
        self.tree_usuarios.column('nombre', width=150)
        self.tree_usuarios.heading('rol', text='Rol')
        self.tree_usuarios.column('rol', width=80)
        self.tree_usuarios.heading('local', text='Local')
        self.tree_usuarios.column('local', width=150)
        self.tree_usuarios.heading('estado', text='Estado')
        self.tree_usuarios.column('estado', width=80, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree_usuarios.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree_usuarios.configure(yscrollcommand=scrollbar.set)
        self.tree_usuarios.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        
        # Evento de selección
        self.tree_usuarios.bind('<<TreeviewSelect>>', self.cargar_usuario_seleccionado)
        
        # Cargar datos iniciales
        self.actualizar_lista_usuarios()
    
    def cargar_locales_usuarios(self):
        """Carga los locales en el combobox de usuarios"""
        locales = self.db.fetch_all("SELECT id, nombre FROM locales ORDER BY nombre")
        self.locales_usuarios_data = {f"{l[1]} (ID: {l[0]})": l[0] for l in locales}
        self.combo_usuario_local['values'] = list(self.locales_usuarios_data.keys())
        if locales:
            self.combo_usuario_local.current(0)
    
    def cargar_local_seleccionado(self, event):
        """Carga los datos del local seleccionado en el formulario"""
        seleccion = self.tree_locales.selection()
        if not seleccion:
            return
            
        item = self.tree_locales.item(seleccion[0])
        id_local = item['values'][0]
        
        query = "SELECT nombre, direccion, telefono, activo FROM locales WHERE id = ?"
        local = self.db.fetch_one(query, (id_local,))
        
        if local:
            nombre, direccion, telefono, activo = local
            
            self.entry_local_nombre.delete(0, 'end')
            self.entry_local_nombre.insert(0, nombre)
            
            self.entry_local_direccion.delete(0, 'end')
            self.entry_local_direccion.insert(0, direccion if direccion else "")
            
            self.entry_local_telefono.delete(0, 'end')
            self.entry_local_telefono.insert(0, telefono if telefono else "")
            
            self.combo_local_activo.set('Activo' if activo else 'Inactivo')
    
    def cargar_usuario_seleccionado(self, event):
        """Carga los datos del usuario seleccionado en el formulario"""
        seleccion = self.tree_usuarios.selection()
        if not seleccion:
            return
            
        item = self.tree_usuarios.item(seleccion[0])
        id_usuario = item['values'][0]
        
        query = """
        SELECT u.username, u.password, u.nombre, u.rol, u.activo, l.nombre 
        FROM usuarios u
        LEFT JOIN locales l ON u.local_id = l.id
        WHERE u.id = ?
        """
        usuario = self.db.fetch_one(query, (id_usuario,))
        
        if usuario:
            username, password, nombre, rol, activo, local_nombre = usuario
            
            self.entry_usuario_username.delete(0, 'end')
            self.entry_usuario_username.insert(0, username)
            
            self.entry_usuario_password.delete(0, 'end')
            self.entry_usuario_password.insert(0, password)
            
            self.entry_usuario_nombre.delete(0, 'end')
            self.entry_usuario_nombre.insert(0, nombre)
            
            self.combo_usuario_rol.set(rol)
            
            if local_nombre:
                local_str = f"{local_nombre} (ID: {self.get_local_id_by_name(local_nombre)})"
                self.combo_usuario_local.set(local_str)
            else:
                self.combo_usuario_local.set('')
            
            self.combo_usuario_activo.set('Activo' if activo else 'Inactivo')
    
    def get_local_id_by_name(self, nombre):
        """Obtiene el ID de un local por su nombre"""
        query = "SELECT id FROM locales WHERE nombre = ?"
        result = self.db.fetch_one(query, (nombre,))
        return result[0] if result else None
    
    def limpiar_formulario_local(self):
        """Limpia el formulario de local"""
        self.entry_local_nombre.delete(0, 'end')
        self.entry_local_direccion.delete(0, 'end')
        self.entry_local_telefono.delete(0, 'end')
        self.combo_local_activo.set('Activo')
        self.tree_locales.selection_remove(self.tree_locales.selection())
    
    def limpiar_formulario_usuario(self):
        """Limpia el formulario de usuario"""
        self.entry_usuario_username.delete(0, 'end')
        self.entry_usuario_password.delete(0, 'end')
        self.entry_usuario_nombre.delete(0, 'end')
        self.combo_usuario_rol.set('')
        self.combo_usuario_local.set('')
        self.combo_usuario_activo.set('Activo')
        self.tree_usuarios.selection_remove(self.tree_usuarios.selection())
    
    def guardar_local(self):
        """Guarda un local nuevo o existente"""
        nombre = self.entry_local_nombre.get().strip()
        direccion = self.entry_local_direccion.get().strip()
        telefono = self.entry_local_telefono.get().strip()
        activo = 1 if self.combo_local_activo.get() == 'Activo' else 0
        
        if not nombre:
            messagebox.showerror("Error", "El nombre del local es obligatorio")
            return
        
        # Verificar si es un local nuevo o existente
        seleccion = self.tree_locales.selection()
        if seleccion:
            # Editar local existente
            item = self.tree_locales.item(seleccion[0])
            id_local = item['values'][0]
            
            query = """
            UPDATE locales 
            SET nombre = ?, direccion = ?, telefono = ?, activo = ?
            WHERE id = ?
            """
            self.db.execute_query(query, (nombre, direccion, telefono, activo, id_local))
            
            messagebox.showinfo("Éxito", "Local actualizado correctamente")
            
            # Si estamos editando el local actual, actualizar la interfaz
            if id_local == self.local_id:
                self.local_nombre = nombre
                self.root.title(f"Inventario Licores - {self.nombre_empresa} - {self.local_nombre}")
        else:
            # Nuevo local
            query = """
            INSERT INTO locales (nombre, direccion, telefono, activo)
            VALUES (?, ?, ?, ?)
            """
            self.db.execute_query(query, (nombre, direccion, telefono, activo))
            
            messagebox.showinfo("Éxito", "Local agregado correctamente")
        
        # Actualizar interfaces
        self.limpiar_formulario_local()
        self.actualizar_lista_locales()
        self.cargar_locales_usuarios()
    
    def guardar_usuario(self):
        """Guarda un usuario nuevo o existente"""
        username = self.entry_usuario_username.get().strip()
        password = self.entry_usuario_password.get().strip()
        nombre = self.entry_usuario_nombre.get().strip()
        rol = self.combo_usuario_rol.get().strip()
        local_str = self.combo_usuario_local.get()
        activo = 1 if self.combo_usuario_activo.get() == 'Activo' else 0
        
        if not username or not password or not nombre or not rol:
            messagebox.showerror("Error", "Usuario, contraseña, nombre y rol son campos obligatorios")
            return
        
        # Obtener local_id
        local_id = None
        if local_str:
            try:
                local_id = self.locales_usuarios_data[local_str]
            except:
                messagebox.showerror("Error", "Seleccione un local válido")
                return
        
        # Verificar si es un usuario nuevo o existente
        seleccion = self.tree_usuarios.selection()
        if seleccion:
            # Editar usuario existente
            item = self.tree_usuarios.item(seleccion[0])
            id_usuario = item['values'][0]
            
            query = """
            UPDATE usuarios 
            SET username = ?, password = ?, nombre = ?, rol = ?, local_id = ?, activo = ?
            WHERE id = ?
            """
            self.db.execute_query(query, (username, password, nombre, rol, local_id, activo, id_usuario))
            
            messagebox.showinfo("Éxito", "Usuario actualizado correctamente")
        else:
            # Nuevo usuario
            query = """
            INSERT INTO usuarios (username, password, nombre, rol, local_id, activo)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            self.db.execute_query(query, (username, password, nombre, rol, local_id, activo))
            
            messagebox.showinfo("Éxito", "Usuario agregado correctamente")
        
        # Actualizar interfaces
        self.limpiar_formulario_usuario()
        self.actualizar_lista_usuarios()
    
    def eliminar_local(self):
        """Elimina el local seleccionado"""
        seleccion = self.tree_locales.selection()
        if not seleccion:
            messagebox.showerror("Error", "Seleccione un local primero")
            return
            
        item = self.tree_locales.item(seleccion[0])
        id_local = item['values'][0]
        nombre = item['values'][1]
        
        # Verificar si hay productos asociados
        productos = self.db.fetch_one("SELECT COUNT(*) FROM productos WHERE local_id = ?", (id_local,))[0]
        if productos > 0:
            messagebox.showerror("Error", "No se puede eliminar un local que tiene productos asociados")
            return
        
        # Verificar si hay usuarios asociados
        usuarios = self.db.fetch_one("SELECT COUNT(*) FROM usuarios WHERE local_id = ?", (id_local,))[0]
        if usuarios > 0:
            messagebox.showerror("Error", "No se puede eliminar un local que tiene usuarios asociados")
            return
        
        confirmacion = messagebox.askyesno("Confirmar", f"¿Eliminar permanentemente el local '{nombre}'?")
        if not confirmacion:
            return
            
        # Eliminar el local
        self.db.execute_query("DELETE FROM locales WHERE id = ?", (id_local,))
        
        messagebox.showinfo("Éxito", "Local eliminado correctamente")
        
        # Actualizar interfaces
        self.limpiar_formulario_local()
        self.actualizar_lista_locales()
        self.cargar_locales_usuarios()
    
    def eliminar_usuario(self):
        """Elimina el usuario seleccionado"""
        seleccion = self.tree_usuarios.selection()
        if not seleccion:
            messagebox.showerror("Error", "Seleccione un usuario primero")
            return
            
        item = self.tree_usuarios.item(seleccion[0])
        id_usuario = item['values'][0]
        username = item['values'][1]
        
        # No permitir eliminar al propio usuario
        if id_usuario == self.user_id:
            messagebox.showerror("Error", "No puede eliminarse a sí mismo")
            return
        
        confirmacion = messagebox.askyesno("Confirmar", f"¿Eliminar permanentemente el usuario '{username}'?")
        if not confirmacion:
            return
            
        # Eliminar movimientos asociados primero
        self.db.execute_query("DELETE FROM movimientos WHERE user_id = ?", (id_usuario,))
        
        # Luego eliminar el usuario
        self.db.execute_query("DELETE FROM usuarios WHERE id = ?", (id_usuario,))
        
        messagebox.showinfo("Éxito", "Usuario eliminado correctamente")
        
        # Actualizar interfaces
        self.limpiar_formulario_usuario()
        self.actualizar_lista_usuarios()
    
    def actualizar_lista_locales(self):
        """Actualiza la lista de locales"""
        query = "SELECT id, nombre, direccion, telefono, activo FROM locales ORDER BY nombre"
        locales = self.db.fetch_all(query)
        
        self.tree_locales.delete(*self.tree_locales.get_children())
        
        for loc in locales:
            id, nombre, direccion, telefono, activo = loc
            estado = "Activo" if activo else "Inactivo"
            self.tree_locales.insert('', 'end', values=(id, nombre, direccion or "", telefono or "", estado))
    
    def actualizar_lista_usuarios(self):
        """Actualiza la lista de usuarios"""
        query = """
        SELECT u.id, u.username, u.nombre, u.rol, u.activo, l.nombre 
        FROM usuarios u
        LEFT JOIN locales l ON u.local_id = l.id
        ORDER BY u.nombre
        """
        usuarios = self.db.fetch_all(query)
        
        self.tree_usuarios.delete(*self.tree_usuarios.get_children())
        
        for user in usuarios:
            id, username, nombre, rol, activo, local_nombre = user
            estado = "Activo" if activo else "Inactivo"
            self.tree_usuarios.insert('', 'end', values=(id, username, nombre, rol, local_nombre or "", estado))
    
    def actualizar_densidad_por_tipo(self, event=None):
        """Actualiza la densidad según el tipo de licor seleccionado"""
        tipo = self.combo_prod_tipo.get()
        densidad = self.densidades_licores.get(tipo)
        if densidad:
            self.entry_prod_densidad.delete(0, tk.END)
            self.entry_prod_densidad.insert(0, str(densidad))
    
    def cargar_productos(self):
        """Carga los productos desde la base de datos"""
        try:
            if self.user_role == 'admin':
                query = "SELECT id, nombre, marca, tipo FROM productos ORDER BY nombre"
                productos = self.db.fetch_all(query)
            else:
                query = "SELECT id, nombre, marca, tipo FROM productos WHERE local_id = ? ORDER BY nombre"
                productos = self.db.fetch_all(query, (self.local_id,))
        
            # Actualizar comboboxes
            nombres_productos = ["Todos"] + [p[1] for p in productos]
            self.combo_filtro_producto['values'] = nombres_productos
            self.combo_filtro_producto.set('Todos')

            if productos:
                self.combo_reporte_producto['values'] = [p[1] for p in productos]
                self.combo_reporte_producto.current(0)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los productos: {str(e)}")
    
    def cargar_movimientos_recientes(self):
        """Carga los movimientos más recientes"""
        if self.user_role == 'admin':
            query = """
            SELECT m.fecha, p.nombre, m.tipo, m.cantidad_ml, m.notas, u.nombre
            FROM movimientos m
            JOIN productos p ON m.producto_id = p.id
            JOIN usuarios u ON m.user_id = u.id
            ORDER BY m.fecha DESC
            LIMIT 50
            """
            movimientos = self.db.fetch_all(query)
        else:
            query = """
            SELECT m.fecha, p.nombre, m.tipo, m.cantidad_ml, m.notas, u.nombre
            FROM movimientos m
            JOIN productos p ON m.producto_id = p.id
            JOIN usuarios u ON m.user_id = u.id
            WHERE p.local_id = ?
            ORDER BY m.fecha DESC
            LIMIT 50
            """
            movimientos = self.db.fetch_all(query, (self.local_id,))
        
        self.tree_movimientos.delete(*self.tree_movimientos.get_children())
        for mov in movimientos:
            self.tree_movimientos.insert('', 'end', values=mov)
    
    def cargar_producto_seleccionado(self, event):
        """Carga los datos del producto seleccionado en el formulario"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            return
            
        item = self.tree_productos.item(seleccion[0])
        id_producto = item['values'][0]
        
        query = "SELECT nombre, marca, tipo, densidad, capacidad_ml, peso_envase, minimo_inventario FROM productos WHERE id = ?"
        producto = self.db.fetch_one(query, (id_producto,))
        
        if producto:
            nombre, marca, tipo, densidad, capacidad, peso_envase, minimo = producto
            
            self.entry_prod_nombre.delete(0, 'end')
            self.entry_prod_nombre.insert(0, nombre)
            
            self.entry_prod_marca.delete(0, 'end')
            self.entry_prod_marca.insert(0, marca)
            
            self.combo_prod_tipo.set(tipo)
            
            self.entry_prod_densidad.delete(0, 'end')
            self.entry_prod_densidad.insert(0, str(densidad))
            
            self.entry_prod_capacidad.delete(0, 'end')
            self.entry_prod_capacidad.insert(0, str(capacidad))
            
            self.entry_prod_peso_envase.delete(0, 'end')
            self.entry_prod_peso_envase.insert(0, str(peso_envase            ))
            
            self.entry_prod_minimo.delete(0, 'end')
            self.entry_prod_minimo.insert(0, str(minimo * 100))  # Convertir a porcentaje
    
    def limpiar_formulario_producto(self):
        """Limpia el formulario de producto"""
        self.entry_prod_nombre.delete(0, 'end')
        self.entry_prod_marca.delete(0, 'end')
        self.combo_prod_tipo.set('')
        self.entry_prod_densidad.delete(0, 'end')
        self.entry_prod_capacidad.delete(0, 'end')
        self.entry_prod_peso_envase.delete(0, 'end')
        self.entry_prod_minimo.delete(0, 'end')
        self.entry_prod_minimo.insert(0, "20")
    
    def guardar_producto(self):
        """Guarda un producto nuevo o existente"""
        nombre = self.entry_prod_nombre.get().strip()
        marca = self.entry_prod_marca.get().strip()
        tipo = self.combo_prod_tipo.get().strip()
        
    # Verificar que local_id existe
        if not hasattr(self, 'local_id') or self.local_id is None:
            messagebox.showerror("Error", "No se ha asignado un local válido")
            return
            
        try:
            densidad = float(self.entry_prod_densidad.get())
            capacidad = float(self.entry_prod_capacidad.get())
            peso_envase = float(self.entry_prod_peso_envase.get())
            minimo = float(self.entry_prod_minimo.get()) / 100  # Convertir a fracción
            
            if densidad <= 0 or densidad > 2:
                raise ValueError("Densidad debe estar entre 0 y 2 g/ml")
            if capacidad <= 0:
                raise ValueError("La capacidad debe ser mayor que cero")
            if peso_envase <= 0:
                raise ValueError("El peso del envase debe ser mayor que cero")
            if minimo <= 0 or minimo > 1:
                raise ValueError("El mínimo de inventario debe estar entre 0% y 100%")
                
        except ValueError as e:
            messagebox.showerror("Error", f"Datos inválidos: {str(e)}")
            return
        
        # Verificar si es un producto nuevo o existente
        seleccion = self.tree_productos.selection()
        if seleccion:
            # Editar producto existente
            item = self.tree_productos.item(seleccion[0])
            id_producto = item['values'][0]
            
            query = """
            UPDATE productos 
            SET nombre = ?, marca = ?, tipo = ?, densidad = ?, capacidad_ml = ?, 
                peso_envase = ?, minimo_inventario = ?
            WHERE id = ?
            """
            self.db.execute_query(query, (nombre, marca, tipo, densidad, capacidad, peso_envase, minimo, id_producto))
            
            messagebox.showinfo("Éxito", "Producto actualizado correctamente")
        else:
            # Nuevo producto
            query = """
            INSERT INTO productos (local_id, nombre, marca, tipo, densidad, capacidad_ml, peso_envase, minimo_inventario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.db.execute_query(query, (self.local_id, nombre, marca, tipo, densidad, capacidad, peso_envase, minimo))
            
            messagebox.showinfo("Éxito", "Producto agregado correctamente")
        
        # Actualizar interfaces
        self.limpiar_formulario_producto()
        self.cargar_productos()
        self.actualizar_lista_productos()
        self.actualizar_inventario()
    
    def eliminar_producto(self):
        """Elimina el producto seleccionado"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            messagebox.showerror("Error", "Seleccione un producto primero")
            return
            
        item = self.tree_productos.item(seleccion[0])
        id_producto = item['values'][0]
        nombre = item['values'][1]
        
        confirmacion = messagebox.askyesno("Confirmar", f"¿Eliminar permanentemente el producto '{nombre}'?")
        if not confirmacion:
            return
            
        # Eliminar movimientos asociados primero
        self.db.execute_query("DELETE FROM movimientos WHERE producto_id = ?", (id_producto,))
        
        # Luego eliminar el producto
        self.db.execute_query("DELETE FROM productos WHERE id = ?", (id_producto,))
        
        messagebox.showinfo("Éxito", "Producto eliminado correctamente")
        
        # Actualizar interfaces
        self.limpiar_formulario_producto()
        self.cargar_productos()
        self.actualizar_lista_productos()
        self.actualizar_inventario()
    
    def actualizar_lista_productos(self):
        """Actualiza la lista de productos"""
        if self.user_role == 'admin':
            query = "SELECT id, nombre, marca, tipo, botellas_completas, activo FROM productos ORDER BY nombre"
            productos = self.db.fetch_all(query)
        else:
            query = "SELECT id, nombre, marca, tipo, botellas_completas, activo FROM productos WHERE local_id = ? ORDER BY nombre"
            productos = self.db.fetch_all(query, (self.local_id,))
        
        self.tree_productos.delete(*self.tree_productos.get_children())
        
        for prod in productos:
            id, nombre, marca, tipo, botellas, activo = prod
            estado = "Activo" if activo else "Inactivo"
            self.tree_productos.insert('', 'end', values=(id, nombre, marca, tipo, botellas, estado))
    
    def actualizar_inventario(self):
        """Actualiza la lista de inventario con los niveles actuales"""
        if self.user_role == 'admin':
            query = """
            SELECT 
                p.id, p.nombre, p.marca, p.tipo, p.botellas_completas, p.activo,
                (SELECT SUM(cantidad_ml) FROM movimientos WHERE producto_id = p.id) as total_ml
            FROM productos p
            ORDER BY p.nombre
            """
            productos = self.db.fetch_all(query)
        else:
            query = """
            SELECT 
                p.id, p.nombre, p.marca, p.tipo, p.botellas_completas, p.activo,
                (SELECT SUM(cantidad_ml) FROM movimientos WHERE producto_id = p.id) as total_ml
            FROM productos p
            WHERE p.local_id = ?
            ORDER BY p.nombre
            """
            productos = self.db.fetch_all(query, (self.local_id,))
        
        self.tree_inventario.delete(*self.tree_inventario.get_children())
        
        total_productos = 0
        total_botellas = 0
        bajos_inventario = 0
        
        for prod in productos:
            id, nombre, marca, tipo, botellas, activo, total_ml = prod
            total_productos += 1
            total_botellas += botellas
            
            if total_ml is None:
                disponible_text = "No registrado"
                estado = "Sin datos"
            else:
                # Obtener capacidad total del producto
                cap_query = "SELECT capacidad_ml FROM productos WHERE id = ?"
                capacidad = self.db.fetch_one(cap_query, (id,))[0]
                
                total_ml = total_ml or 0
                total_oz = total_ml * ML_A_OZ
                disponible_text = f"{total_ml:.1f} ml ({total_oz:.1f} oz)"
                
                # Verificar si está bajo en inventario
                if total_ml < (capacidad * 0.2):  # Menos del 20%
                    estado = "Bajo"
                    bajos_inventario += 1
                else:
                    estado = "OK"
            
            estado_text = "Activo" if activo else "Inactivo"
            
            self.tree_inventario.insert('', 'end', values=(
                nombre, marca, tipo, disponible_text, botellas, estado_text
            ), tags=(estado.lower(),))
        
        # Actualizar resumen
        self.lbl_total_productos.config(text=f"Productos: {total_productos}")
        self.lbl_botellas_completas.config(text=f"Botellas completas: {total_botellas}")
        self.lbl_bajos_inventario.config(text=f"Productos bajos: {bajos_inventario}")
        
        # Actualizar gráfico
        self.actualizar_grafico_inventario()
    
    def actualizar_grafico_inventario(self):
        """Actualiza el gráfico de niveles de inventario"""
        if self.user_role == 'admin':
            query = """
            SELECT 
                p.nombre, 
                (SELECT SUM(cantidad_ml) FROM movimientos WHERE producto_id = p.id) as total_ml,
                p.capacidad_ml
            FROM productos p
            WHERE p.activo = 1
            ORDER BY p.nombre
            """
            datos = self.db.fetch_all(query)
        else:
            query = """
            SELECT 
                p.nombre, 
                (SELECT SUM(cantidad_ml) FROM movimientos WHERE producto_id = p.id) as total_ml,
                p.capacidad_ml
            FROM productos p
            WHERE p.activo = 1 AND p.local_id = ?
            ORDER BY p.nombre
            """
            datos = self.db.fetch_all(query, (self.local_id,))
        
        self.ax.clear()
        
        nombres = []
        porcentajes = []
        colores = []
        
        for nombre, total_ml, capacidad in datos:
            if total_ml is None or capacidad == 0:
                continue
                
            porcentaje = (total_ml / capacidad) * 100
            nombres.append(nombre)
            porcentajes.append(porcentaje)
            
            if porcentaje < 20:
                colores.append('red')
            elif porcentaje < 50:
                colores.append('orange')
            else:
                colores.append('green')
        
        if nombres:
            y_pos = range(len(nombres))
            self.ax.barh(y_pos, porcentajes, color=colores)
            self.ax.set_yticks(y_pos)
            self.ax.set_yticklabels(nombres)
            self.ax.set_xlabel('Porcentaje de capacidad (%)')
            self.ax.set_title('Niveles de Inventario')
            self.ax.grid(axis='x', linestyle='--', alpha=0.7)
            
            # Añadir etiquetas de valor
            for i, v in enumerate(porcentajes):
                self.ax.text(v + 1, i, f"{v:.1f}%", color='black', va='center')
        
        self.canvas.draw()
    
    def mostrar_detalles_producto(self, event):
        """Muestra los detalles del producto seleccionado en el inventario"""
        seleccion = self.tree_inventario.selection()
        if not seleccion:
            return
            
        item = self.tree_inventario.item(seleccion[0])
        nombre = item['values'][0]
        
        # Obtener datos del producto
        query = """
        SELECT 
            p.id, p.nombre, p.marca, p.tipo, p.densidad, p.capacidad_ml, p.peso_envase, p.botellas_completas,
            (SELECT SUM(cantidad_ml) FROM movimientos WHERE producto_id = p.id) as total_ml
        FROM productos p
        WHERE p.nombre = ?
        """
        producto = self.db.fetch_one(query, (nombre,))
        
        if not producto:
            return
            
        id_prod, nombre, marca, tipo, densidad, capacidad, peso_envase, botellas, total_ml = producto
        
        # Calcular valores derivados
        if total_ml is not None:
            total_oz = total_ml * ML_A_OZ
            peso_licor = total_ml * densidad
            porcentaje = (total_ml / capacidad) * 100 if capacidad > 0 else 0
        else:
            total_ml = total_oz = peso_licor = porcentaje = 0
        
        # Mostrar detalles
        detalles = (
            f"Producto: {nombre} {marca}\n"
            f"Tipo: {tipo}\n"
            f"Densidad: {densidad} g/ml\n"
            f"Capacidad total: {capacidad} ml ({capacidad * ML_A_OZ:.1f} oz)\n"
            f"Peso envase vacío: {peso_envase} g\n"
            f"Disponible: {total_ml:.1f} ml ({total_oz:.1f} oz)\n"
            f"Peso licor actual: {peso_licor:.1f} g\n"
            f"Porcentaje de capacidad: {porcentaje:.1f}%\n"
            f"Botellas completas: {botellas}"
        )
        
        self.lbl_detalles.config(text=detalles)
        
        # Actualizar barra de progreso
        self.canvas_progreso.delete('all')
        ancho = self.canvas_progreso.winfo_width()
        progreso = (ancho * porcentaje) / 100
        
        color = 'green'
        if porcentaje < 20:
            color = 'red'
        elif porcentaje < 50:
            color = 'orange'
        
        self.canvas_progreso.create_rectangle(0, 0, progreso, 25, fill=color, outline='')
        self.canvas_progreso.create_text(ancho/2, 12, text=f"{porcentaje:.1f}% ({total_ml:.1f} ml)")
    
    def registrar_peso(self):
        """Registra un nuevo peso para el producto seleccionado"""
        seleccion = self.tree_inventario.selection()
        if not seleccion:
            messagebox.showerror("Error", "Seleccione un producto primero")
            return
            
        try:
            peso_total = float(self.entry_peso.get())
        except ValueError:
            messagebox.showerror("Error", "Ingrese un peso válido")
            return
            
        item = self.tree_inventario.item(seleccion[0])
        nombre = item['values'][0]
        
        # Obtener datos del producto
        query = "SELECT id, densidad, peso_envase, capacidad_ml FROM productos WHERE nombre = ?"
        producto = self.db.fetch_one(query, (nombre,))
        
        if not producto:
            messagebox.showerror("Error", "Producto no encontrado")
            return
            
        id_prod, densidad, peso_envase, capacidad = producto
        
        # Calcular volumen
        peso_licor = peso_total - peso_envase
        volumen_ml = peso_licor / densidad
        
        # Determinar tipo de movimiento
        if volumen_ml < 0:
            if not messagebox.askyesno("Advertencia", "El peso es menor que el envase vacío. ¿Registrar como ajuste?"):
                return
            tipo = "ajuste"
        else:
            # Verificar último registro para determinar si es entrada o salida
            ultimo_query = """
            SELECT cantidad_ml 
            FROM movimientos 
            WHERE producto_id = ? 
            ORDER BY fecha DESC 
            LIMIT 1
            """
            ultimo_ml = self.db.fetch_one(ultimo_query, (id_prod,))
            
            if ultimo_ml:
                diferencia = volumen_ml - ultimo_ml[0]
                tipo = "entrada" if diferencia > 0 else "salida"
            else:
                tipo = "entrada"  # Primer registro
        
        # Insertar movimiento
        query = """
        INSERT INTO movimientos (producto_id, user_id, tipo, cantidad_ml, peso_bruto, notas)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        notas = f"Registro manual. Peso total: {peso_total}g"
        self.db.execute_query(query, (id_prod, self.user_id, tipo, volumen_ml, peso_total, notas))
        
        # Actualizar interfaces
        self.actualizar_inventario()
        self.cargar_movimientos_recientes()
        self.mostrar_detalles_producto(None)
        
        # Mostrar confirmación
        messagebox.showinfo("Registro exitoso", 
                          f"Volumen registrado: {volumen_ml:.1f} ml\n"
                          f"Tipo de movimiento: {tipo}")
        
        # Limpiar campo de peso
        self.entry_peso.delete(0, 'end')
    
    def auto_completar_peso_vacio(self):
        """Autocompleta el campo de peso con el peso del envase vacío"""
        seleccion = self.tree_inventario.selection()
        if not seleccion:
            messagebox.showerror("Error", "Seleccione un producto primero")
            return
            
        item = self.tree_inventario.item(seleccion[0])
        nombre = item['values'][0]
        
        query = "SELECT peso_envase FROM productos WHERE nombre = ?"
        peso_envase = self.db.fetch_one(query, (nombre,))[0]
        
        self.entry_peso.delete(0, 'end')
        self.entry_peso.insert(0, str(peso_envase))
    
    def agregar_botella_completa(self):
        """Agrega una botella completa al inventario"""
        seleccion = self.tree_inventario.selection()
        if not seleccion:
            messagebox.showerror("Error", "Seleccione un producto primero")
            return
            
        item = self.tree_inventario.item(seleccion[0])
        nombre = item['values'][0]
        
        query = "SELECT id, capacidad_ml FROM productos WHERE nombre = ?"
        producto = self.db.fetch_one(query, (nombre,))
        
        if not producto:
            messagebox.showerror("Error", "Producto no encontrado")
            return
            
        id_prod, capacidad = producto
        
        # Actualizar contador de botellas
        query = "UPDATE productos SET botellas_completas = botellas_completas + 1 WHERE id = ?"
        self.db.execute_query(query, (id_prod,))
        
        # Registrar movimiento de entrada
        query = """
        INSERT INTO movimientos (producto_id, user_id, tipo, cantidad_ml, notas)
        VALUES (?, ?, ?, ?, ?)
        """
        self.db.execute_query(query, (id_prod, self.user_id, 'entrada', capacidad, 'Botella completa agregada'))
        
        # Actualizar interfaces
        self.actualizar_inventario()
        self.cargar_movimientos_recientes()
        
        messagebox.showinfo("Éxito", f"Botella completa de {nombre} agregada al inventario")
    
    def quitar_botella_completa(self):
        """Quita una botella completa del inventario"""
        seleccion = self.tree_inventario.selection()
        if not seleccion:
            messagebox.showerror("Error", "Seleccione un producto primero")
            return
            
        item = self.tree_inventario.item(seleccion[0])
        nombre = item['values'][0]
        botellas = item['values'][4]
        
        if botellas <= 0:
            messagebox.showerror("Error", "No hay botellas completas para quitar")
            return
            
        query = "SELECT id, capacidad_ml FROM productos WHERE nombre = ?"
        producto = self.db.fetch_one(query, (nombre,))
        
        if not producto:
            messagebox.showerror("Error", "Producto no encontrado")
            return
            
        id_prod, capacidad = producto
        
        # Actualizar contador de botellas
        query = "UPDATE productos SET botellas_completas = botellas_completas - 1 WHERE id = ?"
        self.db.execute_query(query, (id_prod,))
        
        # Registrar movimiento de salida
        query = """
        INSERT INTO movimientos (producto_id, user_id, tipo, cantidad_ml, notas)
        VALUES (?, ?, ?, ?, ?)
        """
        self.db.execute_query(query, (id_prod, self.user_id, 'salida', capacidad, 'Botella completa retirada'))
        
        # Actualizar interfaces
        self.actualizar_inventario()
        self.cargar_movimientos_recientes()
        
        messagebox.showinfo("Éxito", f"Botella completa de {nombre} retirada del inventario")
    
    def filtrar_movimientos(self, event=None):
        """Filtra los movimientos según los criterios seleccionados"""
        producto = self.combo_filtro_producto.get()
        tipo = self.combo_filtro_tipo.get()
        desde = self.entry_filtro_desde.get()
        hasta = self.entry_filtro_hasta.get()
        
        query = """
        SELECT m.fecha, p.nombre, m.tipo, m.cantidad_ml, m.notas, u.nombre 
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        JOIN usuarios u ON m.user_id = u.id
        WHERE 1=1
        """
        params = []
        
        if producto and producto != "Todos":
            query += " AND p.nombre = ?"
            params.append(producto)
            
        if tipo and tipo != "Todos":
            query += " AND m.tipo = ?"
            params.append(tipo.lower())
            
        if desde:
            try:
                datetime.strptime(desde, '%Y-%m-%d')
                query += " AND DATE(m.fecha) >= ?"
                params.append(desde)
            except ValueError:
                messagebox.showerror("Error", "Formato de fecha desde incorrecto (YYYY-MM-DD)")
                return
                
        if hasta:
            try:
                datetime.strptime(hasta, '%Y-%m-%d')
                query += " AND DATE(m.fecha) <= ?"
                params.append(hasta)
            except ValueError:
                messagebox.showerror("Error", "Formato de fecha hasta incorrecto (YYYY-MM-DD)")
                return
        
        # Filtro por local si no es admin
        if self.user_role != 'admin':
            query += " AND p.local_id = ?"
            params.append(self.local_id)
        
        query += " ORDER BY m.fecha DESC"
        
        movimientos = self.db.fetch_all(query, params)
        
        self.tree_movimientos.delete(*self.tree_movimientos.get_children())
        for mov in movimientos:
            self.tree_movimientos.insert('', 'end', values=mov)
    
    def exportar_movimientos_excel(self):
        """Exporta los movimientos filtrados a un archivo Excel"""
        # Obtener los datos actualmente mostrados en el Treeview
        items = self.tree_movimientos.get_children()
        datos = [self.tree_movimientos.item(item)['values'] for item in items]
        
        if not datos:
            messagebox.showerror("Error", "No hay datos para exportar")
            return
            
        # Crear DataFrame
        df = pd.DataFrame(datos, columns=['Fecha', 'Producto', 'Tipo', 'Cantidad (ml)', 'Notas', 'Usuario'])
        
        # Pedir ubicación para guardar
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title="Guardar movimientos como"
        )
        
        if not filepath:
            return
            
        try:
            df.to_excel(filepath, index=False)
            messagebox.showinfo("Éxito", f"Datos exportados a {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar: {str(e)}")
    
    def generar_reporte_consumo(self):
        """Genera el reporte de consumo para el producto seleccionado"""
        producto = self.combo_reporte_producto.get()
        periodo = self.combo_reporte_periodo.get()
        
        if not producto:
            return
            
        # Determinar fecha de inicio según el período seleccionado
        if periodo == '7 días':
            dias = 7
        elif periodo == '15 días':
            dias = 15
        elif periodo == '30 días':
            dias = 30
        elif periodo == '60 días':
            dias = 60
        elif periodo == '90 días':
            dias = 90
        else:
            dias = 30  # Por defecto
        
        fecha_inicio = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d')
        
        # Obtener datos del producto
        query = "SELECT id FROM productos WHERE nombre = ?"
        id_prod = self.db.fetch_one(query, (producto,))[0]
        
        # Obtener movimientos del período
        query = """
        SELECT DATE(fecha) as dia, 
               SUM(CASE WHEN tipo = 'entrada' THEN cantidad_ml ELSE 0 END) as entradas,
               SUM(CASE WHEN tipo = 'salida' THEN cantidad_ml ELSE 0 END) as salidas
        FROM movimientos
        WHERE producto_id = ? AND DATE(fecha) >= ?
        GROUP BY DATE(fecha)
        ORDER BY DATE(fecha)
        """
        datos = self.db.fetch_all(query, (id_prod, fecha_inicio))
        
        # Preparar datos para el gráfico
        fechas = [datetime.strptime(d[0], '%Y-%m-%d') for d in datos]
        entradas = [d[1] for d in datos]
        salidas = [-d[2] for d in datos]  # Negativo para mostrar hacia abajo
        
        # Crear gráfico
        self.ax_reportes.clear()
        
        if datos:
            self.ax_reportes.bar(fechas, entradas, color='green', label='Entradas')
            self.ax_reportes.bar(fechas, salidas, color='red', label='Salidas')
            
            # Línea de tendencia de consumo
            consumos = [e + s for e, s in zip(entradas, salidas)]
            self.ax_reportes.plot(fechas, consumos, color='blue', marker='o', linestyle='--', label='Consumo neto')
            
            self.ax_reportes.axhline(0, color='black', linewidth=0.5)
            self.ax_reportes.set_title(f'Consumo de {producto} - Últimos {dias} días')
            self.ax_reportes.set_xlabel('Fecha')
            self.ax_reportes.set_ylabel('Cantidad (ml)')
            self.ax_reportes.legend()
            self.ax_reportes.grid(True, linestyle='--', alpha=0.7)
            
            # Rotar fechas para mejor visualización
            plt.setp(self.ax_reportes.get_xticklabels(), rotation=45, ha='right')
            
            # Ajustar layout
            self.fig_reportes.tight_layout()
        
        self.canvas_reportes.draw()
    
    def exportar_grafico(self):
        """Exporta el gráfico actual a un archivo de imagen"""
        if not hasattr(self, 'fig_reportes'):
            messagebox.showerror("Error", "No hay gráfico para exportar")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
            title="Guardar gráfico como"
        )
        
        if not filepath:
            return
            
        try:
            self.fig_reportes.savefig(filepath, dpi=300, bbox_inches='tight')
            messagebox.showinfo("Éxito", f"Gráfico exportado a {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar: {str(e)}")
    
    def abrir_manual(self):
        """Abre el manual de usuario (puede ser un PDF o página web)"""
        try:
            webbrowser.open("https://ig_cal94@hotmail.com/manual-inventario-licores")
        except:
            messagebox.showinfo("Manual de Usuario", "El manual de usuario no está disponible actualmente.")
    
    def abrir_soporte(self):
        """Muestra la información de contacto de soporte técnico"""
        mensaje = (
            "Para soporte técnico, puede comunicarse con nosotros:\n\n"
            "📞 Teléfono: +506 8407-4148\n"
            "📞 WhatsApp: +506 8407-4148\n"
            "✉️ Correo: ig_cal94@hotmail.com"
        )
        messagebox.showinfo("Soporte Técnico", mensaje)
    
    def ver_actualizaciones(self):
        """Verifica si hay actualizaciones disponibles"""
        messagebox.showinfo("Actualizaciones", 
                          f"Estás utilizando la versión {VERSION}\n\n"
                          "Las actualizaciones se descargan automáticamente cuando están disponibles.")
    
    def show_page(self, page_name):
        """Muestra la página seleccionada"""
        for page in self.pages.values():
            page.pack_forget()
        
        self.pages[page_name].pack(fill='both', expand=True)
        self.current_page = page_name
        
        # Actualizar datos específicos de la página
        if page_name == 'inventario':
            self.actualizar_inventario()
        elif page_name == 'productos':
            self.actualizar_lista_productos()
        elif page_name == 'movimientos':
            self.cargar_movimientos_recientes()
        elif page_name == 'reportes':
            self.generar_reporte_consumo()
        elif page_name == 'admin_locales':
            self.actualizar_lista_locales()
        elif page_name == 'admin_usuarios':
            self.actualizar_lista_usuarios()
    
    def on_close(self):
        """Maneja el cierre de la aplicación"""
        self.db.close()
        self.root.destroy()

if __name__ == "__main__":
    # Configuración para alta resolución en Windows
    if sys.platform == "win32":
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    
    # Crear conexión a la base de datos
    db = LicorDB()
    
    # Crear ventana de login
    root_login = tk.Tk()
    login_app = LoginWindow(root_login, db)
    root_login.mainloop()