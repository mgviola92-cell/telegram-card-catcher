"""One bounded cleanup pass for temporary Telegram replay records.

Run only on demand or in a separately approved low-frequency schedule.
No polling loop, no owned card/character deletion, and no automatic startup run.
"""
import json
from app.storage import prune_counted_messages
from app.webhook_guard import prune_updates

def cleanup():
    counted=prune_counted_messages(days=7,batch_size=1000)
    updates=prune_updates()
    return {'counted_messages_removed':counted,'processed_updates_removed':updates}

if __name__=='__main__':
    print(json.dumps(cleanup()))
