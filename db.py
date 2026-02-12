import sqlite3
from datetime import datetime

import config


def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT,
            caption TEXT,
            video_filename TEXT,
            album_id INTEGER REFERENCES albums(id) ON DELETE SET NULL,
            hidden INTEGER NOT NULL DEFAULT 0,
            taken_at TIMESTAMP,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Migrate: add hidden column if missing
    cols = [r[1] for r in conn.execute("PRAGMA table_info(photos)").fetchall()]
    if "hidden" not in cols:
        conn.execute("ALTER TABLE photos ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


# --- Albums ---

def create_album(name):
    conn = get_db()
    cursor = conn.execute("INSERT INTO albums (name) VALUES (?)", (name,))
    album_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return album_id


def get_albums():
    conn = get_db()
    albums = conn.execute("""
        SELECT a.*, COUNT(p.id) AS photo_count,
               (SELECT p2.filename FROM photos p2 WHERE p2.album_id = a.id
                ORDER BY p2.uploaded_at DESC LIMIT 1) AS cover_filename
        FROM albums a
        LEFT JOIN photos p ON p.album_id = a.id
        GROUP BY a.id
        ORDER BY a.created_at DESC
    """).fetchall()
    conn.close()
    return albums


def get_album(album_id):
    conn = get_db()
    album = conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)).fetchone()
    conn.close()
    return album


def rename_album(album_id, name):
    conn = get_db()
    conn.execute("UPDATE albums SET name = ? WHERE id = ?", (name, album_id))
    conn.commit()
    conn.close()


def delete_album(album_id, delete_photos=False):
    conn = get_db()
    files = []
    if delete_photos:
        rows = conn.execute(
            "SELECT filename, video_filename FROM photos WHERE album_id = ?", (album_id,)
        ).fetchall()
        files = [(r["filename"], r["video_filename"]) for r in rows]
        conn.execute("DELETE FROM photos WHERE album_id = ?", (album_id,))
    else:
        conn.execute("UPDATE photos SET album_id = NULL WHERE album_id = ?", (album_id,))
    conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
    conn.commit()
    conn.close()
    return files


# --- Photos ---

def add_photo(filename, original_name, caption, album_id, taken_at, video_filename=None, hidden=False):
    conn = get_db()
    conn.execute(
        """INSERT INTO photos (filename, original_name, caption, album_id, taken_at, video_filename, hidden)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (filename, original_name, caption or None, album_id or None, taken_at, video_filename, int(hidden)),
    )
    conn.commit()
    conn.close()


def add_photos_batch(photos):
    """Insert multiple photos in a single transaction.
    photos: list of (filename, original_name, caption, album_id, taken_at, video_filename, hidden)
    """
    conn = get_db()
    conn.executemany(
        """INSERT INTO photos (filename, original_name, caption, album_id, taken_at, video_filename, hidden)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        photos,
    )
    conn.commit()
    conn.close()


def get_photos(album_id=None, page=1, per_page=40, feed_only=False):
    conn = get_db()
    offset = (page - 1) * per_page

    if album_id:
        photos = conn.execute(
            """SELECT p.*, a.name AS album_name FROM photos p
               LEFT JOIN albums a ON a.id = p.album_id
               WHERE p.album_id = ?
               ORDER BY COALESCE(p.taken_at, p.uploaded_at) DESC
               LIMIT ? OFFSET ?""",
            (album_id, per_page, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM photos WHERE album_id = ?", (album_id,)
        ).fetchone()[0]
    elif feed_only:
        photos = conn.execute(
            """SELECT p.*, a.name AS album_name FROM photos p
               LEFT JOIN albums a ON a.id = p.album_id
               WHERE p.hidden = 0
               ORDER BY COALESCE(p.taken_at, p.uploaded_at) DESC
               LIMIT ? OFFSET ?""",
            (per_page, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM photos WHERE hidden = 0").fetchone()[0]
    else:
        photos = conn.execute(
            """SELECT p.*, a.name AS album_name FROM photos p
               LEFT JOIN albums a ON a.id = p.album_id
               ORDER BY COALESCE(p.taken_at, p.uploaded_at) DESC
               LIMIT ? OFFSET ?""",
            (per_page, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]

    conn.close()
    return photos, total


def get_photo(photo_id):
    conn = get_db()
    photo = conn.execute(
        """SELECT p.*, a.name AS album_name FROM photos p
           LEFT JOIN albums a ON a.id = p.album_id
           WHERE p.id = ?""",
        (photo_id,),
    ).fetchone()
    conn.close()
    return photo


def get_all_photos(unassigned_only=False):
    conn = get_db()
    if unassigned_only:
        photos = conn.execute(
            """SELECT p.*, a.name AS album_name FROM photos p
               LEFT JOIN albums a ON a.id = p.album_id
               WHERE p.album_id IS NULL
               ORDER BY COALESCE(p.taken_at, p.uploaded_at) DESC"""
        ).fetchall()
    else:
        photos = conn.execute(
            """SELECT p.*, a.name AS album_name FROM photos p
               LEFT JOIN albums a ON a.id = p.album_id
               ORDER BY COALESCE(p.taken_at, p.uploaded_at) DESC"""
        ).fetchall()
    conn.close()
    return photos


def bulk_assign_album(photo_ids, album_id):
    conn = get_db()
    for pid in photo_ids:
        conn.execute("UPDATE photos SET album_id = ? WHERE id = ?", (album_id, pid))
    conn.commit()
    conn.close()


def update_photo_album(photo_id, album_id):
    conn = get_db()
    conn.execute(
        "UPDATE photos SET album_id = ? WHERE id = ?",
        (album_id or None, photo_id),
    )
    conn.commit()
    conn.close()


def delete_photo(photo_id):
    conn = get_db()
    photo = conn.execute("SELECT filename, video_filename FROM photos WHERE id = ?", (photo_id,)).fetchone()
    conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    conn.commit()
    conn.close()
    if photo:
        return photo["filename"], photo["video_filename"]
    return None, None


def delete_photos_bulk(photo_ids):
    """Delete multiple photos, return list of (filename, video_filename) for file cleanup."""
    conn = get_db()
    placeholders = ",".join("?" for _ in photo_ids)
    rows = conn.execute(
        f"SELECT filename, video_filename FROM photos WHERE id IN ({placeholders})", photo_ids
    ).fetchall()
    conn.execute(f"DELETE FROM photos WHERE id IN ({placeholders})", photo_ids)
    conn.commit()
    conn.close()
    return [(r["filename"], r["video_filename"]) for r in rows]
