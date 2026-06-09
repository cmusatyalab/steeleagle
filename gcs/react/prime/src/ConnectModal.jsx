import { useState } from 'react';
import { Dialog } from 'primereact/dialog';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';
import { Dropdown } from 'primereact/dropdown';
import FieldInput from './FieldInput.jsx';

function NewEventForm({ schema, onAdd }) {
    const eventTypes = Object.keys(schema.events || {});
    const [typeName, setTypeName] = useState(eventTypes[0] ?? '');
    const [instanceId, setInstanceId] = useState('');
    const [params, setParams] = useState({});

    const fields = typeName ? (schema.events[typeName]?.fields ?? []) : [];

    function updateParam(name, val) {
        setParams(p => ({ ...p, [name]: val }));
    }

    function handleAdd() {
        if (!typeName || !instanceId.trim()) return;
        onAdd({ instance_id: instanceId.trim(), type_name: typeName, params });
    }

    return (
        <div style={{ border: '1px solid #2a3a4a', borderRadius: 6, padding: 10, marginTop: 8 }}>
            <p style={{ fontSize: 11, color: '#7ecfff', marginBottom: 8 }}>Define new event</p>
            <div className="flex gap-2 mb-2">
                <Dropdown
                    value={typeName}
                    options={eventTypes.map(t => ({ label: t, value: t }))}
                    onChange={e => { setTypeName(e.value); setParams({}); }}
                    placeholder="Event type"
                    style={{ flex: 1 }}
                    className="p-inputtext-sm"
                />
                <InputText
                    value={instanceId}
                    onChange={e => setInstanceId(e.target.value)}
                    placeholder="instance_id"
                    className="p-inputtext-sm"
                    style={{ flex: 1 }}
                />
            </div>
            {fields.map(f => (
                <div key={f.name} className="mb-2">
                    <label style={{ fontSize: 9, color: '#aaa', display: 'block' }}>
                        {f.name}{f.required && <span style={{ color: '#e88' }}> *</span>}
                    </label>
                    <FieldInput
                        field={f}
                        value={params[f.name]}
                        onChange={val => updateParam(f.name, val)}
                    />
                </div>
            ))}
            <Button label="Add event" size="small" onClick={handleAdd} disabled={!typeName || !instanceId.trim()} />
        </div>
    );
}

function ConnectModal({ visible, onHide, connection, eventInstances, schema, onConfirm, onAddEvent }) {
    const [showNewForm, setShowNewForm] = useState(false);

    if (!connection) return null;
    const isSelfLoop = connection.source === connection.target;

    function handlePick(eventId) {
        onConfirm(connection, eventId);
        onHide();
    }

    function handleAddEvent(ev) {
        onAddEvent(ev);
        setShowNewForm(false);
        onConfirm(connection, ev.instance_id);
        onHide();
    }

    return (
        <Dialog
            header={
                <span style={{ fontSize: 13 }}>
                    Transition: {connection.source} → {isSelfLoop ? connection.source : connection.target}
                    {isSelfLoop && <span style={{ color: '#e8c87a', marginLeft: 8, fontSize: 10 }}>(self-loop)</span>}
                </span>
            }
            visible={visible}
            onHide={() => { setShowNewForm(false); onHide(); }}
            style={{ width: 360 }}
        >
            <p style={{ fontSize: 11, color: '#aaa', marginBottom: 8 }}>Trigger event:</p>

            {/* done — always shown */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                <Button
                    label="done"
                    size="small"
                    severity="success"
                    outlined
                    onClick={() => handlePick('done')}
                />
                {eventInstances.map(ev => (
                    <Button
                        key={ev.instance_id}
                        label={ev.instance_id}
                        size="small"
                        severity="secondary"
                        outlined
                        onClick={() => handlePick(ev.instance_id)}
                    />
                ))}
            </div>

            <Button
                label={showNewForm ? '— cancel' : '+ Define new event…'}
                size="small"
                text
                onClick={() => setShowNewForm(f => !f)}
            />

            {showNewForm && (
                <NewEventForm schema={schema} onAdd={handleAddEvent} />
            )}
        </Dialog>
    );
}

export default ConnectModal;
