import { InputText } from 'primereact/inputtext';
import { InputNumber } from 'primereact/inputnumber';
import { Dropdown } from 'primereact/dropdown';

function FieldInput({ field, value, onChange, namedAreas = [] }) {
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
    if (field.type === 'number' || field.type === 'integer') {
        return (
            <InputNumber
                value={value === undefined ? (field.default ?? 0) : value}
                onChange={e => onChange(e.value)}
                className="w-full"
                useGrouping={false}
                maxFractionDigits={field.type === 'number' ? 10 : 0}
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
