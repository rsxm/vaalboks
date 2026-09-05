"use strict";

// Drag & drop file/folder upload for vaalboks.
// Folders are traversed with webkitGetAsEntry (supported by all current browsers);
// each file is uploaded with its relative path so the server can rebuild the tree.
// Uploads use XHR because it is the portable browser API with upload progress
// events. Downloads use streaming fetch for response progress.

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const progressWrap = document.getElementById("progress-wrap");
const progress = document.getElementById("progress");
const progressLabel = document.getElementById("progress-label");

const statUpTotal = document.getElementById("stat-up-total");
const statDownTotal = document.getElementById("stat-down-total");
const statUpSpeed = document.getElementById("stat-up-speed");
const statDownSpeed = document.getElementById("stat-down-speed");
let uploadedBytes = 0;
let downloadedBytes = 0;

function csrfToken() {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

function fmtBytes(n) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${i === 0 ? n : n.toFixed(1)} ${units[i]}`;
}

// Exponentially-smoothed speed meter over streamed byte counts.
function speedMeter() {
  let lastTime = performance.now();
  let lastBytes = 0;
  let ema = 0;
  return (totalBytes) => {
    const now = performance.now();
    const dt = (now - lastTime) / 1000;
    if (dt >= 0.15) {
      const inst = (totalBytes - lastBytes) / dt;
      ema = ema === 0 ? inst : ema * 0.7 + inst * 0.3;
      lastTime = now;
      lastBytes = totalBytes;
    }
    return ema;
  };
}

// Recursively collect {file, path} from a FileSystemEntry tree.
async function collectFromEntry(entry, prefix = "") {
  if (entry.isFile) {
    const file = await new Promise((resolve, reject) =>
      entry.file(resolve, reject),
    );
    return [{ file, path: prefix + file.name }];
  }
  if (entry.isDirectory) {
    const reader = entry.createReader();
    const results = [];
    // readEntries returns batches; loop until it comes back empty.
    for (;;) {
      const batch = await new Promise((resolve, reject) =>
        reader.readEntries(resolve, reject),
      );
      if (batch.length === 0) break;
      for (const child of batch) {
        results.push(
          ...(await collectFromEntry(child, `${prefix + entry.name}/`)),
        );
      }
    }
    return results;
  }
  return [];
}

async function collectItems(dataTransfer) {
  const jobs = [];
  for (const item of dataTransfer.items) {
    if (item.kind !== "file") continue;
    const entry = item.webkitGetAsEntry();
    if (entry) jobs.push(collectFromEntry(entry));
  }
  return (await Promise.all(jobs)).flat();
}

async function upload(files) {
  if (files.length === 0) return;
  const form = new FormData();
  let totalSize = 0;
  for (const { file, path } of files) {
    form.append("files", file);
    form.append("paths", path);
    totalSize += file.size;
  }

  const meter = speedMeter();
  progressWrap.classList.add("active");
  progress.max = totalSize;
  progress.value = 0;

  const t0 = performance.now();
  await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload/");
    xhr.setRequestHeader("X-CSRFToken", csrfToken());
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      progress.value = event.loaded;
      const speed = meter(event.loaded);
      progressLabel.textContent =
        `Uploading ${files.length} file${files.length === 1 ? "" : "s"} — ` +
        `${fmtBytes(event.loaded)} / ${fmtBytes(totalSize)} @ ${fmtBytes(speed)}/s`;
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(
          new Error(
            `HTTP ${xhr.status}: ${xhr.responseText || "upload failed"}`,
          ),
        );
      }
    };
    xhr.onerror = () => reject(new Error("network error"));
    xhr.onabort = () => reject(new Error("upload cancelled"));
    xhr.send(form);
  });

  const secs = (performance.now() - t0) / 1000;
  const avg = secs > 0 ? totalSize / secs : 0;
  uploadedBytes += totalSize;
  statUpTotal.textContent = fmtBytes(uploadedBytes);
  statUpSpeed.textContent = `${fmtBytes(avg)}/s`;
  progress.value = 100;
  progress.max = 100;
  progressLabel.textContent = `Uploaded ${fmtBytes(totalSize)} in ${secs.toFixed(1)}s (${fmtBytes(avg)}/s).`;
  setTimeout(() => progressWrap.classList.remove("active"), 2500);
  htmx.trigger(document.body, "fileschanged");
}

// Download via streaming fetch so we can measure speed, then save as a blob.
async function downloadWithStats(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const total = Number(resp.headers.get("Content-Length")) || 0;
  const disposition = resp.headers.get("Content-Disposition") || "";
  const name =
    disposition.match(/filename="?([^";]+)"?/)?.[1] || url.split("/").pop();

  const meter = speedMeter();
  progressWrap.classList.add("active");
  progress.max = total;
  progress.value = 0;

  const chunks = [];
  let received = 0;
  const t0 = performance.now();
  const reader = resp.body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    progress.value = received;
    const speed = meter(received);
    progressLabel.textContent = total
      ? `Downloading ${name} — ${fmtBytes(received)} / ${fmtBytes(total)} @ ${fmtBytes(speed)}/s`
      : `Downloading ${name} — ${fmtBytes(received)} @ ${fmtBytes(speed)}/s`;
  }

  const secs = (performance.now() - t0) / 1000;
  const avg = secs > 0 ? received / secs : 0;
  downloadedBytes += received;
  statDownTotal.textContent = fmtBytes(downloadedBytes);
  statDownSpeed.textContent = `${fmtBytes(avg)}/s`;
  progressLabel.textContent = `Downloaded ${name} (${fmtBytes(received)}) in ${secs.toFixed(1)}s (${fmtBytes(avg)}/s).`;
  setTimeout(() => progressWrap.classList.remove("active"), 2500);

  const blobUrl = URL.createObjectURL(new Blob(chunks));
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 10_000);
}

// Intercept clicks on file links inside the (htmx-rendered) listing.
document.getElementById("file-list").addEventListener("click", (e) => {
  const folderButton = e.target.closest(".folder-toggle:not(.empty)");
  if (folderButton) {
    const children = folderButton.parentElement.nextElementSibling;
    const expanded = folderButton.getAttribute("aria-expanded") === "true";
    folderButton.setAttribute("aria-expanded", String(!expanded));
    children?.classList.toggle("open", !expanded);
  }
  const link = e.target.closest("a.name");
  if (!link) return;
  e.preventDefault();
  downloadWithStats(link.href).catch((err) => {
    progressLabel.textContent = `Download failed: ${err.message}`;
  });
});

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () =>
  dropzone.classList.remove("dragover"),
);
dropzone.addEventListener("drop", async (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  try {
    await upload(await collectItems(e.dataTransfer));
  } catch (err) {
    progressLabel.textContent = `Upload failed: ${err.message}`;
  }
});

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  upload([...fileInput.files].map((f) => ({ file: f, path: f.name })));
  fileInput.value = "";
});
