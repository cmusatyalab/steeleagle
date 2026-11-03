package download

import (
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// literalPathspec makes git take the path after it literally, with no globbing.
const literalPathspec = ":(literal)"

// lsTreeFields is the number of fields in the metadata of a git ls-tree entry: mode, type and object id.
const lsTreeFields = 3

// InstallPackage installs a git url into target. Like Terraform, a sub directory of the
// repository can be selected by appending it to the url after a double slash
// (https://host/repo.git//sub/dir). Like Go, a version (branch, tag, or commit) can be
// selected by appending it to the end of the url after an @ (https://host/repo.git//sub/dir@v1),
// defaulting to the default branch. Only the files of the sub directory are checked out.
// Only https and local (file) repositories are allowed.
func InstallPackage(url, target string) error {
	// Check if git is installed
	if _, err := exec.LookPath("git"); err != nil {
		return fmt.Errorf("no git found on system")
	}
	url, version := splitVersion(url)
	url, subdir := splitSubdir(url)
	// Normalize the sub directory, with "." for the whole repository
	subdir = strings.Trim(filepath.ToSlash(subdir), "/")
	if subdir == "" {
		subdir = "."
	}
	if !fs.ValidPath(subdir) {
		return fmt.Errorf("invalid subdir %q", subdir)
	}
	// Make sure the target directory exists
	if _, err := os.Stat(filepath.Dir(target)); err != nil {
		return fmt.Errorf("failed to find directory %s", filepath.Dir(target))
	} else if _, err := os.Lstat(target); err == nil {
		return fmt.Errorf("target path %s already exists", target)
	}
	// Create a temp directory where we can write the output
	tmp, err := os.MkdirTemp(filepath.Dir(target), ".gitfetch-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmp)
	repo := filepath.Join(tmp, "repo")
	if err := os.Mkdir(repo, 0755); err != nil {
		return err
	}

	// git runs git in the repository, feeding it stdin, and returns its stdout
	git := func(stdin string, args ...string) (string, error) {
		cmd := exec.Command("git", append([]string{"-C", repo}, args...)...)
		cmd.Env = append(os.Environ(),
			"GIT_TERMINAL_PROMPT=0",         // fail instead of prompting for creds
			"GIT_ALLOW_PROTOCOL=https:file", // no ssh, git or ext transports
		)
		cmd.Stdin = strings.NewReader(stdin)
		var stdout, stderr strings.Builder
		cmd.Stdout, cmd.Stderr = &stdout, &stderr
		if err := cmd.Run(); err != nil {
			return "", fmt.Errorf("git %v: %w\n%s", args, err, stderr.String())
		}
		return stdout.String(), nil
	}

	for _, args := range [][]string{
		{"init", "-q"},
		{"remote", "add", "origin", url},
		{"fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", version},
	} {
		if _, err := git("", args...); err != nil {
			return err
		}
	}
	// Pin the commit, since FETCH_HEAD is for the fetch, and later ones may replace it
	commit, err := git("", "rev-parse", "FETCH_HEAD")
	if err != nil {
		return err
	}
	commit = strings.TrimSpace(commit)

	// Only the sub directory is checked out, so only its files are
	// fetched; the literal magic stops git reading it as a glob
	var pathspec []string
	if subdir != "." {
		pathspec = []string{"--", literalPathspec + subdir}
	}
	// The blobless fetch got no file contents, and a checkout would fetch the
	// missing ones one at a time, a round trip each. Fetch them all at once.
	if err := prefetchBlobs(git, commit, pathspec); err != nil {
		return err
	}
	checkout := append([]string{"-c", "advice.detachedHead=false", "checkout", "-q", commit}, pathspec...)
	if _, err := git("", checkout...); err != nil {
		return err
	}
	if err := os.RemoveAll(filepath.Join(repo, ".git")); err != nil {
		return err
	}

	// Copy the sub directory out through an os.Root, so that symlinks
	// pointing outside of the package are refused
	root, err := os.OpenRoot(repo)
	if err != nil {
		return err
	}
	defer root.Close()
	src, err := root.OpenRoot(subdir)
	if err != nil {
		return fmt.Errorf("subdir %q not found at %s: %w", subdir, version, err)
	}
	defer src.Close()
	staged := filepath.Join(tmp, "pkg")
	if err := copyRoot(staged, src); err != nil {
		return err
	}
	return os.Rename(staged, target)
}

// prefetchBlobs fetches, in one request, the file contents under pathspec at
// commit that the repository is missing. git is a function that runs git in
// the repository with the given stdin and returns its stdout.
func prefetchBlobs(git func(stdin string, args ...string) (string, error), commit string, pathspec []string) error {
	out, err := git("", append([]string{"ls-tree", "-r", "-z", commit}, pathspec...)...)
	if err != nil {
		return err
	}
	// Entries are "<mode> <type> <oid>\t<path>", separated by NULs
	var oids strings.Builder
	for _, entry := range strings.Split(out, "\x00") {
		meta, _, _ := strings.Cut(entry, "\t")
		fields := strings.Fields(meta)
		// Submodules (type commit) aren't in this repository
		if len(fields) == lsTreeFields && fields[1] == "blob" {
			oids.WriteString(fields[lsTreeFields-1] + "\n")
		}
	}
	if oids.Len() == 0 {
		return nil
	}
	// These are the options git itself fetches missing objects with
	_, err = git(oids.String(),
		"-c", "fetch.negotiationAlgorithm=noop",
		"fetch", "--no-tags", "--no-write-fetch-head", "--recurse-submodules=no",
		"--filter=blob:none", "origin", "--stdin")
	return err
}

// splitVersion splits a url of the form repo@version into the repository and
// the version, ignoring an @ in the host like https://user@host.
func splitVersion(url string) (string, string) {
	offset := 0
	if i := strings.Index(url, "://"); i >= 0 {
		offset = i + len("://")
		if j := strings.Index(url[offset:], "/"); j >= 0 {
			offset += j
		} else {
			offset = len(url)
		}
	}
	i := strings.LastIndex(url[offset:], "@")
	if i < 0 {
		return url, ""
	}
	i += offset
	return url[:i], url[i+len("@"):]
}

// splitSubdir splits a url of the form repo//subdir into the repository and
// the sub directory, skipping the double slash of a scheme like https://.
func splitSubdir(url string) (string, string) {
	offset := 0
	if i := strings.Index(url, "://"); i >= 0 {
		offset = i + len("://")
	}
	i := strings.Index(url[offset:], "//")
	if i < 0 {
		return url, ""
	}
	i += offset
	return url[:i], url[i+len("//"):]
}

// copyRoot copies the files in root into dir. Symlinks are replaced by
// copies of the files they point to, which must be inside of root.
func copyRoot(dir string, root *os.Root) error {
	fsys := root.FS()
	return fs.WalkDir(fsys, ".", func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		dst := filepath.Join(dir, filepath.FromSlash(path))
		if d.IsDir() {
			return os.MkdirAll(dst, 0755)
		}
		if !d.Type().IsRegular() && d.Type()&fs.ModeSymlink == 0 {
			return fmt.Errorf("%s: unsupported file type %s", path, d.Type())
		}
		r, err := fsys.Open(path)
		if err != nil {
			return err
		}
		defer r.Close()
		info, err := r.Stat()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			return fmt.Errorf("%s: symlink to a non-regular file", path)
		}
		w, err := os.OpenFile(dst, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644|info.Mode()&0111)
		if err != nil {
			return err
		}
		if _, err := io.Copy(w, r); err != nil {
			w.Close()
			return err
		}
		return w.Close()
	})
}
