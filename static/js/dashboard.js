// Dashboard: ask the backend for the live status (on open, every POLL_SECONDS and when the
// tab comes back into view) and redraw the bars and squares. Nothing here changes a task's
// status: that only ever comes from GitHub.
(function () {
  "use strict";

  var root = document.getElementById("dashboard");
  var POLL_MS = (Number(root.dataset.pollSeconds) || 10) * 1000;
  var els = {
    feedback: document.getElementById("feedback"),
    overall: document.getElementById("overall"),
    overallBar: document.getElementById("overall-bar"),
    criteria: document.getElementById("criteria"),
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

  function renderCriteria(data) {
    var totals = data.totals;
    els.overall.textContent = (totals.percent === null ? "No tasks" : "Overall · " + totals.percent + "%") +
      " · " + totals.tasks_closed + " / " + plural(totals.tasks_total, "task", "tasks") + " closed";
    if (!els.overallBar.firstChild) { els.overallBar.appendChild(bar(totals.percent)); }
    setBar(els.overallBar.firstChild, totals.percent);
    els.overallBar.firstChild.setAttribute("aria-label", "Overall progress");

    var loading = els.criteria.querySelector(".loading-row");
    if (loading) { loading.remove(); }
    data.criteria.forEach(function (criterion) {
      var row = keyed(els.criteria, criterion.id, function () {
        var li = make("li", "criterion-row");
        var head = make("div", "criterion-row-head");
        head.appendChild(make("span", "criterion-name"));
        head.appendChild(make("span", "criterion-value"));
        li.appendChild(head);
        li.appendChild(bar(criterion.percent));
        els.criteria.appendChild(li);
        return li;
      });
      var label = "Criterion " + criterion.number + " · " + criterion.title;
      row.querySelector(".criterion-name").textContent = label;
      var value = row.querySelector(".criterion-value");
      if (criterion.percent === null) {
        value.textContent = "No tasks";
      } else {
        value.textContent = criterion.percent + "%";
        value.title = criterion.done_points + " of " + criterion.total_points + " points done";
      }
      setBar(row.querySelector(".bar"), criterion.percent);
      row.querySelector(".bar").setAttribute("aria-label", label);
      row.classList.toggle("no-tasks", criterion.percent === null);
    });

    els.droppedNote.hidden = !data.dropped_note;
    els.droppedNote.textContent = data.dropped_note || "";
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
    fetch("/api/status", { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (response.status === 409 && data.redirect) {
            window.location.assign(data.redirect);
            return;
          }
          appUnreachable = false;
          if (!response.ok) { throw new Error(data.error || "Couldn't reach GitHub."); }
          renderFeedback(data.feedback);
          renderCriteria(data);
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
          [els.criteria, els.people].forEach(function (list) {
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

  // --- Weekly summary --------------------------------------------------------------------

  var openButton = document.getElementById("start-over-open");
  var summaryButton = document.getElementById("summary-button");
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
              make("p", "summary-meta muted", data.summary.period_label + " · Written by Claude from your closed issues")
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
