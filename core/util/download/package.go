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

// InstallPackage installs a git url into target. Like Terraform, a sub directory of the
// repository can be selected by appending it to the url after a double slash
// (https://host/repo.git//sub/dir). Like Go, a version (branch, tag, or commit) can be
// selected by appending it to the end of the url after an @ (https://host/repo.git//sub/dir@v1),
// defaulting to the default branch. It does a sparse checkout, ignoring files outside of
// the sub directory. Only https and local (file) repositories are allowed.
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

	run := func(args ...string) error {
		cmd := exec.Command("git", append([]string{"-C", repo}, args...)...)
		cmd.Env = append(os.Environ(),
			"GIT_TERMINAL_PROMPT=0",         // fail instead of prompting for creds
			"GIT_ALLOW_PROTOCOL=https:file", // no ssh, git or ext transports
		)
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("git %v: %w\n%s", args, err, out)
		}
		return nil
	}

	steps := [][]string{
		{"init", "-q"},
		{"remote", "add", "origin", url},
		{"fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", version},
		{"-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD"},
	}
	if subdir != "." {
		sparse := []string{"sparse-checkout", "set", "--no-cone", "/" + subdir + "/"}
		steps = append(steps[:3], append([][]string{sparse}, steps[3:]...)...)
	}
	for _, s := range steps {
		if err := run(s...); err != nil {
			return err
		}
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
