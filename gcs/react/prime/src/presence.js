// Collapses the backend's per-tab viewer list (see /ws/presence) into one
// entry per host, with the host this tab belongs to listed first.
export function groupViewers(viewers, youId) {
    const groups = new Map();
    for (const v of viewers ?? []) {
        const group = groups.get(v.host) ?? { host: v.host, count: 0, isYou: false };
        group.count += 1;
        if (v.id === youId) group.isYou = true;
        groups.set(v.host, group);
    }
    return [...groups.values()].sort((a, b) => Number(b.isYou) - Number(a.isYou));
}

export function viewerLabel({ host, count, isYou }) {
    return `${host}${isYou ? ' (you)' : ''}${count > 1 ? ` ×${count}` : ''}`;
}
