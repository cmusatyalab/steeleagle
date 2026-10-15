# Launch with uv

```
uv run main.py
```

## Requirements

The Plan page compiles missions with `eaglec` (`sdk/cmd/eaglec`), so the
backend host needs the Go toolchain (`go` on `PATH`, version 1.26.5 or newer
per the `go` line in `sdk/go.mod`). At every start the backend rebuilds
`eaglec` with `go build` (incremental, so fast when up to date), which keeps
it in step with the checkout's SDK; the user running the backend therefore
needs a writable `HOME` / `GOCACHE`. If you set `eaglec` in the `[compiler]`
section of `config.toml` that binary is used as-is and nothing is built; see
the commented section in `config.toml.template` to use a different `eaglec`
or SDK version.
