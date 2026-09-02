// sdk/dsl/compiler/graph_test.go

package compiler

import (
	"os"
	"testing"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
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

// TestAstToGraphRoundTripsKnownFixture parses testdata/takeoff_gimbal.test.dsl
// (the same fixture ir_test.go uses) with the real lexer and checks
// AstToGraph reconstructs the exact graph shape that file encodes: two
// nodes, one edge, a Role stanza, and a nested InlineCtor value for the
// gimbal's Pose param.
func TestAstToGraphRoundTripsKnownFixture(t *testing.T) {
	f, err := os.Open("testdata/takeoff_gimbal.test.dsl")
	if err != nil {
		t.Fatalf("opening fixture: %v", err)
	}
	defer f.Close()

	ast, err := parser.Parse("takeoff_gimbal.test.dsl", f)
	if err != nil {
		t.Fatalf("parser.Parse() = %v, want nil", err)
	}

	mission, err := AstToGraph(ast)
	if err != nil {
		t.Fatalf("AstToGraph() = %v, want nil", err)
	}

	if mission.GetStartId() != "takeoff" {
		t.Errorf("StartId = %q, want %q", mission.GetStartId(), "takeoff")
	}
	if !mission.HasRole() || mission.GetRole() != "Patrol" {
		t.Errorf("Role = %q (has=%v), want %q", mission.GetRole(), mission.HasRole(), "Patrol")
	}
	if len(mission.GetImports()) != 3 {
		t.Fatalf("len(Imports) = %d, want 3", len(mission.GetImports()))
	}
	if len(mission.GetNodes()) != 2 {
		t.Fatalf("len(Nodes) = %d, want 2", len(mission.GetNodes()))
	}
	gimbal := mission.GetNodes()[1]
	if gimbal.GetInstanceId() != "gimbal" || gimbal.GetTypeName() != "actions.SetGimbalPose" {
		t.Errorf("gimbal node = %+v, want InstanceId=gimbal TypeName=actions.SetGimbalPose", gimbal)
	}
	pose, ok := gimbal.GetParams()["Pose"]
	if !ok || !pose.HasInlineValue() {
		t.Fatalf("gimbal Pose param = %+v, want an inline_value", gimbal.GetParams())
	}
	if pose.GetInlineValue().GetTypeName() != "types.Pose" {
		t.Errorf("Pose inline type_name = %q, want %q", pose.GetInlineValue().GetTypeName(), "types.Pose")
	}
	pitch, ok := pose.GetInlineValue().GetArgs()["Pitch"]
	if !ok || !pitch.HasFloatValue() || pitch.GetFloatValue() != -30.0 {
		t.Errorf("Pose.Pitch = %+v, want float_value -30.0", pitch)
	}
	angleMode, ok := gimbal.GetParams()["AngleMode"]
	if !ok || !angleMode.HasIdentRef() || angleMode.GetIdentRef() != "enums.AngleModeAbsolute" {
		t.Errorf("AngleMode = %+v, want ident_ref enums.AngleModeAbsolute", angleMode)
	}
	if len(mission.GetEdges()) != 1 {
		t.Fatalf("len(Edges) = %d, want 1", len(mission.GetEdges()))
	}
	edge := mission.GetEdges()[0]
	if edge.GetSource() != "takeoff" || edge.GetEventId() != "done" || edge.GetTarget() != "gimbal" {
		t.Errorf("edge = %+v, want takeoff -done-> gimbal", edge)
	}
}

// TestAstToGraphThenBuildAstRoundTrips checks AstToGraph's output feeds
// straight back into the existing BuildAst without error -- the two
// functions are meant to be exact inverses of each other on the
// MissionGraph <-> Ast boundary.
func TestAstToGraphThenBuildAstRoundTrips(t *testing.T) {
	f, err := os.Open("testdata/takeoff_gimbal.test.dsl")
	if err != nil {
		t.Fatalf("opening fixture: %v", err)
	}
	defer f.Close()
	ast, err := parser.Parse("takeoff_gimbal.test.dsl", f)
	if err != nil {
		t.Fatalf("parser.Parse() = %v, want nil", err)
	}
	mission, err := AstToGraph(ast)
	if err != nil {
		t.Fatalf("AstToGraph() = %v, want nil", err)
	}
	if _, err := BuildAst(mission, nil, ""); err != nil {
		t.Errorf("BuildAst(AstToGraph(ast)) = %v, want nil", err)
	}
}

// TestAstToGraphRejectsMissingMissionStanza checks a DSL file with no
// Mission block (so no start_id could be derived) fails clearly instead
// of silently producing a MissionGraph with an empty StartId.
func TestAstToGraphRejectsMissingMissionStanza(t *testing.T) {
	ast := &parser.Ast{
		Actions: &parser.ActionsStanza{Decls: []*parser.Decl{{Type: "actions.TakeOff", Name: "takeoff"}}},
	}
	if _, err := AstToGraph(ast); err == nil {
		t.Fatal("AstToGraph() = nil error, want an error for a missing Mission stanza")
	}
}
