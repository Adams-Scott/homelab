const state = {
  expiry: "1d",
};

const textInput = document.getElementById("text-input");
const postTextBtn = document.getElementById("post-text-btn");
const fileInput = document.getElementById("file-input");
const itemsList = document.getElementById("items-list");
const emptyState = document.getElementById("empty-state");
const toastEl = document.getElementById("toast");
const newPostBtn = document.getElementById("new-post-btn");
const composerModal = document.getElementById("composer-modal");
const closeComposerBtn = document.getElementById("close-composer-btn");

function openComposer() {
  composerModal.hidden = false;
  composerModal.classList.add("is-open");
  document.body.classList.add("modal-open");
  textInput.focus();
}

function closeComposer() {
  composerModal.classList.remove("is-open");
  document.body.classList.remove("modal-open");
  composerModal.hidden = true;
  textInput.value = "";
}

document.querySelectorAll(".expiry-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".expiry-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.expiry = btn.dataset.expiry;
  });
});

function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => { toastEl.hidden = true; }, 2200);
}

async function postText() {
  const text = textInput.value.trim();
  if (!text) return;
  const form = new FormData();
  form.append("text", text);
  form.append("expiry", state.expiry);
  postTextBtn.disabled = true;
  try {
    const res = await fetch("/api/items", { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    textInput.value = "";
    closeComposer();
    await loadItems();
    showToast("Posted");
  } catch (e) {
    showToast("Failed to post");
    console.error(e);
  } finally {
    postTextBtn.disabled = false;
  }
}

async function postFile(file) {
  const form = new FormData();
  form.append("file", file);
  form.append("expiry", state.expiry);
  try {
    const res = await fetch("/api/items", { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    await loadItems();
    showToast("Uploaded");
  } catch (e) {
    showToast("Failed to upload");
    console.error(e);
  }
}

newPostBtn.addEventListener("click", openComposer);
closeComposerBtn.addEventListener("click", closeComposer);
composerModal.addEventListener("click", (e) => {
  if (e.target.matches("[data-close='true']")) closeComposer();
});
postTextBtn.addEventListener("click", postText);
textInput.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") postText();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !composerModal.hidden && composerModal.classList.contains("is-open")) {
    closeComposer();
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) {
    postFile(fileInput.files[0]);
    fileInput.value = "";
  }
});

// Paste images anywhere on the page
document.addEventListener("paste", (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.kind === "file") {
      const file = item.getAsFile();
      if (file) {
        postFile(file);
        e.preventDefault();
      }
    }
  }
});

// Drag & drop anywhere on the page
["dragenter", "dragover"].forEach((evt) => {
  document.addEventListener(evt, (e) => {
    e.preventDefault();
    document.querySelector(".page").classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((evt) => {
  document.addEventListener(evt, (e) => {
    e.preventDefault();
    document.querySelector(".page").classList.remove("dragging");
  });
});
document.addEventListener("drop", (e) => {
  const files = e.dataTransfer?.files;
  if (files && files.length) {
    for (const f of files) postFile(f);
  }
});

function fmtSize(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtTimeLeft(seconds) {
  if (seconds <= 0) return "expired";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h left`;
  if (hours > 0) return `${hours}h ${mins}m left`;
  return `${mins}m left`;
}

function iconFor(kind) {
  if (kind === "image") return "🖼";
  if (kind === "file") return "📄";
  return "✎";
}

function renderTextContent(content) {
  const wrapper = document.createElement("div");
  const parts = content.split(/(https?:\/\/\S+)/gi);
  parts.forEach((part) => {
    if (!part) return;
    if (/^https?:\/\//i.test(part)) {
      const link = document.createElement("a");
      link.href = part;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = part;
      wrapper.appendChild(link);
    } else {
      wrapper.appendChild(document.createTextNode(part));
    }
  });
  return wrapper;
}

function renderItem(item) {
  const div = document.createElement("div");
  div.className = "item";
  div.dataset.id = item.id;

  const icon = document.createElement("div");
  icon.className = "item-icon";
  icon.textContent = iconFor(item.kind);
  div.appendChild(icon);

  const body = document.createElement("div");
  body.className = "item-body";

  if (item.kind === "text") {
    const p = document.createElement("p");
    p.className = "item-text";
    p.appendChild(renderTextContent(item.content));
    body.appendChild(p);
  } else {
    const name = document.createElement("p");
    name.className = "item-filename";
    name.textContent = item.original_name;
    body.appendChild(name);
    if (item.kind === "image") {
      const img = document.createElement("img");
      img.className = "item-image-preview";
      img.src = `/api/items/${item.id}/download`;
      img.alt = item.original_name;
      body.appendChild(img);
    }
  }

  const meta = document.createElement("div");
  meta.className = "item-meta";
  const timeSpan = document.createElement("span");
  timeSpan.className = "time-left";
  timeSpan.textContent = fmtTimeLeft(item.seconds_left);
  meta.appendChild(timeSpan);
  if (item.size != null) {
    const sizeSpan = document.createElement("span");
    sizeSpan.textContent = fmtSize(item.size);
    meta.appendChild(sizeSpan);
  }
  body.appendChild(meta);
  div.appendChild(body);

  const actions = document.createElement("div");
  actions.className = "item-actions";

  if (item.kind === "text") {
    const copyBtn = document.createElement("button");
    copyBtn.className = "icon-btn";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", async () => {
      await navigator.clipboard.writeText(item.content);
      showToast("Copied");
    });
    actions.appendChild(copyBtn);
  } else {
    const dlBtn = document.createElement("a");
    dlBtn.className = "icon-btn";
    dlBtn.textContent = "Download";
    dlBtn.href = `/api/items/${item.id}/download`;
    // Hint to the browser to download the file instead of opening it in a tab
    dlBtn.setAttribute("download", item.original_name);
    actions.appendChild(dlBtn);
  }

  const delBtn = document.createElement("button");
  delBtn.className = "icon-btn danger";
  delBtn.textContent = "Delete";
  delBtn.addEventListener("click", async () => {
    await fetch(`/api/items/${item.id}`, { method: "DELETE" });
    div.remove();
    if (!itemsList.children.length) emptyState.hidden = false;
  });
  actions.appendChild(delBtn);

  div.appendChild(actions);
  return div;
}

let cachedItems = [];

async function loadItems() {
  const res = await fetch("/api/items");
  cachedItems = await res.json();
  itemsList.innerHTML = "";
  if (!cachedItems.length) {
    emptyState.hidden = false;
  } else {
    emptyState.hidden = true;
    for (const item of cachedItems) {
      itemsList.appendChild(renderItem(item));
    }
  }
}

// Tick countdowns locally, refresh from server periodically
setInterval(() => {
  cachedItems.forEach((item) => {
    item.seconds_left = Math.max(0, item.seconds_left - 1);
    const el = itemsList.querySelector(`.item[data-id="${item.id}"] .time-left`);
    if (el) el.textContent = fmtTimeLeft(item.seconds_left);
  });
}, 1000);

setInterval(loadItems, 30000);

loadItems();
