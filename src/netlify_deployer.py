import os
import requests

class NetlifyDeployer:
    """Maneja la integración HTTP con la API REST de Netlify."""

    API_BASE_URL = "https://api.netlify.com/api/v1"

    def __init__(self, site_id=None, auth_token=None):
        self.auth_token = auth_token or os.getenv("NETLIFY_AUTH_TOKEN")
        self.site_id = site_id or os.getenv("NETLIFY_SITE_ID")

        self.last_error = ""
        self.last_status_code = None
        self.enabled = False

    def deploy_zip(self, zip_buffer):
        """Envia los bytes del archivo ZIP empaquetado a Netlify.

        Retorna:
            - str: URL publica del deploy (si Netlify la devuelve)
            - True: deploy correcto sin URL en payload
            - False: error (detalle en self.last_error)
        """
        self.last_error = ""
        self.last_status_code = None

        if not self.enabled:
            self.last_error = (
                "Despliegue directo a Netlify desactivado (migración Fase 2). "
                "La WebApp/PWA se despliega por pipeline independiente conectado a Supabase."
            )
            return False

        if not self.site_id or not self.auth_token:
            self.last_error = "Faltan NETLIFY_SITE_ID o NETLIFY_AUTH_TOKEN en variables de entorno."
            return False

        url = f"{self.API_BASE_URL}/sites/{self.site_id}/deploys"
        headers = {
            "Content-Type": "application/zip",
            "Authorization": f"Bearer {self.auth_token}"
        }

        try:
            if hasattr(zip_buffer, "seek"):
                zip_buffer.seek(0)

            response = requests.post(
                url,
                headers=headers,
                data=zip_buffer.getvalue(),
                timeout=30
            )
            self.last_status_code = response.status_code

            if response.status_code in (200, 201):
                try:
                    res_json = response.json()
                except ValueError:
                    res_json = {}

                deploy_url = res_json.get("ssl_url") or res_json.get("url")
                return deploy_url if deploy_url else True

            response_text = (response.text or "").strip()
            self.last_error = f"Netlify devolvio el codigo {response.status_code}."
            if response_text:
                self.last_error += f"\n{response_text}"
            return False

        except requests.RequestException as e:
            self.last_error = f"Fallo de conexion con Netlify: {str(e)}"
            return False