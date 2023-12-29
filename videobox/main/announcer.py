import queue

close_message = object()

class MessageAnnouncer(object):
    """
    Server-sent events in Flask without extra dependencies.
    See https://maxhalford.github.io/blog/flask-sse-no-deps/
    """

    def __init__(self):
        self.listeners = []

    def listen(self):
        q = queue.Queue(maxsize=5)
        self.listeners.append(q)
        return q

    def format_sse(self, data, event=None):
        msg = f'data: {data}\n\n'
        if event:
            msg = f'event: {event}\n{msg}'
        return msg

    def close(self):
        self.announce(close_message)

    def is_close_message(self, msg):
        return msg is close_message

    def announce(self, msg):
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except queue.Full:
                del self.listeners[i]

announcer = MessageAnnouncer()