from celery import Celery

# Configure connection broker matching settings
broker_url = "amqp://guest:guest@localhost:5672//"
celery_app = Celery("gitty-worker", broker=broker_url)

# Trigger indexing task
repository_id = "test-repo"
repo_url = "https://github.com/pallets/flask.git"

print(f"Triggering ingestion for {repository_id} ({repo_url})...")
celery_app.send_task("gitty.tasks.index_repository", args=[repository_id, repo_url])
print("Task sent to queue successfully!")
