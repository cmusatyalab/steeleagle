// Pure helpers for squad selection and control-group snapshot/recall logic.
// Kept free of React state so they can be unit tested directly and reused
// from both App.jsx (keyboard shortcuts) and ControlPage.jsx (mouse/marker
// interactions) without duplicating the add/remove/snapshot semantics.

export function toggleVehicleInSquad(squadList, name) {
    const current = squadList ?? [];
    return current.includes(name)
        ? current.filter((n) => n !== name)
        : [...current, name];
}

export function assignControlGroup(controlGroups, digit, squadList) {
    return { ...controlGroups, [digit]: squadList ?? [] };
}

export function recallControlGroup(controlGroups, digit) {
    return controlGroups[digit] ?? [];
}
