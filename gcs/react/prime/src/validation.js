/**
 * Returns { issues: { [reactFlowNodeId]: string[] }, noStart: boolean }
 *
 * issues  — map from React Flow node id to list of warning messages
 * noStart — true when no start node is selected
 */
export function runValidation(nodes, schema, startNodeId) {
    const issues = {};

    function addIssue(nodeId, msg) {
        if (!issues[nodeId]) issues[nodeId] = [];
        issues[nodeId].push(msg);
    }

    // Check 1: required fields not set
    for (const node of nodes) {
        const fields = schema.actions?.[node.data.type_name]?.fields ?? [];
        for (const field of fields) {
            if (field.required) {
                const val = node.data.params?.[field.name];
                if (val === undefined || val === null || val === '') {
                    addIssue(node.id, `${field.name} is required`);
                }
            }
        }
    }

    // Check 2: duplicate instance IDs
    const idCounts = {};
    for (const node of nodes) {
        const sid = node.data.instance_id;
        idCounts[sid] = (idCounts[sid] ?? 0) + 1;
    }
    for (const node of nodes) {
        if (idCounts[node.data.instance_id] > 1) {
            addIssue(node.id, `Duplicate ID '${node.data.instance_id}'`);
        }
    }

    // Check 3: no start state
    const noStart = !startNodeId || !nodes.some(n => n.id === startNodeId);

    return { issues, noStart };
}
