export class Problem extends Error {
  constructor(body, status = 0) {
    super(
      typeof body.detail === "string"
        ? body.detail
        : "Check the file and selected rules, then try again.",
    );
    this.issues = body.issues || [];
    this.hint = body.hint || "";
    this.code = body.code;
    this.status = status;
  }
}
export async function request(path, body, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      credentials: "same-origin",
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Problem({
      detail:
        "We couldn’t reach the server. Your current file and rules are still here.",
      hint: "Check your connection and retry. Nothing has been published.",
    });
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Problem(
      { detail: "The server returned an incomplete response. Please retry." },
      response.status,
    );
  }
  if (!response.ok) throw new Problem(data, response.status);
  return data;
}
export async function verify(body, onStage, signal) {
  let response;
  try {
    response = await fetch("/api/uploads/analyze-stream", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Problem({
      detail:
        "Connection interrupted. Your file and rules are still available.",
      hint: "Retry verification when you’re connected.",
    });
  }
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new Problem(value, response.status);
  }
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "",
    result;
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder
        .decode(chunk.value || new Uint8Array(), { stream: !chunk.done })
        .replaceAll("\r\n", "\n");
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = block
          .split("\n")
          .find((v) => v.startsWith("event: "))
          ?.slice(7);
        const raw = block
          .split("\n")
          .filter((v) => v.startsWith("data: "))
          .map((v) => v.slice(6))
          .join("\n");
        if (!raw) continue;
        const value = JSON.parse(raw);
        if (event === "stage") onStage(value);
        if (event === "problem") throw new Problem(value, 422);
        if (event === "result") result = value;
      }
      if (chunk.done) break;
    }
  } finally {
    reader.releaseLock();
  }
  if (!result)
    throw new Problem({
      detail: "Verification ended without a complete result.",
      hint: "Your file is unchanged. Retry to run every check again.",
    });
  return result;
}
let refreshing;
export async function cloud(path, body) {
  try {
    return await request("/api/account" + path, body);
  } catch (error) {
    if (error.status !== 401 || path === "/sign-in" || path === "/refresh")
      throw error;
    if (!refreshing)
      refreshing = request("/api/account/refresh", {}).finally(() => {
        refreshing = undefined;
      });
    await refreshing;
    return request("/api/account" + path, body);
  }
}
