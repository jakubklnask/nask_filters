import logging
from django.apps import AppConfig
import sys # Dodajemy sys do printowania na stdout

log = logging.getLogger(__name__)

class NaskFiltersConfig(AppConfig):
    name = "nask_filters"
    verbose_name = "Nask Specific Filters"

    def ready(self):
        try:
            import nask_filters.signals
            print("!!! NASK FILTERS: Signals zaimportowane poprawnie !!!", file=sys.stderr)
        except Exception as e:
            print(f"!!! NASK FILTERS: BŁĄD importu signals: {e} !!!", file=sys.stderr)  