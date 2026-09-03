import { useState } from 'react';
import { InputText } from 'primereact/inputtext';
import { InputNumber } from 'primereact/inputnumber';
import { Dropdown } from 'primereact/dropdown';

function FloatInput({ value, onChange, className }) {
    const [text, setText] = useState(() =>
        value === undefined || value === null ? '' : String(value)
    );
    const [editing, setEditing] = useState(false);
    // Resync the local edit buffer from an external value change during
    // render, not in an effect -- React's "adjusting state when a prop
    // changes" pattern. prevValue tracks what text was last derived from
    // so this only fires on an actual external change, not every render,
    // and never while the user is actively typing.
    const [prevValue, setPrevValue] = useState(value);
    if (!editing && value !== prevValue) {
        setPrevValue(value);
        setText(value === undefined || value === null ? '' : String(value));
    }

    const handleChange = (e) => {
        setEditing(true);
        const raw = e.target.value;
        // Allow only valid float-in-progress characters
        if (raw !== '' && raw !== '-' && !/^-?\d*\.?\d*$/.test(raw)) return;
        setText(raw);
        const parsed = parseFloat(raw);
        if (!isNaN(parsed) && !raw.trim().endsWith('.') && raw.trim() !== '-') {
            onChange(parsed);
        }
    };

    const handleBlur = () => {
        setEditing(false);
        const parsed = parseFloat(text);
        if (!isNaN(parsed)) {
            onChange(parsed);
            setText(String(parsed));
        } else {
            const fallback = value === undefined || value === null ? 0 : value;
            onChange(fallback);
            setText(String(fallback));
        }
    };

    return (
        <InputText
            value={text}
            onChange={handleChange}
            onBlur={handleBlur}
            className={className}
        />
    );
}

function FieldInput({ field, value, onChange, namedAreas = [], enums = {} }) {
    if (field.enum_type) {
        const enumSchema = enums[field.enum_type];
        const values = enumSchema?.values ?? [];
        // Values follow the SDK's "<EnumType><Value>" const-naming
        // convention (e.g. "PatrolModeCorridor") -- strip the type-name
        // prefix for a readable label while still sending the full name
        // as the ident_ref value the compiler expects.
        const options = values.map(v => ({
            label: v.startsWith(field.enum_type) ? v.slice(field.enum_type.length) : v,
            value: v,
        }));
        return (
            <Dropdown
                value={value ?? field.default ?? null}
                options={options.length ? options : [{ label: '(no values)', value: null }]}
                onChange={e => onChange(e.value)}
                className="w-full"
                placeholder={`Select ${field.enum_type}`}
            />
        );
    }
    if (field.type === 'boolean') {
        return (
            <Dropdown
                value={value ?? field.default ?? false}
                options={[{ label: 'true', value: true }, { label: 'false', value: false }]}
                onChange={e => onChange(e.value)}
                className="w-full"
            />
        );
    }
    if (field.type === 'number') {
        return (
            <FloatInput
                value={value === undefined ? (field.default ?? 0) : value}
                onChange={onChange}
                className="w-full"
            />
        );
    }
    if (field.type === 'integer') {
        return (
            <InputNumber
                value={value === undefined ? (field.default ?? 0) : value}
                onChange={e => onChange(e.value)}
                className="w-full"
                useGrouping={false}
                maxFractionDigits={0}
            />
        );
    }
    if (field.nested_fields?.length) {
        return (
            <div style={{ border: '1px solid #2a3a4a', borderRadius: 4, padding: '6px 8px', marginTop: 2 }}>
                {field.nested_fields.map(nf => {
                    const nestedValue = value?.[nf.name];
                    const isWaypointsArea = field.object_type === 'Waypoints' && nf.name === 'area';
                    return (
                        <div key={nf.name} style={{ marginBottom: 4 }}>
                            <label style={{ fontSize: 9, color: '#888', display: 'block' }}>{nf.name}</label>
                            {isWaypointsArea ? (
                                <Dropdown
                                    value={nestedValue ?? null}
                                    options={namedAreas.length
                                        ? namedAreas.map(a => ({ label: a, value: a }))
                                        : [{ label: '(draw area on Map tab)', value: null }]
                                    }
                                    onChange={e => onChange({ ...(value || {}), [nf.name]: e.value })}
                                    className="w-full"
                                    placeholder="Select area"
                                />
                            ) : (
                                <FieldInput
                                    field={nf}
                                    value={nestedValue}
                                    onChange={val => onChange({ ...(value || {}), [nf.name]: val })}
                                    namedAreas={namedAreas}
                                    enums={enums}
                                />
                            )}
                        </div>
                    );
                })}
            </div>
        );
    }
    return (
        <InputText
            value={value ?? field.default ?? ''}
            onChange={e => onChange(e.target.value)}
            className="w-full"
        />
    );
}

export default FieldInput;
