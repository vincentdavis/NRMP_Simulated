// Site-wide behaviour: toasts, the confirmation dialog, HTMX error reporting and the theme toggle.
// Loaded on every page after htmx. Text is always inserted with textContent, never as HTML.
(function () {
  "use strict";

  const ALERT_CLASSES = { success: "alert-success", info: "alert-info", warning: "alert-warning", error: "alert-error" };

  // --- Toasts -------------------------------------------------------------------------------------------------
  function dismissLater(alert, level) {
    window.setTimeout(() => alert.remove(), level === "error" ? 10000 : 5000);
  }

  function showToast(level, text) {
    const region = document.getElementById("toasts");
    if (!region || !text) return;
    const alert = document.createElement("div");
    alert.className = `alert ${ALERT_CLASSES[level] || "alert-info"} shadow`;
    alert.setAttribute("role", level === "error" ? "alert" : "status");
    const span = document.createElement("span");
    span.textContent = text;
    alert.appendChild(span);
    region.appendChild(alert);
    dismissLater(alert, level);
  }
  window.showToast = showToast;

  // --- Confirmation dialog --------------------------------------------------------------------------------------
  function confirmAction(message, onConfirm) {
    const dialog = document.getElementById("confirm-dialog");
    if (!dialog || typeof dialog.showModal !== "function") {
      if (window.confirm(message)) onConfirm();
      return;
    }
    dialog.querySelector("[data-confirm-message]").textContent = message;
    const ok = dialog.querySelector("[data-confirm-ok]");
    const cancel = dialog.querySelector("[data-confirm-cancel]");
    const finish = (confirmed) => {
      ok.onclick = null;
      cancel.onclick = null;
      dialog.close();
      if (confirmed) onConfirm();
    };
    ok.onclick = () => finish(true);
    cancel.onclick = () => finish(false);
    dialog.showModal();
    cancel.focus(); // the safe choice has the focus
  }

  // Ordinary forms opt in with data-confirm="question".
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirm || form.dataset.confirmed) return;
    event.preventDefault();
    confirmAction(form.dataset.confirm, () => {
      form.dataset.confirmed = "1";
      form.requestSubmit();
    });
  });

  document.addEventListener("DOMContentLoaded", () => {
    // Messages rendered by the server (after a redirect) disappear on their own too.
    document.querySelectorAll("#toasts .alert").forEach((alert) => {
      dismissLater(alert, alert.classList.contains("alert-error") ? "error" : "info");
    });

    const body = document.body;
    // HTMX actions with hx-confirm use the same dialog.
    body.addEventListener("htmx:confirm", (event) => {
      if (!event.detail.question) return;
      event.preventDefault();
      confirmAction(event.detail.question, () => event.detail.issueRequest(true));
    });
    // The server sends {"toast": {"level": ..., "text": ...}} in the HX-Trigger header.
    body.addEventListener("toast", (event) => showToast(event.detail.level, event.detail.text));
    // HTMX does not swap error responses; say something instead of failing silently.
    body.addEventListener("htmx:responseError", (event) => {
      const status = event.detail.xhr ? event.detail.xhr.status : "";
      showToast("error", `The server could not complete that action (error ${status}). It has been logged; please try again.`);
    });
    body.addEventListener("htmx:sendError", () => {
      showToast("error", "Could not reach the server. Check your connection and try again.");
    });
  });

  // --- List editors (formsets) ---------------------------------------------------------------------------------
  // Alpine component for the parameter tables: "Add row" copies the formset's empty form, numbered with the next
  // index, and raises TOTAL_FORMS; the server validates everything, so this is only a convenience.
  window.formsetRows = function (prefix) {
    return {
      get total() {
        return document.getElementById(`id_${prefix}-TOTAL_FORMS`);
      },
      get full() {
        const max = document.getElementById(`id_${prefix}-MAX_NUM_FORMS`);
        return Boolean(this.total && max && Number(this.total.value) >= Number(max.value));
      },
      add() {
        if (!this.total || this.full) return;
        const index = Number(this.total.value);
        const html = this.$refs.empty.innerHTML.replaceAll("__prefix__", String(index));
        this.$refs.rows.insertAdjacentHTML("beforeend", html);
        this.total.value = String(index + 1);
        const added = this.$refs.rows.lastElementChild;
        const first = added && added.querySelector("input, select");
        if (first) first.focus();
      },
    };
  };

  // --- Theme toggle ---------------------------------------------------------------------------------------------
  // The saved choice is applied before first paint by a small script in <head>; without one, daisyUI follows the
  // system preference.
  function currentTheme() {
    const explicit = document.documentElement.dataset.theme;
    if (explicit) return explicit;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem("theme", next);
    } catch (error) {
      // Storage may be unavailable (private mode); the toggle still works for this page.
    }
    button.setAttribute("aria-pressed", String(next === "dark"));
  });
})();
