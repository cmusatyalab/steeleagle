import { Splitter, SplitterPanel } from 'primereact/splitter';
import { useChatSessions } from './hooks/useChatSessions.js';
import ConversationSidebar from './components/ConversationSidebar.jsx';
import ChatHeader from './components/ChatHeader.jsx';
import MessageList from './components/MessageList.jsx';
import ChatComposer from './components/ChatComposer.jsx';
import { isPristine } from './hooks/sessionLogic.js';
import './chat.css';

// Top-level chat page. Owns no business logic itself; it coordinates the
// session store (useChatSessions) with presentational components and forwards
// artifact "apply" actions up to the host app via onApplyArtifact.
function ChatPage({ onApplyArtifact }) {
    const {
        sessions,
        activeId,
        activeSession,
        isResponding,
        newConversation,
        selectConversation,
        rename,
        remove,
        clearActive,
        sendMessage,
        stopResponding,
    } = useChatSessions();

    const messages = activeSession?.messages ?? [];
    const canClear = activeSession ? !isPristine(activeSession) : false;

    return (
        <div className="se-chat-page">
            <Splitter className="se-chat-splitter">
                <SplitterPanel size={24} minSize={16} className="se-chat-splitter__side">
                    <ConversationSidebar
                        sessions={sessions}
                        activeId={activeId}
                        onNew={newConversation}
                        onSelect={selectConversation}
                        onRename={rename}
                        onDelete={remove}
                    />
                </SplitterPanel>
                <SplitterPanel size={76} minSize={40} className="se-chat-splitter__main">
                    <div className="se-chat-window">
                        <ChatHeader
                            title={activeSession?.title}
                            onClear={clearActive}
                            canClear={canClear}
                        />
                        <MessageList
                            messages={messages}
                            onApply={onApplyArtifact}
                            onSuggestion={sendMessage}
                        />
                        <ChatComposer
                            onSend={sendMessage}
                            onStop={stopResponding}
                            isResponding={isResponding}
                            disabled={!activeId}
                        />
                    </div>
                </SplitterPanel>
            </Splitter>
        </div>
    );
}

export default ChatPage;
