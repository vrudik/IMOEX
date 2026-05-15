from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_language import LANGUAGE_COOKIE
from apps.api.routes.dashboard_page_hints import page_hint


def render_page_utility_style() -> str:
    return """
  <style>
    .utility-shell {
      width: min(1320px, calc(100% - 28px));
      margin: 18px auto 0;
    }
    .utility-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 16px;
      border-radius: 18px;
      border: 1px solid rgba(23, 34, 44, 0.12);
      background: rgba(255, 250, 241, 0.82);
      box-shadow: 0 10px 26px rgba(23, 34, 44, 0.08);
      backdrop-filter: blur(12px);
    }
    .utility-controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .utility-label {
      font-size: 13px;
      font-weight: 600;
      color: #425057;
    }
    .utility-select,
    .utility-button {
      min-height: 40px;
      border-radius: 12px;
      border: 1px solid rgba(23, 34, 44, 0.12);
      background: rgba(255, 255, 255, 0.8);
      color: #17222c;
      font: inherit;
    }
    .utility-select {
      padding: 0 12px;
    }
    .utility-button {
      padding: 0 14px;
      cursor: pointer;
      font-weight: 600;
    }
    .utility-hint {
      margin-top: 10px;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(25, 58, 82, 0.08);
      color: #23323d;
      line-height: 1.5;
      border: 1px solid rgba(25, 58, 82, 0.12);
    }
  </style>
"""


def render_page_utility_markup(*, language: str, page_key: str) -> str:
    language_label = "Язык" if language == "ru" else "Language"
    hint_button_label = "Куда смотреть?" if language == "ru" else "Where to look?"
    hint = escape(page_hint(page_key, language))
    return f"""
  <div class="utility-shell">
    <div class="utility-bar">
      <div class="utility-controls">
        <label class="utility-label" for="ui-language-select">{language_label}</label>
        <select class="utility-select" id="ui-language-select" data-language-select>
          <option value="ru">Русский</option>
          <option value="en">English</option>
        </select>
      </div>
      <button class="utility-button" type="button" data-hint-toggle aria-expanded="false">{hint_button_label}</button>
    </div>
    <div class="utility-hint" data-hint-box data-message="{hint}" hidden></div>
  </div>
"""


def render_page_utility_script(*, language: str) -> str:
    return f"""
  <script>
    (() => {{
      const select = document.querySelector("[data-language-select]");
      const hintButton = document.querySelector("[data-hint-toggle]");
      const hintBox = document.querySelector("[data-hint-box]");
      const swapPage = async (nextUrl) => {{
        if (window.__imoexMarketLiveRefreshStop) {{
          window.__imoexMarketLiveRefreshStop();
          window.__imoexMarketLiveRefreshStop = null;
        }}
        const currentUrl = new URL(window.location.href);
        const targetUrl = new URL(nextUrl, window.location.href);
        if (currentUrl.toString() === targetUrl.toString()) {{
          window.location.reload();
          return;
        }}
        window.location.assign(targetUrl.toString());
      }};
      window.__imoexSwapPage = swapPage;
      window.__imoexRefreshPage = async (nextUrl) => {{
        await swapPage(nextUrl || window.location.href);
      }};
      document.addEventListener("click", async (event) => {{
        const link = event.target.closest("a[data-swap-link]");
        if (!link || event.defaultPrevented || event.button !== 0) {{
          return;
        }}
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target) {{
          return;
        }}
        event.preventDefault();
        await swapPage(link.href);
      }});
      if (select) {{
        select.value = "{language}";
        select.addEventListener("change", async () => {{
          document.cookie = "{LANGUAGE_COOKIE}=" + encodeURIComponent(select.value) + "; path=/; max-age=31536000; SameSite=Lax";
          const nextUrl = new URL(window.location.href);
          nextUrl.searchParams.set("lang", select.value);
          await swapPage(nextUrl.toString());
        }});
      }}
      const rootSwitch = document.querySelector("[data-root-switch]");
      if (rootSwitch) {{
        rootSwitch.addEventListener("change", async () => {{
          const nextRoot = rootSwitch.value;
          if (!nextRoot) {{
            return;
          }}
          const nextUrl = new URL(window.location.href);
          const pageKey = rootSwitch.dataset.pageKey || "";
          const fallbackPath = rootSwitch.dataset.fallbackPath || "/workspace";
          nextUrl.searchParams.delete("signal_id");
          if (pageKey === "signal") {{
            nextUrl.pathname = fallbackPath;
            nextUrl.search = "";
          }}
          nextUrl.searchParams.set("root", nextRoot);
          if (pageKey === "delivery-history") {{
            nextUrl.searchParams.set("activity_root_scope", nextRoot);
          }}
          await swapPage(nextUrl.toString());
        }});
      }}
      if (hintButton && hintBox) {{
        hintButton.addEventListener("click", () => {{
          const hidden = hintBox.hasAttribute("hidden");
          if (hidden) {{
            hintBox.textContent = hintBox.dataset.message || "";
            hintBox.removeAttribute("hidden");
            hintButton.setAttribute("aria-expanded", "true");
            return;
          }}
          hintBox.setAttribute("hidden", "hidden");
          hintButton.setAttribute("aria-expanded", "false");
        }});
      }}
    }})();
  </script>
"""


def apply_page_utility_shell(html: str, *, language: str, page_key: str) -> str:
    html = html.replace("</head>", render_page_utility_style() + "\n</head>", 1)
    html = html.replace("<body>", "<body>\n" + render_page_utility_markup(language=language, page_key=page_key), 1)
    html = html.replace("</body>", render_page_utility_script(language=language) + "\n</body>", 1)
    return html
