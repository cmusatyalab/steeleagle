package main

import (
	"bufio"
	"bytes"
	"cmp"
	"context"
	_ "embed"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// serviceUnit is the systemd user unit that runs eagled.
//
//go:embed eagled.service
var serviceUnit []byte

// serviceEnv is the default environment file read by serviceUnit.
//
//go:embed eagled.env
var serviceEnv []byte

// defaultConfig is the daemon config init starts eagled with, a copy of
// eagled's default (core/daemon/defaults/config.toml).
//
//go:embed defaults/config.toml
var defaultConfig []byte

// logo is printed when init starts.
//
//go:embed logo.txt
var logo string

// unitExecStart is the line of serviceUnit that starts eagled, which
// installService points at the eagled it finds.
const unitExecStart = "ExecStart=%h/.local/bin/eagled $EAGLED_ARGS"

// authKeyVar is the variable of the environment file that holds the VPN auth
// key.
const authKeyVar = "STEELEAGLE_AUTH_KEY"

// loginExitCode is the code eagled exits with when the VPN rejects its auth
// key (eagled's LoginExitCode), which eagled.service doesn't restart on.
const loginExitCode = 78

// errAuthKey is returned by waitReady when the VPN rejected eagled's auth
// key.
var errAuthKey = errors.New("the VPN rejected the auth key")

// safeModeError is returned by waitReady when eagled is up, but its services
// failed to start, so it is running without them (in safe mode).
type safeModeError struct{ msg string }

func (e safeModeError) Error() string { return e.msg }

const (
	// pluginsRepo is the repository init installs plugins from.
	pluginsRepo = "https://github.com/cmusatyalab/steeleagle_plugins"
	// pluginsRef is the branch of pluginsRepo plugins are installed from.
	pluginsRef = "v4_backend_rework"
	// gcsURL is where the GCS of a default installation serves its web UI.
	gcsURL = "http://localhost:8002"
	// readyTimeout is how long init waits for eagled to answer once started.
	readyTimeout = 2 * time.Minute
	// pixiBinDir is where Pixi puts the tools installed with pixi global,
	// relative to the home directory, which eagled.service has on its PATH.
	pixiBinDir = ".pixi/bin"
	// preflightTimeout is how long init waits for eagled to print its usage.
	preflightTimeout = 10 * time.Second
	// journalTailLines is how many lines of eagled's log are added to the
	// error when it fails to start.
	journalTailLines = 20
)

// The oldest git that fetches with a filter without being set up as a
// partial clone first.
const (
	minGitMajor = 2
	minGitMinor = 27
)

// gitVersionPattern matches the output of git --version, such as
// "git version 2.56.0" or "git version 2.39.5 (Apple Git-154)".
var gitVersionPattern = regexp.MustCompile(`git version (\d+)\.(\d+)`)

// rootRisk is what init tells a user it is running as root, before asking to
// go on.
const rootRisk = `You are running eagle init as root.

eagled runs the plugins it installs, which are cloned from git repositories.
As root, a faulty plugin has the whole machine, and the rootless podman and
bwrap isolation protects nothing. It is safer to run eagled as an unprivileged
user: create one, with "sudo adduser steeleagle", and run eagle init as them.
`

// servicePaths are where installService writes the service files. They are
// fixed relative to the home directory, since eagled.service refers to the
// environment file through %h, and the service reads its config from the
// default XDG config directory.
type servicePaths struct {
	unit   string // ~/.config/systemd/user/eagled.service
	env    string // ~/.config/steeleagle/eagled.env
	config string // ~/.config/steeleagle/config.toml
}

func newServicePaths(home string) servicePaths {
	return servicePaths{
		unit:   filepath.Join(home, ".config", "systemd", "user", "eagled.service"),
		env:    filepath.Join(home, ".config", "steeleagle", "eagled.env"),
		config: filepath.Join(home, ".config", "steeleagle", "config.toml"),
	}
}

// hostnamePattern matches a valid hostname: a DNS label of letters, digits
// and hyphens, which neither starts nor ends with a hyphen.
var hostnamePattern = regexp.MustCompile(`^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$`)

// validHostname reports whether name can be the daemon's hostname.
func validHostname(name string) bool {
	return hostnamePattern.MatchString(name)
}

// defaultHostname returns the name to suggest for this machine: the
// hostname of the daemon config at path, if it has one, or else the
// machine's hostname, if it is valid, or else the daemon's default.
func defaultHostname(path string) string {
	if content, err := os.ReadFile(path); err == nil {
		if cfg, err := config.ParseDaemonConfigFromBytes(content); err == nil && cfg.Daemon.Hostname != "" {
			return cfg.Daemon.Hostname
		}
	}
	if name, err := os.Hostname(); err == nil {
		name, _, _ = strings.Cut(name, ".")
		if validHostname(name) {
			return name
		}
	}
	cfg, err := config.ParseDaemonConfigFromBytes(defaultConfig)
	if err != nil || cfg.Daemon.Hostname == "" {
		return "eagled"
	}
	return cfg.Daemon.Hostname
}

// writeDefaultConfig replaces the daemon config at path with the default
// config, named hostname. Starting over means a config with services that
// can't run yet, which would start eagled in safe mode, can't get init stuck.
func writeDefaultConfig(path, hostname string) error {
	cfg, err := config.ParseDaemonConfigFromBytes(defaultConfig)
	if err != nil {
		return fmt.Errorf("default config is invalid: %w", err)
	}
	cfg.Daemon.Hostname = hostname
	content, err := cfg.ToBytes()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, content, 0o644)
}

// initDaemon installs and starts eagled as a systemd user service, then
// walks through installing plugins and configuring it (see initModel).
func initDaemon(ctx context.Context, conn grpc.ClientConnInterface, fs *flag.FlagSet, args []string, out io.Writer) error {
	allowRoot := fs.Bool("allow-root", false, "don't ask before installing eagled as root")
	if err := parseArgs(fs, args, 0); err != nil {
		return err
	}
	if os.Geteuid() == 0 && !*allowRoot && !confirmRoot(os.Stdin, out) {
		return errors.New("not installing eagled as root")
	}
	// Look for eagled first, so that a missing one fails before any prompt
	eagled, err := findEagled()
	if err != nil {
		return err
	}
	// Check for git too, which installing the plugins needs
	if _, err := findGit(); err != nil {
		return err
	}
	// Try eagled too, since one that can't run only fails once started
	if err := checkEagled(ctx, eagled); err != nil {
		return err
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}
	// Print the logo before the UI starts, since the UI's renderer can draw
	// over lines printed from inside it
	fmt.Fprintf(out, "\n%s\n\n%s\n\n", strings.TrimRight(logo, "\n"), welcomeStyle.Render("Welcome to SteelEagle"))
	m := newInitModel(ctx, conn, eagled, newServicePaths(home))
	final, err := tea.NewProgram(m, tea.WithContext(ctx), tea.WithOutput(out)).Run()
	if err != nil {
		return err
	}
	return final.(*initModel).err
}

// confirmRoot warns that eagled is about to be installed as root, and asks to
// go on, reading the answer from in. Anything but yes, including a closed
// input, is a no.
func confirmRoot(in io.Reader, out io.Writer) bool {
	fmt.Fprintf(out, "%s\nInstall eagled as root anyway? [y/N] ", rootRisk)
	answer, _ := bufio.NewReader(in).ReadString('\n')
	switch strings.ToLower(strings.TrimSpace(answer)) {
	case "y", "yes":
		return true
	}
	return false
}

// checkEagled runs the eagled at path eagled to print its usage, which
// fails with why if it can't run, such as a binary for another architecture
// or built for a newer glibc than this machine has. Those otherwise only show
// up in the journal once the service is started.
func checkEagled(ctx context.Context, eagled string) error {
	ctx, cancel := context.WithTimeout(ctx, preflightTimeout)
	defer cancel()
	out, err := exec.CommandContext(ctx, eagled, "-h").CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s can't run: %w\n%s", eagled, err, strings.TrimSpace(string(out)))
	}
	return nil
}

// journalTail returns the last lines of the log of the eagled service, or ""
// if it can't be read. It is read by unit, since a user journal doesn't exist
// for root.
func journalTail() string {
	out, err := systemCommand("journalctl", "--user-unit", "eagled",
		"-n", strconv.Itoa(journalTailLines), "--no-pager").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

// withJournal adds the tail of the eagled service's log to the error msg, or
// says how to read it if it can't be.
func withJournal(msg string) error {
	if tail := journalTail(); tail != "" {
		return fmt.Errorf("%s; its log ends:\n%s", msg, tail)
	}
	return fmt.Errorf("%s (see journalctl --user-unit eagled)", msg)
}

// installService installs the eagled at path eagled as a systemd user
// service, with the default config named hostname, with the VPN auth key authKey (none, logging in
// interactively, if it is empty), then enables and (re)starts it. The key
// replaces any the service had, so that a rejected one doesn't linger.
func installService(eagled, hostname, authKey string, paths servicePaths) error {
	if err := writeServiceFiles(paths, eagled); err != nil {
		return err
	}
	// The hostname must be set before eagled first joins the VPN, which
	// registers it under that name
	if err := writeDefaultConfig(paths.config, hostname); err != nil {
		return err
	}
	if err := setAuthKey(paths.env, authKey); err != nil {
		return err
	}
	for _, args := range [][]string{
		{"--user", "daemon-reload"},
		{"--user", "enable", "eagled"},
		// restart rather than start, so that a reinstall runs the new eagled
		{"--user", "restart", "eagled"},
	} {
		if out, err := systemCommand("systemctl", args...).CombinedOutput(); err != nil {
			return fmt.Errorf("systemctl %s: %w\n%s", strings.Join(args, " "), err, out)
		}
	}
	return nil
}

// systemDirs are where systemPath looks for system tools that aren't on the
// PATH, which may have been stripped (by sudo or a script, say).
var systemDirs = []string{"/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"}

// systemPath returns the path of the system tool name, such as systemctl,
// which is looked for on the PATH, then in systemDirs. If it isn't found,
// name is returned as is, so that running it fails saying so.
func systemPath(name string) string {
	if path, err := exec.LookPath(name); err == nil {
		return path
	}
	for _, dir := range systemDirs {
		if path, err := exec.LookPath(filepath.Join(dir, name)); err == nil {
			return path
		}
	}
	return name
}

// systemCommand returns a command running the system tool name (see
// systemPath) with args.
func systemCommand(name string, args ...string) *exec.Cmd {
	return exec.Command(systemPath(name), args...)
}

// findGit returns the path of a git that can fetch with a filter (see
// minGitMajor): the one Pixi installed, if any, since eagled.service prefers
// it, or else the one on the PATH. The error says how to install one.
func findGit() (string, error) {
	var candidates []string
	if home, err := os.UserHomeDir(); err == nil {
		candidates = append(candidates, filepath.Join(home, pixiBinDir, "git"))
	}
	if path, err := exec.LookPath("git"); err == nil {
		candidates = append(candidates, path)
	}
	for _, path := range candidates {
		major, minor, err := gitVersion(path)
		if err == nil && (major > minGitMajor || major == minGitMajor && minor >= minGitMinor) {
			return path, nil
		}
	}
	return "", fmt.Errorf("could not find git %d.%d or newer; install it with: pixi global install git",
		minGitMajor, minGitMinor)
}

// gitVersion returns the major and minor version of the git at path.
func gitVersion(path string) (major, minor int, err error) {
	out, err := exec.Command(path, "--version").Output()
	if err != nil {
		return 0, 0, err
	}
	match := gitVersionPattern.FindStringSubmatch(string(out))
	if match == nil {
		return 0, 0, fmt.Errorf("unrecognized git version %q", strings.TrimSpace(string(out)))
	}
	major, _ = strconv.Atoi(match[1])
	minor, _ = strconv.Atoi(match[2])
	return major, minor, nil
}

// findEagled returns the absolute path of eagled, which is looked for next
// to eagle first and then on the PATH.
func findEagled() (string, error) {
	if exe, err := os.Executable(); err == nil {
		if exe, err := filepath.EvalSymlinks(exe); err == nil {
			path := filepath.Join(filepath.Dir(exe), "eagled")
			if info, err := os.Stat(path); err == nil && !info.IsDir() {
				return path, nil
			}
		}
	}
	path, err := exec.LookPath("eagled")
	if err != nil {
		return "", errors.New("could not find eagled next to eagle or on the PATH")
	}
	return filepath.Abs(path)
}

// writeServiceFiles writes the service unit, starting the eagled at path
// eagled, and the environment file. An existing environment file is kept,
// since it holds the user's settings.
func writeServiceFiles(paths servicePaths, eagled string) error {
	if !bytes.Contains(serviceUnit, []byte(unitExecStart)) {
		return fmt.Errorf("eagled.service has no %q line", unitExecStart)
	}
	// systemd expands % specifiers in the path, and splits it on spaces
	execStart := fmt.Sprintf("ExecStart=%q $EAGLED_ARGS", strings.ReplaceAll(eagled, "%", "%%"))
	unit := bytes.Replace(serviceUnit, []byte(unitExecStart), []byte(execStart), 1)
	if err := os.MkdirAll(filepath.Dir(paths.unit), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(paths.unit, unit, 0o644); err != nil {
		return err
	}

	if err := os.MkdirAll(filepath.Dir(paths.env), 0o700); err != nil {
		return err
	}
	// The env file holds the VPN auth key, so only the user may read it
	f, err := os.OpenFile(paths.env, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if errors.Is(err, fs.ErrExist) {
		return nil
	} else if err != nil {
		return err
	}
	if _, err := f.Write(serviceEnv); err != nil {
		f.Close()
		return err
	}
	return f.Close()
}

// setAuthKey sets the VPN auth key in the environment file at path,
// replacing the key it has, if any.
func setAuthKey(path, key string) error {
	if strings.ContainsAny(key, "\r\n") {
		return errors.New("auth key must be one line")
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	line := authKeyVar + "=" + key
	lines := strings.Split(strings.TrimSuffix(string(content), "\n"), "\n")
	i := slices.IndexFunc(lines, func(l string) bool { return strings.HasPrefix(l, authKeyVar+"=") })
	if i >= 0 {
		lines[i] = line
	} else {
		lines = append(lines, line)
	}
	return os.WriteFile(path, []byte(strings.Join(lines, "\n")+"\n"), 0o600)
}

// waitReady waits for eagled to answer on conn, which it does once it has
// joined its network and started its services. It returns a safeModeError if
// the services failed to start, and gives up early if the service fails,
// returning errAuthKey if the VPN rejected its auth key.
func waitReady(ctx context.Context, conn grpc.ClientConnInterface) error {
	ctx, cancel := context.WithTimeout(ctx, readyTimeout)
	defer cancel()
	client := daemonpb.NewDaemonServiceClient(conn)
	for {
		callCtx, callCancel := context.WithTimeout(ctx, time.Second)
		_, err := client.ListServices(callCtx, &daemonpb.ListServicesRequest{}, grpc.WaitForReady(true))
		callCancel()
		switch status.Code(err) {
		case codes.OK:
			return nil
		case codes.FailedPrecondition:
			return safeModeError{status.Convert(err).Message()}
		case codes.Unavailable, codes.DeadlineExceeded:
			// Not up yet
		default:
			return err
		}
		if state, code := serviceState(); state == "failed" {
			if code == loginExitCode {
				return errAuthKey
			}
			return withJournal("eagled failed to start")
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("%w: %w", withJournal("eagled didn't come up"), err)
		case <-time.After(250 * time.Millisecond):
		}
	}
}

// serviceState returns the state of the eagled service (such as "active" or
// "failed") and the exit code of its last run, or "" if it can't be found.
func serviceState() (state string, code int) {
	out, err := systemCommand("systemctl", "--user", "show", "eagled", "--property=ActiveState,ExecMainStatus").Output()
	if err != nil {
		return "", 0
	}
	for line := range strings.Lines(string(out)) {
		key, value, _ := strings.Cut(strings.TrimSpace(line), "=")
		switch key {
		case "ActiveState":
			state = value
		case "ExecMainStatus":
			code, _ = strconv.Atoi(value)
		}
	}
	return state, code
}

// mainPID returns the PID of the running eagled service, or 0 if it isn't
// running.
func mainPID() int {
	out, err := systemCommand("systemctl", "--user", "show", "eagled", "--property=MainPID", "--value").Output()
	if err != nil {
		return 0
	}
	pid, _ := strconv.Atoi(strings.TrimSpace(string(out)))
	return pid
}

// pluginDirs are the plugin packages in pluginsRepo, by the directories
// they are in, and the simulator's directory, if it has one.
type pluginDirs struct {
	defaults, drivers, engines []string
	simulator                  string
}

// listPlugins lists the plugin packages in pluginsRepo at pluginsRef: the
// directories in its defaults, drivers and engines directories, and its
// simulator directory. Only the repository's trees are fetched, not its files.
func listPlugins(ctx context.Context) (pluginDirs, error) {
	gitPath, err := findGit()
	if err != nil {
		return pluginDirs{}, err
	}
	tmp, err := os.MkdirTemp("", "eagle-plugins-")
	if err != nil {
		return pluginDirs{}, err
	}
	defer os.RemoveAll(tmp)
	git := func(args ...string) ([]byte, error) {
		cmd := exec.CommandContext(ctx, gitPath, append([]string{"-C", tmp}, args...)...)
		cmd.Env = append(os.Environ(), "GIT_TERMINAL_PROMPT=0")
		out, err := cmd.Output()
		if err != nil {
			return nil, fmt.Errorf("git %s: %w", strings.Join(args, " "), err)
		}
		return out, nil
	}
	if _, err := git("init", "-q"); err != nil {
		return pluginDirs{}, err
	}
	if _, err := git("fetch", "-q", "--depth", "1", "--filter=blob:none", pluginsRepo, pluginsRef); err != nil {
		return pluginDirs{}, err
	}
	out, err := git("ls-tree", "-d", "--name-only", "FETCH_HEAD", "defaults/", "drivers/", "engines/", "simulator")
	if err != nil {
		return pluginDirs{}, err
	}
	var dirs pluginDirs
	for _, path := range strings.Fields(string(out)) {
		switch parent, _, _ := strings.Cut(path, "/"); parent {
		case "defaults":
			dirs.defaults = append(dirs.defaults, path)
		case "drivers":
			dirs.drivers = append(dirs.drivers, path)
		case "engines":
			dirs.engines = append(dirs.engines, path)
		case "simulator":
			dirs.simulator = path
		}
	}
	return dirs, nil
}

// pluginURI is the package uri of the directory dir of pluginsRepo.
func pluginURI(dir string) string {
	return pluginsRepo + "//" + dir + "@" + pluginsRef
}

// installPlugin installs the plugin package in the directory dir of
// pluginsRepo.
func installPlugin(ctx context.Context, conn grpc.ClientConnInterface, dir string) error {
	req := daemonpb.InstallPackageRequest_builder{Uri: pluginURI(dir)}.Build()
	_, err := daemonpb.NewDaemonServiceClient(conn).InstallPackage(ctx, req)
	return err
}

// reconfigure replaces the daemon's services with one for each plugin of
// the installed packages among uris, sets its simulator to simulator if it is
// an installed package (none otherwise), sets its orchestrator to
// orchestrator (none if it is empty), and waits for it to restart with the
// new config.
// With an orchestrator, it doesn't wait, since eagled may not be ready until
// the orchestrator is up.
func reconfigure(ctx context.Context, conn grpc.ClientConnInterface, orchestrator, simulator string, uris []string) error {
	client := daemonpb.NewDaemonServiceClient(conn)
	resp, err := client.GetConfiguration(ctx, &daemonpb.GetConfigurationRequest{})
	if err != nil {
		return err
	}
	cfg, err := config.ParseDaemonConfigFromBytes(resp.GetConfigToml())
	if err != nil {
		return fmt.Errorf("daemon's config is invalid: %w", err)
	}
	packages, err := client.ListPackages(ctx, &daemonpb.ListPackagesRequest{})
	if err != nil {
		return err
	}
	var chosen []*daemonpb.Package
	cfg.Simulator.Package = ""
	for _, p := range packages.GetPackages() {
		if slices.Contains(uris, p.GetUri()) {
			chosen = append(chosen, p)
		}
		// A simulator that failed to install would start eagled in safe mode
		if simulator != "" && p.GetUri() == simulator {
			cfg.Simulator.Package = simulator
		}
	}
	cfg.Services, err = pluginServices(chosen)
	if err != nil {
		return err
	}
	cfg.Daemon.Orchestrator = orchestrator
	content, err := cfg.ToBytes()
	if err != nil {
		return err
	}

	pid := mainPID()
	req := daemonpb.ConfigureRequest_builder{ConfigToml: string(content)}.Build()
	if _, err := client.Configure(ctx, req); err != nil {
		return err
	}
	if orchestrator != "" {
		return nil
	}
	// The old eagled may answer until it exits, so wait for the new one
	ctx, cancel := context.WithTimeout(ctx, readyTimeout)
	defer cancel()
	for pid != 0 {
		if p := mainPID(); p != 0 && p != pid {
			break
		}
		select {
		case <-ctx.Done():
			return errors.New("eagled didn't restart (see journalctl --user -u eagled)")
		case <-time.After(250 * time.Millisecond):
		}
	}
	return waitReady(ctx, conn)
}

// pluginServices returns a service for each plugin of packages, named after
// its plugin, with a numbered suffix when another service of its type has
// the name already. Simulator plugins are left out, since they aren't
// services.
func pluginServices(packages []*daemonpb.Package) ([]config.ServiceField, error) {
	type plugin struct{ name, uri string }
	var plugins []plugin
	for _, p := range packages {
		for name := range p.GetPlugins() {
			plugins = append(plugins, plugin{name, p.GetUri()})
		}
	}
	slices.SortFunc(plugins, func(a, b plugin) int {
		return cmp.Or(cmp.Compare(a.name, b.name), cmp.Compare(a.uri, b.uri))
	})

	byPackage := map[string]*daemonpb.Package{}
	for _, p := range packages {
		byPackage[p.GetUri()] = p
	}
	var services []config.ServiceField
	taken := map[config.ServiceType]map[string]bool{}
	for _, p := range plugins {
		conf, err := config.ParsePluginConfigFromBytes(byPackage[p.uri].GetPlugins()[p.name])
		if err != nil {
			return nil, fmt.Errorf("plugin %s of %s: %w", p.name, p.uri, err)
		}
		var typ config.ServiceType
		switch conf.Plugin.Type {
		case "driver":
			typ = config.ServiceVehicle
		case "engine":
			typ = config.ServiceEngine
		case "simulator":
			continue
		default:
			typ = config.ServiceExtra
		}
		if taken[typ] == nil {
			taken[typ] = map[string]bool{}
		}
		name := p.name
		for i := 2; taken[typ][name]; i++ {
			name = fmt.Sprintf("%s_%d", p.name, i)
		}
		taken[typ][name] = true
		services = append(services, config.ServiceField{
			Name:   name,
			Type:   typ,
			Plugin: config.PluginField{Plugin: p.name, Package: p.uri},
		})
	}
	return services, nil
}
