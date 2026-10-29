package main

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"charm.land/bubbles/v2/progress"
	"charm.land/bubbles/v2/spinner"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
	"charm.land/lipgloss/v2/table"
	"github.com/charmbracelet/x/term"
)

var (
	boldStyle    = lipgloss.NewStyle().Bold(true)
	welcomeStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("214"))
	dimStyle     = lipgloss.NewStyle().Faint(true)
	cursorStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("214"))
	checkStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("2"))
	errorStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("1"))
)

// errCancelled is returned when the user quits with ctrl+c.
var errCancelled = errors.New("cancelled")

// isTerminal reports whether out is a terminal, which gets the terminal UI;
// anything else, such as a pipe or a file, gets plain output for scripts.
func isTerminal(out io.Writer) bool {
	f, ok := out.(*os.File)
	return ok && term.IsTerminal(f.Fd())
}

// result is what a task prints once it is done: plain to a pipe or file, and
// styled to a terminal.
type result struct {
	plain, styled string
}

// done is the result of a task that succeeded with msg, which is marked with
// a check on a terminal.
func done(msg string) result {
	return result{msg + "\n", checkStyle.Render("✓ ") + capitalize(msg) + "\n"}
}

// warn is the result of a task that went through, but found a problem msg,
// which is marked with a ! on a terminal.
func warn(msg string) result {
	return result{msg + "\n", errorStyle.Render("! ") + capitalize(msg) + "\n"}
}

// capitalize returns s with its first letter in upper case.
func capitalize(s string) string {
	if s == "" {
		return s
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

// printResult prints res to out: styled to a terminal, and plain to anything
// else. It is for results that come back without a wait worth showing.
func printResult(out io.Writer, res result) error {
	s := res.plain
	if isTerminal(out) {
		s = res.styled
	}
	_, err := io.WriteString(out, s)
	return err
}

// reportFunc reports the progress of a task, as done out of total.
type reportFunc func(done, total int64)

// taskFunc does the work of a task, reporting its progress, if it can, with
// report.
type taskFunc func(ctx context.Context, report reportFunc) (result, error)

// runTask runs work, printing its result to out. On a terminal, it shows
// title with a spinner while it works, or a progress bar once work reports
// its progress, then replaces it with the result, or with a cross if work
// fails.
func runTask(ctx context.Context, out io.Writer, title string, work taskFunc) error {
	if !isTerminal(out) {
		res, err := work(ctx, func(int64, int64) {})
		if err != nil {
			return err
		}
		_, err = io.WriteString(out, res.plain)
		return err
	}
	// The terminal is in raw mode, so ctrl+c is a key press, which cancels
	// workCtx, rather than an interrupt
	workCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	m := &taskModel{
		title:   title,
		cancel:  cancel,
		spinner: spinner.New(spinner.WithSpinner(spinner.Dot), spinner.WithStyle(cursorStyle)),
	}
	p := tea.NewProgram(m, tea.WithContext(ctx), tea.WithOutput(out))
	m.work = func() tea.Msg {
		res, err := work(workCtx, func(done, total int64) { p.Send(progressMsg{done, total}) })
		return taskDoneMsg{res, err}
	}
	if _, err := p.Run(); err != nil {
		return err
	}
	return m.err
}

// Messages of a task.
type (
	progressMsg struct{ done, total int64 }
	taskDoneMsg struct {
		res result
		err error
	}
)

// taskModel is the terminal UI of a task (see runTask).
type taskModel struct {
	title    string
	work     tea.Cmd
	cancel   context.CancelFunc
	spinner  spinner.Model
	progress *progress.Model // shown once the task reports its progress
	sent     progressMsg     // the progress last reported
	err      error           // why the task failed
}

func (m *taskModel) Init() tea.Cmd {
	return tea.Batch(m.spinner.Tick, m.work)
}

func (m *taskModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyPressMsg:
		if msg.Keystroke() == "ctrl+c" {
			m.err = errCancelled
			m.cancel()
			return m, tea.Quit
		}
	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd
	case progressMsg:
		if m.progress == nil {
			bar := progress.New(progress.WithDefaultBlend(), progress.WithWidth(40))
			m.progress = &bar
		}
		m.sent = msg
	case taskDoneMsg:
		if msg.err != nil {
			m.err = msg.err
			return m, tea.Sequence(tea.Println(errorStyle.Render("✗ ")+m.title), tea.Quit)
		}
		return m, tea.Sequence(tea.Println(strings.TrimSuffix(msg.res.styled, "\n")), tea.Quit)
	}
	return m, nil
}

func (m *taskModel) View() tea.View {
	if m.err != nil {
		return tea.NewView("")
	}
	if m.progress == nil {
		return tea.NewView(fmt.Sprintf("%s %s\n", m.spinner.View(), m.title))
	}
	// The bar shows the progress as is, since animating it lags behind
	percent := float64(m.sent.done) / float64(max(m.sent.total, 1))
	return tea.NewView(fmt.Sprintf("%s\n%s  %s\n", m.title, m.progress.ViewAs(percent),
		dimStyle.Render(formatBytes(m.sent.done)+" / "+formatBytes(m.sent.total))))
}

// formatBytes formats n bytes in the largest unit it has at least one of.
func formatBytes(n int64) string {
	const unit = 1000
	if n < unit {
		return fmt.Sprintf("%d B", n)
	}
	div, exp := int64(unit), 0
	for m := n / unit; m >= unit; m /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(n)/float64(div), "kMGTPE"[exp])
}

// newTable returns a table with headers, in the style of the terminal UI:
// bold headers in a rounded border, with dashes for blank cells dimmed.
func newTable(headers ...string) *table.Table {
	return table.New().
		Border(lipgloss.RoundedBorder()).
		BorderStyle(dimStyle).
		Headers(headers...).
		StyleFunc(func(row, col int) lipgloss.Style {
			style := lipgloss.NewStyle().Padding(0, 1)
			if row == table.HeaderRow {
				return style.Bold(true)
			}
			return style
		})
}

// renderTable renders t to fit out, wrapping its cells if it is wider than a
// terminal out is shown on.
func renderTable(t *table.Table, out io.Writer) string {
	s := t.Render()
	f, ok := out.(*os.File)
	if !ok {
		return s
	}
	// Setting the width also stretches a narrower table, so it is only set
	// on a table too wide to fit
	if width, _, err := term.GetSize(f.Fd()); err == nil && width > 0 && lipgloss.Width(s) > width {
		s = t.Width(width).Render()
	}
	return s
}

// orDim returns s, or a dimmed dash if it is empty, so table cells are never
// blank.
func orDim(s string) string {
	if s == "" {
		return dimStyle.Render("-")
	}
	return s
}

// confirmModel asks a yes/no question, whose answer defaults to no.
type confirmModel struct {
	question string
	cursor   int // 0 on yes, 1 on no
	answered bool
	yes      bool
}

func (m *confirmModel) Init() tea.Cmd { return nil }

func (m *confirmModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	if m.answered {
		return m, nil
	}
	key, ok := msg.(tea.KeyPressMsg)
	if !ok {
		return m, nil
	}
	switch key.Keystroke() {
	case "y":
		m.answered, m.yes = true, true
	case "n", "ctrl+c", "esc":
		m.answered = true
	case "enter":
		m.answered, m.yes = true, m.cursor == 0
	case "left", "right", "h", "l", "tab", "shift+tab":
		m.cursor = 1 - m.cursor
	}
	if m.answered {
		answer := "No"
		if m.yes {
			answer = "Yes"
		}
		return m, tea.Sequence(tea.Println(boldStyle.Render(m.question)+" "+dimStyle.Render(answer)), tea.Quit)
	}
	return m, nil
}

func (m *confirmModel) View() tea.View {
	if m.answered {
		return tea.NewView("")
	}
	return tea.NewView(question(m.question, m.cursor))
}

// confirm asks q, reading the answer from in and showing it on out. When in
// and out aren't a terminal, the answer is read as a line instead. Anything
// but yes, including a closed input, is a no.
func confirm(ctx context.Context, in io.Reader, out io.Writer, q string) bool {
	if f, ok := in.(*os.File); !ok || !term.IsTerminal(f.Fd()) || !isTerminal(out) {
		fmt.Fprintf(out, "%s [y/N] ", q)
		answer, _ := bufio.NewReader(in).ReadString('\n')
		switch strings.ToLower(strings.TrimSpace(answer)) {
		case "y", "yes":
			return true
		}
		return false
	}
	m := &confirmModel{question: q, cursor: 1}
	_, err := tea.NewProgram(m, tea.WithContext(ctx), tea.WithInput(in), tea.WithOutput(out)).Run()
	return err == nil && m.yes
}

// question renders a yes/no question, with the cursor on yes if it is 0, or
// on no if it is 1.
func question(q string, cursor int) string {
	answers := []string{"Yes", "No"}
	for i, a := range answers {
		if i == cursor {
			answers[i] = cursorStyle.Render("› " + a)
		} else {
			answers[i] = "  " + a
		}
	}
	return boldStyle.Render(q) + "\n" + strings.Join(answers, "  ") + "\n"
}
