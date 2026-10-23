import React from 'react';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';
import { SelectButton } from 'primereact/selectbutton';
import KeyValueEditor from './KeyValueEditor.jsx';
import SimFields from './SimFields.jsx';
import { RUNTIMES } from './configForm.js';
import { runtimeLabel, sourceLabel } from './pluginView.js';

const RUNTIME_OPTIONS = RUNTIMES.map((r) => ({ label: runtimeLabel(r), value: r }));
const SOURCE_KINDS = [{ label: 'Repository', value: 'repo' }, { label: 'Image', value: 'image' }];

// One service instance in the Configure dialog: a collapsible card with its
// plugin fields, plugin args and, for vehicles, sim origin and vehicle args.
function InstanceEditor({ inst, errors = {}, expanded, onToggle, onChange, onRemove, onDuplicate, disabled }) {
    const isVehicle = inst.category === 'vehicle';
    const isImage = inst.runtime === 'container' && inst.sourceKind === 'image';
    const summary = sourceLabel(inst.url.trim() ? { url: inst.url.trim(), tag: inst.tag.trim() } : null);

    const text = (label, field, props = {}) => (
        <div className="flex flex-column gap-1 flex-1">
            <label className="text-sm">{label}</label>
            <InputText value={inst[field]} onChange={(e) => onChange({ [field]: e.target.value })} disabled={disabled} invalid={!!errors[field]} {...props} />
            {errors[field] && <small className="p-error">{errors[field]}</small>}
        </div>
    );

    return (
        <div className="border-round" style={{ border: '1px solid var(--surface-border)' }}>
            <div className="flex align-items-center gap-2 p-2 cursor-pointer" onClick={onToggle}>
                <i className={expanded ? 'pi pi-chevron-down' : 'pi pi-chevron-right'} />
                <span className="font-semibold">{inst.name.trim() || <span className="text-color-secondary">(unnamed)</span>}</span>
                <span className="text-sm text-color-secondary flex-1 white-space-nowrap overflow-hidden text-overflow-ellipsis">{summary === '—' ? inst.pluginId : summary}</span>
                {Object.keys(errors).length > 0 && <i className="pi pi-exclamation-circle" style={{ color: 'var(--red-500)' }} title="Has errors" />}
                <span className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                    {isVehicle && (
                        <Button icon="pi pi-clone" size="small" text rounded tooltip="Duplicate vehicle" tooltipOptions={{ position: 'top' }} aria-label="Duplicate vehicle" onClick={onDuplicate} disabled={disabled} />
                    )}
                    <Button icon="pi pi-trash" size="small" text rounded severity="danger" tooltip="Remove" tooltipOptions={{ position: 'top' }} aria-label="Remove" onClick={onRemove} disabled={disabled} />
                </span>
            </div>
            {expanded && (
                <div className="flex flex-column gap-3 p-3 pt-1">
                    <div className="flex gap-2">
                        {text('Name', 'name')}
                        {text('Plugin ID', 'pluginId', { placeholder: 'defaults from the source' })}
                    </div>
                    <div className="flex flex-column gap-1">
                        <label className="text-sm">Runtime</label>
                        <SelectButton value={inst.runtime} options={RUNTIME_OPTIONS} onChange={(e) => onChange({ runtime: e.value ?? null })} disabled={disabled} />
                    </div>
                    {inst.runtime === 'container' && (
                        <SelectButton value={inst.sourceKind} options={SOURCE_KINDS} onChange={(e) => e.value && onChange({ sourceKind: e.value })} disabled={disabled} />
                    )}
                    <div className="flex gap-2">
                        {text(isImage ? 'Image' : 'Repository URL', 'url', { placeholder: isImage ? 'docker.io/org/image' : 'https://github.com/org/plugin.git' })}
                        <div style={{ width: '10rem' }}>{text(isImage ? 'Tag' : 'Branch / tag', 'tag')}</div>
                    </div>
                    <div className="flex flex-column gap-1">
                        <span className="font-semibold text-sm">Plugin args</span>
                        <KeyValueEditor rows={inst.argRows} onChange={(argRows) => onChange({ argRows })} disabled={disabled} />
                    </div>
                    {isVehicle && (
                        <>
                            <div className="flex flex-column gap-1">
                                <span className="font-semibold text-sm">Vehicle args</span>
                                <KeyValueEditor rows={inst.vehicleArgRows} onChange={(vehicleArgRows) => onChange({ vehicleArgRows })} disabled={disabled} />
                            </div>
                            <SimFields sim={inst.sim} onChange={(sim) => onChange({ sim })} disabled={disabled} errors={errors.sim ?? {}} />
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

export default InstanceEditor;
