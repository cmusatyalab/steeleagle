import { ProgressBar } from 'primereact/progressbar';
import { Dialog } from 'primereact/dialog';
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

// Floating per-vehicle mission upload progress, shared by the Control page
// upload and the Plan page deploy. Non-modal and pinned to the top right of the
// window so it never blocks the controls; it stays until dismissed, and can
// only be dismissed once every vehicle has a result or the whole operation
// failed.
export default function MissionUploadProgress({ state, onDismiss }) {
    if (!state) return null;
    const finished = isUploadFinished(state);
    return (
        <Dialog
            visible
            modal={false}
            position="top-right"
            draggable={false}
            resizable={false}
            closable={finished}
            closeOnEscape={false}
            header={finished ? 'Mission upload finished' : (STAGE_LABELS[state.stage] ?? 'Starting…')}
            style={{ width: '40rem', maxWidth: '95vw' }}
            onHide={onDismiss}
        >
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
        </Dialog>
    );
}
