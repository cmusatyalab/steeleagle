import { getApiUrl } from './urls.js';

// missionRequestBody converts canvas state into the graph every
// /api/compile, /api/build, /api/deploy and /api/render_dsl request takes:
// React Flow node ids are swapped for the instance_ids the backend and
// compiler key everything by.
export function missionRequestBody(nodes, edges, eventInstances, startNodeId) {
    const instanceId = id => nodes.find(n => n.id === id)?.data.instance_id;
    return {
        nodes: nodes.map(n => ({
            instance_id: n.data.instance_id,
            type_name: n.data.type_name,
            params: n.data.params,
        })),
        events: eventInstances,
        edges: edges.map(e => ({
            source: instanceId(e.source),
            event_id: e.data?.eventId ?? 'done',
            target: instanceId(e.target),
        })),
        start_id: instanceId(startNodeId),
    };
}

// renderDsl asks the backend for a mission graph's DSL text, rendered from
// the same AST it compiles, so the DSL tab and Export DSL always match
// what gets built.
export async function renderDsl(body, signal) {
    const resp = await fetch(getApiUrl('/api/render_dsl'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal,
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        throw new Error(detail ?? `Server error ${resp.status}`);
    }
    return data.dsl;
}
