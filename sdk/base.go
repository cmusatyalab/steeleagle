//go:build ignore

package sdk

// Action holds an action type that can be used as a state in the mission FSM.
type Action interface {
	// Execute performs an action until it is complete or it
	// encounters an error.
	Execute(v vehicleContext) error
}

// Event holds an event type that can be used as a transition function in the mission FSM.
type Event interface {
	// Monitor continues to check for an event state until it
	// occurs or encounters an error.
	Monitor(v vehicleContext) (bool, error)
}
