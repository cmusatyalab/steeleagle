import { Button } from 'primereact/button';

// Apply card on an assistant response. Clicking loads the DSL draft into the FSM Builder canvas.
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
