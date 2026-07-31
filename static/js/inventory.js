/* Real-time inventory sync via Server-Sent Events */
(function () {
  const root = document.documentElement;
  const apiBase = root.dataset.apiBase || "/api/v1";

  function parseIds(value) {
    if (!value) return [];
    return String(value)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function qs(params) {
    const parts = [];
    (params.variantIds || []).forEach((id) => parts.push("variant_id=" + encodeURIComponent(id)));
    (params.productIds || []).forEach((id) => parts.push("product_id=" + encodeURIComponent(id)));
    return parts.length ? "?" + parts.join("&") : "";
  }

  function applyEvent(data) {
    if (!data || data.variant_id == null) return;

    document.querySelectorAll('[data-variant-id="' + data.variant_id + '"]').forEach((el) => {
      const stock = Number(data.stock);
      el.dataset.stock = String(stock);

      if (el.tagName === "OPTION") {
        const label = el.dataset.label || el.textContent.replace(/\s*\(\d+\s+in stock\)\s*$/, "");
        el.dataset.label = label;
        el.textContent = label + " (" + stock + " in stock)";
        el.disabled = stock <= 0;
      } else if (el.classList.contains("ss-stock-badge") || el.matches("span, strong, td, .badge")) {
        el.textContent = String(stock);
        el.classList.toggle("text-bg-danger", stock < 5);
        el.classList.toggle("text-bg-success", stock >= 5);
        el.classList.toggle("text-danger", stock < 5 && !el.classList.contains("badge"));
      }
    });

    document.querySelectorAll('[data-product-stock="' + data.product_id + '"]').forEach((el) => {
      // Recompute sum from sibling variant cells when present
      const row = el.closest("tr");
      if (row) {
        let total = 0;
        row.querySelectorAll("[data-variant-id][data-stock]").forEach((cell) => {
          total += Number(cell.dataset.stock || 0);
        });
        if (row.querySelectorAll("[data-variant-id][data-stock]").length) {
          el.textContent = String(total);
          return;
        }
      }
      el.textContent = String(data.stock);
    });

    const live = document.getElementById("ss-inventory-live");
    if (live) {
      const name = data.product_name || data.sku;
      live.textContent = "Live: " + name + " → " + data.stock + " in stock";
      live.classList.remove("d-none");
    }

    window.dispatchEvent(new CustomEvent("shopsphere:inventory", { detail: data }));
  }

  function connect() {
    const cfg = document.getElementById("ss-inventory-sync");
    const variantIds = parseIds(cfg && cfg.dataset.variantIds);
    const productIds = parseIds(cfg && cfg.dataset.productIds);
    const url = apiBase + "/inventory/stream" + qs({ variantIds, productIds });

    let es;
    try {
      es = new EventSource(url);
    } catch (err) {
      console.warn("Inventory SSE unavailable", err);
      return;
    }

    es.addEventListener("inventory", (ev) => {
      try {
        applyEvent(JSON.parse(ev.data));
      } catch (err) {
        console.warn("Bad inventory event", err);
      }
    });

    es.onerror = function () {
      // Browser auto-reconnects; show subtle status if present
      const live = document.getElementById("ss-inventory-live");
      if (live) {
        live.textContent = "Reconnecting inventory sync…";
      }
    };
  }

  async function adjustStock(variantId, stock, reason) {
    const tokenCookie = document.cookie
      .split(";")
      .map((c) => c.trim())
      .find((c) => c.startsWith("access_token="));
    const headers = { "Content-Type": "application/json" };
    // Cookie auth is enough for same-origin form sessions; Bearer optional

    const resp = await fetch(apiBase + "/products/variants/" + variantId + "/inventory", {
      method: "PATCH",
      headers: headers,
      credentials: "same-origin",
      body: JSON.stringify({ stock: Number(stock), reason: reason || "manual_adjustment" }),
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || "Inventory update failed");
    }
    return resp.json();
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("ss-inventory-sync") || document.querySelector("[data-variant-id]")) {
      connect();
    }

    document.querySelectorAll("[data-inventory-adjust]").forEach((form) => {
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const variantId = form.dataset.variantId || form.querySelector('[name="variant_id"]').value;
        const stock = form.querySelector('[name="stock"]').value;
        const reason = (form.querySelector('[name="reason"]') || {}).value || "manual_adjustment";
        const status = form.querySelector("[data-inventory-status]");
        try {
          const updated = await adjustStock(variantId, stock, reason);
          applyEvent({
            variant_id: updated.id,
            product_id: updated.product_id || Number(form.dataset.productId || 0),
            sku: updated.sku,
            stock: updated.stock,
            product_name: form.dataset.productName || updated.sku,
          });
          if (status) status.textContent = "Saved — synced live";
        } catch (err) {
          if (status) status.textContent = "Error: " + err.message;
          else alert(err.message);
        }
      });
    });
  });

  window.ShopSphereInventory = { applyEvent, adjustStock };
})();
