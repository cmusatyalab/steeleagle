// Right-click menu shared by the Mission Builder and Flow Builder canvases.
// `position` is {x, y} in viewport coordinates (or null for closed); each
// item is {label, onClick, danger?}. Choosing an item runs it and closes the
// menu. The border follows --menu-accent where a canvas defines it.
function CanvasContextMenu({ position, items, onClose }) {
    if (!position) return null;
    return (
        <div
            style={{
                position: 'fixed', left: position.x, top: position.y,
                background: '#1e2a38', border: '1px solid var(--menu-accent, #4a7a9b)', borderRadius: 6,
                zIndex: 1000, minWidth: 160, boxShadow: '0 4px 12px #00000088',
            }}
            onClick={(e) => e.stopPropagation()}
            onContextMenu={(e) => e.preventDefault()}
        >
            {items.map((item) => (
                <div
                    key={item.label}
                    style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12, color: item.danger ? '#e88080' : undefined }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = '#2a3a50'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}
                    onClick={() => { item.onClick(); onClose(); }}
                >
                    {item.label}
                </div>
            ))}
        </div>
    );
}

export default CanvasContextMenu;
