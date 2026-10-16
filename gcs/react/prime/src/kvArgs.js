// Rows <-> object conversion for KeyValueEditor. Values are TOML scalars
// typed string / number / boolean. Arrays and tables have no form
// representation, so they become read-only 'other' rows whose value passes
// through untouched (they're edited in Raw TOML instead).

export const KV_TYPES = ['string', 'number', 'boolean'];

let nextRowId = 0;
const rowId = () => `kv-${nextRowId++}`;

export function typeOf(value) {
    if (typeof value === 'boolean') return 'boolean';
    if (typeof value === 'number') return 'number';
    if (typeof value === 'string') return 'string';
    return 'other';
}

// Number values are held as text while editing so "1." or "" can be typed.
export function toRows(obj) {
    return Object.entries(obj ?? {}).map(([key, value]) => {
        const type = typeOf(value);
        return { id: rowId(), key, type, value: type === 'number' ? String(value) : value };
    });
}

export function newRow() {
    return { id: rowId(), key: '', type: 'string', value: '' };
}

// Changing a row's type converts its value as sensibly as it can.
export function retype(row, type) {
    if (type === row.type) return row;
    if (type === 'boolean') return { ...row, type, value: row.value === true || row.value === 'true' };
    if (type === 'number') {
        return { ...row, type, value: typeof row.value === 'boolean' ? (row.value ? '1' : '0') : String(row.value) };
    }
    return { ...row, type, value: String(row.value) };
}

// Returns { value, errors }: errors maps row id -> message, and value holds
// every valid row (only meaningful to submit when errors is empty).
export function fromRows(rows) {
    const value = {};
    const errors = {};
    const seen = new Set();
    for (const row of rows) {
        const key = row.key.trim();
        if (!key) {
            errors[row.id] = 'Key is required';
            continue;
        }
        if (seen.has(key)) {
            errors[row.id] = `Duplicate key "${key}"`;
            continue;
        }
        seen.add(key);
        if (row.type === 'number') {
            const text = String(row.value).trim();
            const number = Number(text);
            if (text === '' || !Number.isFinite(number)) {
                errors[row.id] = 'Not a number';
                continue;
            }
            value[key] = number;
        } else {
            value[key] = row.value;
        }
    }
    return { value, errors };
}
