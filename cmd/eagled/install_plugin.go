package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	git "github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/config"
	"github.com/go-git/go-git/v5/plumbing"
)

// InstallTimeout bounds how long a plugin's install.sh is allowed to run.
const InstallTimeout = 5 * time.Minute

// fetchRefName is the local branch every narrow fetch lands under,
// regardless of what name or hash the caller's ref resolves to remotely.
// Using a fixed local name means the caller's ref never needs to double as a
// valid local git ref name.
const fetchRefName = plumbing.ReferenceName("refs/heads/install-target")

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

	repository, hash, err := fetchAtRef(ctx, cloneDir, repo, ref)
	if err != nil {
		return fmt.Errorf("fetching %s@%s: %w", repo, ref, err)
	}
	worktree, err := repository.Worktree()
	if err != nil {
		return fmt.Errorf("getting worktree: %w", err)
	}
	if err := worktree.Checkout(&git.CheckoutOptions{Hash: hash}); err != nil {
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

// fetchAtRef populates cloneDir with just enough of repo to check out ref,
// avoiding a full clone when possible. ref may be a branch, tag, or a full
// commit SHA; an empty ref means the remote's default branch (its HEAD).
//
// It first tries a depth-1 fetch of exactly that ref. For a branch or tag
// name this always works and is cheap. For a raw commit SHA it only works if
// the remote advertises SHA1-in-want support (GitHub and GitLab do; many
// self-hosted servers don't). When the narrow fetch isn't possible, this
// falls back to a full clone, which works against any server but pulls the
// whole history — so any valid ref still resolves, just slower.
func fetchAtRef(ctx context.Context, cloneDir, repo, ref string) (*git.Repository, plumbing.Hash, error) {
	src := ref
	if src == "" {
		src = "HEAD"
	}

	repository, remote, err := initScratchRemote(cloneDir, repo)
	if err != nil {
		return nil, plumbing.ZeroHash, err
	}

	refspec := config.RefSpec(src + ":" + string(fetchRefName))
	fetchErr := remote.FetchContext(ctx, &git.FetchOptions{
		RefSpecs: []config.RefSpec{refspec},
		Depth:    1,
		Tags:     git.NoTags,
	})
	if fetchErr == nil {
		fetchedRef, err := repository.Reference(fetchRefName, true)
		if err != nil {
			return nil, plumbing.ZeroHash, fmt.Errorf("resolving fetched ref: %w", err)
		}
		return repository, fetchedRef.Hash(), nil
	}

	// The narrow fetch can legitimately fail — ref might not be an
	// advertised branch/tag name, or (for a raw SHA) the server might not
	// support fetching arbitrary object IDs. Reset the scratch directory and
	// fall back to a full clone so any valid ref still resolves.
	if err := os.RemoveAll(cloneDir); err != nil {
		return nil, plumbing.ZeroHash, fmt.Errorf("resetting scratch directory after narrow fetch failed (%v): %w", fetchErr, err)
	}
	if err := os.MkdirAll(cloneDir, 0755); err != nil {
		return nil, plumbing.ZeroHash, fmt.Errorf("recreating scratch directory: %w", err)
	}

	repository, err = git.PlainCloneContext(ctx, cloneDir, false, &git.CloneOptions{URL: repo})
	if err != nil {
		return nil, plumbing.ZeroHash, fmt.Errorf("cloning %s (narrow fetch failed: %v): %w", repo, fetchErr, err)
	}
	if ref == "" {
		headRef, err := repository.Head()
		if err != nil {
			return nil, plumbing.ZeroHash, fmt.Errorf("resolving HEAD: %w", err)
		}
		return repository, headRef.Hash(), nil
	}
	hash, err := repository.ResolveRevision(plumbing.Revision(ref))
	if err != nil {
		return nil, plumbing.ZeroHash, fmt.Errorf("resolving ref %q: %w", ref, err)
	}
	return repository, *hash, nil
}

func initScratchRemote(cloneDir, repo string) (*git.Repository, *git.Remote, error) {
	repository, err := git.PlainInit(cloneDir, false)
	if err != nil {
		return nil, nil, fmt.Errorf("initializing scratch repo: %w", err)
	}
	remote, err := repository.CreateRemote(&config.RemoteConfig{Name: "origin", URLs: []string{repo}})
	if err != nil {
		return nil, nil, fmt.Errorf("adding remote: %w", err)
	}
	return repository, remote, nil
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
