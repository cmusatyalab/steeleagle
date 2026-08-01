export function getWebSocketUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host; // includes port if present
  return `${protocol}//${host}${path}`;
}

export function getApiUrl(path) {
  const protocol = window.location.protocol;
  const host = window.location.host; // includes port if present
  return `${protocol}//${host}${path}`;
}
