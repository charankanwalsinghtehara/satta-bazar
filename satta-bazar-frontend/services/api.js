const API_BASE_URL = "/api/v1";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getErrorMessage(data, fallback) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.join(" ");
  if (detail && typeof detail === "object") {
    return Object.values(detail).flat().join(" ");
  }
  if (data && typeof data === "object") {
    return Object.values(data).flat().join(" ");
  }
  return fallback;
}

async function request(path, { method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: "same-origin",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data =
    response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(data, `Request failed (${response.status}).`),
      response.status,
    );
  }
  return data;
}

function csrfToken() {
  return document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("csrftoken="))
    ?.slice("csrftoken=".length);
}

async function csrfRequest(path, body) {
  await request("/auth/csrf/");
  const token = csrfToken();
  if (!token) throw new Error("The server did not provide a CSRF cookie.");

  const headers = {
    Accept: "application/json",
    "Content-Type": "application/json",
    "X-CSRFToken": decodeURIComponent(token),
  };
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "same-origin",
    headers,
    body: JSON.stringify(body),
  });
  const data =
    response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(data, `Request failed (${response.status}).`),
      response.status,
    );
  }
  return data;
}

export function getMarketOverview() {
  return request("/market/overview/");
}

export function getMarketMovers() {
  return request("/market/movers/");
}

export function getLeaderboard() {
  return request("/leaderboards/");
}

export function getMe() {
  return request("/auth/me/");
}

export function getWallet() {
  return request("/wallet/");
}

export function login(credentials) {
  return csrfRequest("/auth/login/", credentials);
}

export function register(details) {
  return csrfRequest("/auth/register/", details);
}

export function logout() {
  return csrfRequest("/auth/logout/", {});
}

export function buyAsset(trade) {
  return csrfRequest("/trades/buy/", trade);
}

export function sellAsset(trade) {
  return csrfRequest("/trades/sell/", trade);
}

export function getAssetHistory(symbol) {
  return request(`/assets/${encodeURIComponent(symbol)}/history/`);
}
