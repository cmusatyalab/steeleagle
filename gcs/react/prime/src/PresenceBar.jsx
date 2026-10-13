import React, { useMemo } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { getWebSocketUrl } from './urls.js';
import { groupViewers, viewerLabel } from './presence.js';

export const PRESENCE_BAR_HEIGHT = 28;

// Thin status bar pinned to the bottom of the page listing everyone who has
// the GCS open. The websocket itself is the presence signal: the backend
// counts this tab as a viewer for exactly as long as the socket is open.
function PresenceBar({ left }) {
    const { lastJsonMessage, readyState } = useWebSocket(getWebSocketUrl('/ws/presence'), {
        share: false,
        shouldReconnect: () => true,
    });

    const connected = readyState === ReadyState.OPEN && lastJsonMessage != null;
    const groups = useMemo(
        () => groupViewers(lastJsonMessage?.viewers, lastJsonMessage?.you),
        [lastJsonMessage],
    );
    const count = lastJsonMessage?.viewers?.length ?? 0;
    const shared = connected && count > 1;

    return (
        <div
            className="flex align-items-center gap-2 px-3 text-sm white-space-nowrap overflow-hidden"
            style={{
                position: 'fixed', bottom: 0, right: 0, left, height: PRESENCE_BAR_HEIGHT,
                transition: 'left 0.2s', zIndex: 1000,
                backgroundColor: shared ? 'var(--yellow-100)' : 'var(--surface-card)',
                color: shared ? 'var(--yellow-900)' : 'var(--text-color-secondary)',
                borderTop: '1px solid var(--surface-border)',
            }}
        >
            {connected ? (
                <>
                    <i className={shared ? 'pi pi-users' : 'pi pi-user'} />
                    <span className="font-semibold">{count} {count === 1 ? 'viewer' : 'viewers'}:</span>
                    <span className="overflow-hidden text-overflow-ellipsis" title={groups.map(viewerLabel).join(', ')}>
                        {groups.map(viewerLabel).join(', ')}
                    </span>
                </>
            ) : (
                <>
                    <i className="pi pi-question-circle" />
                    <span>Presence unavailable</span>
                </>
            )}
        </div>
    );
}

export default React.memo(PresenceBar);
