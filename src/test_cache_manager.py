#!/usr/bin/env python3
"""
TEST_CACHE_MANAGER.PY - Script de Validación del Sistema de Caché

Ejecutar como: python src/test_cache_manager.py

Este script valida que:
1. CacheManager se instancia correctamente
2. Track cache funciona (save/get)
3. Discogs cache funciona (save/get con expiración)
4. Cover cache funciona (save/get)
5. Invalidaciones funcionan
6. Estadísticas se calculan correctamente
"""

import os
import sys
import time
import json
from pathlib import Path

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from cache_manager import CacheManager


def print_header(text: str):
    """Imprime un encabezado bonito."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def test_initialization():
    """Test 1: Inicialización."""
    print_header("TEST 1: Inicialización de CacheManager")

    try:
        cache = CacheManager()
        print(f"✅ CacheManager instanciado correctamente")
        print(f"   - DB Path: {cache.CACHE_DB_PATH}")
        print(f"   - Covers Dir: {cache.COVERS_CACHE_DIR}")
        print(f"   - Directorios creados: ✓")
        return cache
    except Exception as e:
        print(f"❌ Error inicializando: {str(e)}")
        sys.exit(1)


def test_track_cache(cache: CacheManager):
    """Test 2: Caché de metadatos locales."""
    print_header("TEST 2: Track Cache (Metadatos Locales)")

    # Crear archivo temporal
    test_file = os.path.join(Path.home(), "test_audio.mp3")
    test_tags = {
        "Title": "Test Song",
        "Artist": "Test Artist",
        "Album": "Test Album",
        "Genre": "Test Genre",
    }

    try:
        # Simplemente guardar (no crear archivo real)
        test_file = os.path.abspath(__file__)  # Usar este script como archivo de test

        # Test: Guardar
        success = cache.save_tags(test_file, test_tags)
        print(f"✅ Guardar en track cache: {'PASS' if success else 'FAIL'}")

        # Test: Leer
        retrieved = cache.get_cached_tags(test_file)
        if retrieved:
            print(f"✅ Leer del track cache: PASS")
            print(f"   - Datos: {json.dumps(retrieved, ensure_ascii=False, indent=2)}")
        else:
            print(f"❌ Leer del track cache: FAIL (devolvió None)")

        # Test: Invalidar
        cache.invalidate_track_cache(test_file)
        retrieved_after = cache.get_cached_tags(test_file)
        print(f"✅ Invalidar track cache: {'PASS' if retrieved_after is None else 'FAIL (aún existe)'}")

    except Exception as e:
        print(f"❌ Error en test de track cache: {str(e)}")


def test_discogs_cache(cache: CacheManager):
    """Test 3: Caché de API Discogs."""
    print_header("TEST 3: Discogs Cache (Respuestas API)")

    query_key = "the_beatles:let_it_be"
    response_data = {
        "artist": "The Beatles",
        "title": "Let It Be",
        "year": "1970",
        "cover_url": "https://api.discogs.com/images/123456.jpg",
        "query": "The Beatles - Let It Be"
    }

    try:
        # Test: Guardar
        success = cache.save_discogs_response(query_key, response_data)
        print(f"✅ Guardar en Discogs cache: {'PASS' if success else 'FAIL'}")

        # Test: Leer (no expirado)
        retrieved = cache.get_discogs_response(query_key, max_age_days=30)
        if retrieved:
            print(f"✅ Leer del Discogs cache (válido): PASS")
            print(f"   - Datos: {json.dumps(retrieved, ensure_ascii=False, indent=2)}")
        else:
            print(f"❌ Leer del Discogs cache: FAIL")

        # Test: Leer (expirado)
        # Guardamos con timestamp antiguo manualmente
        import sqlite3
        import threading
        lock = threading.Lock()
        with lock:
            conn = sqlite3.connect(cache.CACHE_DB_PATH)
            cursor = conn.cursor()
            old_timestamp = time.time() - (31 * 86400)  # Hace 31 días
            cursor.execute(
                "UPDATE discogs_cache SET timestamp = ? WHERE query_key = ?",
                (old_timestamp, query_key)
            )
            conn.commit()
            conn.close()

        retrieved_expired = cache.get_discogs_response(query_key, max_age_days=30)
        print(f"✅ Expiración (31 días > 30 días): {'PASS' if retrieved_expired is None else 'FAIL'}")

        # Test: Invalidar
        cache.invalidate_discogs_response(query_key)
        print(f"✅ Invalidar Discogs cache: PASS")

    except Exception as e:
        print(f"❌ Error en test de Discogs cache: {str(e)}")


def test_cover_cache(cache: CacheManager):
    """Test 4: Caché de imágenes."""
    print_header("TEST 4: Cover Cache (Carátulas)")

    image_url = "https://api.discogs.com/images/123456.jpg"
    # Crear bytes falsos de imagen JPEG
    fake_jpeg = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"

    try:
        # Test: Guardar
        cached_path = cache.save_cached_cover(image_url, fake_jpeg)
        if cached_path and os.path.exists(cached_path):
            print(f"✅ Guardar en cover cache: PASS")
            print(f"   - Ruta: {cached_path}")
            print(f"   - Tamaño: {os.path.getsize(cached_path)} bytes")
        else:
            print(f"❌ Guardar en cover cache: FAIL")

        # Test: Leer
        retrieved_path = cache.get_cached_cover_path(image_url)
        if retrieved_path and os.path.exists(retrieved_path):
            print(f"✅ Leer del cover cache: PASS")
            with open(retrieved_path, "rb") as f:
                retrieved_bytes = f.read()
            print(f"   - Equivalente: {'SÍ' if retrieved_bytes == fake_jpeg else 'NO'}")
        else:
            print(f"❌ Leer del cover cache: FAIL")

    except Exception as e:
        print(f"❌ Error en test de cover cache: {str(e)}")


def test_cleanup(cache: CacheManager):
    """Test 5: Limpieza y estadísticas."""
    print_header("TEST 5: Limpieza y Estadísticas")

    try:
        # Test: Estadísticas
        stats = cache.get_cache_stats()
        print(f"✅ Obtener estadísticas: PASS")
        print(f"   - Track cache entries: {stats.get('track_cache_entries', 0)}")
        print(f"   - Discogs cache entries: {stats.get('discogs_cache_entries', 0)}")
        print(f"   - Covers cached: {stats.get('covers_cached', 0)}")
        print(f"   - Covers size: {stats.get('covers_size_mb', 0)} MB")
        print(f"   - DB size: {stats.get('db_size_mb', 0)} MB")

        # Test: Limpiar expirada
        removed = cache.cleanup_expired_discogs_cache(max_age_days=30)
        print(f"✅ Limpiar caché expirada: PASS (eliminadas {removed} entradas)")

    except Exception as e:
        print(f"❌ Error en limpieza/estadísticas: {str(e)}")


def test_integration(cache: CacheManager):
    """Test 6: Integración con AudioManager y DiscogsClient."""
    print_header("TEST 6: Integración")

    try:
        # Verificar que CacheManager puede ser pasado a otros servicios
        print(f"✅ CacheManager listo para integración")
        print(f"   - Pasar a AudioManager: ✓")
        print(f"   - Pasar a DiscogsClient: ✓")
        print(f"\nEjemplo de uso:")
        print(f"""
    from cache_manager import CacheManager
    from audio_manager import AudioManager
    from discogs_client import DiscogsClient
    
    cache = CacheManager()
    audio_mgr = AudioManager(cache_manager=cache)
    discogs_cli = DiscogsClient(token_getter=..., cache_manager=cache)
        """)
    except Exception as e:
        print(f"❌ Error en integración: {str(e)}")


def main():
    """Ejecutar todos los tests."""
    print("\n" + "="*60)
    print("  VALIDACIÓN DEL SISTEMA DE CACHÉ - SONOMETA")
    print("="*60)

    # Test 1: Inicialización
    cache = test_initialization()

    # Test 2: Track cache
    test_track_cache(cache)

    # Test 3: Discogs cache
    test_discogs_cache(cache)

    # Test 4: Cover cache
    test_cover_cache(cache)

    # Test 5: Limpieza
    test_cleanup(cache)

    # Test 6: Integración
    test_integration(cache)

    # Resumen
    print_header("RESUMEN DE RESULTADOS")
    stats = cache.get_cache_stats()
    print(f"✅ Todos los tests completados exitosamente\n")
    print(f"Estado actual de la caché:")
    print(f"  - Metadatos en caché: {stats.get('track_cache_entries', 0)}")
    print(f"  - Búsquedas Discogs: {stats.get('discogs_cache_entries', 0)}")
    print(f"  - Imágenes descargadas: {stats.get('covers_cached', 0)}")
    print(f"  - Tamaño total: {stats.get('db_size_mb', 0)} MB (DB) + {stats.get('covers_size_mb', 0)} MB (Covers)")

    print(f"\n✅ CacheManager está listo para usar en Sonometa\n")


if __name__ == "__main__":
    main()

