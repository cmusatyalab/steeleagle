package linker

import (
	"strings"
	"testing"
)

// TestLinkEndToEnd checks that a mission declaring a datatype, actions and
// an event links into an IR with every declaration in source order (Data,
// then Actions, then Events), each tagged with its stanza and prefixed Go
// variable name, along with its start state and transitions.
func TestLinkEndToEnd(t *testing.T) {
	ir := mustLink(t, `Import:
    "`+fixturesPkgPath+`"
Data:
    fixtures.Waypoint home(Lat=1.0, Lon=2.0)
Actions:
    fixtures.Hover hover()
    fixtures.Fly fly(Speed=5.0, Target=home)
Events:
    fixtures.Seen seen()
Mission:
Start hover
During hover:
    done -> fly
During fly:
    seen -> hover
`)

	if ir.Start != "hover" {
		t.Errorf("Start = %q, want %q", ir.Start, "hover")
	}

	var order []string
	for _, decl := range ir.AllOrdered {
		order = append(order, decl.Name)
	}
	if got, want := strings.Join(order, ","), "home,hover,fly,seen"; got != want {
		t.Errorf("AllOrdered = %s, want %s", got, want)
	}

	home := mustDecl(t, ir, "home")
	if home.IsAction() || home.IsEvent() {
		t.Errorf("home IsAction/IsEvent = %v/%v, want false/false for a datatype", home.IsAction(), home.IsEvent())
	}
	if fly := mustDecl(t, ir, "fly"); !fly.IsAction() || fly.Var != "decl_fly" || fly.Type != "fixtures.Fly" {
		t.Errorf("fly = %+v, want an action with Var decl_fly and Type fixtures.Fly", fly)
	}
	if seen := mustDecl(t, ir, "seen"); !seen.IsEvent() {
		t.Errorf("seen.IsEvent() = false, want true")
	}

	hover, ok := ir.Transitions["hover"]
	if !ok || len(hover.Rules) != 1 {
		t.Fatalf("Transitions[hover] = %+v, want one rule", hover)
	}
	if got, want := hover.Rules[0].Render, `"done": "fly"`; got != want {
		t.Errorf("hover rule Render = %s, want %s", got, want)
	}
	if fly, ok := ir.Transitions["fly"]; !ok || len(fly.Rules) != 1 || fly.Rules[0].LValue != "seen" || fly.Rules[0].RValue != "hover" {
		t.Errorf("Transitions[fly] = %+v, want seen -> hover", fly)
	}
}

// TestLinkUndefinedType checks that a declaration whose type is not in the
// registry is reported against that declaration.
func TestLinkUndefinedType(t *testing.T) {
	errs := mustFailLink(t, mission("", "    fixtures.Missing m()\n"))
	if e := findError(t, errs, "type name fixtures.Missing is undefined"); e.Decl != "m" {
		t.Errorf("Decl = %q, want %q", e.Decl, "m")
	}
}

// TestLinkWrongStanza checks that a registered type declared in a stanza
// other than its own (a datatype under Actions) is rejected.
func TestLinkWrongStanza(t *testing.T) {
	errs := mustFailLink(t, mission("", "    fixtures.Waypoint w(Lat=1.0, Lon=2.0)\n"))
	findError(t, errs, "fixtures.Waypoint cannot be declared in this stanza")
}

// TestLinkDuplicateDefinition checks that two declarations sharing a name
// are rejected, even across stanzas.
func TestLinkDuplicateDefinition(t *testing.T) {
	errs := mustFailLink(t, mission("", "    fixtures.Fly seen(Speed=1.0)\n"))
	findError(t, errs, "duplicate definition seen")
}

// TestLinkUnknownField checks that setting a field the type does not have
// is reported.
func TestLinkUnknownField(t *testing.T) {
	errs := mustFailLink(t, mission("", "    fixtures.Fly f(Speed=1.0, Bogus=2)\n"))
	findError(t, errs, "fixtures.Fly has no field Bogus")
}

// TestLinkFieldSetTwice checks that setting the same field twice is
// reported instead of the last value silently winning.
func TestLinkFieldSetTwice(t *testing.T) {
	errs := mustFailLink(t, mission("", "    fixtures.Fly f(Speed=1.0, Speed=2.0)\n"))
	findError(t, errs, "field Speed set more than once")
}

// TestLinkRequiredFieldMissing checks that leaving out a required field is
// reported, while leaving out optional fields is not.
func TestLinkRequiredFieldMissing(t *testing.T) {
	errs := mustFailLink(t, mission("", "    fixtures.Fly f(Count=1)\n"))
	findError(t, errs, "fixtures.Fly required field Speed not present")
	if len(errs) != 1 {
		t.Errorf("errors = %v, want only the missing Speed", errs)
	}
}

// TestLinkValueTypeMismatch checks that each kind of DSL value is rejected
// when given for a field of an incompatible Go type.
func TestLinkValueTypeMismatch(t *testing.T) {
	cases := map[string]string{
		`Speed="fast"`:            "string given for float32",
		`Speed=1.0, Note=3`:       "number given for string",
		`Speed=1.0, Count=2.5`:    "2.5 given for integer type int32",
		`Speed=[1.0]`:             "array given for float32",
		`Speed=1.0, Points=["a"]`: "string given for float64",
		`Speed=1.0, Mode=Bogus`:   "Bogus is neither a fixtures.Mode constant nor a declared datatype",
		`Speed=1.0, Enabled=yes`:  "yes is neither a bool constant nor a declared datatype",
	}
	for attrs, want := range cases {
		errs := mustFailLink(t, mission("", "    fixtures.Fly f("+attrs+")\n"))
		findError(t, errs, want)
	}
}

// TestLinkAcceptsEveryValueKind checks that a value of every kind the DSL
// can express links when given for a compatible field, including integer
// literals for float fields and every spelling of an enum constant.
func TestLinkAcceptsEveryValueKind(t *testing.T) {
	mustLink(t, mission("", `    fixtures.Fly a(Speed=1, Count=2, Note="hi", Enabled=true, Points=[1, 2.5])
    fixtures.Fly b(Speed=1.0, Mode=Active)
    fixtures.Fly c(Speed=1.0, Mode=ModeActive)
    fixtures.Fly d(Speed=1.0, Mode=fixtures.ModeActive)
`))
}

// TestLinkInlineCtorRecursesIntoArgs checks that an inline constructor's
// arguments are checked like a declaration's attributes, including in a
// constructor nested inside another one.
func TestLinkInlineCtorRecursesIntoArgs(t *testing.T) {
	errs := mustFailLink(t, mission("",
		"    fixtures.Fly f(Speed=1.0, Route=fixtures.Route(Start=fixtures.Waypoint(Lat=1.0, Bogus=2.0)))\n"))
	findError(t, errs, "fixtures.Waypoint has no field Bogus")
	findError(t, errs, "fixtures.Waypoint required field Lon not present")
}

// TestLinkInlineCtorUndefined checks that an inline constructor naming a
// type that isn't a registered datatype is reported.
func TestLinkInlineCtorUndefined(t *testing.T) {
	errs := mustFailLink(t, mission("", "    fixtures.Fly f(Speed=1.0, Target=fixtures.Hover())\n"))
	findError(t, errs, "datatype fixtures.Hover is undefined")
}

// TestLinkInlineCtorWrongType checks that an inline constructor of one
// datatype given for a field of another is reported.
func TestLinkInlineCtorWrongType(t *testing.T) {
	errs := mustFailLink(t, mission("",
		"    fixtures.Fly f(Speed=1.0, Target=fixtures.Route(Start=fixtures.Waypoint(Lat=1.0, Lon=2.0)))\n"))
	findError(t, errs, "fixtures.Route given for *fixtures.Waypoint")
}

// TestLinkDataReference checks that a Data declaration can be referenced
// both by value and through a pointer field.
func TestLinkDataReference(t *testing.T) {
	mustLink(t, mission(
		"    fixtures.Waypoint home(Lat=1.0, Lon=2.0)\n",
		"    fixtures.Fly f(Speed=1.0, Target=home, Route=fixtures.Route(Start=home))\n",
	))
}

// TestLinkDataReferenceMustBeEarlier checks that a Data declaration can
// only reference datatypes declared before it, which rules out
// self-references and initialization cycles in the generated code.
func TestLinkDataReferenceMustBeEarlier(t *testing.T) {
	errs := mustFailLink(t, mission(
		"    fixtures.Route r(Start=home)\n    fixtures.Waypoint home(Lat=1.0, Lon=2.0)\n",
		"",
	))
	findError(t, errs, "home is neither a fixtures.Waypoint constant nor a declared datatype")
}

// TestLinkReferenceMustBeDatatype checks that an action or event cannot be
// referenced as a value.
func TestLinkReferenceMustBeDatatype(t *testing.T) {
	errs := mustFailLink(t, mission("", "    fixtures.Fly f(Speed=1.0, Target=hover)\n"))
	findError(t, errs, "hover is neither a *fixtures.Waypoint constant nor a declared datatype")
}

// TestLinkReferenceWrongType checks that referencing a datatype of the
// wrong type is reported.
func TestLinkReferenceWrongType(t *testing.T) {
	errs := mustFailLink(t, mission(
		"    fixtures.Waypoint home(Lat=1.0, Lon=2.0)\n    fixtures.Route r(Start=home)\n",
		"    fixtures.Fly f(Speed=1.0, Target=r)\n",
	))
	findError(t, errs, "r has type fixtures.Route, but *fixtures.Waypoint is required")
}

// TestLinkStartMustBeAction checks that the mission's start state must be
// a declared action, not an event or an undeclared name.
func TestLinkStartMustBeAction(t *testing.T) {
	src := strings.Replace(mission("", ""), "Start hover", "Start seen", 1)
	errs := mustFailLink(t, src)
	findError(t, errs, "declaration seen is not an action")
}

// TestLinkTransitionChecks checks that a During block must name an action,
// each rule's trigger must be an event (or the built-in done), and each
// rule's target must be an action.
func TestLinkTransitionChecks(t *testing.T) {
	errs := mustFailLink(t, mission("", "")+`During seen:
    done -> hover
During hover:
    hover -> hover
    done -> seen
`)
	// Both "During seen" (line 10) and "done -> seen" (line 14) report
	// that seen is not an action
	var lines []uint32
	for _, e := range errs {
		if e.Error() == "declaration seen is not an action" {
			lines = append(lines, e.LineNo)
		}
	}
	if len(lines) != 2 || lines[0] != 10 || lines[1] != 14 {
		t.Errorf("\"seen is not an action\" lines = %v, want [10 14]", lines)
	}
	if e := findError(t, errs, "declaration hover is not an event"); e.LineNo != 13 {
		t.Errorf("hover -> hover LineNo = %d, want 13", e.LineNo)
	}
	if len(errs) != 3 {
		t.Errorf("errors = %v, want exactly 3 (done -> hover is valid)", errs)
	}
}

// TestLinkDoneIsAlwaysAnEvent checks that the built-in done event can
// trigger a transition without being declared.
func TestLinkDoneIsAlwaysAnEvent(t *testing.T) {
	ir := mustLink(t, mission("", "")+"During hover:\n    done -> hover\n")
	if rules := ir.Transitions["hover"].Rules; len(rules) != 1 || rules[0].LValue != "done" {
		t.Errorf("Transitions[hover].Rules = %+v, want done -> hover", rules)
	}
}

// TestLinkUnimportedPackage checks that importing a package the loader did
// not load is reported against that import.
func TestLinkUnimportedPackage(t *testing.T) {
	src := strings.Replace(mission("", ""), "Import:\n", "Import:\n    \"example.com/missing\"\n", 1)
	errs := mustFailLink(t, src)
	if e := findError(t, errs, "unimported package example.com/missing"); e.LineNo != 2 {
		t.Errorf("LineNo = %d, want 2", e.LineNo)
	}
}

// TestLinkErrorPosition checks that errors carry the source file, line,
// and enclosing declaration of the offending value, even for one nested
// inside an inline constructor.
func TestLinkErrorPosition(t *testing.T) {
	errs := mustFailLink(t, mission("",
		"    fixtures.Fly f(Speed=1.0,\n        Route=fixtures.Route(Start=fixtures.Waypoint(Lat=\"x\", Lon=2.0)))\n"))
	e := findError(t, errs, "string given for float64")
	if e.File != "test.dsl" || e.LineNo != 7 || e.Decl != "f" {
		t.Errorf("error at %s:%d in %q, want test.dsl:7 in %q", e.File, e.LineNo, e.Decl, "f")
	}
}

// TestLinkImportsOnlyUsedPackages checks that only packages the rendered
// declarations reference are imported: neither a package that is imported
// but never used, nor a package the template already imports.
func TestLinkImportsOnlyUsedPackages(t *testing.T) {
	src := strings.Replace(mission("", ""), "Import:\n", "Import:\n    \""+geoPkgPath+"\"\n    \""+dslPkgPath+"\"\n", 1)
	ir := mustLink(t, src)
	if len(ir.Imports) != 1 {
		t.Fatalf("Imports = %v, want only %s", keys(ir.Imports), fixturesPkgPath)
	}
	imp, ok := ir.Imports[fixturesPkgPath]
	if !ok {
		t.Fatalf("Imports = %v, want %s", keys(ir.Imports), fixturesPkgPath)
	}
	if imp.Alias != "fixtures" || imp.Render != `"`+fixturesPkgPath+`"` {
		t.Errorf("Imports[fixtures] = %+v, want alias fixtures rendered without an alias", imp)
	}
}

// TestLinkImportsFromDefaults checks that a package referenced only by an
// optional field's default is still imported.
func TestLinkImportsFromDefaults(t *testing.T) {
	ir := mustLink(t, mission("", "    fixtures.Fly f(Speed=1.0)\n"))
	if _, ok := ir.Imports[fixturesPkgPath]; !ok {
		t.Errorf("Imports = %v, want %s", keys(ir.Imports), fixturesPkgPath)
	}
}

// TestLinkImportNameConflict checks that using a package whose name is
// already taken by a template import is reported, since the generated code
// would otherwise import two packages under the same name.
func TestLinkImportNameConflict(t *testing.T) {
	src := strings.Replace(mission("    geo.Spot s(X=1.0)\n", ""), "Import:\n", "Import:\n    \""+geoPkgPath+"\"\n", 1)
	errs := mustFailLink(t, src)
	findError(t, errs, "package "+geoPkgPath+" is named geo, which conflicts with github.com/cmusatyalab/steeleagle/sdk/geo")
}

// TestLinkAliasedImport checks that a package imported under an alias is
// referenced and imported under that alias.
func TestLinkAliasedImport(t *testing.T) {
	src := `Import:
    fx "` + fixturesPkgPath + `"
Data:
Actions:
    fx.Fly f(Speed=1.0, Mode=fx.ModeActive)
Events:
Mission:
Start f
`
	ir, errs := Link(mustParse(t, src), aliasedRegistry(t))
	if len(errs) > 0 {
		t.Fatalf("Link() errors = %v, want none", errs)
	}
	if imp := ir.Imports[fixturesPkgPath]; imp == nil || imp.Render != `fx "`+fixturesPkgPath+`"` {
		t.Errorf("Imports[fixtures] = %+v, want rendered as fx %q", imp, fixturesPkgPath)
	}
	if render := mustDecl(t, ir, "f").Render; !strings.Contains(render, "fx.Fly{") || !strings.Contains(render, "Mode: fx.ModeActive") {
		t.Errorf("Render = %s, want fx.Fly with Mode: fx.ModeActive", render)
	}
}

// keys returns m's keys, for use in test failure messages.
func keys[V any](m map[string]V) []string {
	ks := make([]string, 0, len(m))
	for k := range m {
		ks = append(ks, k)
	}
	return ks
}
