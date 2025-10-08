const vscode = require("vscode");
const path = require("path");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let client;

function activate(context) {

  const serverEntry = "steeleagle_sdk.tools.lsp.server.main";

  const serverOptions = {
    command: "uv",
    args: ["run", "python", "-m", serverEntry],
    transport: TransportKind.stdio,
  };

  const clientOptions = {
    documentSelector: [{ scheme: "file", language: "dsl" }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.dsl"),
    },
  };

  client = new LanguageClient(
    "steeleagle-gcs-vscode-client",
    "Steeleagle GCS DSL Language Client",
    serverOptions,
    clientOptions
  );

  context.subscriptions.push(client.start());
}

function deactivate() {
  return client?.stop();
}

module.exports = { activate, deactivate };
