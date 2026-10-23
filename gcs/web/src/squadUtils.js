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

// Set-equality (order-insensitive) between the current squad and a control
// group's saved snapshot -- lets the UI highlight whichever group button
// (if any) matches what's currently selected. Two empty arrays match; it's
// the caller's job to separately treat a never-assigned group as "unset"
// rather than "matches the current (possibly also empty) squad".
export function squadMatchesGroup(squadList, controlGroups, digit) {
    const squad = squadList ?? [];
    const group = controlGroups[digit] ?? [];
    if (squad.length !== group.length) return false;
    const groupSet = new Set(group);
    return squad.every((name) => groupSet.has(name));
}

// Which quick-select squad digits (if any) a vehicle is a saved member of.
// A vehicle can belong to more than one control group at once, since
// groups are independent saved snapshots rather than a partition -- lets
// the popup show every applicable digit rather than picking one.
export function vehicleControlGroupDigits(controlGroups, name) {
    return Object.keys(controlGroups)
        .filter((digit) => (controlGroups[digit] ?? []).includes(name))
        .sort();
}
