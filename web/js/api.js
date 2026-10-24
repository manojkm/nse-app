// Calls the local server's REST API (same tools the MCP server exposes).

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export const state = { demo: false };

export async function callTool(name, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== ""));
  let res;
  try {
    res = await fetch(`api/tools/${name}${qs.size ? `?${qs}` : ""}`, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError("Can't reach the local server. Is it still running?", 0);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(body.error || `Request failed (${res.status})`, res.status);
  if (body.demo !== state.demo) {
    state.demo = !!body.demo;
    document.dispatchEvent(new CustomEvent("demo-change"));
  }
  return body.data;
}
