import os
from mutagen.flac import FLAC

# Replace with the exact path of one of your problematic FLAC files
FILE_PATH = r"C:\Users\cpetreccas\Music\Pruebas Sonometa c2\C. Dj Suze - 1\Double Dare feat Yvonne F. - I Believe (Club remix).flac"

def inspect_flac(file_path):
    if not os.path.exists(file_path):
        print(f"❌ Error: El archivo no existe en la ruta especificada:\n{file_path}")
        return

    print(f"\n==========================================")
    print(f"🔍 INSPECCIONANDO: {os.path.basename(file_path)}")
    print(f"==========================================\n")

    try:
        audio = FLAC(file_path)
        print("Etiquetas encontradas en el archivo FLAC:\n")

        found_any = False
        for key, value in audio.items():
            key_upper = str(key).upper()
            # Filtramos solo las etiquetas relevantes para la inspección
            if any(term in key_upper for term in ["RATING", "TRAKTOR", "POPM", "CUE", "STARS"]):
                print(f"  📌 [{key}] -> {value}")
                found_any = True

        if not found_any:
            print("⚠️ No se encontraron etiquetas relacionadas con Rating, Cues o Traktor.")
            print("\nListado completo de claves presentes:")
            for key in audio.keys():
                print(f"  • {key}")

    except Exception as e:
        print(f"❌ Error al abrir con Mutagen: {e}")

if __name__ == "__main__":
    inspect_flac(FILE_PATH)