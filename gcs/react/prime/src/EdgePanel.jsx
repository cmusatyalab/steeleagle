import { Sidebar } from 'primereact/sidebar';
import { Button } from 'primereact/button';
import FieldInput from './FieldInput.jsx';

function EdgePanel({ visible, onHide, edge, eventInstance, eventSchema, sourceLabel, targetLabel, onUpdateEvent, onDeleteEdge }) {
    if (!edge) return null;

    const eventId = edge.data?.eventId ?? 'done';
    const isDone = eventId === 'done';
    const fields = eventSchema?.fields ?? [];
    const params = eventInstance?.params ?? {};

    function updateParam(fieldName, val) {
        onUpdateEvent(eventInstance.instance_id, { ...params, [fieldName]: val });
    }

    return (
        <Sidebar
            visible={visible}
            position="right"
            onHide={onHide}
            style={{ width: 320 }}
            header={<span style={{ fontWeight: 'bold' }}>Transition</span>}
        >
            <div className="flex flex-column gap-3 p-2">
                <div style={{ fontSize: 12, color: '#aaa' }}>
                    <span style={{ color: '#7ecfff' }}>{sourceLabel}</span>
                    <span> → </span>
                    <span style={{ color: '#7ecfff' }}>{targetLabel}</span>
                </div>

                <div style={{ fontSize: 12 }}>
                    <span style={{ color: '#aaa' }}>Event: </span>
                    <span style={{ color: isDone ? '#a3e8a0' : '#c47aff', fontWeight: 'bold' }}>{eventId}</span>
                    {eventInstance && (
                        <span style={{ color: '#666', fontSize: 11, marginLeft: 6 }}>({eventInstance.type_name})</span>
                    )}
                </div>

                {isDone && (
                    <p style={{ fontSize: 11, color: '#666', margin: 0 }}>
                        "done" is the built-in completion event and has no parameters.
                    </p>
                )}

                {!isDone && fields.map(f => (
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
                        />
                    </div>
                ))}

                {!isDone && !fields.length && (
                    <p style={{ fontSize: 11, color: '#666', margin: 0 }}>This event type has no configurable parameters.</p>
                )}

                <hr style={{ borderColor: '#2a3a4a', margin: '4px 0' }} />

                <Button
                    label="Delete transition"
                    icon="pi pi-trash"
                    severity="danger"
                    outlined
                    size="small"
                    onClick={() => { onDeleteEdge(edge.id); onHide(); }}
                />
            </div>
        </Sidebar>
    );
}

export default EdgePanel;
