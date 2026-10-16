import React, { useId } from 'react';
import { Checkbox } from 'primereact/checkbox';
import { InputNumber } from 'primereact/inputnumber';

// A vehicle's [vehicles.sim] table: whether it runs in the aviary simulator,
// and its origin. Coordinates are only required when it does (see
// configForm.js simErrors).
function SimFields({ sim, onChange, disabled = false, errors = {} }) {
    const checkboxId = useId();
    const coord = (key, label) => (
        <div className="flex flex-column gap-1 flex-1">
            <label className="text-sm">{label}</label>
            <InputNumber
                value={sim[key]}
                onValueChange={(e) => onChange({ ...sim, [key]: e.value })}
                disabled={disabled}
                mode="decimal"
                minFractionDigits={0}
                maxFractionDigits={7}
                useGrouping={false}
                invalid={!!errors[key]}
                inputClassName="w-full"
            />
            {errors[key] && <small className="p-error">{errors[key]}</small>}
        </div>
    );

    return (
        <div className="flex flex-column gap-2">
            <div className="flex align-items-center gap-2">
                <Checkbox inputId={checkboxId} checked={!!sim.default} onChange={(e) => onChange({ ...sim, default: e.checked })} disabled={disabled} />
                <label htmlFor={checkboxId} className="text-sm">Simulated (runs in the aviary simulator)</label>
            </div>
            <div className="flex gap-2">
                {coord('lat', 'Latitude')}
                {coord('lon', 'Longitude')}
                {coord('alt', 'Altitude (m)')}
            </div>
        </div>
    );
}

export default SimFields;
