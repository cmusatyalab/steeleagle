// Form rules for installing a plugin on a daemon. They mirror the backend's
// InstallPluginBody (gcs/react/backend/app/eagled_routes.py) so the form
// can't submit something the route would reject: name and subpath end up as
// filesystem paths on the daemon host, so they're checked here at the edge.

export const PLUGIN_CATEGORIES = ['driver', 'mission', 'extra'];

const NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const NAME_MAX_LENGTH = 64;

export function emptyInstallForm() {
    return { name: '', repo: '', ref: '', subpath: '', category: null };
}

// Returns { field: message } for every invalid field; {} means valid.
export function validateInstallForm(form) {
    const errors = {};

    const name = form.name.trim();
    if (!name) errors.name = 'Required';
    else if (name.length > NAME_MAX_LENGTH) errors.name = `At most ${NAME_MAX_LENGTH} characters`;
    else if (!NAME_PATTERN.test(name)) errors.name = 'Letters, digits, ".", "_" and "-" only; must start with a letter or digit';

    if (!form.repo.trim()) errors.repo = 'Required';
    if (!form.ref.trim()) errors.ref = 'Required';

    const subpath = form.subpath.trim();
    if (subpath && (subpath.startsWith('/') || subpath.split('/').includes('..'))) {
        errors.subpath = 'Must be relative and stay inside the repo';
    }

    if (!PLUGIN_CATEGORIES.includes(form.category)) errors.category = 'Required';

    return errors;
}

export function installRequestBody(address, form) {
    return {
        address,
        name: form.name.trim(),
        repo: form.repo.trim(),
        ref: form.ref.trim(),
        subpath: form.subpath.trim(),
        category: form.category,
    };
}
