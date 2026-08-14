// Shared chat constants (name, welcome, suggestions, apply targets, ids).
// Reply generation lives on the GCS backend `/api/chat` endpoint.

export const ASSISTANT_NAME = 'GCS Assistant';

export const WELCOME_MESSAGE =
    "Hi, I'm the GCS Assistant. Describe a mission in natural language and I will " +
    'draft SteelEagle DSL you can Apply into the FSM Builder. Follow-up messages ' +
    'can revise the current draft. I will not upload or start missions for you.';

export const SUGGESTED_PROMPTS = [
    'Patrol areaB, then return home',
    'Take off and track the nearest person',
    'Fly a 300s patrol and return home when the battery is below 30%',
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

