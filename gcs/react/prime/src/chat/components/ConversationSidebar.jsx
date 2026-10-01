import { useState } from 'react';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';
import { IconField } from 'primereact/iconfield';
import { InputIcon } from 'primereact/inputicon';
import { Dialog } from 'primereact/dialog';
import { confirmDialog, ConfirmDialog } from 'primereact/confirmdialog';
import { classNames } from 'primereact/utils';
import { filterSessions } from '../hooks/sessionLogic.js';

function relativeTime(ts) {
    const diff = Date.now() - ts;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
}

// Left column: create, search, select, rename and delete conversations.
function ConversationSidebar({
    sessions,
    activeId,
    onNew,
    onSelect,
    onRename,
    onDelete,
}) {
    const [query, setQuery] = useState('');
    const [renameTarget, setRenameTarget] = useState(null);
    const [renameValue, setRenameValue] = useState('');

    const visible = filterSessions(sessions, query);

    function openRename(session, e) {
        e.stopPropagation();
        setRenameTarget(session);
        setRenameValue(session.title);
    }

    function commitRename() {
        if (renameTarget) onRename(renameTarget.id, renameValue);
        setRenameTarget(null);
    }

    function confirmDelete(session, e) {
        e.stopPropagation();
        confirmDialog({
            message: `Delete "${session.title}"?`,
            header: 'Delete conversation',
            icon: 'pi pi-exclamation-triangle',
            acceptClassName: 'p-button-danger',
            accept: () => onDelete(session.id),
        });
    }

    return (
        <div className="se-chat-sidebar">
            <ConfirmDialog />
            <div className="se-chat-sidebar__top">
                <Button
                    label="New chat"
                    icon="pi pi-plus"
                    className="w-full"
                    size="small"
                    onClick={onNew}
                />
                <IconField iconPosition="left" className="w-full mt-2">
                    <InputIcon className="pi pi-search" />
                    <InputText
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search conversations"
                        className="w-full p-inputtext-sm"
                    />
                </IconField>
            </div>

            <div className="se-chat-sidebar__list">
                {visible.length === 0 && (
                    <div className="se-chat-sidebar__empty">No conversations found</div>
                )}
                {visible.map((s) => (
                    <div
                        key={s.id}
                        className={classNames('se-chat-conv', { 'se-chat-conv--active': s.id === activeId })}
                        onClick={() => onSelect(s.id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => e.key === 'Enter' && onSelect(s.id)}
                    >
                        <div className="se-chat-conv__body">
                            <div className="se-chat-conv__title" data-title={s.title}>
                                {s.title}
                            </div>
                            <div className="se-chat-conv__meta">{relativeTime(s.updatedAt)}</div>
                        </div>
                        <div className="se-chat-conv__actions">
                            <Button
                                icon="pi pi-pencil"
                                rounded
                                text
                                size="small"
                                onClick={(e) => openRename(s, e)}
                                aria-label="Rename conversation"
                            />
                            <Button
                                icon="pi pi-trash"
                                rounded
                                text
                                severity="danger"
                                size="small"
                                onClick={(e) => confirmDelete(s, e)}
                                aria-label="Delete conversation"
                            />
                        </div>
                    </div>
                ))}
            </div>

            <Dialog
                header="Rename conversation"
                visible={!!renameTarget}
                style={{ width: 320 }}
                onHide={() => setRenameTarget(null)}
                footer={
                    <>
                        <Button label="Cancel" text size="small" onClick={() => setRenameTarget(null)} />
                        <Button label="Save" size="small" onClick={commitRename} />
                    </>
                }
            >
                <InputText
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && commitRename()}
                    className="w-full"
                    autoFocus
                />
            </Dialog>
        </div>
    );
}

export default ConversationSidebar;
