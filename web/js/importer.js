// Drag-and-drop CSV importer card. Reads the file in the browser and hands it to onFile.

import { h } from "./dom.js";

/**
 * @param {{ title: string, intro: string, steps: (string|Node)[], fields?: {name:string,label:string,placeholder?:string,inputmode?:string}[],
 *           onFile: (file: File, values: Record<string,string>) => Promise<string|void> }} opts
 */
export function importer({ title, intro, steps, fields = [], onFile }) {
  const status = h("p", { class: "importer__status", role: "status", "aria-live": "polite" });
  const input = h("input", { type: "file", accept: ".csv,text/csv", class: "visually-hidden", id: `file-${Math.random().toString(36).slice(2)}` });
  const inputs = fields.map((f) => h("input", { class: "input", name: f.name, placeholder: f.placeholder ?? "", inputmode: f.inputmode, "aria-label": f.label }));

  const handle = async (file) => {
    if (!file) return;
    if (!/\.csv$/i.test(file.name)) { status.className = "importer__status importer__status--error"; status.textContent = "Please choose a .csv file."; return; }
    status.className = "importer__status";
    status.textContent = `Reading ${file.name}…`;
    try {
      const values = Object.fromEntries(inputs.map((i) => [i.name, i.value.trim()]));
      const msg = await onFile(file, values);
      status.className = "importer__status importer__status--ok";
      status.textContent = msg || `Imported ${file.name}.`;
    } catch (err) {
      status.className = "importer__status importer__status--error";
      status.textContent = err.message;
    } finally {
      input.value = "";
    }
  };
  input.addEventListener("change", () => handle(input.files?.[0]));

  const zone = h("label", { class: "importer__drop", for: input.id },
    icon(),
    h("span", { class: "importer__cta" }, h("b", {}, "Drop the CSV here"), " or ", h("u", {}, "choose a file")),
    h("span", { class: "muted" }, "Stays on your computer; nothing is uploaded to the internet."));
  ["dragenter", "dragover"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.remove("is-over"); }));
  zone.addEventListener("drop", (e) => handle(e.dataTransfer?.files?.[0]));

  return h("div", { class: "importer" },
    h("div", { class: "importer__text" },
      h("h3", {}, title),
      h("p", { class: "muted" }, intro),
      h("ol", { class: "importer__steps" }, steps.map((s) => h("li", {}, s)))),
    h("div", { class: "importer__side" },
      inputs.length ? h("div", { class: "importer__fields" }, fields.map((f, i) => h("label", { class: "importer__field" }, h("span", {}, f.label), inputs[i]))) : null,
      zone, input, status));
}

function icon() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "importer__icon");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", "M12 16V4M7 9l5-5 5 5M4 20h16");
  svg.append(path);
  return svg;
}

export const nseLink = (href, label) => h("a", { href, target: "_blank", rel: "noopener noreferrer" }, label);
