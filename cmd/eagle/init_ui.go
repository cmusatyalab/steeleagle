package main

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"path"
	"strconv"
	"strings"
	"time"

	"charm.land/bubbles/v2/spinner"
	"charm.land/bubbles/v2/textinput"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
	"google.golang.org/grpc"
	"google.golang.org/grpc/status"
)

// stage is a step of init, in the order they are taken; some are skipped
// depending on the answers.
type stage int

const (
	stageName         stage = iota // asks for the machine's name
	stageVPN                       // asks whether a VPN is used
	stageAuthKey                   // asks for the VPN auth key
	stageStarting                  // installs and starts eagled
	stageMode                      // asks for the installation mode
	stageFetching                  // lists the plugins in pluginsRepo
	stageInstalling                // installs the queued plugins
	stageSimulator                 // asks whether to install the simulator
	stageDrivers                   // asks which drivers to install
	stageEngines                   // asks which engines to install
	stageOrchestrator              // asks whether to use an orchestrator
	stageOrchForm                  // asks for the orchestrator's address
	stageLinger                    // asks whether to start eagled on boot
	stageConfiguring               // reconfigures eagled with the plugins
	stageDone
)

// mode is an installation mode.
type mode int

const (
	modeBare mode = iota
	modeMinimal
	modeDefault
)

// option is an option of a select or checklist.
type option struct {
	label, description string
}

var modeOptions = []option{
	modeBare:    {"Bare", "only the daemon, with no plugins"},
	modeMinimal: {"Minimal", "the H.264 video plugin, and the simulator, drivers and engines you pick"},
	modeDefault: {"Default", "every default plugin, including the web GCS, and the simulator, drivers and engines you pick"},
}

// showRows is how long the finished installs stay up before they are
// cleared.
const showRows = time.Second / 4

// minimalPlugins are the plugins of a minimal installation.
var minimalPlugins = []string{"defaults/h264"}

var (
	boldStyle    = lipgloss.NewStyle().Bold(true)
	welcomeStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("214"))
	dimStyle     = lipgloss.NewStyle().Faint(true)
	cursorStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("214"))
	checkStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("2"))
	errorStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("1"))
)

// row is a plugin install, shown with a spinner until it is done.
type row struct {
	dir  string
	done bool
	err  error
}

// Messages of the commands init runs.
type (
	startedMsg struct{ err error }
	pluginsMsg struct {
		dirs pluginDirs
		err  error
	}
	installedMsg  struct{ err error }
	shownMsg      struct{}
	lingerMsg     struct{ err error }
	configuredMsg struct{ err error }
)

// initModel is the terminal UI of eagle init. It asks for the machine's
// name and a VPN auth key, starts eagled, installs the plugins of the chosen
// mode, the simulator if wanted, and the drivers and engines picked,
// optionally sets an orchestrator and starts eagled on boot, and finally
// reconfigures eagled with a service for each default plugin and the
// simulator.
// The drivers and engines are left out, since they may not run until their
// vehicle or hardware is there, which would start eagled in safe mode.
type initModel struct {
	ctx    context.Context
	conn   grpc.ClientConnInterface
	eagled string
	paths  servicePaths

	stage   stage
	spinner spinner.Model
	cursor  int    // selected option of a select, checklist or yes/no
	checked []bool // checked options of a checklist
	inputs  []textinput.Model
	invalid string // why the inputs can't be accepted

	hostname     string
	mode         mode
	plugins      pluginDirs
	simulator    bool     // whether the simulator was chosen
	queue        []string // plugins left to install
	rows         []row
	afterInstall stage // stage to go on to once queue is installed
	installed    bool  // whether queue had any plugins to install
	orchestrator string
	notes        []string // problems that didn't stop init

	err error // why init failed
}

func newInitModel(ctx context.Context, conn grpc.ClientConnInterface, eagled string, paths servicePaths) *initModel {
	return &initModel{
		ctx:     ctx,
		conn:    conn,
		eagled:  eagled,
		paths:   paths,
		stage:   stageName,
		spinner: spinner.New(spinner.WithSpinner(spinner.Dot), spinner.WithStyle(cursorStyle)),
		inputs:  []textinput.Model{newInput("Name: ", defaultHostname(paths.config), false)},
	}
}

func (m *initModel) Init() tea.Cmd {
	return tea.Batch(m.spinner.Tick, m.focus(0))
}

func (m *initModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyPressMsg:
		if msg.Keystroke() == "ctrl+c" {
			return m, m.fail(errors.New("cancelled"))
		}
		return m.key(msg)
	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd
	case startedMsg:
		if errors.Is(msg.err, errAuthKey) {
			// Ask again, rather than leaving eagled with a key that won't work
			m.stage = stageAuthKey
			m.invalid = "The VPN rejected that auth key; try another, or leave it blank to log in with a URL"
			return m, m.setInputs(newInput("Auth key: ", "leave blank if not applicable", true))
		}
		if msg.err != nil {
			return m, m.fail(msg.err)
		}
		m.stage, m.cursor = stageMode, 0
	case pluginsMsg:
		if msg.err != nil {
			return m, m.fail(fmt.Errorf("could not list the plugins: %w", msg.err))
		}
		m.plugins = msg.dirs
		queue := minimalPlugins
		if m.mode == modeDefault {
			queue = m.plugins.defaults
		}
		return m, m.install(queue, stageSimulator)
	case installedMsg:
		m.rows[len(m.rows)-1].done = true
		m.rows[len(m.rows)-1].err = msg.err
		return m, m.installNext()
	case shownMsg:
		m.rows = nil
		m.stage = stageOrchestrator
	case lingerMsg:
		if msg.err != nil {
			m.notes = append(m.notes, fmt.Sprintf("could not start eagled on boot: %v", msg.err))
		}
		return m, m.configure()
	case configuredMsg:
		var safeMode safeModeError
		if errors.As(msg.err, &safeMode) {
			m.notes = append(m.notes, fmt.Sprintf("eagled is running without its services (see eagle list-services): %v", safeMode))
			return m, m.finish()
		}
		if msg.err != nil {
			return m, m.fail(msg.err)
		}
		return m, m.finish()
	}
	// Keys and blinks go to the focused input, if there is one
	if len(m.inputs) > 0 {
		return m, m.updateInputs(msg)
	}
	return m, nil
}

// key handles a key press in the current stage.
func (m *initModel) key(msg tea.KeyPressMsg) (tea.Model, tea.Cmd) {
	key := msg.Keystroke()
	switch m.stage {
	case stageName:
		if key == "enter" {
			name := strings.TrimSpace(m.inputs[0].Value())
			if name == "" {
				name = m.inputs[0].Placeholder
			}
			if !validHostname(name) {
				m.invalid = fmt.Sprintf("%q is not a valid hostname; use letters, digits and hyphens", name)
				return m, nil
			}
			m.hostname = name
			m.inputs, m.invalid = nil, ""
			m.stage, m.cursor = stageVPN, 0
			return m, nil
		}
		return m, m.updateInputs(msg)
	case stageVPN:
		if yes, ok := m.yesNo(key); ok {
			if yes {
				m.stage = stageAuthKey
				return m, m.setInputs(newInput("Auth key: ", "leave blank if not applicable", true))
			}
			return m, m.start("")
		}
	case stageAuthKey:
		if key == "enter" {
			key := strings.TrimSpace(m.inputs[0].Value())
			m.inputs, m.invalid = nil, ""
			return m, m.start(key)
		}
		return m, m.updateInputs(msg)
	case stageMode:
		if m.move(key, len(modeOptions)) {
			return m, nil
		}
		if key == "enter" {
			m.mode = mode(m.cursor)
			if m.mode == modeBare {
				return m, m.configure()
			}
			m.stage = stageFetching
			return m, func() tea.Msg {
				dirs, err := listPlugins(m.ctx)
				return pluginsMsg{dirs, err}
			}
		}
	case stageSimulator:
		if yes, ok := m.yesNo(key); ok {
			var queue []string
			if yes {
				m.simulator = true
				queue = []string{m.plugins.simulator}
			}
			return m, m.install(queue, stageDrivers)
		}
	case stageDrivers, stageEngines:
		dirs, next := m.plugins.drivers, stageEngines
		if m.stage == stageEngines {
			dirs, next = m.plugins.engines, stageOrchestrator
		}
		if m.move(key, len(dirs)) {
			return m, nil
		}
		switch key {
		case "space", "x":
			m.checked[m.cursor] = !m.checked[m.cursor]
		case "enter":
			var queue []string
			for i, dir := range dirs {
				if m.checked[i] {
					queue = append(queue, dir)
				}
			}
			return m, m.install(queue, next)
		}
	case stageOrchestrator:
		if yes, ok := m.yesNo(key); ok {
			if yes {
				m.stage = stageOrchForm
				return m, m.setInputs(
					newInput("IP/Hostname: ", "homebase", false),
					newInput("Port: ", "9000", false),
				)
			}
			return m, m.askLinger()
		}
	case stageOrchForm:
		return m, m.orchestratorKey(msg)
	case stageLinger:
		if yes, ok := m.yesNo(key); ok {
			if yes {
				cmd := systemCommand("sudo", systemCommand("loginctl").Path, "enable-linger", os.Getenv("USER"))
				return m, tea.ExecProcess(cmd, func(err error) tea.Msg { return lingerMsg{err} })
			}
			return m, m.configure()
		}
	}
	return m, nil
}

// move moves the cursor of a list of n options on an arrow key, reporting
// whether key was one.
func (m *initModel) move(key string, n int) bool {
	switch key {
	case "up", "k", "shift+tab":
		m.cursor = (m.cursor + n - 1) % n
	case "down", "j", "tab":
		m.cursor = (m.cursor + 1) % n
	default:
		return false
	}
	return true
}

// yesNo handles a key of a yes/no question, whose cursor is 0 on yes and 1
// on no, returning the answer once it is given.
func (m *initModel) yesNo(key string) (yes, ok bool) {
	switch key {
	case "y":
		return true, true
	case "n":
		return false, true
	case "enter":
		return m.cursor == 0, true
	case "left", "right", "h", "l", "tab", "shift+tab":
		m.cursor = 1 - m.cursor
	}
	return false, false
}

// start installs and starts eagled with the VPN auth key authKey, if it
// isn't empty, and waits for it to answer.
func (m *initModel) start(authKey string) tea.Cmd {
	m.stage = stageStarting
	return func() tea.Msg {
		if err := installService(m.eagled, m.hostname, authKey, m.paths); err != nil {
			return startedMsg{err}
		}
		return startedMsg{waitReady(m.ctx, m.conn)}
	}
}

// install installs the plugins in queue, one at a time, then goes on to
// stage next.
func (m *initModel) install(queue []string, next stage) tea.Cmd {
	m.stage = stageInstalling
	m.queue = queue
	m.afterInstall = next
	m.installed = len(queue) > 0
	return m.installNext()
}

// installNext installs the next plugin in the queue, or goes on to the
// stage after it once it is empty, skipping a checklist with no options.
func (m *initModel) installNext() tea.Cmd {
	if len(m.queue) == 0 {
		next := m.afterInstall
		if next == stageSimulator && m.plugins.simulator == "" {
			next = stageDrivers
		}
		if next == stageDrivers && len(m.plugins.drivers) == 0 {
			next = stageEngines
		}
		if next == stageEngines && len(m.plugins.engines) == 0 {
			next = stageOrchestrator
		}
		m.cursor = 0
		switch next {
		case stageDrivers:
			m.checked = make([]bool, len(m.plugins.drivers))
		case stageEngines:
			m.checked = make([]bool, len(m.plugins.engines))
		case stageOrchestrator:
			if m.installed {
				// Leave the last check mark up long enough to be seen
				return tea.Tick(showRows, func(time.Time) tea.Msg { return shownMsg{} })
			}
			m.rows = nil
		}
		m.stage = next
		return nil
	}
	dir := m.queue[0]
	m.queue = m.queue[1:]
	m.rows = append(m.rows, row{dir: dir})
	return func() tea.Msg { return installedMsg{installPlugin(m.ctx, m.conn, dir)} }
}

// orchestratorKey handles a key of the orchestrator form.
func (m *initModel) orchestratorKey(msg tea.KeyPressMsg) tea.Cmd {
	focused := 0
	if m.inputs[1].Focused() {
		focused = 1
	}
	switch msg.Keystroke() {
	case "up", "shift+tab", "down", "tab":
		return m.focus(1 - focused)
	case "enter":
		if focused == 0 {
			return m.focus(1)
		}
		host := strings.TrimSpace(m.inputs[0].Value())
		port := strings.TrimSpace(m.inputs[1].Value())
		if port == "" {
			port = m.inputs[1].Placeholder
		}
		if host == "" {
			m.invalid = "enter the orchestrator's IP or hostname"
			return m.focus(0)
		}
		if n, err := strconv.Atoi(port); err != nil || n < 1 || n > 65535 {
			m.invalid = fmt.Sprintf("%q is not a port", port)
			return nil
		}
		m.orchestrator = net.JoinHostPort(host, port)
		m.inputs, m.invalid = nil, ""
		return m.askLinger()
	}
	return m.updateInputs(msg)
}

// askLinger asks whether eagled should start on boot, unless it already
// does.
func (m *initModel) askLinger() tea.Cmd {
	out, err := systemCommand("loginctl", "show-user", os.Getenv("USER"), "--property=Linger", "--value").Output()
	if err == nil && strings.TrimSpace(string(out)) == "yes" {
		return m.configure()
	}
	m.stage, m.cursor = stageLinger, 0
	return nil
}

// configure reconfigures eagled with the default plugins of the mode and
// the orchestrator, and waits for it to restart.
func (m *initModel) configure() tea.Cmd {
	m.stage = stageConfiguring
	m.rows = nil
	var dirs []string
	switch m.mode {
	case modeMinimal:
		dirs = minimalPlugins
	case modeDefault:
		dirs = m.plugins.defaults
	}
	uris := make([]string, len(dirs))
	for i, dir := range dirs {
		uris[i] = pluginURI(dir)
	}
	var simulator string
	if m.simulator {
		simulator = pluginURI(m.plugins.simulator)
	}
	return func() tea.Msg { return configuredMsg{reconfigure(m.ctx, m.conn, m.orchestrator, simulator, uris)} }
}

// finish prints how to get started, and any problems along the way, then
// quits.
func (m *initModel) finish() tea.Cmd {
	m.stage = stageDone
	var b strings.Builder
	for _, note := range m.notes {
		fmt.Fprintln(&b, errorStyle.Render("! "+note))
	}
	b.WriteString(checkStyle.Render("✓ ") + boldStyle.Render("SteelEagle is installed"))
	if m.orchestrator != "" {
		host, _, _ := net.SplitHostPort(m.orchestrator)
		fmt.Fprintf(&b, ", please open the daemon on %s to get started. Happy flying!", boldStyle.Render(host))
		return tea.Sequence(tea.Println(b.String()), tea.Quit)
	}
	b.WriteString(", use ")
	b.WriteString(boldStyle.Render("eagle"))
	if m.mode == modeDefault {
		link := lipgloss.NewStyle().Underline(true).Hyperlink(gcsURL).Render("here")
		fmt.Fprintf(&b, " or click %s (%s)", link, gcsURL)
	}
	b.WriteString(" to get started. Happy flying!")
	return tea.Sequence(tea.Println(b.String()), tea.Quit)
}

// fail quits with err.
func (m *initModel) fail(err error) tea.Cmd {
	m.err = err
	m.stage = stageDone
	return tea.Quit
}

// newInput returns a text input with prompt and placeholder, which hides
// what is typed if secret.
func newInput(prompt, placeholder string, secret bool) textinput.Model {
	input := textinput.New()
	input.Prompt = prompt
	input.Placeholder = placeholder
	// Without a width, the input only shows the placeholder's first letter
	input.SetWidth(max(64, lipgloss.Width(placeholder)))
	if secret {
		input.EchoMode = textinput.EchoPassword
	}
	return input
}

// setInputs shows inputs, focusing the first.
func (m *initModel) setInputs(inputs ...textinput.Model) tea.Cmd {
	m.inputs = inputs
	return m.focus(0)
}

// focus focuses the input i, blurring the others.
func (m *initModel) focus(i int) tea.Cmd {
	for j := range m.inputs {
		m.inputs[j].Blur()
	}
	return m.inputs[i].Focus()
}

// updateInputs passes msg to the inputs.
func (m *initModel) updateInputs(msg tea.Msg) tea.Cmd {
	cmds := make([]tea.Cmd, len(m.inputs))
	for i := range m.inputs {
		m.inputs[i], cmds[i] = m.inputs[i].Update(msg)
	}
	return tea.Batch(cmds...)
}

func (m *initModel) View() tea.View {
	var b strings.Builder
	for _, r := range m.rows {
		name := path.Base(r.dir)
		switch {
		case !r.done:
			fmt.Fprintf(&b, "%s Installing %s\n", m.spinner.View(), name)
		case r.err != nil:
			fmt.Fprintf(&b, "%s Installing %s %s\n", errorStyle.Render("✗"), name, dimStyle.Render(firstLine(r.err)))
		default:
			fmt.Fprintf(&b, "%s Installing %s\n", checkStyle.Render("✓"), name)
		}
	}

	switch m.stage {
	case stageName:
		b.WriteString(boldStyle.Render("What would you like to name this machine?") + "\n")
		b.WriteString(dimStyle.Render("This will be used as the hostname for the VPN") + "\n")
		b.WriteString(m.inputs[0].View() + "\n")
		if m.invalid != "" {
			b.WriteString(errorStyle.Render(m.invalid) + "\n")
		}
	case stageVPN:
		b.WriteString(m.question("Are you using a VPN?"))
	case stageAuthKey:
		b.WriteString(boldStyle.Render("Please provide a VPN auth key") + "\n")
		b.WriteString(m.inputs[0].View() + "\n")
		if m.invalid != "" {
			b.WriteString(errorStyle.Render(m.invalid) + "\n")
		}
	case stageStarting:
		fmt.Fprintf(&b, "%s Starting eagled\n", m.spinner.View())
		b.WriteString(dimStyle.Render("  without an auth key, log in to the VPN with the URL in: journalctl --user -u eagled") + "\n")
	case stageMode:
		b.WriteString(boldStyle.Render("Which installation would you like?") + "\n")
		for i, o := range modeOptions {
			fmt.Fprintf(&b, "%s %s %s\n", m.pointer(i), boldStyle.Render(o.label), dimStyle.Render(o.description))
		}
	case stageFetching:
		fmt.Fprintf(&b, "%s Fetching the plugin list\n", m.spinner.View())
	case stageSimulator:
		b.WriteString(m.question("Do you want to install the SteelEagle simulator?"))
	case stageDrivers:
		b.WriteString(m.checklist("Would you like to install any drivers?", m.plugins.drivers))
	case stageEngines:
		b.WriteString(m.checklist("Would you like to install any engines?", m.plugins.engines))
	case stageOrchestrator:
		b.WriteString(m.question("Would you like to configure this daemon with an orchestrator?"))
	case stageOrchForm:
		b.WriteString(boldStyle.Render("Orchestrator") + "\n")
		for _, input := range m.inputs {
			b.WriteString(input.View() + "\n")
		}
		if m.invalid != "" {
			b.WriteString(errorStyle.Render(m.invalid) + "\n")
		}
		b.WriteString(dimStyle.Render("tab to switch fields, enter to accept") + "\n")
	case stageLinger:
		b.WriteString(m.question("Would you like the daemon to start on boot (requires sudo)?"))
	case stageConfiguring:
		fmt.Fprintf(&b, "%s Configuring eagled\n", m.spinner.View())
	}
	return tea.NewView(b.String())
}

// question renders a yes/no question.
func (m *initModel) question(q string) string {
	answers := []string{"Yes", "No"}
	for i, a := range answers {
		if i == m.cursor {
			answers[i] = cursorStyle.Render("› " + a)
		} else {
			answers[i] = "  " + a
		}
	}
	return boldStyle.Render(q) + "\n" + strings.Join(answers, "  ") + "\n"
}

// checklist renders a checklist of the plugins in dirs.
func (m *initModel) checklist(q string, dirs []string) string {
	var b strings.Builder
	b.WriteString(boldStyle.Render(q) + "\n")
	for i, dir := range dirs {
		box := "[ ]"
		if m.checked[i] {
			box = checkStyle.Render("[x]")
		}
		fmt.Fprintf(&b, "%s %s %s\n", m.pointer(i), box, path.Base(dir))
	}
	b.WriteString(dimStyle.Render("These are installed, but not added to the initial configuration; configure them in when you need them") + "\n")
	b.WriteString(dimStyle.Render("space to select, enter to install") + "\n")
	return b.String()
}

// pointer renders the cursor next to option i, if it is there.
func (m *initModel) pointer(i int) string {
	if i == m.cursor {
		return cursorStyle.Render("›")
	}
	return " "
}

// firstLine returns the first line of the message of err, since some (like
// git's) go on with their output.
func firstLine(err error) string {
	line, _, _ := strings.Cut(status.Convert(err).Message(), "\n")
	return line
}
