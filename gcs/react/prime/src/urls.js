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

// Imagery stream for one vehicle, or null (react-use-websocket's "don't
// connect") when none is selected. Connecting with an empty vehicle name hits
// a path the backend rejects, and react-use-websocket then retries every 5s;
// Firefox answers repeated failed handshakes by delaying *every* new websocket
// to the same host, which stalled the presence bar for seconds at a time.
export function getImagerySocketUrl(vehicle) {
  if (!vehicle) return null;
  return getWebSocketUrl(`/ws/imagery/remote/${vehicle}`);
}
