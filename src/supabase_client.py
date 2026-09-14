import os
import logging
from typing import Optional, Dict, Any, List
from supabase import create_client, Client

logger = logging.getLogger("Sonometa")

# Se pueden cargar desde settings.json o variables de entorno
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://iwgpfqnyhjewuufrqali.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml3Z3BmcW55aGpld3V1ZnJxYWxpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkzMjcxNzAsImV4cCI6MjEwNDkwMzE3MH0.3cHCKKVaqrU2-NhKHFzNU7-SuFRIjWhv3h0by8hQOdE")

class SupabaseClientManager:
    """Gestiona la autenticación y las peticiones a Supabase Cloud."""

    def __init__(self):
        self.client: Optional[Client] = None
        self.user = None
        self.session = None
        self.last_upsert_status_code: Optional[int] = None
        self._init_client()

    def _init_client(self):
        try:
            if SUPABASE_URL and SUPABASE_KEY:
                self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            logger.error(f"Error al inicializar cliente Supabase: {e}")

    def is_authenticated(self) -> bool:
        return self.user is not None

    def login(self, email: str, password: str) -> bool:
        """Inicia sesión en la plataforma cloud."""
        if not self.client:
            return False
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            self.user = response.user
            self.session = response.session
            logger.info(f"Sesión iniciada en Supabase: {self.user.email}")
            return True
        except Exception as e:
            logger.error(f"Error en login Supabase: {e}")
            return False

    def get_user_id(self) -> Optional[str]:
        return self.user.id if self.user else None

    def upload_storage_file(self, bucket: str, destination_path: str, file_bytes: bytes, content_type: str = "image/jpeg") -> Optional[str]:
        """Subes portadas o audios preview a Supabase Storage y retorna la URL pública."""
        if not self.client:
            return None
        try:
            # Subir o reemplazar archivo en el bucket
            self.client.storage.from_(bucket).upload(
                path=destination_path,
                file=file_bytes,
                file_options={"content-type": content_type, "x-upsert": "true"}
            )
            # Obtener URL pública
            public_url = self.client.storage.from_(bucket).get_public_url(destination_path)
            return public_url
        except Exception as e:
            logger.error(f"Error subiendo archivo a Storage ({bucket}/{destination_path}): {e}")
            return None

    def upsert_tracks_batch(self, tracks_data: List[Dict[str, Any]]) -> bool:
        """Envía un lote de canciones a PostgreSQL mediante un UPSERT."""
        self.last_upsert_status_code = None
        if not self.client or not tracks_data:
            return False
        try:
            # Upsert usando la restricción única (user_id, filepath_local)
            response = self.client.table("tracks").upsert(
                tracks_data,
                on_conflict="user_id, filepath_local"
            ).execute()
            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, int):
                self.last_upsert_status_code = status_code
                return status_code in (200, 201)
            return True
        except Exception as e:
            logger.error(f"Error en upsert masivo de tracks: {e}")
            return False