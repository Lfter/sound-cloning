import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Resolve everything from the repository root so Tauri and npm can call this
// script from different working directories.
const root = dirname(dirname(fileURLToPath(import.meta.url)));
const viteBin = join(root, "node_modules", "vite", "bin", "vite.js");
const pythonBin = join(root, ".venv", "bin", "python");
const venvBin = join(root, ".venv", "bin");
const cargoBin = join(root, ".cargo", "bin");

if (!existsSync(viteBin)) {
  console.error("Vite is not installed. Run npm install first.");
  process.exit(1);
}

// Run backend and frontend side by side; if either exits with an error, stop both.
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
  // Child processes may already have exited, so kill only live handles.
  for (const child of children) {
    if (!child.killed) {
      child.kill(signal);
    }
  }
}

for (const child of children) {
  child.on("exit", (code) => {
    // A non-zero child exit means the dev session is no longer healthy.
    if (code && code !== 0) {
      stopAll();
      process.exit(code);
    }
  });
}

process.on("SIGINT", () => {
  // Forward terminal interrupts so uvicorn and Vite can clean up.
  stopAll("SIGINT");
  process.exit(130);
});

process.on("SIGTERM", () => {
  // Tauri may terminate this process directly during shutdown.
  stopAll("SIGTERM");
  process.exit(143);
});
