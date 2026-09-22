import { getApiUrl } from './urls.js';

// Posts body to path and returns the parsed JSON response, or null on any
// failure. Every failure path surfaces an error toast (via the passed-in
// toast ref) instead of failing silently. Originally App.jsx-private
// (onJoystick/onCommand/onGimbal); factored out so OrchestrationPage.jsx
// gets the same fetch/error-toast handling instead of reimplementing it.
export async function postToApi(path, body, toast, errorSummary) {
    let response;
    try {
        response = await fetch(getApiUrl(path), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
    } catch (err) {
        toast.current.show({ severity: 'error', summary: errorSummary, detail: `request failed: ${err.message}` });
        return null;
    }

    let result;
    try {
        result = await response.json();
    } catch {
        toast.current.show({ severity: 'error', summary: errorSummary, detail: `server returned a non-JSON response (status ${response.status})` });
        return null;
    }

    if (!response.ok) {
        toast.current.show({ severity: 'error', summary: errorSummary, detail: `HTTP error! status: ${result.detail ?? response.status}` });
        return null;
    }
    return result;
}
