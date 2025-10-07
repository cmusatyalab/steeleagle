const path = require('path');
const fs = require('fs');
const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client;

function pickPython(output) {
  const cfg = vscode.workspace.getConfiguration('steeleagle.dsl-lsp-client');
  const cfgPy = cfg.get('pythonPath');
  const envPy = process.env.MIN_LARK_LSP_PY;
  const hard = '/mnt/c/Users/92513/Desktop/steeleagle/.venv/bin/python';
  const candidates = [cfgPy, envPy, hard, 'python'].filter(Boolean);
  output.appendLine(`Python candidates: ${JSON.stringify(candidates)}`);
  for (const p of candidates) {
    if (typeof p === 'string' && p.startsWith('/') && fs.existsSync(p)) return p;
    if (p === 'python') return p;
  }
  return 'python';
}

function activate(context) {
  const output = vscode.window.createOutputChannel('SteelEagle DSL LSP Client');
  output.appendLine('Activating SteelEagle DSL LSP client...');
  vscode.window.showInformationMessage('SteelEagle DSL LSP client ACTIVATED');

  // Dummy completion to prove activation/language association works
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { language: 'dsl' },
      {
        provideCompletionItems() {
          return [
            new vscode.CompletionItem('HELLO_FROM_CLIENT'),
            new vscode.CompletionItem('mission'),
            new vscode.CompletionItem('action'),
          ];
        }
      },
      '.', ' ', '('
    )
  );

  const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
  const serverPath = path.resolve(ws, '../server/server.py');
  const PY = pickPython(output);
  output.appendLine(`Using PY=${PY}`);
  output.appendLine(`serverPath=${serverPath}`);

  if (!fs.existsSync(serverPath)) {
    vscode.window.showErrorMessage(`steeleagle.dsl-lsp-client: server not found at ${serverPath}`);
    output.appendLine(`ERROR: server not found at ${serverPath}`);
    return;
  }

  client = new LanguageClient(
    'steeleagle.dsl-lsp-client',
    'SteelEagle DSL LSP Client',
    { command: PY, args: [serverPath], transport: TransportKind.stdio },
    {
      documentSelector: [{ scheme: 'file', language: 'dsl' }],
      synchronize: { fileEvents: vscode.workspace.createFileSystemWatcher('**/*.dsl') },
      outputChannel: output
    }
  );

  context.subscriptions.push(client.start());
}

function deactivate() {
  return client?.stop();
}

module.exports = { activate, deactivate };
