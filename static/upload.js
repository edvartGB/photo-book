const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const folderInput = document.getElementById("folder-input");
const preview = document.getElementById("preview");
const uploadBtn = document.getElementById("upload-btn");
const browseFilesBtn = document.getElementById("browse-files-btn");
const browseFolderBtn = document.getElementById("browse-folder-btn");

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

function addFiles(fileList) {
    for (const file of fileList) {
        if (ALLOWED_EXT.has(getExt(file.name))) {
            collectedFiles.items.add(file);
        }
    }
    fileInput.files = collectedFiles.files;
    showPreviews();
}

function showPreviews() {
    preview.innerHTML = "";
    const files = collectedFiles.files;
    if (files.length === 0) {
        uploadBtn.disabled = true;
        dropZone.querySelector("p").textContent = "Drag & drop photos here";
        return;
    }
    uploadBtn.disabled = false;
    for (const file of files) {
        if (!file.type.startsWith("image/")) continue;
        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        preview.appendChild(img);
    }
    const imageCount = [...files].filter(f => !getExt(f.name).match(/mov/)).length;
    const videoCount = files.length - imageCount;
    let label = `${imageCount} photo${imageCount !== 1 ? "s" : ""}`;
    if (videoCount > 0) label += ` + ${videoCount} video${videoCount !== 1 ? "s" : ""}`;
    dropZone.querySelector("p").textContent = label + " selected";
}
