from app.queue import InMemoryEventQueue
from app.worker import EventWorker, process_event


def test_worker_processes_queue_events():
    queue = InMemoryEventQueue()
    queue.publish("post.published", {"post_id": "abc"})

    worker = EventWorker(queue=queue, callback=process_event)
    worker.start()

    # allow the worker thread to consume the item
    import time

    time.sleep(0.5)
    worker.stop()

    assert queue.read(limit=10) == []
