import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const viteBin = join(root, "node_modules", "vite", "bin", "vite.js");
const pythonBin = join(root, ".venv", "bin", "python");
const venvBin = join(root, ".venv", "bin");
const cargoBin = join(root, ".cargo", "bin");

if (!existsSync(viteBin)) {
  console.error("Vite is not installed. Run npm install first.");
  process.exit(1);
}

const children = [
  spawn(pythonBin, ["-m", "backend.app.dev_server"], {
    cwd: root,
    stdio: "inherit",
    env: {
      ...process.env,
      PATH: `${cargoBin}:${venvBin}:${process.env.PATH ?? ""}`,
      CARGO_HOME: `${root}/.cargo`,
      RUSTUP_HOME: `${root}/.rustup`
    }
  }),
  spawn(process.execPath, [viteBin, "--host", "127.0.0.1", "--port", "5173"], {
    cwd: root,
    stdio: "inherit"
  })
];

function stopAll(signal = "SIGTERM") {
  for (const child of children) {
    if (!child.killed) {
      child.kill(signal);
    }
  }
}

for (const child of children) {
  child.on("exit", (code) => {
    if (code && code !== 0) {
      stopAll();
      process.exit(code);
    }
  });
}

process.on("SIGINT", () => {
  stopAll("SIGINT");
  process.exit(130);
});

process.on("SIGTERM", () => {
  stopAll("SIGTERM");
  process.exit(143);
});
