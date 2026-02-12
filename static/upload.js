const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const folderInput = document.getElementById("folder-input");
const preview = document.getElementById("preview");
const uploadBtn = document.getElementById("upload-btn");
const browseFilesBtn = document.getElementById("browse-files-btn");
const browseFolderBtn = document.getElementById("browse-folder-btn");
const uploadForm = document.getElementById("upload-form");
const albumSelect = document.getElementById("album-select");
const newAlbumInput = document.getElementById("new-album-input");

const ALLOWED_EXT = new Set(["jpg", "jpeg", "png", "gif", "webp", "heic", "mov"]);
let collectedFiles = new DataTransfer();

browseFilesBtn.addEventListener("click", () => fileInput.click());
browseFolderBtn.addEventListener("click", () => folderInput.click());

// Drag & drop
dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    addFiles(e.dataTransfer.files);
});

// File input
fileInput.addEventListener("change", () => {
    addFiles(fileInput.files);
    fileInput.value = "";
});

// Folder input
folderInput.addEventListener("change", () => {
    addFiles(folderInput.files);
    folderInput.value = "";
});

function getExt(name) {
    const parts = name.split(".");
    return parts.length > 1 ? parts.pop().toLowerCase() : "";
}

function getBaseName(name) {
    const parts = name.split(".");
    if (parts.length === 1) return parts[0].toUpperCase();
    parts.pop();
    return parts.join(".").toUpperCase();
}

function addFiles(fileList) {
    for (const file of fileList) {
        if (ALLOWED_EXT.has(getExt(file.name))) {
            collectedFiles.items.add(file);
        }
    }
    showPreviews();
}

// Album select: show/hide new album input
albumSelect.addEventListener("change", () => {
    if (albumSelect.value === "__new__") {
        newAlbumInput.hidden = false;
        newAlbumInput.required = true;
        newAlbumInput.focus();
    } else {
        newAlbumInput.hidden = true;
        newAlbumInput.required = false;
        newAlbumInput.value = "";
    }
});

// Upload: one image (+optional paired video) at a time
uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const files = [...collectedFiles.files];
    if (files.length === 0) return;

    const caption = uploadForm.querySelector('[name="caption"]').value;
    const hidden = document.getElementById("hidden-check").checked;
    let albumId = albumSelect.value;
    const newAlbumName = newAlbumInput.value;

    // Group files by base name for Live Photo pairing (image + .mov)
    const groups = new Map();
    for (const file of files) {
        const base = getBaseName(file.name);
        if (!groups.has(base)) groups.set(base, []);
        groups.get(base).push(file);
    }

    // Keep only groups that have at least one image (videos without images are skipped)
    const entries = [...groups.values()].filter(group =>
        group.some(f => getExt(f.name) !== "mov")
    );

    if (entries.length === 0) return;

    setUploading(true);
    let uploaded = 0;
    const total = entries.length;

    function updateProgress() {
        const p = dropZone.querySelector("p");
        if (p) p.textContent = `Uploading ${uploaded}/${total}...`;
    }

    updateProgress();

    try {
        for (const group of entries) {
            const formData = new FormData();
            for (const file of group) {
                formData.append("photos", file);
            }
            formData.append("caption", caption);
            if (hidden) formData.append("hidden", "1");

            if (albumId === "__new__" && newAlbumName) {
                formData.append("album_id", "__new__");
                formData.append("new_album_name", newAlbumName);
            } else if (albumId && albumId !== "__new__") {
                formData.append("album_id", albumId);
            }

            const res = await fetch("/upload", {
                method: "POST",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                body: formData,
            });
            if (!res.ok) throw new Error(`Upload failed (${res.status})`);

            const data = await res.json();

            // After creating a new album on the first request, use its ID for the rest
            if (data.album_id && albumId === "__new__") {
                albumId = String(data.album_id);
            }

            uploaded++;
            updateProgress();
        }

        if (albumId && albumId !== "__new__") {
            window.location = `/album/${albumId}`;
        } else {
            window.location = "/";
        }
    } catch (err) {
        const p = dropZone.querySelector("p");
        if (p) p.textContent = `Error: ${err.message}`;
        setUploading(false);
    }
});

function setUploading(busy) {
    uploadBtn.disabled = busy || collectedFiles.files.length === 0;
    browseFilesBtn.disabled = busy;
    browseFolderBtn.disabled = busy;
    albumSelect.disabled = busy;
    newAlbumInput.disabled = busy;
    uploadBtn.textContent = busy ? "Uploading..." : "Upload";
}

function showPreviews() {
    preview.innerHTML = "";
    const files = collectedFiles.files;
    const p = dropZone.querySelector("p");

    if (files.length === 0) {
        uploadBtn.disabled = true;
        if (p) p.textContent = "Drag & drop photos here";
        return;
    }

    uploadBtn.disabled = false;
    const imageFiles = [...files].filter(f => f.type.startsWith("image/"));
    const maxPreview = 5;

    for (let i = 0; i < Math.min(imageFiles.length, maxPreview); i++) {
        const img = document.createElement("img");
        img.src = URL.createObjectURL(imageFiles[i]);
        preview.appendChild(img);
    }

    if (imageFiles.length > maxPreview) {
        const more = document.createElement("span");
        more.className = "preview-more";
        more.textContent = `+${imageFiles.length - maxPreview} more`;
        preview.appendChild(more);
    }

    const imageCount = [...files].filter(f => getExt(f.name) !== "mov").length;
    const videoCount = files.length - imageCount;
    let label = `${imageCount} photo${imageCount !== 1 ? "s" : ""}`;
    if (videoCount > 0) label += ` + ${videoCount} video${videoCount !== 1 ? "s" : ""}`;
    if (p) p.textContent = label + " selected";
}
