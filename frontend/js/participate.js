(function () {
  "use strict";

  const API = (window.SURVEY_API_BASE || "").replace(/\/$/, "");
  const $ = (id) => document.getElementById(id);

  let accessToken = sessionStorage.getItem("survey_access_token") || "";
  let refreshToken = sessionStorage.getItem("survey_refresh_token") || "";

  let survey = null;
  let questions = [];
  let participationId = null;
  let index = 0;
  const answers = {};       // question_id -> value

  function escapeHTML(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  function money(amount, currency) {
    return `${escapeHTML(currency || "KES")} ${Number(amount || 0).toLocaleString("en-KE", {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    })}`;
  }

  function showMessage(msg, isError = false) {
    const el = $("survey-message");
    el.textContent = msg;
    el.className = isError ? "message error" : "message";
    el.hidden = false;
  }

  function clearTokens() {
    accessToken = ""; refreshToken = "";
    sessionStorage.removeItem("survey_access_token");
    sessionStorage.removeItem("survey_refresh_token");
  }

  async function refreshAccessToken() {
    if (!refreshToken) return false;
    const res = await fetch(`${API}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    if (!res.ok) { clearTokens(); return false; }
    const data = await res.json();
    accessToken = data.access_token;
    refreshToken = data.refresh_token;
    sessionStorage.setItem("survey_access_token", accessToken);
    sessionStorage.setItem("survey_refresh_token", refreshToken);
    return true;
  }

  async function request(path, options = {}, retry = true) {
    const headers = new Headers(options.headers || {});
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const res = await fetch(`${API}${path}`, { ...options, headers });
    if (res.status === 401 && retry && await refreshAccessToken()) {
      return request(path, options, false);
    }
    if (!res.ok) {
      let detail = `Request failed (${res.status})`;
      let code = null;
      try {
        const data = await res.json();
        if (typeof data.detail === "string") detail = data.detail;
        else if (data.detail && typeof data.detail === "object") {
          detail = data.detail.message || detail;
          code = data.detail.code || null;
        }
      } catch (_) {}
      const err = new Error(detail);
      err.code = code;
      err.status = res.status;
      throw err;
    }
    if (res.status === 204) return null;
    return res.json();
  }

  function setProgress(current, total) {
    const pct = total ? Math.round((current / total) * 100) : 0;
    $("progress-fill").style.width = `${pct}%`;
    $("progress-label").textContent =
      total ? `Question ${current} of ${total}` : "";
  }

  function hideAll() {
    ["survey-loading", "survey-info", "question-view", "submitted-view", "disqualified-view"]
      .forEach((id) => { $(id).hidden = true; });
  }

  function showInfo() {
    hideAll();
    $("survey-info").hidden = false;
    $("survey-title").textContent = survey.title || "Survey";
    $("survey-description").textContent = survey.description || "";
    $("survey-minutes").textContent = survey.estimated_minutes
      ? `${survey.estimated_minutes} min` : "Time varies";
    $("survey-reward").textContent = money(survey.reward_amount, survey.reward_currency);
    $("survey-tier").textContent = String(survey.required_tier || "basic").toUpperCase();
    if (survey.instructions) {
      $("survey-instructions-wrap").hidden = false;
      $("survey-instructions").textContent = survey.instructions;
    }
    setProgress(0, questions.length);
  }

  let dwellTimer = null;
  function clearDwellTimer() {
    if (dwellTimer) { clearInterval(dwellTimer); dwellTimer = null; }
  }

  async function startDwellGate(q) {
    clearDwellTimer();
    const nextBtn = $("next-button");
    const label = q ? ` on question ${index + 1}` : "";
    try {
      const v = await request(
        `/api/participations/${participationId}/questions/${q.id}/view`,
        { method: "POST" }
      );
      // Compute remaining from server-returned first_shown_at.
      const firstShown = Date.parse(v.first_shown_at);
      const dwell = Number(v.dwell_seconds || 0) * 1000;
      const until = firstShown + dwell;

      function tick() {
        const remaining = until - Date.now();
        if (remaining <= 0) {
          clearDwellTimer();
          nextBtn.disabled = false;
          nextBtn.textContent = index === questions.length - 1 ? "Submit" : "Next";
          return;
        }
        nextBtn.disabled = true;
        nextBtn.textContent = `Wait ${Math.ceil(remaining / 1000)}s`;
      }
      tick();
      if (!nextBtn.disabled) return; // nothing to wait for
      dwellTimer = setInterval(tick, 250);
    } catch (e) {
      // If the view call fails, do not block the user indefinitely.
      // Server still enforces dwell on save.
      nextBtn.disabled = false;
    }
  }

  function renderQuestion() {
    hideAll();
    $("question-view").hidden = false;

    const q = questions[index];
    $("question-counter").textContent = `Question ${index + 1} of ${questions.length}`;
    $("question-prompt").textContent = q.prompt;
    if (q.help_text) {
      $("question-help").hidden = false;
      $("question-help").textContent = q.help_text;
    } else {
      $("question-help").hidden = true;
    }

    const cfg = q.config || {};
    const controls = $("question-controls");
    controls.innerHTML = "";
    const current = answers[q.id];

    if (q.question_type === "single_choice" || q.question_type === "dropdown" || q.question_type === "multi_select") {
      const isMulti = q.question_type === "multi_select";
      const opts = q.options || [];
      opts.forEach((opt) => {
        const label = document.createElement("label");
        label.className = "option-label";
        const input = document.createElement("input");
        input.type = isMulti ? "checkbox" : "radio";
        input.name = `q_${q.id}`;
        input.value = opt.id;
        const selectedIds = current || [];
        input.checked = selectedIds.includes(opt.id);
        if (input.checked) label.classList.add("is-selected");
        input.addEventListener("change", () => {
          if (isMulti) {
            const set = new Set(answers[q.id] || []);
            input.checked ? set.add(opt.id) : set.delete(opt.id);
            answers[q.id] = Array.from(set);
            label.classList.toggle("is-selected", input.checked);
          } else {
            answers[q.id] = [opt.id];
            controls.querySelectorAll(".option-label").forEach((l) => l.classList.remove("is-selected"));
            label.classList.add("is-selected");
          }
        });
        label.appendChild(input);
        const span = document.createElement("span");
        span.textContent = opt.label;
        label.appendChild(span);
        controls.appendChild(label);
      });
    } else if (q.question_type === "yes_no") {
      ["yes", "no"].forEach((v) => {
        const label = document.createElement("label");
        label.className = "option-label";
        const input = document.createElement("input");
        input.type = "radio"; input.name = `q_${q.id}`; input.value = v;
        if (current === v) { input.checked = true; label.classList.add("is-selected"); }
        input.addEventListener("change", () => {
          answers[q.id] = v;
          controls.querySelectorAll(".option-label").forEach((l) => l.classList.remove("is-selected"));
          label.classList.add("is-selected");
        });
        label.appendChild(input);
        const span = document.createElement("span");
        span.textContent = v === "yes" ? "Yes" : "No";
        label.appendChild(span);
        controls.appendChild(label);
      });
    } else if (q.question_type === "rating") {
      const min = Number(cfg.min_value ?? 1);
      const max = Number(cfg.max_value ?? 10);
      const row = document.createElement("div");
      row.className = "rating-row";
      for (let n = min; n <= max; n++) {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = n;
        if (current === n) b.classList.add("is-selected");
        b.addEventListener("click", () => {
          answers[q.id] = n;
          row.querySelectorAll("button").forEach((x) => x.classList.remove("is-selected"));
          b.classList.add("is-selected");
        });
        row.appendChild(b);
      }
      controls.appendChild(row);
    } else if (q.question_type === "date") {
      const input = document.createElement("input");
      input.type = "date";
      input.className = "text-input";
      input.value = current || "";
      input.addEventListener("change", () => { answers[q.id] = input.value; });
      controls.appendChild(input);
    } else {
      const long = q.question_type === "long_text";
      const input = document.createElement(long ? "textarea" : "input");
      if (long) { input.rows = 4; input.className = "textarea-input"; }
      else { input.type = "text"; input.className = "text-input"; }
      input.value = current || "";
      input.addEventListener("input", () => { answers[q.id] = input.value; });
      controls.appendChild(input);
    }

    $("back-button").disabled = index === 0;
    $("next-button").textContent = index === questions.length - 1 ? "Submit" : "Next";
    setProgress(index + 1, questions.length);
    startDwellGate(q);
  }

  function validate(q) {
    const value = answers[q.id];
    const required = !!q.is_required;
    const cfg = q.config || {};

    if (q.question_type === "single_choice" || q.question_type === "dropdown") {
      const ids = value || [];
      if (ids.length !== 1) return required ? "Please choose one answer." : null;
    } else if (q.question_type === "multi_select") {
      const ids = value || [];
      if (ids.length === 0 && required) return "Please choose at least one answer.";
    } else if (q.question_type === "yes_no") {
      if (!value && required) return "Please choose Yes or No.";
    } else if (q.question_type === "rating") {
      if (value == null && required) return "Please choose a rating.";
    } else if (q.question_type === "date") {
      if (!value && required) return "Please choose a date.";
      if (value && !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "Enter a valid date.";
    } else {
      const text = (value || "").toString().trim();
      if (!text && required) return "Please answer this question.";
      const min = Number(cfg.min_length ?? 0);
      const max = Number(cfg.max_length ?? (q.question_type === "short_text" ? 500 : 10000));
      if (text.length < min) return `Answer must be at least ${min} characters.`;
      if (text.length > max) return `Answer must be at most ${max} characters.`;
    }
    return null;
  }

  function payloadFor(q) {
    const value = answers[q.id];
    if (q.question_type === "single_choice" || q.question_type === "dropdown" || q.question_type === "multi_select") {
      return { question_id: q.id, selected_option_ids: value || [] };
    }
    if (q.question_type === "rating") {
      return { question_id: q.id, rating_value: value ?? null };
    }
    return { question_id: q.id, answer_text: (value ?? "").toString() };
  }

  async function saveCurrentAnswer() {
    const q = questions[index];
    const body = { answers: [payloadFor(q)] };
    const res = await request(`/api/participations/${participationId}/responses`, {
      method: "PUT", body: JSON.stringify(body)
    });
    if (res && res.status === "disqualified") {
      showDisqualified(res.message || "You do not meet the eligibility requirements for this survey.");
      return false;
    }
    return true;
  }

  function showDisqualified(msg) {
    hideAll();
    $("disqualified-view").hidden = false;
    $("disqualified-message").textContent = msg;
    setProgress(questions.length, questions.length);
  }

  function showSubmitted(msg) {
    hideAll();
    $("submitted-view").hidden = false;
    $("submitted-message").textContent = msg || "Thank you for completing this survey.";
    setProgress(questions.length, questions.length);
  }

  async function onStart() {
    $("start-button").disabled = true;
    try {
      const p = await request(`/api/surveys/${survey.id}/participations`, { method: "POST" });
      participationId = p.id;

      if (!questions.length) {
        await request(`/api/participations/${participationId}/submit`, { method: "POST" });
        showSubmitted();
        return;
      }

      // Resume: load any previously saved answers.
      let firstUnanswered = 0;
      try {
        const saved = await request(`/api/participations/${participationId}/responses`);
        const byId = {};
        (saved || []).forEach(r => { byId[r.question_id] = r; });
        for (let i = 0; i < questions.length; i++) {
          const q = questions[i];
          const r = byId[q.id];
          if (!r) { firstUnanswered = i; break; }
          if (q.question_type === "single_choice" || q.question_type === "dropdown" || q.question_type === "multi_select") {
            answers[q.id] = r.selected_option_ids || [];
          } else if (q.question_type === "rating") {
            answers[q.id] = r.rating_value;
          } else {
            answers[q.id] = r.answer_text;
          }
          firstUnanswered = i + 1;
        }
        if (firstUnanswered < questions.length) {
          showMessage(`Resuming — you've completed ${firstUnanswered} of ${questions.length}.`, false);
        }
      } catch (_) { /* ignore resume errors, start at 0 */ }

      index = firstUnanswered < questions.length ? firstUnanswered : 0;
      renderQuestion();
    } catch (e) {
      showMessage(e.message || "Could not start this survey.", true);
      $("start-button").disabled = false;
    }
  }

  async function onNext() {
    const q = questions[index];
    const problem = validate(q);
    if (problem) { showMessage(problem, true); return; }

    $("next-button").disabled = true;
    try {
      const ok = await saveCurrentAnswer();
      if (!ok) return;

      if (index < questions.length - 1) {
        index++;
        showMessage("", false); $("survey-message").hidden = true;
        renderQuestion();
        return;
      }

      const submit = await request(`/api/participations/${participationId}/submit`, { method: "POST" });
      if (submit.status === "disqualified") {
        showDisqualified("Your answers did not pass this survey's quality checks.");
      } else {
        showSubmitted("Your responses have been submitted for review.");
      }
    } catch (e) {
      showMessage(e.message || "Could not save your answer.", true);
    } finally {
      $("next-button").disabled = false;
    }
  }

  function onBack() {
    if (index === 0) return;
    index--;
    $("survey-message").hidden = true;
    renderQuestion();
  }

  async function init() {
    const params = new URLSearchParams(window.location.search);
    const surveyId = params.get("survey");
    if (!surveyId) {
      $("survey-loading").textContent = "No survey specified.";
      return;
    }
    if (!accessToken && refreshToken) await refreshAccessToken();
    if (!accessToken) {
      window.location.replace("dashboard.html");
      return;
    }

    try {
      survey = await request(`/api/surveys/${surveyId}`);
      questions = await request(`/api/surveys/${surveyId}/questions`);
      questions.sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0));
      $("survey-loading").hidden = true;
      showInfo();
    } catch (e) {
      $("survey-loading").hidden = true;
      if (e.code === "upgrade_required" || e.status === 403) {
        showMessage(e.message || "Upgrade your membership to take this survey.", true);
        const link = document.createElement("a");
        link.href = "dashboard.html";
        link.className = "primary-button";
        link.textContent = "Back to dashboard";
        link.style.marginTop = "16px";
        link.style.display = "inline-block";
        $("survey-message").after(link);
      } else {
        showMessage(e.message || "Could not load this survey.", true);
      }
    }
  }

  $("start-button").addEventListener("click", onStart);
  $("next-button").addEventListener("click", onNext);
  $("back-button").addEventListener("click", onBack);
  $("exit-button").addEventListener("click", () => {
    if (confirm("Leave this survey? Your saved answers are kept.")) {
      window.location.href = "dashboard.html";
    }
  });

  init();
})();
