(function () {
  "use strict";

  const API = (window.SURVEY_API_BASE || "").replace(/\/$/, "");
  const authScreen = document.getElementById("auth-screen");
  const dashboardScreen = document.getElementById("dashboard-screen");
  const loginForm = document.getElementById("login-form");
  const authError = document.getElementById("auth-error");

  let accessToken = sessionStorage.getItem("survey_access_token") || "";
  let refreshToken = sessionStorage.getItem("survey_refresh_token") || "";
  let currentUser = null;
  let loaded = false;

  const $ = (id) => document.getElementById(id);

  function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }

  function money(amount, currency) {
    const value = Number(amount || 0);
    return `${escapeHTML(currency || "KES")} ${value.toLocaleString("en-KE", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;
  }

  function saveTokens(data) {
    accessToken = data.access_token || accessToken;
    refreshToken = data.refresh_token || refreshToken;
    sessionStorage.setItem("survey_access_token", accessToken);
    sessionStorage.setItem("survey_refresh_token", refreshToken);
  }

  function clearTokens() {
    accessToken = "";
    refreshToken = "";
    sessionStorage.removeItem("survey_access_token");
    sessionStorage.removeItem("survey_refresh_token");
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
    saveTokens(await response.json());
    return true;
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
        const body = await response.json();
        detail = body.detail || body.message || detail;
      } catch (_) {}
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    if (response.status === 204) return null;
    return response.json();
  }

  function showAuth(message = "") {
    authScreen.hidden = false;
    dashboardScreen.hidden = true;
    authError.textContent = message;
    authError.hidden = !message;
  }

  function showDashboard() {
    authScreen.hidden = true;
    dashboardScreen.hidden = false;
  }

  function showMessage(message, isError = false) {
    const element = $("dashboard-message");
    element.textContent = message;
    element.className = isError ? "message error" : "message";
    element.hidden = false;
  }

  function setView(view) {
    const titles = {
      overview: "Overview",
      surveys: "Available surveys",
      activity: "My activity",
      wallet: "My wallet"
    };
    document.querySelectorAll(".view").forEach((section) => {
      section.hidden = section.id !== `view-${view}`;
    });
    document.querySelectorAll(".nav-link").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === view);
    });
    $("page-title").textContent = titles[view] || "Overview";
    $("sidebar").classList.remove("open");
  }

  function renderSurveys(items, target) {
    const container = $(target);
    if (!items || !items.length) {
      container.innerHTML = '<p class="muted">No published surveys are available right now. Please check again later.</p>';
      return;
    }

    container.innerHTML = items.map((survey) => {
      const locked = Boolean(survey.is_locked);
      const tier = escapeHTML(survey.required_tier);
      const duration = survey.estimated_minutes
        ? `${escapeHTML(survey.estimated_minutes)} min`
        : "Time varies";

      return `
        <article class="survey-card">
          <span class="tier-pill ${locked ? "locked" : ""}">
            ${locked ? "Locked · " : ""}${tier}
          </span>
          <h3>${escapeHTML(survey.title)}</h3>
          <div class="survey-meta">
            <span>◷ ${duration}</span>
            <span>${locked ? "Upgrade required" : "Available to you"}</span>
          </div>
          <p class="survey-reward">${money(survey.reward_amount, survey.reward_currency)}</p>
          ${locked ? `<p class="locked-note">Requires ${tier} membership or higher.</p>` : `<a href="participate.html?survey=${encodeURIComponent(survey.id)}" style="display:inline-block;margin-top:14px;padding:10px 18px;border-radius:8px;background:var(--dash-primary);color:#fff;font-weight:700;text-decoration:none;font-size:13px">Participate →</a>`}
        </article>`;
    }).join("");
  }

  function renderActivity(items, target) {
    const container = $(target);
    if (!items || !items.length) {
      container.innerHTML = '<p class="muted">You have not started or submitted any surveys yet.</p>';
      return;
    }

    container.innerHTML = items.map((item) => {
      const status = String(item.status || "unknown").toLowerCase();
      const date = item.submitted_at || item.started_at;
      const formatted = date ? new Date(date).toLocaleDateString() : "Date unavailable";
      return `
        <article class="activity-item">
          <div>
            <strong>${escapeHTML(item.survey_title)}</strong>
            <small>${escapeHTML(formatted)} · Potential reward ${money(item.reward_amount, item.reward_currency)}</small>
          </div>
          <span class="status-pill status-${escapeHTML(status)}">${escapeHTML(status.replaceAll("_", " "))}</span>
        </article>`;
    }).join("");
  }

  async function loadDashboard() {
    if (loaded) return;
    showDashboard();
    $("year").textContent = new Date().getFullYear();

    try {
      currentUser = await request("/api/auth/me");

      if (["admin", "super_admin"].includes(currentUser.role)) {
        window.location.replace("admin.html");
        return;
      }

      $("user-name").textContent = currentUser.full_name;
      $("user-email").textContent = currentUser.email;
      $("user-avatar").textContent = (currentUser.full_name || "U").trim().charAt(0).toUpperCase();
      $("welcome-name").textContent = (currentUser.full_name || "there").split(" ")[0];

      const results = await Promise.allSettled([
        request("/api/surveys/?page=1&page_size=12"),
        request("/api/subscriptions/me"),
        request("/api/wallet/me"),
        request("/api/participations/me?page=1&page_size=10")
      ]);

      const [surveysResult, subscriptionResult, walletResult, activityResult] = results;

      if (surveysResult.status === "fulfilled") {
        const surveys = surveysResult.value.items || [];
        renderSurveys(surveys.slice(0, 3), "overview-surveys");
        renderSurveys(surveys, "all-surveys");
      } else {
        $("overview-surveys").textContent = "Unable to load surveys.";
        $("all-surveys").textContent = "Unable to load surveys.";
      }

      if (subscriptionResult.status === "fulfilled") {
        const sub = subscriptionResult.value;
        $("membership-tier").textContent = (sub.tier || "Basic").toString().toUpperCase();
        $("membership-description").textContent = `Tier level ${sub.tier_rank ?? 1}`;
      } else {
        $("membership-tier").textContent = "—";
      }

      if (walletResult.status === "fulfilled") {
        const walletData = walletResult.value;
        const preferredCurrency = currentUser.preferred_currency || "KES";
        const wallet = Array.isArray(walletData)
          ? (walletData.find(item => item.currency === preferredCurrency) || walletData[0] || {})
          : (walletData || {});
        const currency = wallet.currency || preferredCurrency;
        const available = money(wallet.available_balance, currency);
        const pending = money(wallet.pending_balance, currency);
        const earned = money(wallet.total_earned, currency);

        $("available-balance").textContent = available;
        $("pending-balance").textContent = pending;
        $("wallet-available").textContent = available;
        $("wallet-pending").textContent = pending;
        $("wallet-earned").textContent = earned;
      } else {
        ["available-balance", "pending-balance", "wallet-available",
         "wallet-pending", "wallet-earned"].forEach((id) => $(id).textContent = "Unavailable");
      }

      if (activityResult.status === "fulfilled") {
        const activity = activityResult.value;
        $("participation-count").textContent = activity.total ?? activity.items.length;
        renderActivity((activity.items || []).slice(0, 4), "overview-activity");
        renderActivity(activity.items || [], "all-activity");
      } else {
        $("participation-count").textContent = "—";
        $("overview-activity").textContent = "Unable to load your activity.";
        $("all-activity").textContent = "Unable to load your activity.";
      }

      loaded = true;
    } catch (error) {
      if (!accessToken) {
        showAuth("Please sign in to continue.");
      } else {
        showMessage(error.message || "Unable to load your dashboard.", true);
      }
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("login-button");
    button.disabled = true;
    button.textContent = "Signing in...";
    authError.hidden = true;

    try {
      const response = await fetch(`${API}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: $("email").value.trim(),
          password: $("password").value
        })
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to sign in.");

      saveTokens(data);

      const profileResponse = await fetch(`${API}/api/auth/me`, {
        headers: { "Authorization": `Bearer ${data.access_token}` }
      });
      if (!profileResponse.ok) {
        throw new Error("Signed in, but your profile could not be loaded.");
      }

      const profile = await profileResponse.json();
      if (["admin", "super_admin"].includes(profile.role)) {
        window.location.replace("admin.html");
        return;
      }

      loaded = false;
      await loadDashboard();
    } catch (error) {
      showAuth(error.message || "Sign-in failed.");
    } finally {
      button.disabled = false;
      button.textContent = "Sign in";
    }
  });

  $("logout-button").addEventListener("click", async () => {
    try {
      if (accessToken) {
        await request("/api/auth/logout", { method: "POST" });
      }
    } catch (_) {
      // Clear local session even if the network is unavailable.
    }
    clearTokens();
    loaded = false;
    currentUser = null;
    showAuth("You have signed out.");
  });

  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });

  document.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.go));
  });

  $("menu-button").addEventListener("click", () => {
    $("sidebar").classList.toggle("open");
  });

  $("year").textContent = new Date().getFullYear();


  // --- Wallet data loading (additive) ---
  async function loadWalletData() {
    try {
      const txns = await request("/api/wallet/me/transactions?limit=20&offset=0");
      const box = $("wallet-txns");
      if (box) {
        box.innerHTML = (!txns.items || !txns.items.length)
          ? '<p class="muted">No transactions yet.</p>'
          : txns.items.map(t => `
            <div class="activity-item">
              <div>
                <strong>${escapeHTML(String(t.type).replaceAll("_", " "))}</strong>
                <small>${new Date(t.created_at).toLocaleString()} · ${escapeHTML(t.description || "")}</small>
              </div>
              <span class="status-pill">${money(t.amount, t.currency)}</span>
            </div>`).join("");
      }
    } catch (e) {
      const box = $("wallet-txns");
      if (box) box.innerHTML = `<p class="muted">${escapeHTML(e.message)}</p>`;
    }

    try {
      const wds = await request("/api/wallet/me/withdrawals?limit=20&offset=0");
      const box = $("wallet-withdrawals");
      if (box) {
        box.innerHTML = (!wds.items || !wds.items.length)
          ? '<p class="muted">No withdrawal requests yet.</p>'
          : wds.items.map(w => `
            <div class="activity-item">
              <div>
                <strong>${money(w.amount, w.currency)} · ${escapeHTML(w.method)}</strong>
                <small>${escapeHTML(w.destination_masked)} · ${new Date(w.requested_at).toLocaleString()}</small>
              </div>
              <span class="status-pill status-${escapeHTML(w.status)}">${escapeHTML(w.status)}</span>
            </div>`).join("");
      }
    } catch (e) {
      const box = $("wallet-withdrawals");
      if (box) box.innerHTML = `<p class="muted">${escapeHTML(e.message)}</p>`;
    }
  }

  const wdForm = document.getElementById("withdraw-form");
  if (wdForm) {
    wdForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("wd-message");
      const btn = document.getElementById("wd-submit");
      msg.hidden = true;
      btn.disabled = true;
      try {
        await request("/api/wallet/me/withdrawals", {
          method: "POST",
          body: JSON.stringify({
            amount: document.getElementById("wd-amount").value,
            currency: "KES",
            method: document.getElementById("wd-method").value,
            destination_masked: document.getElementById("wd-destination").value
          })
        });
        msg.textContent = "Withdrawal request submitted.";
        msg.className = "message";
        msg.hidden = false;
        wdForm.reset();
        await loadWalletData();
      } catch (e2) {
        msg.textContent = e2.message || "Withdrawal failed.";
        msg.className = "message error";
        msg.hidden = false;
      } finally {
        btn.disabled = false;
      }
    });
  }

  document.querySelectorAll('[data-view="wallet"]').forEach((b) => {
    b.addEventListener("click", () => { loadWalletData(); });
  });

  (async function init() {
    if (!accessToken && refreshToken) {
      await refreshAccessToken();
    }
    if (accessToken) {
      await loadDashboard();
    } else {
      showAuth();
    }
  })();
})();
