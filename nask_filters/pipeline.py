# my_filters/pipeline.py
import logging
from openedx_filters import PipelineStep

log = logging.getLogger(__name__)

class ModifyUsername(PipelineStep):
    """
    My custom step to modify usernames.
    """
    def run_filter(self, form_data, *args, **kwargs):
        username = form_data.get("username")
        log.info(f"Triggered custom filter for: {username}")
        
        # Your logic here
        form_data["username"] = f"{username}-custom"
        
        return {"form_data": form_data}