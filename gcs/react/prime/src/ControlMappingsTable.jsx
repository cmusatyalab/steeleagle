import { useRef, useState, useCallback } from 'react';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { CONTROL_MAPPINGS } from './controlMappings.js';

// How close to the bottom (px) counts as "reached the end" -- guards
// against subpixel scroll math leaving the fade visibly stuck on even
// after the user has scrolled all the way down.
const BOTTOM_THRESHOLD = 4;

// The table's own scrollHeight="300px" clips rows with no visual hint that
// there's more below -- easy to mistake for the complete list, especially
// once it's just a couple of rows past the fold. This overlays a fade +
// chevron at the bottom, shown only while there's unscrolled content, and
// hidden once scrolled to the end.
function ControlMappingsTable() {
    const scrollElRef = useRef(null);
    const [hasMore, setHasMore] = useState(false);

    const checkScroll = useCallback(() => {
        const el = scrollElRef.current;
        if (!el) return;
        setHasMore(el.scrollHeight - el.scrollTop - el.clientHeight > BOTTOM_THRESHOLD);
    }, []);

    // A ref callback rather than a useEffect: it fires during the commit
    // phase once the table's real DOM exists, so the initial measurement
    // doesn't need the "measure after mount via an effect + setState"
    // dance (and the lint footgun that comes with calling setState
    // synchronously inside an effect body).
    const setWrapperRef = useCallback((node) => {
        scrollElRef.current?.removeEventListener('scroll', checkScroll);
        const el = node?.querySelector('.p-datatable-wrapper') ?? null;
        scrollElRef.current = el;
        if (el) {
            el.addEventListener('scroll', checkScroll);
            checkScroll();
        }
    }, [checkScroll]);

    return (
        <div ref={setWrapperRef} style={{ position: 'relative' }}>
            <DataTable value={CONTROL_MAPPINGS} size="small" scrollable scrollHeight="300px">
                <Column field="action" header="Action" />
                <Column field="keyboard" header="Keyboard" />
                <Column field="gamepad" header="Gamepad" />
            </DataTable>
            <div
                aria-hidden="true"
                style={{
                    position: 'absolute',
                    left: 0,
                    right: '1rem', // stay clear of the table's own scrollbar
                    bottom: 0,
                    height: '2.25rem',
                    pointerEvents: 'none',
                    background: 'linear-gradient(to bottom, transparent, var(--surface-overlay))',
                    opacity: hasMore ? 1 : 0,
                    transition: 'opacity 0.15s',
                }}
            />
            <i
                className="pi pi-chevron-down"
                aria-hidden="true"
                style={{
                    position: 'absolute',
                    bottom: '0.25rem',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    fontSize: '0.7rem',
                    color: 'var(--text-color-secondary)',
                    pointerEvents: 'none',
                    opacity: hasMore ? 1 : 0,
                    transition: 'opacity 0.15s',
                }}
            />
        </div>
    );
}

export default ControlMappingsTable;
