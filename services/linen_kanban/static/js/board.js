(function () {
  "use strict";

  const boardId = document.body.dataset.boardId;

  const sectionsRow = document.getElementById("sectionsRow");
  const sectionTemplate = document.getElementById("sectionTemplate");
  const taskCardTemplate = document.getElementById("taskCardTemplate");
  const boardNameEl = document.getElementById("boardName");
  const saveStatusEl = document.getElementById("saveStatus");
  const addSectionBtn = document.getElementById("addSectionBtn");

  const taskModal = document.getElementById("taskModal");
  const taskModalTitle = document.getElementById("taskModalTitle");
  const taskTitleInput = document.getElementById("taskTitle");
  const taskDescInput = document.getElementById("taskDesc");
  const saveTaskBtn = document.getElementById("saveTask");
  const cancelTaskBtn = document.getElementById("cancelTask");
  const deleteTaskBtn = document.getElementById("deleteTaskBtn");

  const confirmModal = document.getElementById("confirmModal");
  const confirmModalTitle = document.getElementById("confirmModalTitle");
  const confirmModalBody = document.getElementById("confirmModalBody");
  const confirmOk = document.getElementById("confirmOk");
  const confirmCancel = document.getElementById("confirmCancel");

  let state = null;
  let sectionSortable = null;
  const taskSortables = [];
  let saveTimer = null;
  let saveInFlight = false;
  let saveQueued = false;

  let editingTaskCtx = null; // { sectionId, taskId } | { sectionId } for new

  taskModal.hidden = true;
  confirmModal.hidden = true;

  function uid() {
    return Math.random().toString(36).slice(2, 10);
  }

  // ---------- Data loading ----------

  async function loadBoard() {
    const res = await fetch(`/api/boards/${boardId}`);
    if (!res.ok) {
      sectionsRow.innerHTML = `<p style="color: var(--danger);">Board not found.</p>`;
      return;
    }
    state = await res.json();
    boardNameEl.textContent = state.name;
    render();
  }

  // ---------- Saving ----------

  function scheduleSave() {
    setStatus("unsaved");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(doSave, 500);
  }

  function setStatus(text) {
    saveStatusEl.textContent = text;
  }

  async function doSave() {
    if (saveInFlight) {
      saveQueued = true;
      return;
    }
    saveInFlight = true;
    setStatus("saving…");
    try {
      const res = await fetch(`/api/boards/${boardId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state),
      });
      if (!res.ok) throw new Error("save failed");
      const saved = await res.json();
      state.updated = saved.updated;
      setStatus("saved");
    } catch (err) {
      setStatus("error saving — retrying…");
      saveTimer = setTimeout(doSave, 1500);
      saveInFlight = false;
      return;
    }
    saveInFlight = false;
    if (saveQueued) {
      saveQueued = false;
      scheduleSave();
    }
  }

  // ---------- Rendering ----------

  function findSection(sectionId) {
    return state.sections.find((s) => s.id === sectionId);
  }

  function findTask(taskId) {
    for (const section of state.sections) {
      const task = section.tasks.find((t) => t.id === taskId);
      if (task) return task;
    }
    return null;
  }

  function render() {
    // tear down old sortables
    if (sectionSortable) sectionSortable.destroy();
    taskSortables.forEach((s) => s.destroy());
    taskSortables.length = 0;

    sectionsRow.innerHTML = "";

    for (const section of state.sections) {
      const node = sectionTemplate.content.cloneNode(true);
      const card = node.querySelector(".section-card");
      card.dataset.sectionId = section.id;

      const nameEl = node.querySelector(".section-name");
      nameEl.textContent = section.name;
      nameEl.addEventListener("blur", () => onSectionRename(section.id, nameEl));
      nameEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          nameEl.blur();
        }
      });

      node.querySelector(".section-count").textContent = section.tasks.length;

      node.querySelector(".section-delete").addEventListener("click", () => {
        confirmDelete({
          title: "Delete section?",
          body: `"${section.name}" and its ${section.tasks.length} task${section.tasks.length === 1 ? "" : "s"} will be removed for good.`,
          onConfirm: () => deleteSection(section.id),
        });
      });

      const taskList = node.querySelector(".task-list");
      taskList.dataset.sectionId = section.id;

      for (const task of section.tasks) {
        const taskNode = taskCardTemplate.content.cloneNode(true);
        const taskCard = taskNode.querySelector(".task-card");
        taskCard.dataset.taskId = task.id;
        taskNode.querySelector(".task-title").textContent = task.title;
        taskNode.querySelector(".task-desc").textContent = task.description || "";
        taskCard.addEventListener("click", () => openTaskModal(section.id, task.id));
        taskList.appendChild(taskNode);
      }

      node.querySelector(".add-task-btn").addEventListener("click", () => openTaskModal(section.id, null));

      sectionsRow.appendChild(node);
    }

    initSortables();
  }

  function initSortables() {
    sectionSortable = new Sortable(sectionsRow, {
      animation: 150,
      handle: ".section-drag-handle",
      draggable: ".section-card",
      ghostClass: "sortable-ghost",
      onEnd: () => {
        resyncSectionOrderFromDom();
        render();
        scheduleSave();
      },
    });

    const taskLists = sectionsRow.querySelectorAll(".task-list");
    taskLists.forEach((list) => {
      const sortable = new Sortable(list, {
        group: "kanban-tasks",
        animation: 150,
        ghostClass: "sortable-ghost",
        chosenClass: "sortable-chosen",
        dragClass: "sortable-drag",
        onEnd: () => {
          resyncTasksFromDom();
          render();
          scheduleSave();
        },
      });
      taskSortables.push(sortable);
    });
  }

  function resyncSectionOrderFromDom() {
    const ids = [...sectionsRow.querySelectorAll(":scope > .section-card")].map(
      (el) => el.dataset.sectionId
    );
    const bySectionId = new Map(state.sections.map((s) => [s.id, s]));
    state.sections = ids.map((id) => bySectionId.get(id)).filter(Boolean);
  }

  function resyncTasksFromDom() {
    const taskById = new Map();
    state.sections.forEach((section) => {
      section.tasks.forEach((task) => taskById.set(task.id, task));
    });

    const sectionEls = sectionsRow.querySelectorAll(":scope > .section-card");
    sectionEls.forEach((el) => {
      const sectionId = el.dataset.sectionId;
      const section = findSection(sectionId);
      if (!section) return;
      const taskIds = [...el.querySelectorAll(".task-card")].map((t) => t.dataset.taskId);
      section.tasks = taskIds.map((id) => taskById.get(id)).filter(Boolean);
    });
  }

  // ---------- Board name ----------

  boardNameEl.addEventListener("blur", () => {
    const value = boardNameEl.textContent.trim() || "Untitled board";
    boardNameEl.textContent = value;
    if (value !== state.name) {
      state.name = value;
      scheduleSave();
    }
  });
  boardNameEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      boardNameEl.blur();
    }
  });

  // ---------- Section rename ----------

  function onSectionRename(sectionId, nameEl) {
    const section = findSection(sectionId);
    if (!section) return;
    const value = nameEl.textContent.trim() || "Untitled section";
    nameEl.textContent = value;
    if (value !== section.name) {
      section.name = value;
      scheduleSave();
    }
  }

  // ---------- Section add/delete ----------

  addSectionBtn.addEventListener("click", () => {
    const section = { id: uid(), name: "New section", tasks: [] };
    state.sections.push(section);
    render();
    scheduleSave();
    const newEl = sectionsRow.querySelector(
      `.section-card[data-section-id="${section.id}"] .section-name`
    );
    if (newEl) {
      const range = document.createRange();
      range.selectNodeContents(newEl);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      newEl.focus();
    }
  });

  function deleteSection(sectionId) {
    state.sections = state.sections.filter((s) => s.id !== sectionId);
    render();
    scheduleSave();
  }

  // ---------- Task modal ----------

  function openTaskModal(sectionId, taskId) {
    editingTaskCtx = { sectionId, taskId };
    if (taskId) {
      const task = findTask(taskId);
      taskModalTitle.textContent = "Edit task";
      taskTitleInput.value = task.title;
      taskDescInput.value = task.description || "";
      deleteTaskBtn.hidden = false;
    } else {
      taskModalTitle.textContent = "New task";
      taskTitleInput.value = "";
      taskDescInput.value = "";
      deleteTaskBtn.hidden = true;
    }
    taskModal.hidden = false;
    setTimeout(() => taskTitleInput.focus(), 30);
  }

  function closeTaskModal() {
    taskTitleInput.value = "";
    taskDescInput.value = "";
    taskModal.hidden = true;
    editingTaskCtx = null;
  }

  cancelTaskBtn.addEventListener("click", closeTaskModal);
  taskModal.addEventListener("click", (e) => {
    if (e.target === taskModal) closeTaskModal();
  });

  function saveTaskFromForm() {
    const title = taskTitleInput.value.trim();
    if (!title) {
      taskTitleInput.focus();
      return;
    }
    const description = taskDescInput.value.trim();
    const section = findSection(editingTaskCtx.sectionId);
    if (!section) return;

    if (editingTaskCtx.taskId) {
      const task = findTask(editingTaskCtx.taskId);
      task.title = title;
      task.description = description;
    } else {
      section.tasks.push({ id: uid(), title, description });
    }
    closeTaskModal();
    render();
    scheduleSave();
  }

  taskTitleInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      saveTaskFromForm();
    }
  });

  taskDescInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      saveTaskFromForm();
    }
  });

  saveTaskBtn.addEventListener("click", saveTaskFromForm);

  deleteTaskBtn.addEventListener("click", () => {
    const { sectionId, taskId } = editingTaskCtx;
    confirmDelete({
      title: "Delete task?",
      body: "This task will be removed for good.",
      onConfirm: () => {
        const section = findSection(sectionId);
        section.tasks = section.tasks.filter((t) => t.id !== taskId);
        closeTaskModal();
        render();
        scheduleSave();
      },
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!taskModal.hidden) closeTaskModal();
      if (!confirmModal.hidden) closeConfirmModal();
    }
  });

  // ---------- Confirm modal (generic) ----------

  let pendingConfirm = null;

  function confirmDelete({ title, body, onConfirm }) {
    confirmModalTitle.textContent = title;
    confirmModalBody.textContent = body;
    pendingConfirm = onConfirm;
    confirmModal.hidden = false;
  }

  function closeConfirmModal() {
    confirmModal.hidden = true;
    pendingConfirm = null;
  }

  confirmCancel.addEventListener("click", closeConfirmModal);
  confirmModal.addEventListener("click", (e) => {
    if (e.target === confirmModal) closeConfirmModal();
  });
  confirmOk.addEventListener("click", () => {
    const fn = pendingConfirm;
    closeConfirmModal();
    if (fn) fn();
  });

  loadBoard();
})();
