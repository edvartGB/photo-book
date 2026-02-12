import logging
import os
import time
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from pillow_heif import register_heif_opener
from PIL import Image, ExifTags

register_heif_opener()
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import config
import db

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 50 MB per request

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "heic"}
VIDEO_EXTENSIONS = {"mov"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
THUMBNAIL_SIZE = (400, 400)
DISPLAY_SIZE = (1400, 1400)

# Hash passwords from config on startup
_users = {config.USERNAME: generate_password_hash(config.PASSWORD)}
if config.USERNAME2 and config.PASSWORD2:
    _users[config.USERNAME2] = generate_password_hash(config.PASSWORD2)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


_EXIF_DATE_TAG = 36867  # DateTimeOriginal


def extract_exif_date(image):
    try:
        exif = image._getexif()
        if exif and _EXIF_DATE_TAG in exif:
            return datetime.strptime(exif[_EXIF_DATE_TAG], "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def process_image(filepath):
    """Open image once, extract EXIF, generate display + thumbnail."""
    with Image.open(filepath) as img:
        taken_at = extract_exif_date(img)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Display first (larger), then thumbnail from the display (cheap)
        display = img.copy()
        display.thumbnail(DISPLAY_SIZE)

        thumb = display.copy()
        thumb.thumbnail(THUMBNAIL_SIZE)

        return taken_at, thumb, display


# --- Auth ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username in _users and check_password_hash(_users[username], password):
            session["logged_in"] = True
            return redirect(url_for("feed"))
        flash("Wrong username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Feed ---

@app.route("/")
@login_required
def index():
    return redirect(url_for("feed"))


@app.route("/feed")
@login_required
def feed():
    page = request.args.get("page", 1, type=int)
    photos, total = db.get_photos(page=page, per_page=10, feed_only=True)
    has_next = (page * 10) < total
    return render_template("feed.html", photos=photos, page=page, has_next=has_next)


# --- Library ---

@app.route("/library")
@login_required
def library():
    page = request.args.get("page", 1, type=int)
    photos, total = db.get_photos(page=page, per_page=80)
    has_next = (page * 80) < total
    return render_template("library.html", photos=photos, page=page, has_next=has_next)


@app.route("/library/delete", methods=["POST"])
@login_required
def delete_photos_bulk():
    photo_ids = request.form.getlist("photo_ids", type=int)
    if not photo_ids:
        flash("No photos selected.")
        return redirect(url_for("library"))
    files = db.delete_photos_bulk(photo_ids)
    for filename, video_filename in files:
        jpg_name = filename.rsplit(".", 1)[0] + ".jpg"
        for directory, name in [(config.PHOTOS_DIR, filename),
                                (config.THUMBNAILS_DIR, jpg_name),
                                (config.DISPLAY_DIR, jpg_name)]:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                os.remove(path)
        if video_filename:
            path = os.path.join(config.VIDEOS_DIR, video_filename)
            if os.path.exists(path):
                os.remove(path)
    flash(f"Deleted {len(files)} photo{'s' if len(files) != 1 else ''}.")
    return redirect(url_for("library"))


# --- Albums ---

@app.route("/albums")
@login_required
def albums():
    album_list = db.get_albums()
    return render_template("albums.html", albums=album_list)


@app.route("/albums", methods=["POST"])
@login_required
def create_album():
    name = request.form.get("name", "").strip()
    if name:
        db.create_album(name)
    return redirect(url_for("albums"))


@app.route("/albums/<int:album_id>/rename", methods=["POST"])
@login_required
def rename_album(album_id):
    name = request.form.get("name", "").strip()
    if name:
        db.rename_album(album_id, name)
    return redirect(url_for("album", album_id=album_id))


@app.route("/albums/<int:album_id>")
@login_required
def album(album_id):
    album_data = db.get_album(album_id)
    if not album_data:
        abort(404)
    page = request.args.get("page", 1, type=int)
    photos, total = db.get_photos(album_id=album_id, page=page)
    has_next = (page * 40) < total
    return render_template("album.html", album=album_data, photos=photos, page=page, has_next=has_next)


@app.route("/albums/<int:album_id>/add")
@login_required
def add_photos_to_album(album_id):
    album_data = db.get_album(album_id)
    if not album_data:
        abort(404)
    unassigned = request.args.get("unassigned", "0") == "1"
    photos = db.get_all_photos(unassigned_only=unassigned)
    return render_template("album_add.html", album=album_data, photos=photos, unassigned=unassigned)


@app.route("/albums/<int:album_id>/add", methods=["POST"])
@login_required
def add_photos_to_album_submit(album_id):
    photo_ids = request.form.getlist("photo_ids", type=int)
    if photo_ids:
        db.bulk_assign_album(photo_ids, album_id)
        flash(f"Added {len(photo_ids)} photo{'s' if len(photo_ids) != 1 else ''} to album.")
    return redirect(url_for("album", album_id=album_id))


@app.route("/albums/<int:album_id>/delete", methods=["POST"])
@login_required
def delete_album(album_id):
    delete_photos = request.form.get("delete_photos") == "1"
    files = db.delete_album(album_id, delete_photos=delete_photos)
    for filename, video_filename in files:
        base = filename.rsplit(".", 1)[0]
        for path in [
            os.path.join(config.PHOTOS_DIR, filename),
            os.path.join(config.THUMBNAILS_DIR, base + ".jpg"),
            os.path.join(config.DISPLAY_DIR, base + ".jpg"),
        ]:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
        if video_filename:
            try:
                os.remove(os.path.join(config.VIDEOS_DIR, video_filename))
            except FileNotFoundError:
                pass
    return redirect(url_for("albums"))


# --- Upload ---

@app.route("/upload")
@login_required
def upload_page():
    album_list = db.get_albums()
    return render_template("upload.html", albums=album_list)


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    files = request.files.getlist("photos")
    caption = request.form.get("caption", "").strip()
    hidden = request.form.get("hidden") == "1"
    album_id_raw = request.form.get("album_id", "")
    album_id = None

    if album_id_raw == "__new__":
        new_album_name = request.form.get("new_album_name", "").strip()
        if new_album_name:
            album_id = db.create_album(new_album_name)
    elif album_id_raw:
        album_id = int(album_id_raw)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not files or all(f.filename == "" for f in files):
        if is_ajax:
            return jsonify({"error": "No files selected."}), 400
        flash("No files selected.")
        return redirect(url_for("upload_page"))

    # Separate images and videos, save them all to temp with original names tracked
    images = {}  # base_name -> (file_obj, original_filename)
    videos = {}  # base_name -> (file_obj, original_filename)

    for file in files:
        if not file or not file.filename or not allowed_file(file.filename):
            continue
        ext = file.filename.rsplit(".", 1)[1].lower()
        base = file.filename.rsplit(".", 1)[0].upper()  # normalize case for pairing
        if ext in VIDEO_EXTENSIONS:
            videos[base] = file
        else:
            images[base] = file

    count = 0
    photo_rows = []
    for base, file in images.items():
        ext = file.filename.rsplit(".", 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(config.PHOTOS_DIR, stored_name)
        file.save(filepath)

        jpg_name = stored_name.rsplit(".", 1)[0] + ".jpg"
        taken_at = None
        try:
            t0 = time.time()
            taken_at, thumb, display = process_image(filepath)
            thumb.save(os.path.join(config.THUMBNAILS_DIR, jpg_name), "JPEG", quality=70)
            display.save(os.path.join(config.DISPLAY_DIR, jpg_name), "JPEG", quality=82)
            logging.info(f"Processed {file.filename} in {time.time() - t0:.2f}s")
        except Exception:
            logging.exception(f"Failed to process {file.filename}")
        if not taken_at:
            taken_at = datetime.now()

        # Check for a paired Live Photo video
        video_stored_name = None
        if base in videos:
            video_file = videos.pop(base)
            video_ext = video_file.filename.rsplit(".", 1)[1].lower()
            video_stored_name = f"{stored_name.rsplit('.', 1)[0]}.{video_ext}"
            video_file.save(os.path.join(config.VIDEOS_DIR, video_stored_name))

        photo_rows.append((stored_name, file.filename, caption or None, album_id or None, taken_at, video_stored_name, int(hidden)))
        count += 1

    if photo_rows:
        db.add_photos_batch(photo_rows)

    # Any remaining unpaired videos — skip them (videos need an image)
    skipped_videos = len(videos)

    if is_ajax:
        return jsonify({"album_id": album_id, "count": count, "skipped_videos": skipped_videos})

    if skipped_videos:
        flash(f"{skipped_videos} video(s) skipped (no matching image found).")
    flash(f"Uploaded {count} photo{'s' if count != 1 else ''}.")
    if album_id:
        return redirect(url_for("album", album_id=album_id))
    return redirect(url_for("feed"))


# --- Photo detail ---

@app.route("/photo/<int:photo_id>")
@login_required
def photo(photo_id):
    photo_data = db.get_photo(photo_id)
    if not photo_data:
        abort(404)
    album_list = db.get_albums()
    return render_template("photo.html", photo=photo_data, albums=album_list)


@app.route("/photo/<int:photo_id>/album", methods=["POST"])
@login_required
def update_photo_album(photo_id):
    album_id = request.form.get("album_id", type=int)
    db.update_photo_album(photo_id, album_id)
    return redirect(url_for("photo", photo_id=photo_id))


@app.route("/photo/<int:photo_id>/delete", methods=["POST"])
@login_required
def delete_photo(photo_id):
    filename, video_filename = db.delete_photo(photo_id)
    if filename:
        jpg_name = filename.rsplit(".", 1)[0] + ".jpg"
        for directory, name in [(config.PHOTOS_DIR, filename),
                                (config.THUMBNAILS_DIR, jpg_name),
                                (config.DISPLAY_DIR, jpg_name)]:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                os.remove(path)
    if video_filename:
        path = os.path.join(config.VIDEOS_DIR, video_filename)
        if os.path.exists(path):
            os.remove(path)
    return redirect(url_for("feed"))


# --- Serve images ---

@app.route("/photos/<filename>")
@login_required
def serve_photo(filename):
    return send_from_directory(config.PHOTOS_DIR, filename, max_age=31536000)


@app.route("/thumbnails/<filename>")
@login_required
def serve_thumbnail(filename):
    thumb_name = filename.rsplit(".", 1)[0] + ".jpg"
    return send_from_directory(config.THUMBNAILS_DIR, thumb_name, max_age=31536000)


@app.route("/display/<filename>")
@login_required
def serve_display(filename):
    display_name = filename.rsplit(".", 1)[0] + ".jpg"
    return send_from_directory(config.DISPLAY_DIR, display_name, max_age=31536000)


@app.route("/videos/<filename>")
@login_required
def serve_video(filename):
    return send_from_directory(config.VIDEOS_DIR, filename, max_age=31536000)


# --- Startup ---

if __name__ == "__main__":
    os.makedirs(config.PHOTOS_DIR, exist_ok=True)
    os.makedirs(config.THUMBNAILS_DIR, exist_ok=True)
    os.makedirs(config.VIDEOS_DIR, exist_ok=True)
    os.makedirs(config.DISPLAY_DIR, exist_ok=True)
    db.init_db()
    app.run(host="0.0.0.0", port=config.PORT, debug=True)
