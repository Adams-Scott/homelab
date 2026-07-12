(function () {
  "use strict";

  const boardsGrid = document.getElementById("boardsGrid");
  const boardsEmpty = document.getElementById("boardsEmpty");
  const cardTemplate = document.getElementById("boardCardTemplate");

  const newBoardModal = document.getElementById("newBoardModal");
  const newBoardName = document.getElementById("newBoardName");
  const newBoardHint = document.getElementById("newBoardHint");
  const newBoardBtn = document.getElementById("newBoardBtn");
  const emptyStateBtn = document.getElementById("emptyStateBtn");
  const cancelNewBoard = document.getElementById("cancelNewBoard");
  const confirmNewBoard = document.getElementById("confirmNewBoard");

  newBoardModal.hidden = true;
  confirmNewBoard.disabled = false;

  function openNewBoardModal() {
    newBoardName.value = "";
    newBoardHint.textContent = "";
    confirmNewBoard.disabled = false;
    newBoardModal.hidden = false;
    setTimeout(() => newBoardName.focus(), 30);
  }

  function closeNewBoardModal() {
    newBoardName.value = "";
    newBoardHint.textContent = "";
    confirmNewBoard.disabled = false;
    newBoardModal.hidden = true;
  }

  newBoardBtn.addEventListener("click", openNewBoardModal);
  emptyStateBtn.addEventListener("click", openNewBoardModal);
  cancelNewBoard.addEventListener("click", closeNewBoardModal);
  newBoardModal.addEventListener("click", (e) => {
    if (e.target === newBoardModal) closeNewBoardModal();
  });
  newBoardName.addEventListener("keydown", (e) => {
    if (e.key === "Enter") confirmNewBoard.click();
    if (e.key === "Escape") closeNewBoardModal();
  });

  confirmNewBoard.addEventListener("click", async () => {
    const name = newBoardName.value.trim();
    if (!name) {
      newBoardHint.textContent = "Give the board a name first.";
      newBoardName.focus();
      return;
    }
    confirmNewBoard.disabled = true;
    try {
      const res = await fetch("/api/boards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Could not create board");
      }
      const board = await res.json();
      window.location.href = `/board/${board.id}`;
    } catch (err) {
      newBoardHint.textContent = err.message;
      confirmNewBoard.disabled = false;
    }
  });

  function renderBoards(boards) {
    boardsGrid.innerHTML = "";
    if (!boards.length) {
      boardsEmpty.hidden = false;
      boardsGrid.hidden = true;
      return;
    }
    boardsEmpty.hidden = true;
    boardsGrid.hidden = false;

    for (const board of boards) {
      const node = cardTemplate.content.cloneNode(true);
      const card = node.querySelector(".board-card");
      card.href = `/board/${board.id}`;
      node.querySelector(".board-card-name").textContent = board.name;
      node.querySelector(".meta-sections").textContent =
        `${board.section_count} section${board.section_count === 1 ? "" : "s"}`;
      node.querySelector(".meta-tasks").textContent =
        `${board.task_count} task${board.task_count === 1 ? "" : "s"}`;

      const deleteBtn = node.querySelector(".board-card-delete");
      deleteBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!confirm(`Delete "${board.name}"? This can't be undone.`)) return;
        deleteBtn.disabled = true;
        try {
          const res = await fetch(`/api/boards/${board.id}`, { method: "DELETE" });
          if (!res.ok) throw new Error("Delete failed");
          loadBoards();
        } catch (err) {
          alert("Could not delete the board.");
          deleteBtn.disabled = false;
        }
      });

      boardsGrid.appendChild(node);
    }
  }

  async function loadBoards() {
    try {
      const res = await fetch("/api/boards");
      const boards = await res.json();
      renderBoards(boards);
    } catch (err) {
      boardsGrid.innerHTML = `<p style="color: var(--danger);">Could not load boards. Is the server running?</p>`;
      boardsGrid.hidden = false;
      boardsEmpty.hidden = true;
    }
  }

  loadBoards();
})();
