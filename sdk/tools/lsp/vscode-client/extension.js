// Minimal, uv-powered LSP client for your DSL.
// Launches: uv run python tools/lsp/server/server.py  (cwd = repo root)

const vscode = require("vscode");
const path = require("path");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let client;

function activate(context) {
  // Use the first workspace folder as repo root (fallback to process.cwd()).
  const repoRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();

  // Build absolute path to your server.py relative to the repo root.
  const serverPy = path.resolve(repoRoot, "tools/lsp/server/server.py");

  const serverOptions = {
    command: "uv",
    // If you prefer module mode instead: ["run","python","-m","steeleagle_sdk.lsp.server"]
    args: ["run", "python", serverPy],
    transport: TransportKind.stdio,
    options: {
      cwd: repoRoot, // <-- ensures uv picks the root pyproject.toml / workspace
    },
  };

  const clientOptions = {
    documentSelector: [{ scheme: "file", language: "dsl" }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.dsl"),
    },
  };

  client = new LanguageClient(
    "steeleagle-dsl-lsp",
    "Steeleagle DSL LSP",
    serverOptions,
    clientOptions
  );

  context.subscriptions.push(client.start());
}

function deactivate() {
  return client?.stop();
}

module.exports = { activate, deactivate };
