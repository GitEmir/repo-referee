// Dashboard: ask the backend for the live status (on open, every POLL_SECONDS and when the
// tab comes back into view) and redraw the board, the bars and the squares. Nothing here changes a task's
// status: that only ever comes from GitHub.
(function () {
  "use strict";

  var root = document.getElementById("dashboard");
  var POLL_MS = (Number(root.dataset.pollSeconds) || 10) * 1000;
  var STATUS_URL = root.dataset.statusUrl || "/api/status"; // the view-only board has its own
  var els = {
    feedback: document.getElementById("feedback"),
    overall: document.getElementById("overall"),
    overallBar: document.getElementById("overall-bar"),
    board: document.getElementById("board"),
    droppedNote: document.getElementById("dropped-note"),
    people: document.getElementById("people"),
    sync: document.getElementById("sync"),
    syncText: document.getElementById("sync-text")
  };

  var inFlight = false;
  var lastSuccess = null; // time of the last good answer, in ms
  var problem = null; // the message of the last failed refresh, if the latest one failed
  var appUnreachable = false; // true when Repo Referee itself didn't answer, not GitHub
  var previousStates = {}; // task id -> state, to make squares that just turned done pop
  var firstRender = true;

  // --- Small DOM helpers -----------------------------------------------------------------

  function make(tag, className, text) {
    var element = document.createElement(tag);
    if (className) { element.className = className; }
    if (text !== undefined && text !== null) { element.textContent = text; }
    return element;
  }

  function keyed(container, key, create) {
    var existing = container.querySelector('[data-key="' + key + '"]');
    if (existing) { return existing; }
    var element = create();
    element.dataset.key = key;
    return element;
  }

  function plural(count, one, many) {
    return count + " " + (count === 1 ? one : many);
  }

  // --- Feedback --------------------------------------------------------------------------

  var FEEDBACK_STYLE = {
    celebration: { className: "celebrate", icon: "ti-confetti" },
    tip: { className: "heads-up", icon: "ti-users" },
    info: { className: "info", icon: "ti-info-circle" }
  };
  var lastFeedback = "";

  function renderFeedback(messages) {
    var key = JSON.stringify(messages || []);
    if (key === lastFeedback) { return; } // only redraw when something changed
    lastFeedback = key;
    els.feedback.textContent = "";
    (messages || []).forEach(function (message) {
      var style = FEEDBACK_STYLE[message.kind] || FEEDBACK_STYLE.info;
      var item = make("li", "message " + style.className);
      var icon = make("i", "ti " + style.icon);
      icon.setAttribute("aria-hidden", "true");
      item.appendChild(icon);
      item.appendChild(make("span", null, message.text));
      els.feedback.appendChild(item);
    });
  }

  // --- Progress per criterion ------------------------------------------------------------

  function bar(percent) {
    var track = make("div", "bar");
    var fill = make("div", "bar-fill");
    track.appendChild(fill);
    setBar(track, percent);
    return track;
  }

  function setBar(track, percent) {
    var value = percent === null ? 0 : percent;
    track.querySelector(".bar-fill").style.width = value + "%";
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", "100");
    track.setAttribute("aria-valuenow", String(value));
    track.classList.toggle("complete", value === 100);
  }

  function renderOverall(data) {
    var totals = data.totals;
    els.overall.textContent = (totals.percent === null ? "No tasks" : "Overall · " + totals.percent + "%") +
      " · " + totals.tasks_closed + " / " + plural(totals.tasks_total, "task", "tasks") + " closed";
    if (!els.overallBar.firstChild) { els.overallBar.appendChild(bar(totals.percent)); }
    setBar(els.overallBar.firstChild, totals.percent);
    els.overallBar.firstChild.setAttribute("aria-label", "Overall progress");
    els.droppedNote.hidden = !data.dropped_note;
    els.droppedNote.textContent = data.dropped_note || "";
  }

  // --- The board: one column per criterion, one card per task -----------------------------

  var COLUMN_COLORS = 6; // style.css has .col-color-0 … .col-color-5
  var PERSON_COLORS = 5; // and .person-color-0 … .person-color-4
  var STATE_TEXT = { done: "done", dropped: "not planned", missing: "issue not found", open: "open" };

  // Cards are updated in place (keyed by task id), so a focused card keeps its focus while
  // the page refreshes; a card that just turned done pops once.
  function updateCard(card, task) {
    card.className = "board-card-item " + task.state + " person-color-" + (task.person_index % PERSON_COLORS);
    card.querySelector(".board-card-title").textContent = task.title;
    var avatar = card.querySelector(".board-avatar");
    avatar.textContent = (task.person || "?").trim().slice(0, 1).toUpperCase();
    var label = (task.issue_number ? "#" + task.issue_number + " " : "") + task.title + " · " + task.person +
      " · weight " + task.weight + " · " + (STATE_TEXT[task.state] || "open");
    card.title = label;
    card.setAttribute("aria-label", label);
    if (task.url) {
      card.href = task.url;
      card.target = "_blank";
      card.rel = "noopener noreferrer";
    }
    if (!firstRender && task.state === "done" && previousStates[task.id] && previousStates[task.id] !== "done") {
      card.classList.add("pop");
    }
  }

  function renderCards(container, tasks) {
    var wanted = tasks.map(function (task) { return task.id; }).join(",");
    if (container.dataset.tasks !== wanted) {
      // The set of tasks changed (rare): rebuild the column's cards once.
      container.textContent = "";
      if (tasks.length === 0) { container.appendChild(make("p", "muted board-empty", "No tasks")); }
      tasks.forEach(function (task) {
        var card = make(task.url ? "a" : "div", "board-card-item");
        card.dataset.taskId = task.id;
        var check = make("i", "ti ti-circle-check board-card-check");
        check.setAttribute("aria-hidden", "true");
        card.appendChild(check);
        card.appendChild(make("span", "board-card-title"));
        card.appendChild(make("span", "board-avatar")).setAttribute("aria-hidden", "true");
        container.appendChild(card);
      });
      container.dataset.tasks = wanted;
    }
    tasks.forEach(function (task) {
      var card = container.querySelector('[data-task-id="' + task.id + '"]');
      if (card) { updateCard(card, task); }
    });
  }

  function renderBoard(data) {
    var loading = els.board.querySelector(".loading-row");
    if (loading) { loading.remove(); }
    data.criteria.forEach(function (criterion, index) {
      var column = keyed(els.board, criterion.id, function () {
        var section = make("section", "board-column col-color-" + (index % COLUMN_COLORS));
        var head = make("header", "board-column-head");
        head.appendChild(make("h3", "board-column-title"));
        head.appendChild(make("span", "board-column-count mono-numbers"));
        section.appendChild(head);
        section.appendChild(make("div", "board-cards"));
        els.board.appendChild(section);
        return section;
      });
      var label = criterion.number + " · " + criterion.title;
      column.querySelector(".board-column-title").textContent = label;
      column.setAttribute("aria-label", "Criterion " + label);
      var count = column.querySelector(".board-column-count");
      count.textContent = criterion.tasks_done + "/" + criterion.tasks_total;
      count.title = criterion.percent === null ? "No tasks"
        : criterion.percent + "% · " + criterion.done_points + " of " + criterion.total_points + " points done";
      column.classList.toggle("complete", criterion.percent === 100);
      renderCards(column.querySelector(".board-cards"), (data.board || {})[criterion.id] || []);
    });
  }

  // --- Contribution per person -----------------------------------------------------------

  function squareShade(task) {
    if (task.state !== "done") { return "sq-0"; }
    return "sq-" + Math.min(task.weight, 4);
  }

  // Squares are updated in place (keyed by task id), so a focused square keeps its focus
  // and a hover tooltip stays open while the page refreshes.
  function updateSquare(link, task) {
    if (task.url) {
      link.href = task.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    var state = task.state === "done" ? "done" : task.state === "missing" ? "issue not found" : "open";
    var label = "#" + task.issue_number + " " + task.title + " · weight " + task.weight + " · " + state;
    link.className = "square " + squareShade(task) + (task.state === "missing" ? " missing" : "");
    link.title = label;
    link.setAttribute("aria-label", label);
    if (!firstRender && task.state === "done" && previousStates[task.id] && previousStates[task.id] !== "done") {
      link.classList.add("pop");
    }
  }

  function renderSquares(container, tasks) {
    var wanted = tasks.map(function (task) { return task.id; }).join(",");
    if (container.dataset.tasks !== wanted) {
      // The set of tasks changed (rare): rebuild the row once.
      container.textContent = "";
      if (tasks.length === 0) { container.appendChild(make("span", "muted no-squares", "No tasks")); }
      tasks.forEach(function (task) {
        var link = make(task.url ? "a" : "span", "square");
        link.dataset.taskId = task.id;
        container.appendChild(link);
      });
      container.dataset.tasks = wanted;
    }
    tasks.forEach(function (task) {
      var link = container.querySelector('[data-task-id="' + task.id + '"]');
      if (link) { updateSquare(link, task); }
    });
  }

  function renderPeople(data) {
    var loading = els.people.querySelector(".loading-row");
    if (loading) { loading.remove(); }
    data.people.forEach(function (person) {
      var row = keyed(els.people, person.id, function () {
        var li = make("li", "person");
        li.appendChild(make("span", "avatar", person.name.slice(0, 1).toUpperCase())).setAttribute("aria-hidden", "true");
        var who = make("div", "person-who");
        who.appendChild(make("span", "person-name"));
        who.appendChild(make("span", "mono muted person-github"));
        li.appendChild(who);
        li.appendChild(make("div", "squares"));
        li.appendChild(make("span", "points"));
        els.people.appendChild(li);
        return li;
      });
      row.querySelector(".person-name").textContent = person.name;
      row.querySelector(".person-github").textContent = "@" + person.github;
      renderSquares(row.querySelector(".squares"), person.tasks);
      row.querySelector(".points").textContent = person.done_points + (person.done_points === 1 ? " pt" : " pts");
      row.querySelector(".points").title = person.done_points + " of " + person.chosen_points + " chosen points done";
    });
    data.people.forEach(function (person) {
      person.tasks.forEach(function (task) { previousStates[task.id] = task.state; });
    });
  }

  // --- The "synced 8s ago" footer --------------------------------------------------------

  function ago(ms) {
    var seconds = Math.max(0, Math.round(ms / 1000));
    if (seconds < 60) { return seconds + "s ago"; }
    var minutes = Math.round(seconds / 60);
    if (minutes < 60) { return minutes + " min ago"; }
    return Math.round(minutes / 60) + " h ago";
  }

  function renderFooter() {
    var now = Date.now();
    if (problem) {
      els.sync.classList.add("offline");
      var what = appUnreachable ? "Couldn't reach Repo Referee" : "Couldn't reach GitHub";
      els.syncText.textContent = lastSuccess
        ? what + " · showing the status from " + ago(now - lastSuccess)
        : problem;
    } else if (lastSuccess) {
      els.sync.classList.remove("offline");
      els.syncText.textContent = "synced " + ago(now - lastSuccess);
    }
  }

  // --- Refreshing ------------------------------------------------------------------------

  function refresh() {
    if (inFlight) { return; }
    inFlight = true;
    fetch(STATUS_URL, { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (response.status === 409 && data.redirect) {
            window.location.assign(data.redirect);
            return;
          }
          appUnreachable = false;
          if (!response.ok) { throw new Error(data.error || "Couldn't reach GitHub."); }
          renderFeedback(data.feedback);
          renderOverall(data);
          renderBoard(data);
          renderPeople(data);
          firstRender = false;
          lastSuccess = Date.now();
          problem = null;
        });
      })
      .catch(function (error) {
        if (error instanceof TypeError) {
          // fetch itself failed: the app isn't answering (stopped, or the laptop is offline).
          appUnreachable = true;
          problem = "Couldn't reach Repo Referee. Is the app still running?";
        } else {
          problem = (error && error.message) || "Couldn't reach GitHub.";
        }
        if (!lastSuccess) {
          [els.board, els.people].forEach(function (list) {
            var loading = list.querySelector(".loading-row");
            if (loading) { loading.textContent = problem; }
          });
        }
      })
      .then(function () {
        inFlight = false;
        renderFooter();
      });
  }

  refresh();
  setInterval(refresh, POLL_MS);
  setInterval(renderFooter, 1000);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") { refresh(); }
  });

  // --- Share board: copy the view-only link -----------------------------------------------

  var copyButton = document.getElementById("share-copy");
  if (copyButton) {
    copyButton.addEventListener("click", function () {
      var input = document.getElementById("share-link");
      var label = copyButton.querySelector("span");
      input.select();
      var copied = navigator.clipboard ? navigator.clipboard.writeText(input.value) : Promise.reject();
      copied
        .catch(function () { document.execCommand("copy"); })
        .then(function () {
          label.textContent = "Copied";
          setTimeout(function () { label.textContent = "Copy link"; }, 2000);
        });
    });
  }

  // The view-only board has no buttons that change the project: stop here.
  var openButton = document.getElementById("start-over-open");
  var summaryButton = document.getElementById("summary-button");
  if (!openButton || !summaryButton) { return; }

  // --- Weekly summary --------------------------------------------------------------------

  var summaryBox = document.getElementById("summary");
  var summaryNote = document.getElementById("summary-note");
  var summaryBusy = false;

  function showSummary(parts) {
    summaryBox.textContent = "";
    parts.forEach(function (part) { summaryBox.appendChild(part); });
  }

  // Errors and "nothing closed yet" go above the summary, so the last one stays visible.
  function showSummaryNote(kind, text) {
    summaryNote.hidden = !text;
    summaryNote.className = "summary-note message " + (kind || "");
    summaryNote.textContent = text || "";
  }

  summaryButton.addEventListener("click", function () {
    if (summaryBusy) { return; }
    summaryBusy = true;
    openButton.disabled = true; // don't start a new project while the summary is being written
    showSummaryNote();
    var label = summaryButton.querySelector("span");
    label.textContent = "Writing the summary…";
    summaryButton.setAttribute("aria-disabled", "true");
    fetch("/api/summary", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      .then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (!response.ok) {
            showSummaryNote("error", data.error || "Writing the summary didn't work this time. Try again.");
          } else if (data.summary) {
            showSummary([
              make("p", "summary-text", data.summary.text),
              make("p", "summary-meta muted", data.summary.period_label + " · Written by AI from your closed issues")
            ]);
          } else {
            showSummaryNote("info", data.message);
          }
        });
      })
      .catch(function () {
        showSummaryNote("error", "Couldn't reach Repo Referee. Is the app still running?");
      })
      .then(function () {
        summaryBusy = false;
        openButton.disabled = false;
        label.textContent = "Write weekly summary";
        summaryButton.setAttribute("aria-disabled", "false");
      });
  });

  // --- Start a new project ---------------------------------------------------------------

  var confirmBox = document.getElementById("start-over-confirm");
  var yesButton = document.getElementById("start-over-yes");
  var noButton = document.getElementById("start-over-no");
  var resetError = document.getElementById("start-over-error");

  openButton.addEventListener("click", function () {
    confirmBox.hidden = false;
    openButton.hidden = true;
    noButton.focus();
  });
  noButton.addEventListener("click", function () {
    confirmBox.hidden = true;
    openButton.hidden = false;
    openButton.focus();
  });
  yesButton.addEventListener("click", function () {
    yesButton.disabled = true;
    resetError.hidden = true;
    fetch("/api/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      .then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (!response.ok || !data.redirect) { throw new Error(data.error || "Starting a new project didn't work. Try again."); }
          window.location.assign(data.redirect);
        });
      })
      .catch(function (error) {
        yesButton.disabled = false;
        resetError.textContent = error instanceof TypeError
          ? "Couldn't reach Repo Referee. Is the app still running?"
          : error.message;
        resetError.hidden = false;
        yesButton.focus();
      });
  });
})();
