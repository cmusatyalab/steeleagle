// sdk/dsl/compiler/graph_test.go
package compiler

import (
	"testing"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
)

func floatValue(f float64) *dslcompilerpb.FieldValue {
	return dslcompilerpb.FieldValue_builder{FloatValue: &f}.Build()
}
func identValue(s string) *dslcompilerpb.FieldValue {
	return dslcompilerpb.FieldValue_builder{IdentRef: &s}.Build()
}
func stringValue(s string) *dslcompilerpb.FieldValue {
	return dslcompilerpb.FieldValue_builder{StringValue: &s}.Build()
}

// TestBuildAstSimpleTwoActionMission checks that a minimal two-node graph
// (takeoff -> patrol on "done") produces an Ast whose Actions/Mission
// stanzas match what a hand-written DSL file would parse to.
func TestBuildAstSimpleTwoActionMission(t *testing.T) {
	mission := dslcompilerpb.MissionGraph_builder{
		Nodes: []*dslcompilerpb.Node{
			dslcompilerpb.Node_builder{InstanceId: "takeoff", TypeName: "actions.TakeOff"}.Build(),
			dslcompilerpb.Node_builder{
				InstanceId: "patrol",
				TypeName:   "actions.Patrol",
				Params: map[string]*dslcompilerpb.FieldValue{
					"Altitude": floatValue(15),
					"Area":     identValue("Poly"),
				},
			}.Build(),
		},
		Edges: []*dslcompilerpb.Edge{
			dslcompilerpb.Edge_builder{Source: "takeoff", EventId: "done", Target: "patrol"}.Build(),
		},
		StartId: "takeoff",
	}.Build()

	ast, err := BuildAst(mission, nil, "")
	if err != nil {
		t.Fatalf("BuildAst() = %v, want nil", err)
	}
	if ast.Mission.Start != "takeoff" {
		t.Errorf("ast.Mission.Start = %q, want %q", ast.Mission.Start, "takeoff")
	}
	if len(ast.Actions.Decls) != 2 {
		t.Fatalf("len(ast.Actions.Decls) = %d, want 2", len(ast.Actions.Decls))
	}
	patrol := ast.Actions.Decls[1]
	if patrol.Name != "patrol" || string(patrol.Type) != "actions.Patrol" {
		t.Errorf("patrol decl = %+v, want Name=patrol Type=actions.Patrol", patrol)
	}
	if len(patrol.Attrs) != 2 {
		t.Fatalf("len(patrol.Attrs) = %d, want 2", len(patrol.Attrs))
	}
	if len(ast.Mission.Blocks) != 1 || ast.Mission.Blocks[0].Action != "takeoff" {
		t.Fatalf("ast.Mission.Blocks = %+v, want one During takeoff block", ast.Mission.Blocks)
	}
	rule := ast.Mission.Blocks[0].Rules[0]
	if rule.Event != "done" || rule.Next != "patrol" {
		t.Errorf("rule = %+v, want done->patrol", rule)
	}
}

// TestBuildAstStringValuePreservesContent checks the quoting gotcha found
// while reading ir.go: parser.Value.String stores the RAW lexed token
// including its surrounding quote characters (resolveValue's
// v.StringValue() unconditionally strips the first and last byte), so
// constructing one programmatically must add those quotes back -- a
// naive `Value{String: &raw}` would silently lose raw's first and last
// character.
func TestBuildAstStringValuePreservesContent(t *testing.T) {
	mission := dslcompilerpb.MissionGraph_builder{
		Nodes: []*dslcompilerpb.Node{
			dslcompilerpb.Node_builder{
				InstanceId: "wait",
				TypeName:   "actions.SomeStringAction",
				Params:     map[string]*dslcompilerpb.FieldValue{"Label": stringValue("hello")},
			}.Build(),
		},
		StartId: "wait",
	}.Build()

	ast, err := BuildAst(mission, nil, "")
	if err != nil {
		t.Fatalf("BuildAst() = %v, want nil", err)
	}
	v := ast.Actions.Decls[0].Attrs[0].Value
	got, ok := v.StringValue()
	if !ok {
		t.Fatalf("v.StringValue() ok = false, want true (v = %+v)", v)
	}
	if got != "hello" {
		t.Errorf("v.StringValue() = %q, want %q", got, "hello")
	}
}

// TestBuildAstBoolValueRejected checks that a bool_value FieldValue fails
// immediately with a clear error rather than producing an Ast that fails
// confusingly downstream in resolveIdent (see "A note on bool-typed
// fields" at the top of this plan).
func TestBuildAstBoolValueRejected(t *testing.T) {
	b := true
	mission := dslcompilerpb.MissionGraph_builder{
		Nodes: []*dslcompilerpb.Node{
			dslcompilerpb.Node_builder{
				InstanceId: "n",
				TypeName:   "actions.SomeAction",
				Params:     map[string]*dslcompilerpb.FieldValue{"Flag": dslcompilerpb.FieldValue_builder{BoolValue: &b}.Build()},
			}.Build(),
		},
		StartId: "n",
	}.Build()

	_, err := BuildAst(mission, nil, "")
	if err == nil {
		t.Fatal("BuildAst() = nil error, want an error for a bool_value field")
	}
}
