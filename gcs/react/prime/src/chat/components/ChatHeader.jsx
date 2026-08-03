import { Button } from 'primereact/button';
import { Tag } from 'primereact/tag';
import { ASSISTANT_NAME } from '../data/mockAssistant.js';

// Top bar of the chat window: assistant identity, mock-mode indicator and a
// clear-conversation action. Mirrors the toolbar styling used on the Plan page.
function ChatHeader({ title, onClear, canClear }) {
    return (
        <div className="se-chat-header">
            <div className="se-chat-header__title">
                <i className="pi pi-comments mr-2" />
                <span className="se-chat-header__name">{title || ASSISTANT_NAME}</span>
                <Tag value="Mock mode" severity="warning" className="ml-2" />
            </div>
            <Button
                label="Clear"
                icon="pi pi-eraser"
                size="small"
                outlined
                disabled={!canClear}
                onClick={onClear}
                tooltip="Clear this conversation"
                tooltipOptions={{ position: 'bottom' }}
            />
        </div>
    );
}

export default ChatHeader;
