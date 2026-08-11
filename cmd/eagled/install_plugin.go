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

// installPlugin fetches repo at ref, extracts subpath, moves it into place
// under installDir/<name>, and then runs install.sh. A failed install rolls
// the move back, leaving whatever was previously installed, if anything,
// untouched.
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
	if _, err := os.Stat(filepath.Join(srcDir, "install.sh")); err != nil {
		return fmt.Errorf("install.sh not found: %w", err)
	}

	targetDir := filepath.Join(installDir, name)
	backupDir := targetDir + ".old"
	replaced, err := swapIn(srcDir, targetDir, backupDir)
	if err != nil {
		return err
	}

	installCtx, cancel := context.WithTimeout(ctx, InstallTimeout)
	defer cancel()
	cmd := exec.CommandContext(installCtx, "sh", "install.sh")
	cmd.Dir = targetDir
	if output, err := cmd.CombinedOutput(); err != nil {
		os.RemoveAll(targetDir)
		if replaced {
			os.Rename(backupDir, targetDir) // best-effort rollback
		}
		return fmt.Errorf("install.sh failed: %w\n%s", err, output)
	}

	if replaced {
		os.RemoveAll(backupDir)
	}
	return nil
}

// swapIn moves srcDir into targetDir, backing up whatever was previously at
// targetDir into backupDir (clearing any stale backup first) and restoring
// it if the rename itself fails. replaced reports whether there was an
// existing install to back up, so the caller knows whether backupDir needs
// cleaning up (on success) or restoring (if a later step fails).
func swapIn(srcDir, targetDir, backupDir string) (replaced bool, err error) {
	os.RemoveAll(backupDir) // clear any leftover from a previous failed swap

	if _, err := os.Stat(targetDir); err == nil {
		if err := os.Rename(targetDir, backupDir); err != nil {
			return false, fmt.Errorf("backing up existing plugin: %w", err)
		}
		replaced = true
	}

	if err := os.Rename(srcDir, targetDir); err != nil {
		if replaced {
			os.Rename(backupDir, targetDir) // best-effort rollback
		}
		return false, fmt.Errorf("installing plugin: %w", err)
	}
	return replaced, nil
}
