# Gabriel flows

Each file here is one Gabriel flow a vehicle can run:

| File | Flow |
|---|---|
| `baseline.toml` | A: frames and telemetry to the cloudlet's telemetry engine only |
| `early-discard.toml` | B: YOLO on the vehicle passes on only frames with objects |
| `fusion.toml` | C: YOLO on the vehicle and a detector on the cloudlet, in parallel |
| `raw-detect.toml` | D: YOLO on the vehicle takes the driver's raw frames, without JPEG |

A flow file holds only the flow. The vehicle's own settings stay in its own
config: the vehicles, the swarm controller, and the remote server under
`[gabriel]`:

```toml
[gabriel]
remote-server = "<cloudlet IP>:4433"
# base64 -w0 gabriel-identity/certificate.der, on the cloudlet
remote-certificate = "..."
```

`eagle configure` merges the files in the order given, so the flow goes last:

```sh
eagle configure --daemon <host:port> --config drone.toml --config flows/baseline.toml
```

## Switching flows

The flow is one of eagled's daemon-wide settings, which it takes only from the
first `configure`. To switch flows, clear the config, which stops the vehicles,
and configure again. Do it on the ground:

```sh
eagle reset-config --daemon <host:port> --yes
eagle configure --daemon <host:port> --config drone.toml --config flows/early-discard.toml
```

Before configuring a flow with local engines, start them on the vehicle's
computer; see the comments in each flow. Their names include the vehicle's
name. The cloudlet's gabriel-server must serve every remote engine of the flow
(`--engine`). Serving them all lets it serve every flow.

Each start of a flow is recorded on the vehicle's computer, in
`<data dir>/gabriel-recordings/<vehicle>/` (see eagled's README).
