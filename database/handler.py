import sqlite3
import os
import threading

class DatabaseHandler:
    """
    Manages the local SQLite database for storing download history and client data.
    This class is thread-safe, ensuring each thread gets its own connection.
    """
    def __init__(self, db_name="download_history.db"):
        self.db_path = db_name
        self.thread_local = threading.local()
        # Create tables using the connection for the main thread initially.
        self.create_tables()

    @property
    def _connection(self):
        """
        Returns a thread-local database connection.
        If a connection doesn't exist for the current thread, it creates one.
        """
        if not hasattr(self.thread_local, 'conn'):
            self.thread_local.conn = sqlite3.connect(self.db_path)
        return self.thread_local.conn

    def create_tables(self):
        """Create necessary tables if they don't exist."""
        cursor = self._connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                category TEXT NOT NULL,
                url TEXT,
                download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(filename, category)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                client_id INTEGER PRIMARY KEY,
                client_name TEXT NOT NULL
            )
        ''')
        self._connection.commit()

    def sync_clients(self, clients_data):
        """Insert or update client information."""
        if not clients_data:
            return
        cursor = self._connection.cursor()
        client_tuples = [(client['id'], client['name']) for client in clients_data]
        cursor.executemany("INSERT OR REPLACE INTO clients (client_id, client_name) VALUES (?, ?)", client_tuples)
        self._connection.commit()
        
    def get_client_name(self, client_id):
        """Retrieve a client's name by their ID."""
        cursor = self._connection.cursor()
        cursor.execute("SELECT client_name FROM clients WHERE client_id = ?", (client_id,))
        result = cursor.fetchone()
        return result[0] if result else f"Unknown Client ({client_id})"

    def is_already_downloaded(self, filename, category):
        """Check if a file has already been recorded in the history."""
        cursor = self._connection.cursor()
        cursor.execute("SELECT 1 FROM download_history WHERE filename = ? AND category = ?", (filename, category))
        return cursor.fetchone() is not None

    def add_download_record(self, filename, category, url):
        """Add a new record to the download history."""
        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "INSERT INTO download_history (filename, category, url) VALUES (?, ?, ?)",
                (filename, category, url)
            )
            self._connection.commit()
        except sqlite3.IntegrityError:
            # This can happen in rare race conditions with threads, it's safe to ignore.
            pass

    def clear_history(self):
        """Clear all records from the download history table."""
        cursor = self._connection.cursor()
        cursor.execute("DELETE FROM download_history")
        self._connection.commit()

    def close(self):
        """Close the database connection for the current thread."""
        if hasattr(self.thread_local, 'conn'):
            self.thread_local.conn.close()

