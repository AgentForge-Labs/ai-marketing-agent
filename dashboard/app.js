/* Ops dashboard — same-origin API only, zero external dependencies. */
(function () {
  "use strict";
  var key = sessionStorage.getItem("ama_key") || "";
  var keyInput = document.getElementById("apiKey");
  keyInput.value = key;

  function headers() {
    return { "Content-Type": "application/json", "X-API-Token": key };
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function show(id, html) {
    document.getElementById(id).innerHTML = html;
  }
  function api(path, opts) {
    opts = opts || {};
    opts.headers = headers();
    return fetch(path, opts).then(function (r) {
      return r.json().then(function (body) {
        return { status: r.status, body: body };
      });
    });
  }

  function refresh() {
    if (!key) {
      show("health", "enter API key");
      return;
    }
    fetch("/health").then(function (r) { return r.json(); }).then(function (b) {
      show("health", b.status === "ok" ? '<span class="ok">● online</span>' : '<span class="bad">● degraded</span>');
    }).catch(function () { show("health", '<span class="bad">● unreachable</span>'); });
    api("/quota").then(function (res) {
      show("quota", res.status === 200
        ? "tenant <b>" + esc(res.body.tenant_id) + "</b><br/>remaining: <b>" + esc(res.body.quota_remaining) + "</b>"
        : '<span class="bad">' + esc(res.body.error || res.status) + "</span>");
    });
    api("/stats").then(function (res) {
      if (res.status !== 200) {
        show("metrics", '<span class="bad">' + esc(res.body.error || res.status) + "</span>");
        return;
      }
      var rows = Object.keys(res.body.metrics).sort().slice(0, 40).map(function (k) {
        return "<tr><td>" + esc(k) + "</td><td>" + esc(res.body.metrics[k]) + "</td></tr>";
      });
      show("metrics", "<table><tr><th>metric</th><th>value</th></tr>" + rows.join("") + "</table>");
    });
  }

  document.getElementById("connectBtn").addEventListener("click", function () {
    key = keyInput.value.trim();
    sessionStorage.setItem("ama_key", key);
    refresh();
  });
  document.getElementById("routeBtn").addEventListener("click", function () {
    var payload = {
      domain: document.getElementById("routeDomain").value.trim(),
      action: document.getElementById("routeAction").value.trim()
    };
    api("/route", { method: "POST", body: JSON.stringify(payload) }).then(function (res) {
      document.getElementById("routeOut").textContent = JSON.stringify(res.body, null, 2);
    });
  });
  function consent(action) {
    var payload = {
      subject_id: document.getElementById("cSubject").value.trim(),
      purpose: document.getElementById("cPurpose").value.trim(),
      action: action
    };
    var done = function (res) {
      document.getElementById("cOut").textContent = JSON.stringify(res.body, null, 2);
    };
    if (action === "check") {
      api("/consent?subject_id=" + encodeURIComponent(payload.subject_id) +
          "&purpose=" + encodeURIComponent(payload.purpose)).then(done);
    } else {
      api("/consent", { method: "POST", body: JSON.stringify(payload) }).then(done);
    }
  }
  document.getElementById("cGrant").addEventListener("click", function () { consent("grant"); });
  document.getElementById("cWithdraw").addEventListener("click", function () { consent("withdraw"); });
  document.getElementById("cCheck").addEventListener("click", function () { consent("check"); });

  if (key) { refresh(); }
})();
