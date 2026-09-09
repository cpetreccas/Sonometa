def build_column_index(columns):
    """Construye un indice {columna: posicion} para accesos O(1)."""
    return {str(col): idx for idx, col in enumerate(columns)}


def get_row_value(values, col_index_map, col_name, default=""):
    """Obtiene valor por nombre de columna de forma segura."""
    idx = col_index_map.get(col_name)
    if idx is None or idx >= len(values):
        return default

    value = values[idx]
    return default if value is None else value


def set_row_value(values, col_index_map, col_name, new_value):
    """Asigna valor por nombre de columna; devuelve False si no aplica."""
    idx = col_index_map.get(col_name)
    if idx is None or idx >= len(values):
        return False

    values[idx] = new_value
    return True


def map_row_values(values, columns):
    """Mapea una tupla/lista de valores a dict por nombre de columna."""
    return {
        col_name: values[idx] if idx < len(values) else ""
        for idx, col_name in enumerate(columns)
    }


def build_row_values(metadata, columns, current_values=None):
    """Compone la tupla final de fila respetando orden de columnas."""
    current_values = current_values or []
    current_map = map_row_values(current_values, columns)
    return tuple(metadata.get(col, current_map.get(col, "")) for col in columns)

