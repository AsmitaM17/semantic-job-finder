const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const cwd = path.resolve(__dirname, "..");
const python = path.join(cwd, ".venv", "Scripts", "python.exe");
const dataDir = path.join(cwd, "data");

fs.mkdirSync(dataDir, { recursive: true });

const out = fs.openSync(path.join(dataDir, "streamlit.out.log"), "a");
const err = fs.openSync(path.join(dataDir, "streamlit.err.log"), "a");

const child = spawn(
  python,
  [
    "-m",
    "streamlit",
    "run",
    "app.py",
    "--server.headless",
    "true",
    "--server.port",
    "8501",
    "--server.address",
    "127.0.0.1",
  ],
  {
    cwd,
    detached: true,
    stdio: ["ignore", out, err],
    windowsHide: true,
  },
);

child.unref();
console.log(child.pid);