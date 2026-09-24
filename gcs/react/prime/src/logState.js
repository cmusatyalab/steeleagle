// Pure helpers behind LogViewer: record shaping, resume cursors, the capped
// row buffer, and the client-side level filter. Kept free of React so the
// tricky parts (cursor and cap behavior) are unit-testable.

export const MAX_RECORDS = 5000;
export const LEVELS = ['trace', 'debug', 'info', 'warn', 'error', 'fatal', 'panic'];

export function initialLogState() {
    return { records: [], gapCount: 0 };
}

// SSE `record` payload -> the row shape the viewer renders.
export function toRow(msg) {
    return {
        source: msg.source,
        seq: msg.seq,
        time: new Date(msg.time),
        level: msg.level || '',
        text: msg.text,
        dropped: msg.dropped || 0,
    };
}

// Per-source resume cursor: the highest seq seen. Gap markers (dropped > 0,
// seq 0) never move it -- the dropped lines are exactly what a reconnect
// with these cursors would backfill.
export function advanceCursors(cursors, row) {
    if (row.dropped > 0 || !(row.seq > (cursors[row.source] ?? 0))) return cursors;
    return { ...cursors, [row.source]: row.seq };
}

export function appendRows(state, rows, cap = MAX_RECORDS) {
    if (rows.length === 0) return state;
    let gapCount = state.gapCount;
    const keyed = rows.map((r) =>
        r.dropped > 0 ? { ...r, key: `gap#${gapCount++}` } : { ...r, key: `${r.source}#${r.seq}` }
    );
    const records = state.records.concat(keyed);
    return { records: records.length > cap ? records.slice(records.length - cap) : records, gapCount };
}

// Most plugin output has no parsed level, so level-less rows always show
// rather than vanishing the moment any level filter is chosen.
export function filterRows(rows, levels) {
    if (!levels || levels.length === 0) return rows;
    const allowed = new Set(levels);
    return rows.filter((r) => r.dropped > 0 || r.level === '' || allowed.has(r.level));
}
