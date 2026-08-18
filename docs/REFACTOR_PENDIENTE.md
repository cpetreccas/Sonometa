# Propuesta de Refactorización - Sonometa (`gui.py`)

Esta propuesta analiza la redistribución de métodos de la clase `App` en `gui.py` para eliminar la sobrecarga de responsabilidades (*God Object*) y aplicar los principios **SOLID** (Responsabilidad Única e Inversión de Dependencias).

---

## 1. Redistribución hacia Clases Existentes

Para reducir métodos puente (*wrappers*) y delegar la lógica donde corresponde, se reubicarán los siguientes métodos en las clases ya creadas:

### **`DetailPanel`** (`detail_panel.py`)
Encargada de la interacción con el panel lateral, el estado de la selección visual y la manipulación de carátulas asociadas.
* `on_row_select`
* `paste_cover_from_clipboard`
* `remove_cover_art`
* `_strip_cover_tags`
* `display_cover_art`

### **`GridPanel`** (`grid_panel.py`)
Encargada de la manipulación, filtrado, ordenación y representación visual de la tabla (`Treeview`).
* `sort_by_column`
* `_sync_all_tree_items`
* `_retag_visible_rows`
* `apply_search_filter`
* `select_all_rows`
* `_build_row_search_text`

### **`CatalogManager`** (`catalog_manager.py`)
Se eliminan los métodos *pass-through* en `App`. Los componentes llamarán directamente a la instancia de `CatalogManager`.
* `load_catalog_values`
* `normalize_catalog_text`
* `save_catalog_values`
* `add_catalog_value`
* `get_catalog_combo_values`
* `get_catalog_column_info`
* `apply_catalog_value_change`
* `rename_catalog_value`

### **`AudioManager`** (`audio_manager.py`)
Encargada exclusivamente de la lectura, modificación y persistencia de etiquetas en archivos físicos.
* `clear_audio_file_metadata`
* `save_single_tag`
* `normalize_cover_image_bytes`

---

## 2. Creación de Nuevas Clases (Recomendado)

Para evitar recargar la clase principal con controladores de eventos y lógica pesada de proceso, se propone la creación de 3 nuevos módulos:

### **`MenuBarManager`** (`menu_bar.py`)
Encapsula la creación y gestión de la barra de menú superior y sus callbacks principales.
* `setup_custom_dark_menu`
* `browse_folder`
* `refresh_folder`
* `clear_all`

### **`SearchManager`** (`search_manager.py`)
Encapsula la interfaz de la barra de búsqueda y sus eventos asociados.
* `setup_search_bar`
* `toggle_search_bar`
* `show_search_bar`
* `hide_search_bar`
* `on_escape_pressed`
* `_on_search_text_changed`

### **`MetadataProcessor`** (`metadata_processor.py`)
Aísla la lógica de negocio compleja para el procesamiento de archivos, consultas a Discogs y limpiado masivo.
* `process_discogs_data`
* `build_discogs_query`
* `clear_metadata_for_rows`
* `clear_selected_metadata`
* `clear_all_loaded_metadata`

---

## 3. Estado Final de `gui.py` (`App`)

Tras la refactorización, `App` quedará únicamente como el **orquestador principal** del sistema:
* Inicialización del ciclo de vida de la aplicación (`__init__`).
* Instanciación y enlace entre componentes (`DetailPanel`, `GridPanel`, `CatalogManager`, etc.).
* Gestión del arranque y cierre de la aplicación (`load_audio_files`, `on_close`).