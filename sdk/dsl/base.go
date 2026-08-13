package dsl

import "github.com/cmusatyalab/steeleagle/sdk"

// Action holds an action type that can be used as a state in the mission FSM.
type Action interface {
	// Execute performs an action until it is complete or it
	// encounters an error.
	Execute(v sdk.Vehicle) error
}

// Event holds an event type that can be used as a transition function in the mission FSM.
type Event interface {
	// Monitor continues to check for an event state until it
	// occurs or encounters an error.
	Monitor(v sdk.Vehicle) (bool, error)
}

// Datatype holds a type that is used in an Event or an Action.
type Datatype interface {
	// Type is a blank function that is only used to make a struct as a DSL datatype. Any
	// struct that implements this function will be found by the package loader.
	Type()
}
