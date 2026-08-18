import tkinter as tk
import customtkinter as ctk
from dialogs import DialogManager


class ToolPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#181818", height=28, corner_radius=0, **kwargs)
        self.app = master
        self.setup_custom_dark_menu()

    def setup_custom_dark_menu(self):
        app = self.app

        # Menús desplegables con lambdas para evaluación tardía
        self.menu_archivo = tk.Menu(
            app, tearoff=0, bg="#252526", fg="#FFFFFF",
            activebackground=app.CORP_COLOR, activeforeground="#FFFFFF",
            bd=1, relief="flat", font=('Segoe UI', 10)
        )
        self.menu_archivo.add_command(label="Seleccionar carpeta...  (Ctrl+O)", command=app.browse_folder)
        self.menu_archivo.add_command(label="Actualizar  (F5)", command=app.refresh_folder)
        self.menu_archivo.add_separator()
        self.menu_archivo.add_command(
            label="⚙ Configuración (Token Discogs)",
            command=lambda: DialogManager.show_settings_dialog(app, app.logger)
        )
        self.menu_archivo.add_separator()
        self.menu_archivo.add_command(label="Cerrar  (Ctrl+Q)", command=app.destroy)

        self.menu_acciones = tk.Menu(
            app, tearoff=0, bg="#252526", fg="#FFFFFF",
            activebackground=app.CORP_COLOR, activeforeground="#FFFFFF",
            bd=1, relief="flat", font=('Segoe UI', 10)
        )
        self.menu_acciones.add_command(
            label="Procesar con Discogs",
            command=lambda: app.process_manager.process_discogs_data()
        )
        self.menu_acciones.add_command(
            label="Seleccionar todo  (Ctrl+A)",
            command=lambda: app.grid_panel.select_all_rows()
        )
        self.menu_acciones.add_command(
            label="Buscar en la lista  (Ctrl+F)",
            command=lambda: app.search_manager.toggle_search_bar()
        )
        self.menu_acciones.add_separator()
        self.menu_acciones.add_command(
    label="Limpiar todo",
    command=lambda: app.process_manager.clear_all_loaded_metadata()
)

        self.menu_gestionar = tk.Menu(
            app, tearoff=0, bg="#252526", fg="#FFFFFF",
            activebackground=app.CORP_COLOR, activeforeground="#FFFFFF",
            bd=1, relief="flat", font=('Segoe UI', 10)
        )
        self.menu_gestionar.add_command(label="Géneros", command=lambda: DialogManager.open_catalog_manager(app, "Genre"))
        self.menu_gestionar.add_command(label="Álbumes", command=lambda: DialogManager.open_catalog_manager(app, "Album"))
        self.menu_gestionar.add_command(label="Etiquetas", command=lambda: DialogManager.open_catalog_manager(app, "Publisher"))

        self.menu_ayuda = tk.Menu(
            app, tearoff=0, bg="#252526", fg="#FFFFFF",
            activebackground=app.CORP_COLOR, activeforeground="#FFFFFF",
            bd=1, relief="flat", font=('Segoe UI', 10)
        )
        self.menu_ayuda.add_command(label="Atajos de teclado", command=lambda: DialogManager.show_keyboard_shortcuts_dialog(app))
        self.menu_ayuda.add_command(label="Ver logs", command=lambda: DialogManager.show_logs_dialog(app))
        self.menu_ayuda.add_separator()
        self.menu_ayuda.add_command(label="Acerca de Sonometa", command=lambda: DialogManager.show_about_dialog(app))

        def create_menu_btn(text, menu_widget):
            btn = ctk.CTkButton(
                self,
                text=text,
                width=65,
                height=24,
                fg_color="transparent",
                hover_color="#2A2D32",
                text_color="#E0E0E0",
                font=ctk.CTkFont(family="Inter", size=13)
            )
            btn.configure(command=lambda: menu_widget.post(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height()))
            btn.pack(side="left", padx=2, pady=2)

        create_menu_btn("Archivo", self.menu_archivo)
        create_menu_btn("Acciones", self.menu_acciones)
        create_menu_btn("Gestionar", self.menu_gestionar)
        create_menu_btn("Ayuda", self.menu_ayuda)