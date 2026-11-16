from django.apps import AppConfig
from django.conf import settings
import os


class Proprint3DConfig(AppConfig):
    name = 'proprint3d'

    def ready(self):
        """Crea index.html con redirección segura en carpetas de media para evitar errores 403 de Nginx."""
        redirect_html = '<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0; url=/"><meta name="robots" content="noindex, follow"></head><body><script>window.location.replace("/");</script></body></html>'
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if media_root and os.path.exists(media_root):
            try:
                for target_dir in [str(media_root), os.path.join(str(media_root), 'products')]:
                    if os.path.exists(target_dir):
                        idx_file = os.path.join(target_dir, 'index.html')
                        if not os.path.exists(idx_file):
                            with open(idx_file, 'w', encoding='utf-8') as f:
                                f.write(redirect_html)
            except Exception:
                pass

