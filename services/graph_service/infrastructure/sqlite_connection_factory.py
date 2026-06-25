import sqlite3

class SQLiteConnectionFactory:
    def __init__(self, db_path: str = "gitty_graph.db"):
        self.db_path = db_path

    def create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
