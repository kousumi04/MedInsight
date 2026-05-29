const { execFileSync, spawn } = require("child_process");
const net = require("net");
const path = require("path");

const frontendDir = path.resolve(__dirname, "..");
const projectRoot = path.resolve(frontendDir, "..");
const backendHost = process.env.BACKEND_HOST || "127.0.0.1";
const backendPort = Number(process.env.BACKEND_PORT || 8000);
const pythonCommand = process.env.PYTHON || "python";
const nextCli = path.join(frontendDir, "node_modules", "next", "dist", "bin", "next");
const nextArgs = process.argv.slice(2);
const keepExistingBackend = process.env.KEEP_EXISTING_BACKEND === "1";

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

function stopProcessTree(pid) {
  if (!pid) return;

  try {
    if (process.platform === "win32") {
      execFileSync("taskkill.exe", ["/PID", String(pid), "/T", "/F"], {
        stdio: "ignore",
      });
      return;
    }

    process.kill(pid, "SIGTERM");
  } catch {
    // The process may have already exited.
  }
}

function findWindowsPortOwner(port) {
  if (process.platform !== "win32") return null;

  try {
    const output = execFileSync(
      "powershell.exe",
      [
        "-NoProfile",
        "-Command",
        `(Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess`,
      ],
      { encoding: "utf8" },
    ).trim();

    const pid = Number(output);
    return Number.isFinite(pid) && pid > 0 ? pid : null;
  } catch {
    return null;
  }
}

function stopExistingBackendForVisibleLogs() {
  if (keepExistingBackend) return;

  const pid = findWindowsPortOwner(backendPort);
  if (!pid || pid === process.pid) return;

  console.log(`Stopping existing backend on port ${backendPort} so logs are visible here.`);
  stopProcessTree(pid);
}

async function startBackend() {
  stopExistingBackendForVisibleLogs();

  if (await isPortOpen(backendHost, backendPort)) {
    console.log(
      `Backend already running at http://${backendHost}:${backendPort}; existing process logs cannot be attached.`,
    );
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
    stopProcessTree(backendProcess.pid);
  }
  if (nextProcess && !nextProcess.killed) {
    stopProcessTree(nextProcess.pid);
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
