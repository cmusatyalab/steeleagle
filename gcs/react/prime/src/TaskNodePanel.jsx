import { Sidebar } from 'primereact/sidebar';
import { InputText } from 'primereact/inputtext';
import { InputNumber } from 'primereact/inputnumber';
import { Dropdown } from 'primereact/dropdown';

function FieldInput({ field, value, onChange, namedAreas }) {
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
                value={value ?? field.default ?? 0}
                onValueChange={e => onChange(e.value)}
                className="w-full"
                useGrouping={false}
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

function TaskNodePanel({ visible, onHide, node, schema, namedAreas, onUpdate, onUpdateId }) {
    if (!node) return null;
    const { type_name, instance_id, params } = node.data;
    const fields = schema?.fields ?? [];

    function updateParam(fieldName, val) {
        onUpdate(node.id, { ...params, [fieldName]: val });
    }

    return (
        <Sidebar
            visible={visible}
            position="right"
            onHide={onHide}
            style={{ width: 320 }}
            header={<span style={{ fontWeight: 'bold' }}>{type_name}</span>}
        >
            <div className="flex flex-column gap-3 p-2">
                <div>
                    <label className="text-sm text-color-secondary block mb-1">Instance ID</label>
                    <InputText
                        value={instance_id}
                        onChange={e => onUpdateId(node.id, e.target.value)}
                        className="w-full"
                    />
                </div>
                {fields.map(f => (
                    <div key={f.name}>
                        <label className="text-sm text-color-secondary block mb-1">
                            {f.name}
                            {f.required && <span style={{ color: '#e88' }}> *</span>}
                            {f.description && (
                                <span style={{ fontSize: 10, color: '#666', marginLeft: 6 }}>{f.description}</span>
                            )}
                        </label>
                        <FieldInput
                            field={f}
                            value={params[f.name]}
                            onChange={val => updateParam(f.name, val)}
                            namedAreas={namedAreas}
                        />
                    </div>
                ))}
            </div>
        </Sidebar>
    );
}

export default TaskNodePanel;
