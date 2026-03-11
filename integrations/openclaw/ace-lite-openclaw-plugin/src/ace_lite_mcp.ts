import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

export interface AceLiteMcpConfig {
  command: string;
  args: string[];
  cwd?: string;
  env?: Record<string, string>;
}

export class AceLiteMcpClient {
  private readonly _cfg: AceLiteMcpConfig;
  private _transport: StdioClientTransport | null = null;
  private _client: Client | null = null;
  private _connectPromise: Promise<void> | null = null;

  constructor(cfg: AceLiteMcpConfig) {
    this._cfg = cfg;
  }

  async connect(): Promise<void> {
    if (this._client) return;
    if (!this._connectPromise) {
      this._connectPromise = this._connectInner();
    }
    await this._connectPromise;
  }

  private async _connectInner(): Promise<void> {
    const transport = new StdioClientTransport({
      command: this._cfg.command,
      args: this._cfg.args,
      cwd: this._cfg.cwd,
      env: this._cfg.env,
      stderr: "pipe",
    });
    const client = new Client(
      { name: "openclaw-ace-lite-engine", version: "0.3.20" },
      { capabilities: {} }
    );
    await transport.start();
    await client.connect(transport);
    this._transport = transport;
    this._client = client;
  }

  get stderr() {
    return this._transport?.stderr ?? null;
  }

  async close(): Promise<void> {
    const transport = this._transport;
    this._transport = null;
    this._client = null;
    this._connectPromise = null;
    if (transport) {
      await transport.close();
    }
  }

  async callTool(name: string, args: Record<string, unknown>, timeoutMs: number): Promise<any> {
    await this.connect();
    const client = this._client;
    if (!client) {
      throw new Error("MCP client not connected");
    }
    return await withTimeout(
      // SDK typing uses `arguments` as the key.
      client.callTool({ name, arguments: args } as any),
      timeoutMs,
      `callTool timeout: ${name}`
    );
  }
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  const ms = Math.max(1, Math.floor(timeoutMs));
  if (!Number.isFinite(ms) || ms <= 0) return promise;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(label)), ms);
    promise
      .then((value) => {
        clearTimeout(timer);
        resolve(value);
      })
      .catch((err) => {
        clearTimeout(timer);
        reject(err);
      });
  });
}

