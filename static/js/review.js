// Review page: edit, add and delete tasks, choose people with a live fair-share bar per
// person, autosave every change, and send the tasks to GitHub.
// The task cards in the page are the state: every save reads them and sends the full list.
(function () {
  "use strict";

  var form = document.getElementById("review");
  var saveStatus = document.getElementById("save-status");
  var sendButton = document.getElementById("send-button");
  var sendMessage = document.getElementById("send-message");
  var template = document.getElementById("task-template");
  var team = JSON.parse(document.getElementById("team-data").textContent);
  var SAVE_DELAY_MS = 500;

  var saveTimer = null;
  var saveRunning = null; // the promise of the save in flight, if any
  var saveAgain = false;
  var lastSaveOk = true;
  var sending = false;
  var showProblems = false; // outline unfinished tasks only after someone tries to send
  var newCardCount = 0;

  // --- Reading the page ------------------------------------------------------------------

  function cards() {
    return Array.prototype.slice.call(form.querySelectorAll(".task"));
  }

  function field(card, name) {
    return card.querySelector('[name="' + name + '"]');
  }

  function weightOf(card) {
    var checked = card.querySelector('[data-field="weight"]:checked');
    return checked ? Number(checked.value) : 1;
  }

  function readTask(card) {
    return {
      id: card.dataset.taskId || null,
      title: field(card, "title").value,
      done_when: field(card, "done_when").value,
      weight: weightOf(card),
      criterion_id: field(card, "criterion_id").value,
      owner_id: field(card, "owner_id").value || null
    };
  }

  // --- Fair share (the same sums as referee/logic.py) -------------------------------------

  function formatPoints(value) {
    var rounded = Math.round(value * 10) / 10;
    return rounded === Math.round(rounded) ? String(Math.round(rounded)) : rounded.toFixed(1);
  }

  function updateFairShare() {
    var tasks = cards().map(readTask);
    var total = tasks.reduce(function (sum, task) { return sum + task.weight; }, 0);
    var share = team.length ? total / team.length : 0;
    var chosen = {};
    team.forEach(function (member) { chosen[member.id] = 0; });
    tasks.forEach(function (task) {
      if (task.owner_id && chosen.hasOwnProperty(task.owner_id)) { chosen[task.owner_id] += task.weight; }
    });
    var shareText = formatPoints(share);
    document.getElementById("fair-share-sum").textContent =
      total + " points ÷ " + team.length + (team.length === 1 ? " person" : " people") + " = " + shareText + " points each";
    team.forEach(function (member) {
      var row = document.querySelector('.share-row[data-member-id="' + member.id + '"]');
      if (!row) { return; }
      var points = chosen[member.id];
      var over = points > share + 1e-9;
      row.classList.toggle("over", over);
      row.querySelector(".share-value").textContent = points + " / " + shareText;
      var percent = share > 0 ? Math.min(100, Math.round((points / share) * 100)) : 0;
      var barElement = row.querySelector(".share-bar");
      barElement.querySelector(".bar-fill").style.width = percent + "%";
      barElement.setAttribute("aria-valuenow", String(percent));
      var note = row.querySelector(".share-heads-up");
      note.hidden = !over;
      note.textContent = over ? member.name + " is now at " + points + " / " + shareText + ". Someone else has room for this task." : "";
    });
  }

  // --- Groups: moving cards, empty notes --------------------------------------------------

  function groupFor(criterionId) {
    return form.querySelector('.criterion-group[data-criterion-id="' + criterionId + '"]');
  }

  function updateEmptyNotes() {
    Array.prototype.forEach.call(form.querySelectorAll(".criterion-group"), function (group) {
      group.querySelector(".criterion-empty").hidden = group.querySelectorAll(".task").length > 0;
    });
    // The last remaining task can't be deleted: a project needs at least one task.
    var all = cards();
    all.forEach(function (card) {
      var opener = card.querySelector(".delete-open");
      if (!opener) { return; }
      var last = all.length === 1;
      opener.disabled = last;
      opener.title = last ? "A project needs at least one task" : "Delete this task";
    });
  }

  function moveToCriterionGroup(card) {
    var group = groupFor(field(card, "criterion_id").value);
    if (group && !group.contains(card)) {
      group.querySelector(".task-list").appendChild(card);
      updateEmptyNotes();
      field(card, "criterion_id").focus();
    }
  }

  // --- Adding and deleting tasks ----------------------------------------------------------

  function addTask(criterionId) {
    newCardCount += 1;
    var key = "new-" + newCardCount;
    var holder = document.createElement("div");
    holder.innerHTML = template.innerHTML.split("__KEY__").join(key);
    var card = holder.querySelector(".task");
    field(card, "criterion_id").value = criterionId;
    groupFor(criterionId).querySelector(".task-list").appendChild(card);
    updateEmptyNotes();
    field(card, "title").focus();
    scheduleSave();
  }

  form.addEventListener("click", function (event) {
    var target = event.target.closest("button");
    if (!target || !form.contains(target)) { return; }
    var card = target.closest(".task");
    if (target.classList.contains("add-task")) {
      addTask(target.dataset.criterionId);
    } else if (target.classList.contains("delete-open")) {
      card.querySelector(".delete-confirm").hidden = false;
      target.hidden = true;
      card.querySelector(".delete-no").focus();
    } else if (target.classList.contains("delete-no")) {
      card.querySelector(".delete-confirm").hidden = true;
      var opener = card.querySelector(".delete-open");
      opener.hidden = false;
      opener.focus();
    } else if (target.classList.contains("delete-yes")) {
      var group = card.closest(".criterion-group");
      card.remove();
      updateEmptyNotes();
      var nextFocus = group.querySelector(".add-task");
      if (nextFocus) { nextFocus.focus(); }
      scheduleSave();
    }
  });

  // --- Autosave --------------------------------------------------------------------------

  function setStatus(text, isProblem) {
    saveStatus.textContent = text;
    saveStatus.classList.toggle("problem", Boolean(isProblem));
  }

  function scheduleSave() {
    setStatus("Saving…");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, SAVE_DELAY_MS);
    updateFairShare();
    updateSendButton();
  }

  function save() {
    clearTimeout(saveTimer);
    saveTimer = null;
    if (saveRunning) {
      saveAgain = true;
      return saveRunning;
    }
    var sentCards = cards();
    saveRunning = fetch("/api/tasks", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tasks: sentCards.map(readTask) })
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            setStatus(data.error || "Couldn't save your changes.", true);
            return false;
          }
          // New tasks get their ID from the server, in the same order they were sent.
          data.tasks.forEach(function (task, index) {
            if (sentCards[index] && !sentCards[index].dataset.taskId) {
              sentCards[index].dataset.taskId = task.id;
            }
          });
          setStatus("Saved");
          return true;
        });
      })
      .catch(function () {
        setStatus("Couldn't save. Is the app still running?", true);
        return false;
      })
      .then(function (ok) {
        saveRunning = null;
        lastSaveOk = ok;
        if (saveAgain) {
          saveAgain = false;
          return save();
        }
        return ok;
      });
    return saveRunning;
  }

  // Save right away (used before sending); resolves to true when everything is saved.
  // After a failed save it tries again, so the team isn't stuck once the app is back.
  function flush() {
    if (saveTimer || saveAgain || (!saveRunning && !lastSaveOk)) {
      return save();
    }
    return saveRunning ? saveRunning.then(function () { return flush(); }) : Promise.resolve(lastSaveOk);
  }

  // --- The send button -------------------------------------------------------------------

  function problems() {
    var noTitle = [];
    var noPerson = [];
    cards().forEach(function (card) {
      var task = readTask(card);
      if (!task.title.trim()) { noTitle.push(card); }
      if (!task.owner_id) { noPerson.push(card); }
    });
    return { noTitle: noTitle, noPerson: noPerson };
  }

  function updateSendButton() {
    var found = problems();
    var count = cards().length;
    var remaining = cards().filter(function (card) { return !card.dataset.issued; }).length;
    var label = sendButton.querySelector("span");
    cards().forEach(function (card) {
      card.classList.toggle("needs-attention", showProblems && (found.noPerson.indexOf(card) >= 0 || found.noTitle.indexOf(card) >= 0));
    });
    var blocked = found.noPerson.length > 0 || found.noTitle.length > 0 || count === 0;
    sendButton.setAttribute("aria-disabled", blocked || sending ? "true" : "false");
    if (sending) {
      label.textContent = "Sending tasks to GitHub…";
    } else if (count === 0) {
      label.textContent = "Add a task to send";
    } else if (found.noPerson.length > 0) {
      label.textContent = found.noPerson.length === 1 ? "1 task still needs a person" : found.noPerson.length + " tasks still need a person";
    } else if (found.noTitle.length > 0) {
      label.textContent = found.noTitle.length === 1 ? "1 task needs a title" : found.noTitle.length + " tasks need a title";
    } else if (remaining < count) {
      label.textContent = "Send the remaining " + remaining + (remaining === 1 ? " task" : " tasks") + " to GitHub";
    } else {
      label.textContent = "Send " + count + (count === 1 ? " task" : " tasks") + " to GitHub";
    }
    return found;
  }

  function showMessage(kind, text, buttons) {
    sendMessage.innerHTML = "";
    if (!text) { return; }
    var box = document.createElement("div");
    box.className = "message " + kind;
    box.setAttribute("role", "alert");
    var icon = document.createElement("i");
    icon.className = "ti " + (kind === "error" ? "ti-alert-circle" : "ti-info-circle");
    icon.setAttribute("aria-hidden", "true");
    var body = document.createElement("div");
    var paragraph = document.createElement("p");
    paragraph.textContent = text;
    body.appendChild(paragraph);
    if (buttons && buttons.length) {
      var row = document.createElement("div");
      row.className = "confirm-actions";
      buttons.forEach(function (button) { row.appendChild(button); });
      body.appendChild(row);
    }
    box.appendChild(icon);
    box.appendChild(body);
    sendMessage.appendChild(box);
  }

  function makeButton(text, secondary, onClick) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "button" + (secondary ? " secondary" : "");
    button.textContent = text;
    button.addEventListener("click", onClick);
    return button;
  }

  function setSending(value) {
    sending = value;
    // While the issues are being created nothing on the page may change.
    Array.prototype.forEach.call(form.querySelectorAll(".criterion-group"), function (group) { group.inert = value; });
    updateSendButton();
  }

  function send(sendAnyway) {
    if (sending) { return; }
    if (sendMessage.contains(document.activeElement)) { sendButton.focus(); }
    showMessage();
    setSending(true);
    flush()
      .then(function (saved) {
        if (!saved) { throw new Error("Save your changes first: " + saveStatus.textContent); }
        return fetch("/api/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ send_anyway: Boolean(sendAnyway) })
        });
      })
      .then(function (response) {
        return response.json().then(function (data) {
          if (response.ok && data.redirect) {
            window.location.assign(data.redirect);
            return;
          }
          setSending(false);
          if (data.needs_confirmation) {
            showMessage("heads-up", data.message, [
              makeButton("Send anyway", false, function () { send(true); }),
              makeButton("Wait", true, function () { sendButton.focus(); showMessage(); })
            ]);
            sendMessage.querySelector("button").focus();
          } else {
            showMessage("error", data.error || "Sending didn't work. Try again.");
          }
        });
      })
      .catch(function (error) {
        setSending(false);
        showMessage("error", error && error.message && error.message.indexOf("Save") === 0
          ? error.message
          : "Couldn't reach Repo Referee. Is the app still running?");
      });
  }

  sendButton.addEventListener("click", function () {
    if (sending) { return; }
    showProblems = true;
    var found = updateSendButton();
    var firstProblem = found.noPerson[0] || found.noTitle[0];
    if (firstProblem) {
      firstProblem.scrollIntoView({ behavior: "smooth", block: "center" });
      var focusTarget = found.noPerson[0] ? field(firstProblem, "owner_id") : field(firstProblem, "title");
      if (focusTarget) { focusTarget.focus({ preventScroll: true }); }
      return;
    }
    if (cards().length > 0) { send(false); }
  });

  // --- Wiring ----------------------------------------------------------------------------

  form.addEventListener("change", function (event) {
    if (event.target.name === "criterion_id") {
      moveToCriterionGroup(event.target.closest(".task"));
    }
    scheduleSave();
  });
  form.addEventListener("input", function (event) {
    if (event.target.matches("input[type=text], textarea")) { scheduleSave(); }
  });
  form.addEventListener("submit", function (event) { event.preventDefault(); });
  window.addEventListener("beforeunload", function (event) {
    if (saveTimer || saveRunning) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  updateEmptyNotes();
  updateFairShare();
  updateSendButton();
})();
