// Deterministic mock data for the GCS Assistant chat.
// This module is intentionally free of React and UI concerns so it can be
// swapped for a real SSE/MCP client later without touching the page layout.

export const ASSISTANT_NAME = 'GCS Assistant';

export const WELCOME_MESSAGE =
    "Hi, I'm the GCS Assistant. Describe a mission in plain language and I can " +
    'sketch out a plan for you. Backend connectivity is not wired up yet, so ' +
    'replies below are local mock responses.';

export const SUGGESTED_PROMPTS = [
    'Patrol area B, then return home',
    'Take off and track the nearest person',
    'Fly a 300s patrol with a battery check',
    'What actions are available in the FSM builder?',
];

// Apply target identifiers shared with the host app. Keeping these as
// constants avoids magic strings when the real integration is added.
export const APPLY_TARGETS = {
    fsmBuilder: 'fsm-builder',
    dslPreview: 'dsl-preview',
};

let _seq = 0;
export function nextId(prefix = 'id') {
    _seq += 1;
    return `${prefix}-${Date.now().toString(36)}-${_seq}`;
}

// A tiny keyword-based responder so the UI feels alive without a backend.
// Returns { content, artifacts }. artifacts is an array of apply-able drafts.
export function mockAssistantReply(userText) {
    const text = (userText || '').toLowerCase();

    if (text.includes('action') || text.includes('what can') || text.includes('help')) {
        return {
            content:
                'The FSM builder currently exposes actions such as TakeOff, Land, ' +
                'ReturnToHome, Patrol, Track, Hold, SetGimbalPose and more. Ask me ' +
                'to draft a mission and I will propose a sequence you can apply ' +
                'straight into the FSM Builder canvas.',
            artifacts: [],
        };
    }

    const wantsMission =
        text.includes('patrol') ||
        text.includes('track') ||
        text.includes('take off') ||
        text.includes('takeoff') ||
        text.includes('mission') ||
        text.includes('fly');

    if (wantsMission) {
        return {
            content:
                'Here is a draft mission based on your request. Replies are still a ' +
                'local mock, but you can already apply this draft to load it into ' +
                'the FSM Builder canvas.',
            artifacts: [
                {
                    id: nextId('artifact'),
                    type: 'mission-draft',
                    target: APPLY_TARGETS.fsmBuilder,
                    label: 'Apply draft to FSM Builder',
                    // payload shape is a placeholder for the future compiler input.
                    payload: {
                        summary: userText,
                        nodes: [
                            { type_name: 'TakeOff', instance_id: 'take_off_1' },
                            { type_name: 'Patrol', instance_id: 'patrol_1' },
                            { type_name: 'ReturnToHome', instance_id: 'return_to_home_1' },
                        ],
                        edges: [
                            { source: 'take_off_1', event_id: 'done', target: 'patrol_1' },
                            { source: 'patrol_1', event_id: 'done', target: 'return_to_home_1' },
                        ],
                        start_id: 'take_off_1',
                    },
                },
            ],
        };
    }

    return {
        content:
            "I can't reach a real model yet, so I'm running in mock mode. Try " +
            'describing a mission (for example "patrol area B then return home") ' +
            'and I will draft a plan you can later apply to the FSM Builder.',
        artifacts: [],
    };
}
