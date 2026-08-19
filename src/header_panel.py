import customtkinter as ctk

class HeaderPanel(ctk.CTkFrame):
    def __init__(self, parent, app, logo_pil):
        super().__init__(parent)
        self.app = app

        # Configuración del frame
        self.pack(fill="x", padx=15, pady=(5, 5))

        # Logo principal
        if logo_pil:
            # Mantiene la proporción original de logo_completo.png para que no se deforme
            orig_w, orig_h = logo_pil.size
            target_height = 36
            target_width = int(orig_w * (target_height / orig_h))

            header_logo = ctk.CTkImage(
                light_image=logo_pil,
                dark_image=logo_pil,
                size=(target_width, target_height)
            )

            lbl_logo = ctk.CTkLabel(self, image=header_logo, text="")
            lbl_logo.pack(side="left", padx=(10, 20))

        # Botón Seleccionar Carpeta
        self.btn_browse = ctk.CTkButton(
            self,
            text="📁 Seleccionar Carpeta",
            fg_color=self.app.CORP_COLOR,
            hover_color=self.app.CORP_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            command=self.app.browse_folder
        )
        self.btn_browse.pack(side="left", padx=5, pady=5)

        # Botón Actualizar
        self.btn_refresh = ctk.CTkButton(
            self,
            text="🔄 Actualizar",
            width=100,
            fg_color=self.app.CORP_COLOR,
            hover_color=self.app.CORP_HOVER,
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            height=32,
            command=self.app.refresh_folder
        )
        self.btn_refresh.pack(side="left", padx=5, pady=5)

        # Etiqueta con la ruta actual
        self.label_folder = ctk.CTkLabel(
            self,
            text="Ninguna carpeta seleccionada",
            text_color="gray"
        )
        self.label_folder.pack(side="left", padx=10, pady=5)

    def set_folder_path(self, path):
        """Actualiza la ruta mostrada en la etiqueta del header."""
        if path:
            self.label_folder.configure(text=path, text_color="white")
        else:
            self.label_folder.configure(text="Ninguna carpeta seleccionada", text_color="gray")