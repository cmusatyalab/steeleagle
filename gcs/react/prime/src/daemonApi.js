import { getApiUrl } from './urls.js';

// JSON request to an /api/daemons route. Never rejects: resolves to
// { status, body } (body is the parsed JSON, or null for a non-JSON reply),
// or { status: 0, body: null, networkError } when the request itself fails,
// so callers handle every outcome through describeFailure.
export async function daemonRequest(method, path, body) {
    let response;
    try {
        response = await fetch(getApiUrl(path), {
            method,
            headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
            body: body === undefined ? undefined : JSON.stringify(body),
        });
    } catch (err) {
        return { status: 0, body: null, networkError: err.message };
    }
    try {
        return { status: response.status, body: await response.json() };
    } catch {
        return { status: response.status, body: null };
    }
}

// The 422 detail shapes these routes produce: our {message, line, column}
// object, FastAPI's list of pydantic errors, or a plain string.
export function formatDetail(detail) {
    if (detail && typeof detail === 'object' && !Array.isArray(detail) && detail.message) {
        return detail.line ? `${detail.message} (line ${detail.line}, column ${detail.column})` : detail.message;
    }
    if (Array.isArray(detail)) {
        return detail.map((d) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`).join('; ');
    }
    return String(detail ?? 'Invalid request');
}

// One line describing why a daemonRequest result failed, or null if it
// succeeded. Daemon routes report unreachable daemons and failed
// operations in a 200 body (reachable / ok / error), not via HTTP status.
export function describeFailure({ status, body, networkError }) {
    if (status === 0) return `Request failed: ${networkError}`;
    if (body === null) return `Server returned a non-JSON response (status ${status}).`;
    if (status === 422) return formatDetail(body.detail);
    if (status >= 400) return `Request rejected (HTTP ${status}).`;
    if (body.reachable === false) return body.error ?? 'Daemon unreachable';
    if (body.ok === false) return body.error ?? 'Request failed';
    return null;
}

export function query(params) {
    return new URLSearchParams(params).toString();
}
