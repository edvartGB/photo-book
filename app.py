import os
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
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

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "heic"}
VIDEO_EXTENSIONS = {"mov"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
THUMBNAIL_SIZE = (400, 400)

# Hash the password from config on startup
_password_hash = generate_password_hash(config.PASSWORD)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_exif_date(image):
    try:
        exif = image._getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id)
                if tag == "DateTimeOriginal":
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def make_thumbnail(source_path, thumb_path):
    with Image.open(source_path) as img:
        img.thumbnail(THUMBNAIL_SIZE)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(thumb_path, "JPEG", quality=85)


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
        if username == config.USERNAME and check_password_hash(_password_hash, password):
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
    photos, total = db.get_photos(page=page, per_page=10)
    has_next = (page * 10) < total
    return render_template("feed.html", photos=photos, page=page, has_next=has_next)


# --- Library ---

@app.route("/library")
@login_required
def library():
    page = request.args.get("page", 1, type=int)
    photos, total = db.get_photos(page=page, per_page=500)
    has_next = (page * 500) < total
    return render_template("library.html", photos=photos, page=page, has_next=has_next)


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
    db.delete_album(album_id)
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
    album_id = request.form.get("album_id", type=int)

    if not files or all(f.filename == "" for f in files):
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
    for base, file in images.items():
        ext = file.filename.rsplit(".", 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(config.PHOTOS_DIR, stored_name)
        file.save(filepath)

        # Extract EXIF date
        taken_at = None
        try:
            with Image.open(filepath) as img:
                taken_at = extract_exif_date(img)
        except Exception:
            pass
        if not taken_at:
            taken_at = datetime.now()

        # Generate thumbnail
        thumb_path = os.path.join(config.THUMBNAILS_DIR, stored_name)
        try:
            make_thumbnail(filepath, thumb_path)
        except Exception:
            pass

        # Check for a paired Live Photo video
        video_stored_name = None
        if base in videos:
            video_file = videos.pop(base)
            video_ext = video_file.filename.rsplit(".", 1)[1].lower()
            video_stored_name = f"{stored_name.rsplit('.', 1)[0]}.{video_ext}"
            video_file.save(os.path.join(config.VIDEOS_DIR, video_stored_name))

        db.add_photo(stored_name, file.filename, caption, album_id, taken_at, video_stored_name)
        count += 1

    # Any remaining unpaired videos — skip them (videos need an image)
    if videos:
        flash(f"{len(videos)} video(s) skipped (no matching image found).")

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
        for directory in (config.PHOTOS_DIR, config.THUMBNAILS_DIR):
            path = os.path.join(directory, filename)
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
    return send_from_directory(config.PHOTOS_DIR, filename)


@app.route("/thumbnails/<filename>")
@login_required
def serve_thumbnail(filename):
    return send_from_directory(config.THUMBNAILS_DIR, filename)


@app.route("/videos/<filename>")
@login_required
def serve_video(filename):
    return send_from_directory(config.VIDEOS_DIR, filename)


# --- Startup ---

if __name__ == "__main__":
    os.makedirs(config.PHOTOS_DIR, exist_ok=True)
    os.makedirs(config.THUMBNAILS_DIR, exist_ok=True)
    os.makedirs(config.VIDEOS_DIR, exist_ok=True)
    db.init_db()
    app.run(host="0.0.0.0", port=config.PORT, debug=True)
