const { spawn } = require("child_process");
const net = require("net");
const path = require("path");

const frontendDir = path.resolve(__dirname, "..");
const projectRoot = path.resolve(frontendDir, "..");
const backendHost = process.env.BACKEND_HOST || "127.0.0.1";
const backendPort = Number(process.env.BACKEND_PORT || 8000);
const pythonCommand = process.env.PYTHON || "python";
const nextCli = path.join(frontendDir, "node_modules", "next", "dist", "bin", "next");
const nextArgs = process.argv.slice(2);

let backendProcess = null;
let nextProcess = null;

function isPortOpen(host, port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    socket.setTimeout(800);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("error", () => resolve(false));
  });
}

function startProcess(command, args, options) {
  return spawn(command, args, {
    stdio: "inherit",
    shell: false,
    ...options,
  });
}

async function startBackend() {
  if (await isPortOpen(backendHost, backendPort)) {
    console.log(`Backend already running at http://${backendHost}:${backendPort}`);
    return;
  }

  console.log(`Starting backend at http://${backendHost}:${backendPort}`);
  backendProcess = startProcess(
    pythonCommand,
    [
      "-m",
      "uvicorn",
      "backend.main:app",
      "--host",
      backendHost,
      "--port",
      String(backendPort),
    ],
    { cwd: projectRoot },
  );
}

function startFrontend() {
  nextProcess = startProcess(
    process.execPath,
    [nextCli, "dev", ...nextArgs],
    { cwd: frontendDir },
  );

  nextProcess.on("exit", (code) => {
    shutdown(code || 0);
  });
}

function shutdown(code = 0) {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
  if (nextProcess && !nextProcess.killed) {
    nextProcess.kill();
  }
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

startBackend()
  .then(startFrontend)
  .catch((error) => {
    console.error(error);
    shutdown(1);
  });
