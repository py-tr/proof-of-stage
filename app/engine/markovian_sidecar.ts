// Node sidecar that runs the UNMODIFIED vendored Meterless Markovian reference
// (vendor/meterless-markovian, commit 4eb96f2) for the Python app.
//
// Protocol: one JSON object per line, UTF-8, both ways.
//   stdout  {"ready": true, "impl": "...", "node": "..."}                      once, at start
//   stdin   {"id": n, "method": "run", "params": {goal, chunkConfig, memoryContext?}}
//   stdout  {"cb": "generate", "id": n, "cb_id": k, "step": s, "prompt": "..."}  per chunk
//   stdin   {"cb_id": k, "text": "..."}   or   {"cb_id": k, "error": "..."}
//   stdin   {"id": n, "method": "abort"}                                        optional
//   stdout  {"id": n, "result": {"run": MarkovianRun, "levels": [cascade level per chunk]}}
//   stdout  {"id": n, "error": "..."}
// Nothing else is written to stdout; diagnostics go to stderr.

import readline from "node:readline";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const [major, minor] = process.versions.node.split(".").map(Number);
if (major < 22 || (major === 22 && minor < 7)) {
  process.stderr.write(`markovian sidecar: Node >= 22.7 required (found ${process.versions.node})\n`);
  process.exit(3);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const implPath = path.join(here, "..", "..", "vendor", "meterless-markovian", "reference", "src", "index.ts");
const { Markovian } = await import(pathToFileURL(implPath).href);

function send(message: unknown): void {
  process.stdout.write(JSON.stringify(message) + "\n");
}

const pending = new Map<number, { resolve: (text: string) => void; reject: (err: Error) => void }>();
const aborts = new Map<number, AbortController>();
let nextCallback = 0;

async function run(id: number, params: any): Promise<void> {
  const levels: string[] = [];
  const engine = new Markovian({ chunkConfig: params.chunkConfig });
  // Observe (not change) which compression-cascade level produced each carryover:
  // the reference computes it but does not keep it in the run record.
  const service = (engine as any).carryoverService;
  const original = service.next.bind(service);
  service.next = async (args: unknown) => {
    const result = await original(args);
    levels.push(result.level);
    return result;
  };
  const controller = new AbortController();
  aborts.set(id, controller);
  let step = 0;
  const generator = async (prompt: string) => {
    step += 1;
    const cbId = ++nextCallback;
    const text = await new Promise<string>((resolve, reject) => {
      pending.set(cbId, { resolve, reject });
      send({ cb: "generate", id, cb_id: cbId, step, prompt });
    });
    return { text };
  };
  try {
    const record = await engine.run({
      goal: params.goal,
      generator,
      memoryContext: params.memoryContext,
      abortSignal: controller.signal,
      reflect: false,
    });
    send({ id, result: { run: record, levels } });
  } catch (err) {
    send({ id, error: (err as Error).message });
  } finally {
    aborts.delete(id);
  }
}

send({ ready: true, impl: "meterless-markovian@4eb96f2 (unmodified)", node: process.versions.node });

const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
lines.on("line", (line) => {
  if (!line.trim()) return;
  let message: any;
  try {
    message = JSON.parse(line);
  } catch {
    process.stderr.write("markovian sidecar: bad JSON line\n");
    return;
  }
  if (message.cb_id !== undefined) {
    const waiter = pending.get(message.cb_id);
    if (!waiter) return;
    pending.delete(message.cb_id);
    if (message.error !== undefined) waiter.reject(new Error(String(message.error)));
    else waiter.resolve(String(message.text ?? ""));
  } else if (message.method === "run") {
    void run(message.id, message.params ?? {});
  } else if (message.method === "abort") {
    aborts.get(message.id)?.abort();
  }
});
lines.on("close", () => process.exit(0));
