from datetime import datetime, timezone
import uuid

class DomainEvent:
    def __init__(self):
        self.event_id = str(uuid.uuid4())
        self.occurred_on = datetime.now(timezone.utc)
