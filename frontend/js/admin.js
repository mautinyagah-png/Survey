(function () {
  "use strict";

  const API = (window.SURVEY_API_BASE || "").replace(/\/$/, "");
  const $ = (id) => document.getElementById(id);
  let accessToken = sessionStorage.getItem("survey_access_token") || "";
  let refreshToken = sessionStorage.getItem("survey_refresh_token") || "";
  let surveys = [];
  let pendingRewards = [];
  let withdrawals = [];
  let selectedSurvey = "";
  let currentUser = null;

  function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  function money(amount, currency = "KES") {
    return `${escapeHTML(currency)} ${Number(amount || 0).toLocaleString("en-KE", {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    })}`;
  }

  function showMessage(message, error = false) {
    const el = $("page-message");
    el.textContent = message;
    el.className = error ? "message error" : "message";
    el.hidden = false;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function refreshAccessToken() {
    if (!refreshToken) return false;
    const response = await fetch(`${API}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    if (!response.ok) {
      clearTokens();
      return false;
    }
    const data = await response.json();
    accessToken = data.access_token;
    refreshToken = data.refresh_token;
    sessionStorage.setItem("survey_access_token", accessToken);
    sessionStorage.setItem("survey_refresh_token", refreshToken);
    return true;
  }

  function clearTokens() {
    accessToken = "";
    refreshToken = "";
    sessionStorage.removeItem("survey_access_token");
    sessionStorage.removeItem("survey_refresh_token");
  }

  async function request(path, options = {}, retry = true) {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${API}${path}`, { ...options, headers });
    if (response.status === 401 && retry && await refreshAccessToken()) {
      return request(path, options, false);
    }

    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try {
        const data = await response.json();
        detail = data.detail || data.message || detail;
      } catch (_) {}
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    if (response.status === 204) return null;
    return response.json();
  }

  function itemsOf(data) {
    if (Array.isArray(data)) return data;
    return data?.items || data?.surveys || [];
  }

  function setView(name) {
    const titles = {
      overview: "Overview", surveys: "Survey management",
      questions: "Question management", rewards: "Reward approvals",
      withdrawals: "Withdrawal management", payments: "Payment records", respondents: "Respondent management"
    };
    document.querySelectorAll(".view").forEach(el => {
      el.hidden = el.id !== `view-${name}`;
    });
    document.querySelectorAll(".nav-item").forEach(el => {
      el.classList.toggle("active", el.dataset.view === name);
    });
    $("page-title").textContent = titles[name] || "Overview";
    $("sidebar").classList.remove("open");

    if (name === "surveys") loadSurveys();
    if (name === "rewards") loadRewards();
    if (name === "withdrawals") loadWithdrawals();
    if (name === "respondents") loadRespondents();
    if (name === "payments") loadPayments();
  }

  function surveyTable(rows, target) {
    const el = $(target);
    if (!rows.length) {
      el.innerHTML = '<p class="empty-state">No surveys found. Create your first survey to get started.</p>';
      return;
    }
    el.innerHTML = `<table><thead><tr><th>Survey</th><th>Tier</th><th>Reward</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      ${rows.map(s => `<tr>
        <td><strong>${escapeHTML(s.title)}</strong><br><small>${escapeHTML(s.slug || s.id)}</small></td>
        <td>${escapeHTML(s.required_tier || "basic")}</td>
        <td>${money(s.reward_amount, s.reward_currency)}</td>
        <td><span class="status ${escapeHTML(s.status)}">${escapeHTML(s.status)}</span></td>
        <td><div class="action-row">
          <button class="small-button" data-action="questions" data-id="${escapeHTML(s.id)}">Questions</button>
          ${s.status === "draft" ? `<button class="small-button green" data-action="publish" data-id="${escapeHTML(s.id)}">Publish</button>` : ""}
          ${s.status === "published" ? `<button class="small-button" data-action="close" data-id="${escapeHTML(s.id)}">Close</button>` : ""}
          ${["closed","draft"].includes(s.status) ? `<button class="small-button red" data-action="archive" data-id="${escapeHTML(s.id)}">Archive</button>` : ""}
        </div></td>
      </tr>`).join("")}</tbody></table>`;
  }

  async function loadSurveys() {
    $("surveys-table").innerHTML = '<p class="loading">Loading surveys...</p>';
    try {
      const data = await request("/api/surveys/admin/all");
      surveys = itemsOf(data);
      surveyTable(surveys, "surveys-table");
      $("question-survey").innerHTML = '<option value="">Select a survey</option>' +
        surveys.map(s => `<option value="${escapeHTML(s.id)}">${escapeHTML(s.title)}</option>`).join("");
      $("stat-surveys").textContent = surveys.length;
      $("stat-published").textContent = surveys.filter(s => s.status === "published").length;
      surveyTable(surveys.slice(0, 5), "overview-surveys");
    } catch (e) {
      $("surveys-table").innerHTML = `<p class="empty-state">${escapeHTML(e.message)}</p>`;
      showMessage(e.message, true);
    }
  }

  async function createSurvey(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const body = {
      title: data.get("title").trim(),
      required_tier: data.get("required_tier"),
      reward_amount: Number(data.get("reward_amount") || 0),
      reward_currency: "KES",
      description: data.get("description") || null,
      instructions: data.get("instructions") || null,
      estimated_minutes: data.get("estimated_minutes") ? Number(data.get("estimated_minutes")) : null,
      country_code: data.get("country_code") ? data.get("country_code").trim().toUpperCase() : null,
      target_audience: data.get("target_audience") || null,
      participant_target: data.get("participant_target") ? Number(data.get("participant_target")) : null
    };
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await request("/api/surveys/", { method: "POST", body: JSON.stringify(body) });
      form.reset();
      form.hidden = true;
      showMessage("Survey draft created successfully. Add questions before publishing.");
      await loadSurveys();
    } catch (e) {
      showMessage(e.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function surveyAction(action, id) {
    const paths = {
      publish: `/api/surveys/${id}/publish`,
      close: `/api/surveys/${id}/close`,
      archive: `/api/surveys/${id}/archive`
    };
    const labels = { publish: "publish", close: "close", archive: "archive" };
    if (!paths[action] || !confirm(`Are you sure you want to ${labels[action]} this survey?`)) return;
    try {
      await request(paths[action], { method: "POST" });
      showMessage(`Survey ${labels[action]} action completed.`);
      await loadSurveys();
    } catch (e) {
      showMessage(e.message, true);
    }
  }

  async function loadQuestions(surveyId) {
    selectedSurvey = surveyId;
    const workspace = $("question-workspace");
    if (!surveyId) {
      workspace.innerHTML = '<p class="empty-state">Choose a survey to view and manage its questions.</p>';
      return;
    }
    workspace.innerHTML = '<p class="loading">Loading questions...</p>';
    try {
      const data = await request(`/api/admin/surveys/${surveyId}/questions`);
      const questions = itemsOf(data);
      workspace.innerHTML = `
        <div class="panel-heading"><div><h3>Survey questions</h3><p>${questions.length} question(s) configured.</p></div></div>
        <div id="question-list">${questions.length ? questions.map((q, i) => `
          <div class="question-form">
            <strong>${i + 1}. ${escapeHTML(q.prompt)}</strong>
            <p class="muted">${escapeHTML(q.question_type)} · ${q.is_required ? "Required" : "Optional"} · ${q.options?.length || 0} options</p>
            <button class="small-button red" data-action="delete-question" data-id="${escapeHTML(q.id)}">Delete question</button>
          </div>`).join("") : '<p class="empty-state">No questions yet. Add your first question below.</p>'}</div>
        <div class="question-form" id="question-bank-panel">
          <h3>Generate questions from the question bank</h3>
          <p class="muted">Choose one or more categories and the number of questions to add to this draft.</p>
          <div id="bank-category-list"><p class="loading">Loading question bank categories...</p></div>
          <form id="bank-generate-form">
            <div class="form-grid">
              <label>Number of questions
                <input name="question_count" type="number" min="1" max="100" value="10" required>
              </label>
              <label><span><input type="checkbox" name="shuffle" checked style="width:auto"> Randomise question selection</span></label>
            </div>
            <div class="form-actions">
              <button class="primary-button" type="submit">Generate questions</button>
            </div>
          </form>
          <p class="muted">Generated questions are added to this draft only. Review them before publishing.</p>
        </div>
        <form id="question-form" class="question-form">
          <h3>Add a question</h3>
          <div class="form-grid">
            <label class="full">Question prompt<input name="prompt" required maxlength="5000" placeholder="Enter your question"></label>
            <label>Question type<select name="question_type">
              <option value="single_choice">Single choice</option><option value="multi_select">Multiple selection</option>
              <option value="yes_no">Yes / No</option><option value="rating">Rating</option>
              <option value="short_text">Short text</option><option value="long_text">Long text</option>
              <option value="dropdown">Dropdown</option><option value="date">Date</option>
            </select></label>
            <label>Answer options<textarea name="options" rows="3" placeholder="One option per line (for choice questions)"></textarea></label>
            <label class="full"><span><input type="checkbox" name="is_required" checked style="width:auto"> Required question</span></label>
          </div>
          <div class="form-actions"><button class="primary-button" type="submit">Add question</button></div>
        </form>`;
      await loadBankTitles();
    } catch (e) {
      workspace.innerHTML = `<p class="empty-state">${escapeHTML(e.message)}</p>`;
    }
  }

  async function loadBankTitles() {
    const container = $("bank-category-list");
    try {
      const titles = itemsOf(await request("/api/admin/question-bank/titles?active_only=true"));

      if (!titles.length) {
        container.innerHTML = '<p class="empty-state">No active question-bank categories yet. Add categories and questions to the bank first.</p>';
        return;
      }

      container.innerHTML = `
        <div class="form-grid">
          ${titles.map(title => `
            <label>
              <span>
                <input type="checkbox" name="bank_title_ids" value="${escapeHTML(title.id)}" style="width:auto">
                ${escapeHTML(title.title)}
              </span>
              <small class="muted">${Number(title.question_count || 0)} available question(s)</small>
            </label>
          `).join("")}
        </div>`;
    } catch (e) {
      container.innerHTML = `<p class="empty-state">${escapeHTML(e.message || "Could not load question bank categories.")}</p>`;
    }
  }

  async function generateBankQuestions(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const titleIds = [...form.querySelectorAll('input[name="bank_title_ids"]:checked')]
      .map(input => input.value);

    if (!titleIds.length) {
      showMessage("Select at least one question-bank category.", true);
      return;
    }

    const count = Number(form.querySelector('[name="question_count"]').value);
    if (!Number.isInteger(count) || count < 1 || count > 100) {
      showMessage("Choose a question count between 1 and 100.", true);
      return;
    }

    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = "Generating...";

    try {
      const result = await request(
        `/api/admin/question-bank/surveys/${selectedSurvey}/generate`,
        {
          method: "POST",
          body: JSON.stringify({
            title_ids: titleIds,
            question_count: count,
            shuffle: form.querySelector('[name="shuffle"]').checked
          })
        }
      );

      showMessage(`${result.created_count} question(s) generated successfully. Review them before publishing.`);
      await loadQuestions(selectedSurvey);
    } catch (e) {
      showMessage(e.message || "Question generation failed.", true);
      button.disabled = false;
      button.textContent = "Generate questions";
    }
  }

  async function createQuestion(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const type = data.get("question_type");
    const optionLabels = String(data.get("options") || "").split("\n").map(x => x.trim()).filter(Boolean);
    const needsOptions = ["single_choice", "multi_select", "dropdown"].includes(type);
    if (needsOptions && optionLabels.length < 2) {
      showMessage("Choice and dropdown questions require at least two answer options.", true);
      return;
    }
    const body = {
      question_type: type,
      prompt: data.get("prompt").trim(),
      is_required: data.get("is_required") === "on",
      options: needsOptions ? optionLabels.map(x => ({ label: x, value: x })) : []
    };
    try {
      await request(`/api/admin/surveys/${selectedSurvey}/questions`, {
        method: "POST", body: JSON.stringify(body)
      });
      showMessage("Question added successfully.");
      await loadQuestions(selectedSurvey);
    } catch (e) {
      showMessage(e.message, true);
    }
  }

  async function deleteQuestion(id) {
    if (!confirm("Delete this question? This action cannot be undone.")) return;
    try {
      await request(`/api/admin/questions/${id}`, { method: "DELETE" });
      showMessage("Question deleted.");
      await loadQuestions(selectedSurvey);
    } catch (e) {
      showMessage(e.message, true);
    }
  }

  async function loadRewards() {
    $("rewards-table").innerHTML = '<p class="loading">Loading pending rewards...</p>';
    try {
      pendingRewards = itemsOf(await request("/api/admin/rewards/pending?limit=100&offset=0"));
      $("stat-rewards").textContent = pendingRewards.length;
      $("reward-nav-count").textContent = pendingRewards.length;
      if (!pendingRewards.length) {
        $("rewards-table").innerHTML = '<p class="empty-state">No pending rewards require review. Great work!</p>';
        return;
      }
      $("rewards-table").innerHTML = `<table><thead><tr><th>Respondent</th><th>Survey</th><th>Reward</th><th>Submitted</th><th>Action</th></tr></thead><tbody>
      ${pendingRewards.map(r => `<tr>
        <td><strong>${escapeHTML(r.user_full_name || "Respondent")}</strong><br>${escapeHTML(r.user_email || "")}</td>
        <td>${escapeHTML(r.survey_title || "Survey")}</td><td>${money(r.amount, r.currency)}</td>
        <td>${r.submitted_at ? new Date(r.submitted_at).toLocaleDateString() : "—"}</td>
        <td><div class="action-row"><button class="small-button green" data-action="approve-reward" data-id="${escapeHTML(r.id)}">Approve</button><button class="small-button red" data-action="reject-reward" data-id="${escapeHTML(r.id)}">Reject</button></div></td>
      </tr>`).join("")}</tbody></table>`;
    } catch (e) {
      $("rewards-table").innerHTML = `<p class="empty-state">${escapeHTML(e.message)}</p>`;
      showMessage(e.message, true);
    }
  }

  async function rewardAction(id, approve) {
    let body;
    if (!approve) {
      const reason = prompt("Enter the reason for rejecting this reward:");
      if (reason === null) return;
      if (!reason.trim()) return showMessage("A rejection reason is required.", true);
      body = JSON.stringify({ reason: reason.trim() });
    }
    if (approve && !confirm("Approve this reward and move it to the respondent's available balance?")) return;
    try {
      await request(`/api/admin/rewards/${id}/${approve ? "approve" : "reject"}`, {
        method: "POST", ...(body ? { body } : {})
      });
      showMessage(approve ? "Reward approved." : "Reward rejected.");
      await loadRewards();
    } catch (e) {
      showMessage(e.message, true);
    }
  }

  async function loadWithdrawals() {
    $("withdrawals-table").innerHTML = '<p class="loading">Loading withdrawal requests...</p>';
    try {
      const statuses = ["requested", "approved", "processing"];
      const pages = await Promise.all(statuses.map(status =>
        request(`/api/admin/withdrawals?status=${status}&limit=100&offset=0`)
      ));
      withdrawals = pages.flatMap(page => itemsOf(page));
      const requestedCount = itemsOf(pages[0]).length;
      $("stat-withdrawals").textContent = requestedCount;

      if (!withdrawals.length) {
        $("withdrawals-table").innerHTML = '<p class="empty-state">No active withdrawal requests require attention.</p>';
        return;
      }

      $("withdrawals-table").innerHTML = `<table><thead><tr>
        <th>Respondent ID</th><th>Amount</th><th>Method</th>
        <th>Destination</th><th>Status</th><th>Actions</th>
      </tr></thead><tbody>
      ${withdrawals.map(w => {
        let actions = "";
        if (w.status === "requested") {
          actions = `<button class="small-button green" data-action="approve-withdrawal" data-id="${escapeHTML(w.id)}">Approve</button>
            <button class="small-button red" data-action="reject-withdrawal" data-id="${escapeHTML(w.id)}">Reject</button>`;
        } else if (w.status === "approved") {
          actions = `<button class="small-button green" data-action="processing-withdrawal" data-id="${escapeHTML(w.id)}">Mark processing</button>`;
        } else if (w.status === "processing") {
          actions = `<button class="small-button green" data-action="paid-withdrawal" data-id="${escapeHTML(w.id)}">Mark paid</button>`;
        }
        return `<tr>
          <td>${escapeHTML(w.user_id)}</td>
          <td>${money(w.amount, w.currency)}</td>
          <td>${escapeHTML(w.method)}</td>
          <td>${escapeHTML(w.destination_masked)}</td>
          <td><span class="status ${escapeHTML(w.status)}">${escapeHTML(w.status)}</span></td>
          <td><div class="action-row">${actions || "—"}</div></td>
        </tr>`;
      }).join("")}</tbody></table>`;
    } catch (e) {
      $("withdrawals-table").innerHTML = `<p class="empty-state">${escapeHTML(e.message)}</p>`;
      showMessage(e.message, true);
    }
  }

  async function withdrawalAction(action, id) {
    let body;
    let path = `/api/admin/withdrawals/${id}/${action}`;
    if (action === "reject") {
      const notes = prompt("Enter the reason for rejecting this withdrawal:");
      if (notes === null) return;
      if (!notes.trim()) return showMessage("A rejection reason is required.", true);
      body = JSON.stringify({ notes: notes.trim() });
    } else if (action === "approve") {
      if (!confirm("Approve this withdrawal request?")) return;
      body = JSON.stringify({});
    } else if (action === "paid") {
      const reference = prompt("Enter the M-Pesa or payment transaction reference:");
      if (reference === null || !reference.trim()) return;
      path += `?payment_reference=${encodeURIComponent(reference.trim())}`;
    } else if (action === "processing") {
      if (!confirm("Mark this withdrawal as processing?")) return;
      body = JSON.stringify({});
    }
    try {
      await request(path, { method: "POST", ...(body ? { body } : {}) });
      showMessage("Withdrawal status updated.");
      await loadWithdrawals();
    } catch (e) {
      showMessage(e.message, true);
    }
  }

  async function loadRespondents(search = "") {
    const target = $("respondents-table");
    target.innerHTML = '<p class="loading">Loading respondent accounts...</p>';
    try {
      const query = new URLSearchParams({ limit: "100", offset: "0" });
      if (search.trim()) query.set("search", search.trim());
      const page = await request(`/api/admin/users/?${query.toString()}`);
      const rows = itemsOf(page);

      if (!rows.length) {
        target.innerHTML = '<p class="empty-state">No respondent accounts match this search.</p>';
        return;
      }

      target.innerHTML = `<p class="muted">${Number(page.total || rows.length)} respondent account(s) found.</p>
        <table><thead><tr><th>Respondent</th><th>Status</th><th>Email verification</th><th>Joined</th><th>Last login</th><th>Action</th></tr></thead><tbody>
        ${rows.map(user => `<tr>
          <td><strong>${escapeHTML(user.full_name)}</strong><br><small>${escapeHTML(user.email)}</small></td>
          <td><span class="status ${escapeHTML(user.status)}">${escapeHTML(user.status)}</span></td>
          <td>${user.email_verified_at ? "Verified" : "Not verified"}</td>
          <td>${user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}</td>
          <td>${user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}</td>
          <td>${user.status === "active"
            ? `<button class="small-button red" data-action="suspend-user" data-id="${escapeHTML(user.id)}">Suspend</button>`
            : user.status === "suspended"
              ? `<button class="small-button green" data-action="activate-user" data-id="${escapeHTML(user.id)}">Activate</button>`
              : "—"}
          </td>
        </tr>`).join("")}</tbody></table>`;
    } catch (e) {
      target.innerHTML = `<p class="empty-state">${escapeHTML(e.message)}</p>`;
      showMessage(e.message, true);
    }
  }

  async function respondentStatusAction(id, status) {
    const label = status === "suspended" ? "suspend" : "activate";
    if (!confirm(`Are you sure you want to ${label} this respondent account?`)) return;
    try {
      await request(`/api/admin/users/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status })
      });
      showMessage(`Respondent account ${label}d successfully.`);
      await loadRespondents($("respondent-search").value);
    } catch (e) {
      showMessage(e.message, true);
    }
  }

  async function loadPayments() {
    $("payments-table").innerHTML = '<p class="loading">Loading payments...</p>';
    try {
      const data = await request("/api/admin/payments?limit=100&offset=0");
      const rows = data.items || [];
      if (!rows.length) {
        $("payments-table").innerHTML = '<p class="empty-state">No payment records yet.</p>';
        return;
      }
      $("payments-table").innerHTML = `<p class="muted">${Number(data.total || rows.length)} payment(s) found.</p>
        <table><thead><tr><th>Respondent</th><th>Plan</th><th>Amount</th><th>Status</th><th>Receipt</th><th>Created</th></tr></thead><tbody>
        ${rows.map(p => `<tr>
          <td><strong>${escapeHTML(p.user_full_name || "—")}</strong><br><small>${escapeHTML(p.user_email || "")}</small></td>
          <td>#${escapeHTML(String(p.plan_id))}</td>
          <td>${money(p.amount, p.currency)}</td>
          <td><span class="status ${escapeHTML(p.status)}">${escapeHTML(p.status)}</span></td>
          <td>${escapeHTML(p.mpesa_receipt_number || "—")}</td>
          <td>${new Date(p.created_at).toLocaleString()}</td>
        </tr>`).join("")}</tbody></table>`;
    } catch (e) {
      $("payments-table").innerHTML = `<p class="empty-state">${escapeHTML(e.message)}</p>`;
      showMessage(e.message, true);
    }
  }

  async function loadOverview() {
    await Promise.allSettled([loadSurveys(), loadRewards(), loadWithdrawals()]);
  }

  document.querySelectorAll(".nav-item").forEach(btn =>
    btn.addEventListener("click", () => setView(btn.dataset.view))
  );
  document.querySelectorAll("[data-go]").forEach(btn =>
    btn.addEventListener("click", () => setView(btn.dataset.go))
  );

  $("show-survey-form").addEventListener("click", () => {
    $("survey-form").hidden = false;
    $("survey-form").scrollIntoView({ behavior: "smooth" });
  });
  $("hide-survey-form").addEventListener("click", () => $("survey-form").hidden = true);
  $("cancel-survey").addEventListener("click", () => $("survey-form").hidden = true);
  $("survey-form").addEventListener("submit", createSurvey);
  $("refresh-surveys").addEventListener("click", loadSurveys);
  $("refresh-rewards").addEventListener("click", loadRewards);
  $("refresh-withdrawals").addEventListener("click", loadWithdrawals);
  $("refresh-payments").addEventListener("click", loadPayments);
  $("refresh-respondents").addEventListener("click", () =>
    loadRespondents($("respondent-search").value)
  );
  $("respondent-search").addEventListener("keydown", e => {
    if (e.key === "Enter") {
      e.preventDefault();
      loadRespondents(e.target.value);
    }
  });
  $("question-survey").addEventListener("change", e => loadQuestions(e.target.value));
  $("question-workspace").addEventListener("submit", e => {
    if (e.target.id === "question-form") createQuestion(e);
    if (e.target.id === "bank-generate-form") generateBankQuestions(e);
  });

  document.addEventListener("click", e => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const { action, id } = btn.dataset;
    if (action === "questions") {
      setView("questions");
      $("question-survey").value = id;
      loadQuestions(id);
    } else if (["publish", "close", "archive"].includes(action)) {
      surveyAction(action, id);
    } else if (action === "delete-question") {
      deleteQuestion(id);
    } else if (action === "approve-reward" || action === "reject-reward") {
      rewardAction(id, action === "approve-reward");
    } else if (action === "approve-withdrawal" || action === "reject-withdrawal") {
      withdrawalAction(action === "approve-withdrawal" ? "approve" : "reject", id);
    } else if (action === "processing-withdrawal") {
      withdrawalAction("processing", id);
    } else if (action === "paid-withdrawal") {
      withdrawalAction("paid", id);
    } else if (action === "suspend-user") {
      respondentStatusAction(id, "suspended");
    } else if (action === "activate-user") {
      respondentStatusAction(id, "active");
    }
  });

  $("menu-button").addEventListener("click", () => $("sidebar").classList.toggle("open"));
  $("year").textContent = new Date().getFullYear();

  $("logout-button").addEventListener("click", async () => {
    try {
      if (accessToken) await request("/api/auth/logout", { method: "POST" });
    } catch (_) {}
    clearTokens();
    window.location.replace("dashboard.html");
  });

  (async function init() {
    try {
      if (!accessToken && refreshToken) await refreshAccessToken();
      if (!accessToken) {
        window.location.replace("dashboard.html");
        return;
      }

      currentUser = await request("/api/auth/me");
      if (!["admin", "super_admin"].includes(currentUser.role)) {
        window.location.replace("dashboard.html");
        return;
      }

      $("admin-name").textContent = currentUser.full_name;
      $("admin-email").textContent = currentUser.email;
      $("admin-avatar").textContent = (currentUser.full_name || "A").trim()[0].toUpperCase();
      $("welcome-name").textContent = (currentUser.full_name || "Admin").split(" ")[0];

      $("loading").hidden = true;
      await loadOverview();
      $("view-overview").hidden = false;
    } catch (e) {
      $("loading").textContent = e.message || "Unable to load administrator workspace.";
      showMessage(e.message, true);
    }
  })();
})();
