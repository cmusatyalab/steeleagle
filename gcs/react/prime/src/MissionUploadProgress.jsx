import { ProgressBar } from 'primereact/progressbar';
import { Button } from 'primereact/button';
import { Message } from 'primereact/message';
import { isUploadFinished, progressPercent } from './missionUpload.js';

const STAGE_LABELS = { building: 'Building mission…', uploading: 'Uploading to vehicles…' };

function statusText(v) {
    switch (v.status) {
        case 'success': return '✓ Uploaded';
        case 'failed': return `✗ ${v.details || 'Failed'}`;
        case 'uploading': return `${progressPercent(v)}%`;
        default: return 'Waiting…';
    }
}

// Inline per-vehicle mission upload progress. Stays until dismissed; the
// dismiss button is enabled once every vehicle has a result or the whole
// operation failed.
export default function MissionUploadProgress({ state, onDismiss }) {
    if (!state) return null;
    const finished = isUploadFinished(state);
    return (
        <div className="p-3 my-2 border-1 surface-border border-round">
            <div className="flex align-items-center justify-content-between mb-2">
                <span className="font-bold">
                    {finished ? 'Mission upload finished' : (STAGE_LABELS[state.stage] ?? 'Starting…')}
                </span>
                <Button icon="pi pi-times" rounded text size="small" aria-label="Dismiss"
                    disabled={!finished} onClick={onDismiss} />
            </div>
            {state.error && <Message severity="error" text={state.error} className="w-full mb-2" />}
            {Object.entries(state.vehicles).map(([name, v]) => (
                <div key={name} className="flex align-items-center gap-3 mb-2">
                    <span style={{ minWidth: '8rem' }}>{name}</span>
                    <ProgressBar
                        className="flex-1"
                        style={{ height: '0.75rem' }}
                        mode={v.status === 'pending' && !finished ? 'indeterminate' : 'determinate'}
                        value={progressPercent(v)}
                        showValue={false}
                        color={v.status === 'failed' ? 'var(--red-500)' : undefined}
                    />
                    <span style={{ minWidth: '12rem' }}>{statusText(v)}</span>
                </div>
            ))}
        </div>
    );
}
