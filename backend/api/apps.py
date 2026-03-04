from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        """Pre-load the FAISS index when Django starts."""
        import threading

        def _preload():
            try:
                from rag import get_pipeline
                get_pipeline()
            except Exception as e:
                import logging
                logging.getLogger("api").warning("RAG preload failed: %s", e)

        t = threading.Thread(target=_preload, daemon=True)
        t.start()
