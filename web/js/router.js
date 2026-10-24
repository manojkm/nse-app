// Hash router: #/<view>/<arg>?key=value

export function parse(hash = location.hash) {
  const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
  const [view = "market", ...rest] = path.split("/");
  return { view: view || "market", arg: decodeURIComponent(rest.join("/")), params: Object.fromEntries(new URLSearchParams(query)) };
}

export function go(view, arg = "", params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  const hash = `#/${view}${arg ? `/${encodeURIComponent(arg)}` : ""}${qs ? `?${qs}` : ""}`;
  if (location.hash === hash) window.dispatchEvent(new HashChangeEvent("hashchange"));
  else location.hash = hash;
}

export function onRoute(cb) {
  window.addEventListener("hashchange", () => cb(parse()));
  cb(parse());
}
