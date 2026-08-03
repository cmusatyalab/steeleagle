import { Button } from 'primereact/button';

// Renders an apply-able artifact attached to an assistant message.
// In this first version clicking simply forwards to the host app's
// onApplyArtifact callback, which shows a "not connected yet" toast.
function ApplyActionCard({ artifact, onApply }) {
    if (!artifact) return null;

    const nodeCount = artifact.payload?.nodes?.length ?? 0;

    return (
        <div className="se-chat-apply-card">
            <div className="se-chat-apply-card__info">
                <i className="pi pi-sitemap" />
                <div>
                    <div className="se-chat-apply-card__title">{artifact.label}</div>
                    {nodeCount > 0 && (
                        <div className="se-chat-apply-card__meta">
                            {nodeCount} action{nodeCount !== 1 ? 's' : ''} in draft
                        </div>
                    )}
                </div>
            </div>
            <Button
                label="Apply"
                icon="pi pi-arrow-right"
                size="small"
                onClick={() => onApply?.(artifact.target, artifact)}
            />
        </div>
    );
}

export default ApplyActionCard;
