// Tiny DOM helpers. Strings from the API always go in as text, never as HTML.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/** h("div", { class: "x", onclick: fn }, "text", childNode) */
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k === "dataset") Object.assign(el.dataset, v);
    else if (k === "style") el.style.cssText = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function mount(target, ...nodes) {
  target.replaceChildren(...nodes.flat().filter(Boolean));
  target.removeAttribute("aria-busy");
}

export function skeleton(target, kind = "row", count = 5) {
  target.setAttribute("aria-busy", "true");
  target.replaceChildren(...Array.from({ length: count }, () => h("div", { class: `skeleton skeleton--${kind}` })));
}

export const empty = (text) => h("div", { class: "empty" }, text);

export const errorBox = (message, retry) =>
  h("div", { class: "error", role: "alert" }, h("span", {}, message), retry && h("button", { type: "button", onclick: retry }, "Try again"));

/** Wire a group of aria-pressed buttons. Returns a setter. */
export function segmented(group, attr, onChange) {
  const buttons = $$("button", group);
  const select = (value, fire = true) => {
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset[attr] === value)));
    if (fire) onChange(value);
  };
  buttons.forEach((b) => b.addEventListener("click", () => select(b.dataset[attr])));
  return select;
}

let toastTimer;
export function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 4500);
}
