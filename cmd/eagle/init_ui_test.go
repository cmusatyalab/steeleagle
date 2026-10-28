package main

import (
	"context"
	"errors"
	"slices"
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"
)

// The tests drive initModel with the messages its commands would send,
// without running the commands, which would install and start eagled.

func press(m *initModel, keys ...tea.KeyPressMsg) tea.Cmd {
	var cmd tea.Cmd
	for _, k := range keys {
		_, cmd = m.Update(k)
		m.View() // every stage renders
	}
	return cmd
}

var (
	keyEnter = tea.KeyPressMsg{Code: tea.KeyEnter}
	keyDown  = tea.KeyPressMsg{Code: tea.KeyDown}
	keySpace = tea.KeyPressMsg{Code: tea.KeySpace, Text: " "}
	keyY     = tea.KeyPressMsg{Code: 'y', Text: "y"}
	keyN     = tea.KeyPressMsg{Code: 'n', Text: "n"}
	keyCtrlC = tea.KeyPressMsg{Code: 'c', Mod: tea.ModCtrl}
)

func newTestModel(t *testing.T) *initModel {
	return newInitModel(context.Background(), nil, "/usr/bin/eagled", newServicePaths(t.TempDir()))
}

func expectStage(t *testing.T, m *initModel, want stage) {
	t.Helper()
	if m.stage != want {
		t.Fatalf("stage = %d, want %d", m.stage, want)
	}
}

func TestInitMinimal(t *testing.T) {
	m := newTestModel(t)
	press(m, keyEnter) // the suggested name
	press(m, keyY)
	expectStage(t, m, stageAuthKey)
	m.inputs[0].SetValue(" tskey-auth-x ")
	if press(m, keyEnter) == nil {
		t.Fatal("no command to start eagled")
	}
	expectStage(t, m, stageStarting)

	m.Update(startedMsg{})
	expectStage(t, m, stageMode)
	press(m, keyDown, keyEnter)
	expectStage(t, m, stageFetching)
	if m.mode != modeMinimal {
		t.Fatalf("mode = %d, want minimal", m.mode)
	}

	m.Update(pluginsMsg{dirs: pluginDirs{
		defaults: []string{"defaults/gcs", "defaults/h264"},
		drivers:  []string{"drivers/anafi", "drivers/px4"},
	}})
	expectStage(t, m, stageInstalling)
	if len(m.rows) != 1 || m.rows[0].dir != "defaults/h264" {
		t.Fatalf("rows = %+v, want only defaults/h264", m.rows)
	}
	// A failed install is shown, and init goes on
	m.Update(installedMsg{errors.New("no plugin files\ngit output")})
	expectStage(t, m, stageDrivers)
	if !m.rows[0].done || m.rows[0].err == nil {
		t.Errorf("row = %+v, want done with its error", m.rows[0])
	}
	m.View()

	press(m, keyDown, keySpace, keyEnter)
	expectStage(t, m, stageInstalling)
	if dirs := []string{m.rows[0].dir, m.rows[1].dir}; len(m.rows) != 2 || !slices.Equal(dirs, []string{"defaults/h264", "drivers/px4"}) {
		t.Fatalf("rows = %+v, want h264 then px4", m.rows)
	}
	// There are no engines to pick, so their checklist is skipped
	m.Update(installedMsg{})
	expectStage(t, m, stageInstalling)
	m.Update(shownMsg{})
	expectStage(t, m, stageOrchestrator)
	if m.rows != nil {
		t.Errorf("rows weren't cleared: %+v", m.rows)
	}

	press(m, keyY)
	expectStage(t, m, stageOrchForm)
	press(m, keyEnter, keyEnter)
	if m.invalid == "" {
		t.Error("an empty host was accepted")
	}
	m.inputs[0].SetValue("homebase")
	m.inputs[1].SetValue("99999")
	press(m, keyEnter)
	if m.invalid == "" {
		t.Error("an invalid port was accepted")
	}
	m.inputs[1].SetValue("")
	press(m, keyEnter)
	if m.orchestrator != "homebase:9000" {
		t.Fatalf("orchestrator = %q, want the default port", m.orchestrator)
	}
	// The boot question is skipped if eagled already starts on boot
	if m.stage == stageLinger {
		press(m, keyN)
	}
	expectStage(t, m, stageConfiguring)

	if _, cmd := m.Update(configuredMsg{}); cmd == nil {
		t.Fatal("no command to finish")
	}
	expectStage(t, m, stageDone)
	if m.err != nil {
		t.Errorf("err = %v", m.err)
	}
}

func TestInitBare(t *testing.T) {
	m := newTestModel(t)
	press(m, keyEnter) // the suggested name
	press(m, keyN)
	expectStage(t, m, stageStarting)
	m.Update(startedMsg{})
	press(m, keyEnter)
	expectStage(t, m, stageConfiguring)
	if m.mode != modeBare || m.orchestrator != "" {
		t.Errorf("mode = %d, orchestrator = %q, want bare with none", m.mode, m.orchestrator)
	}
}

func TestInitFailures(t *testing.T) {
	m := newTestModel(t)
	press(m, keyCtrlC)
	if m.stage != stageDone || m.err == nil {
		t.Errorf("ctrl+c left stage %d, err %v", m.stage, m.err)
	}

	m = newTestModel(t)
	press(m, keyEnter) // the suggested name
	press(m, keyN)
	m.Update(startedMsg{errors.New("systemctl failed")})
	if m.stage != stageDone || m.err == nil {
		t.Errorf("a failed start left stage %d, err %v", m.stage, m.err)
	}
}

// TestInitRejectedAuthKey checks that a rejected auth key asks for another,
// rather than failing.
func TestInitRejectedAuthKey(t *testing.T) {
	m := newTestModel(t)
	press(m, keyEnter) // the suggested name
	press(m, keyY)
	expectStage(t, m, stageAuthKey)
	press(m, keyEnter)
	expectStage(t, m, stageStarting)
	m.Update(startedMsg{errAuthKey})
	expectStage(t, m, stageAuthKey)
	if m.err != nil || m.invalid == "" || len(m.inputs) != 1 {
		t.Errorf("err = %v, invalid = %q, %d inputs, want a fresh prompt saying why", m.err, m.invalid, len(m.inputs))
	}
	press(m, keyEnter)
	expectStage(t, m, stageStarting)
	if m.invalid != "" {
		t.Errorf("invalid = %q after answering, want it cleared", m.invalid)
	}
}

// TestInitName checks that the machine's name is asked for first, defaulting
// to the suggested one, and that an invalid one is refused.
func TestInitName(t *testing.T) {
	m := newTestModel(t)
	expectStage(t, m, stageName)
	m.inputs[0].SetValue("-drone")
	press(m, keyEnter)
	expectStage(t, m, stageName)
	if m.invalid == "" {
		t.Error("an invalid name was accepted")
	}
	m.inputs[0].SetValue(" drone-1 ")
	press(m, keyEnter)
	expectStage(t, m, stageVPN)
	if m.hostname != "drone-1" || m.invalid != "" {
		t.Errorf("hostname = %q, invalid = %q, want drone-1 and no error", m.hostname, m.invalid)
	}

	m = newTestModel(t)
	press(m, keyEnter)
	expectStage(t, m, stageVPN)
	if m.hostname == "" || !validHostname(m.hostname) {
		t.Errorf("hostname = %q, want the valid suggested name", m.hostname)
	}
}

// TestInitSafeMode checks that eagled running without its services after
// configuring finishes init with a note, rather than failing it.
func TestInitSafeMode(t *testing.T) {
	m := newTestModel(t)
	press(m, keyEnter, keyN)
	m.Update(startedMsg{})
	press(m, keyEnter)
	expectStage(t, m, stageConfiguring)
	m.Update(configuredMsg{safeModeError{"daemon failed to start services: no drone"}})
	expectStage(t, m, stageDone)
	if m.err != nil || len(m.notes) != 1 || !strings.Contains(m.notes[0], "no drone") {
		t.Errorf("err = %v, notes = %q, want no error and a note saying why", m.err, m.notes)
	}
}

// TestInitNoEnginesPicked checks that picking no engines goes straight on,
// without pausing to show installs that are already shown.
func TestInitNoEnginesPicked(t *testing.T) {
	m := newTestModel(t)
	press(m, keyEnter, keyN)
	m.Update(startedMsg{})
	press(m, keyDown, keyEnter)
	m.Update(pluginsMsg{dirs: pluginDirs{engines: []string{"engines/yolo"}}})
	m.Update(installedMsg{})
	expectStage(t, m, stageEngines)
	press(m, keyEnter)
	expectStage(t, m, stageOrchestrator)
	if m.rows != nil {
		t.Errorf("rows weren't cleared: %+v", m.rows)
	}
}
