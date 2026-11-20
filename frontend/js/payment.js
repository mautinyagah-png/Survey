(function () {
  "use strict";

  const API = (window.SURVEY_API_BASE || "").replace(/\/$/, "");
  const $ = (id) => document.getElementById(id);

  let accessToken = sessionStorage.getItem("survey_access_token") || "";
  let refreshToken = sessionStorage.getItem("survey_refresh_token") || "";

  const params = new URLSearchParams(window.location.search);
  const planId = Number(params.get("plan") || 0);

  function showMsg(msg, isError = false) {
    const el = $("payment-message");
    el.textContent = msg;
    el.className = isError ? "message error" : "message";
    el.hidden = false;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function refreshAccess() {
    if (!refreshToken) return false;
    const r = await fetch(`${API}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!r.ok) return false;
    const d = await r.json();
    accessToken = d.access_token; refreshToken = d.refresh_token;
    sessionStorage.setItem("survey_access_token", accessToken);
    sessionStorage.setItem("survey_refresh_token", refreshToken);
    return true;
  }

  async function req(path, opts = {}, retry = true) {
    const headers = new Headers(opts.headers || {});
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    if (opts.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const res = await fetch(`${API}${path}`, { ...opts, headers });
    if (res.status === 401 && retry && await refreshAccess()) return req(path, opts, false);
    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try { const d = await res.json(); if (typeof d.detail === "string") msg = d.detail; } catch (_) {}
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "idem-" + Date.now() + "-" + Math.random().toString(36).slice(2, 14);
  }

  async function loadPlan() {
    if (!planId) { showMsg("No plan selected. Please go back and choose one.", true); return; }
    try {
      const plans = await req("/api/subscriptions/plans");
      const plan = plans.find(p => p.id === planId);
      if (!plan) { showMsg("Plan not found.", true); return; }
      if (Number(plan.price_amount) === 0) {
        showMsg("This plan is free. No payment required.", true);
        $("mpesa-form-wrap").hidden = true;
        return;
      }
      $("plan-name").textContent = plan.name;
      $("plan-price").textContent = `${plan.currency} ${Number(plan.price_amount).toLocaleString()}`;
    } catch (e) {
      showMsg(e.message, true);
    }
  }

  async function pay() {
    const phone = $("mpesa-phone").value.trim();
    if (!phone) { showMsg("Enter your M-Pesa phone number.", true); return; }

    const btn = $("pay-btn");
    btn.disabled = true;
    btn.textContent = "Sending…";
    $("payment-message").hidden = true;

    try {
      const result = await req("/api/payments/mpesa/checkout", {
        method: "POST",
        headers: { "Idempotency-Key": uuid() },
        body: JSON.stringify({ plan_id: planId, phone_number: phone }),
      });

      $("mpesa-form-wrap").hidden = true;
      $("pending-state").hidden = false;

      const paymentId = result.payment.id;
      let attempts = 0;
      const iv = setInterval(async () => {
        attempts++;
        try {
          const p = await req(`/api/payments/${paymentId}`);
          if (p.status === "completed") {
            clearInterval(iv);
            $("pending-state").hidden = true;
            $("success-state").hidden = false;
          } else if (p.status === "failed") {
            clearInterval(iv);
            $("pending-state").hidden = true;
            $("mpesa-form-wrap").hidden = false;
            btn.disabled = false;
            btn.textContent = "Try again";
            showMsg("Payment failed: " + (p.result_description || "Please try again."), true);
          }
        } catch (_) {}
        if (attempts >= 20) {
          clearInterval(iv);
          $("pending-state").hidden = true;
          showMsg("Payment status uncertain. Check your M-Pesa messages, then refresh this page.", true);
          btn.disabled = false;
          btn.textContent = "Resend STK push";
        }
      }, 3000);
    } catch (e) {
      const msg = String(e.message || "");
      if (msg.toLowerCase().includes("not configured") || msg.toLowerCase().includes("mpesa checkout")) {
        showMsg("M-Pesa payments are not yet configured on this server. Contact support.", true);
      } else {
        showMsg(msg, true);
      }
      btn.disabled = false;
      btn.textContent = "Send STK push";
    }
  }

  $("pay-btn").addEventListener("click", pay);

  (async function init() {
    if (!accessToken && refreshToken) await refreshAccess();
    if (!accessToken) { window.location.replace("dashboard.html"); return; }
    await loadPlan();
  })();
})();
