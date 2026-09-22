import { Sidebar } from 'primereact/sidebar';
import { InputText } from 'primereact/inputtext';
import { Button } from 'primereact/button';
import FieldInput from './FieldInput.jsx';

function TaskNodePanel({ visible, onHide, node, schema, namedAreas, onUpdate, onUpdateId, onDelete }) {
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
                    <label style={{ fontSize: 13, color: 'var(--text-color-secondary)', display: 'block', marginBottom: 4 }}>Instance ID</label>
                    <InputText
                        value={instance_id}
                        onChange={e => onUpdateId(node.id, e.target.value)}
                        className="w-full"
                    />
                </div>
                {fields.map(f => (
                    <div key={f.name}>
                        <label style={{ fontSize: 13, color: 'var(--text-color-secondary)', display: 'block', marginBottom: 4 }}>
                            {f.name}
                            {f.required && <span style={{ color: '#e88' }}> *</span>}
                            {f.description && (
                                <span style={{ fontSize: 12, color: '#666', marginLeft: 6 }}>{f.description}</span>
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

                <hr style={{ borderColor: '#2a3a4a', margin: '4px 0' }} />
                <Button
                    label="Delete node"
                    icon="pi pi-trash"
                    severity="danger"
                    outlined
                    size="small"
                    onClick={() => { onDelete(node.id); onHide(); }}
                />
            </div>
        </Sidebar>
    );
}

export default TaskNodePanel;
