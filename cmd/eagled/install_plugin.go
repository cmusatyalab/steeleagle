package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	git "github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
)

// InstallTimeout bounds how long a plugin's install.sh is allowed to run.
const InstallTimeout = 5 * time.Minute

// installPlugin fetches repo at ref, extracts subpath, and runs the
// resulting install.sh. Only on a zero exit does it atomically replace
// whatever was previously installed under installDir/<name>. A failed
// install leaves the existing plugin, if any, untouched.
func installPlugin(ctx context.Context, installDir, name, repo, ref, subpath string) error {
	if err := os.MkdirAll(installDir, 0755); err != nil {
		return fmt.Errorf("creating install directory: %w", err)
	}

	// Cloned under installDir, not the system temp dir, so the rename into
	// place below stays on one filesystem.
	cloneDir, err := os.MkdirTemp(installDir, ".install-"+name+"-")
	if err != nil {
		return fmt.Errorf("creating scratch directory: %w", err)
	}
	defer os.RemoveAll(cloneDir)

	repository, err := git.PlainCloneContext(ctx, cloneDir, false, &git.CloneOptions{URL: repo})
	if err != nil {
		return fmt.Errorf("cloning %s: %w", repo, err)
	}
	hash, err := repository.ResolveRevision(plumbing.Revision(ref))
	if err != nil {
		return fmt.Errorf("resolving ref %q: %w", ref, err)
	}
	worktree, err := repository.Worktree()
	if err != nil {
		return fmt.Errorf("getting worktree: %w", err)
	}
	if err := worktree.Checkout(&git.CheckoutOptions{Hash: *hash}); err != nil {
		return fmt.Errorf("checking out %s: %w", hash, err)
	}
	os.RemoveAll(filepath.Join(cloneDir, ".git"))

	srcDir := cloneDir
	if subpath != "" {
		srcDir = filepath.Join(cloneDir, subpath)
	}
	if info, err := os.Stat(srcDir); err != nil || !info.IsDir() {
		return fmt.Errorf("subpath %q not found in %s@%s", subpath, repo, ref)
	}

	installScript := filepath.Join(srcDir, "install.sh")
	if _, err := os.Stat(installScript); err != nil {
		return fmt.Errorf("install.sh not found: %w", err)
	}

	installCtx, cancel := context.WithTimeout(ctx, InstallTimeout)
	defer cancel()
	cmd := exec.CommandContext(installCtx, "sh", "install.sh")
	cmd.Dir = srcDir
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("install.sh failed: %w\n%s", err, output)
	}

	return swapIn(srcDir, filepath.Join(installDir, name))
}

// swapIn moves srcDir into targetDir, backing up and restoring whatever was
// previously at targetDir if the final rename fails.
func swapIn(srcDir, targetDir string) error {
	backup := targetDir + ".old"
	os.RemoveAll(backup) // clear any leftover from a previous failed swap

	replaced := false
	if _, err := os.Stat(targetDir); err == nil {
		if err := os.Rename(targetDir, backup); err != nil {
			return fmt.Errorf("backing up existing plugin: %w", err)
		}
		replaced = true
	}

	if err := os.Rename(srcDir, targetDir); err != nil {
		if replaced {
			os.Rename(backup, targetDir) // best-effort rollback
		}
		return fmt.Errorf("installing plugin: %w", err)
	}

	if replaced {
		os.RemoveAll(backup)
	}
	return nil
}
