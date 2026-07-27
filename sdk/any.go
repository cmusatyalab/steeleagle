package sdk

import (
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/anypb"
)

// anyMatches reports whether a holds a message of the same type as want,
// and if so, whether its content is equal to want.
func anyMatches(a *anypb.Any, want proto.Message) (bool, error) {
	// Compares a.TypeUrl's message name against want's
	// descriptor, without unmarshaling the payload
	if !a.MessageIs(want) {
		return false, nil
	}

	// Unmarshal into a fresh instance of the same concrete type as want
	got := want.ProtoReflect().New().Interface()
	if err := a.UnmarshalTo(got); err != nil {
		return false, err
	}

	return proto.Equal(got, want), nil
}
