#!/usr/bin/env node

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const packageRoot = path.resolve(__dirname, "..");
const packageJson = JSON.parse(
  fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"),
);
const packageVersion = packageJson.version;
const stateFileName = ".orca-visualizer-install-state.json";
const supportedMinors = new Set([10, 11, 12]);

function main() {
  const userArgs = process.argv.slice(2);
  if (userArgs.length === 1 && userArgs[0] === "--version") {
    process.stdout.write(`${packageVersion}\n`);
    return;
  }
  if (userArgs.length === 1 && (userArgs[0] === "--help" || userArgs[0] === "-h")) {
    printHelp();
    return;
  }

  const installRoot = getInstallRoot();
  const venvDir = path.join(installRoot, ".venv");
  const pythonExe = getVenvPythonPath(venvDir);

  ensureInstalled({
    installRoot,
    venvDir,
    pythonExe,
  });

  const forwardedArgs = normalizeCliArgs(userArgs);
  runChecked(
    pythonExe,
    ["-m", "orca_viz.cli", ...forwardedArgs],
    {
      cwd: process.cwd(),
      env: process.env,
    },
  );
}

function printHelp() {
  const lines = [
    "ORCA Visualizer npm launcher",
    "",
    "Usage:",
    "  orca-visualizer",
    "  orca-visualizer doctor",
    "  orca-visualizer run -- --server.port 8510",
    "  npx @wuls968/orca-visualizer",
    "",
    "Notes:",
    "  - Requires Python 3.10 / 3.11 / 3.12 on the local machine.",
    "  - Viewing existing ORCA output/cube files does not require ORCA itself.",
    "  - GBW -> cube workflows require local ORCA tools such as orca_plot.",
  ];
  process.stdout.write(`${lines.join("\n")}\n`);
}

function normalizeCliArgs(userArgs) {
  if (userArgs.length === 0) {
    return ["run"];
  }
  const [firstArg] = userArgs;
  if (firstArg === "run" || firstArg === "doctor") {
    return userArgs;
  }
  if (firstArg.startsWith("-")) {
    return ["run", ...userArgs];
  }
  return ["run", ...userArgs];
}

function ensureInstalled({ installRoot, venvDir, pythonExe }) {
  fs.mkdirSync(installRoot, { recursive: true });
  const statePath = path.join(installRoot, stateFileName);
  const state = readInstallState(statePath);
  const needsInstall = !fs.existsSync(pythonExe) || state.version !== packageVersion;

  if (!needsInstall) {
    return;
  }

  const python = detectPython();
  const createdVenv = !fs.existsSync(pythonExe);
  if (createdVenv) {
    console.error(`Preparing Python environment at ${installRoot}`);
    runChecked(python.command, [...python.args, "-m", "venv", venvDir], {
      cwd: packageRoot,
      env: process.env,
    });
  } else {
    console.error(`Refreshing ORCA Visualizer ${packageVersion} in ${installRoot}`);
  }

  runChecked(
    pythonExe,
    ["-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
    {
      cwd: packageRoot,
      env: process.env,
    },
  );
  runChecked(
    pythonExe,
    ["-m", "pip", "install", "--upgrade", packageRoot],
    {
      cwd: packageRoot,
      env: process.env,
    },
  );

  fs.writeFileSync(
    statePath,
    JSON.stringify(
      {
        version: packageVersion,
        installedAt: new Date().toISOString(),
      },
      null,
      2,
    ),
  );
}

function detectPython() {
  const override = process.env.ORCA_VISUALIZER_PYTHON;
  const candidates = [
    ...(override ? [{ command: override, args: [] }] : []),
    ...(process.platform === "win32"
    ? [
        { command: "py", args: ["-3.12"] },
        { command: "py", args: ["-3.11"] },
        { command: "py", args: ["-3.10"] },
        { command: "py", args: ["-3"] },
        { command: "python", args: [] },
        { command: "python3", args: [] },
      ]
    : [
        { command: "python3.12", args: [] },
        { command: "python3.11", args: [] },
        { command: "python3.10", args: [] },
        { command: "python3", args: [] },
        { command: "python", args: [] },
      ]),
  ];

  for (const candidate of candidates) {
    const completed = spawnSync(
      candidate.command,
      [
        ...candidate.args,
        "-c",
        "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
      ],
      {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
        windowsHide: true,
      },
    );
    if (completed.status !== 0) {
      continue;
    }
    const versionText = (completed.stdout || "").trim();
    const match = /^(\d+)\.(\d+)$/.exec(versionText);
    if (!match) {
      continue;
    }
    const major = Number(match[1]);
    const minor = Number(match[2]);
    if (major === 3 && supportedMinors.has(minor)) {
      return candidate;
    }
  }

  console.error("A supported local Python was not found.");
  console.error("Install Python 3.10, 3.11, or 3.12, then rerun `orca-visualizer`.");
  if (!override) {
    console.error("You can also point to a specific interpreter with ORCA_VISUALIZER_PYTHON.");
  }
  process.exit(1);
}

function getInstallRoot() {
  const override = process.env.ORCA_VISUALIZER_HOME;
  if (override) {
    return path.resolve(override, "npm", packageVersion);
  }
  if (process.platform === "win32") {
    const baseDir = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(baseDir, "orca-visualizer", "npm", packageVersion);
  }
  return path.join(os.homedir(), ".orca-visualizer", "npm", packageVersion);
}

function getVenvPythonPath(venvDir) {
  if (process.platform === "win32") {
    return path.join(venvDir, "Scripts", "python.exe");
  }
  return path.join(venvDir, "bin", "python");
}

function readInstallState(statePath) {
  try {
    return JSON.parse(fs.readFileSync(statePath, "utf8"));
  } catch {
    return {};
  }
}

function runChecked(command, args, options) {
  const completed = spawnSync(command, args, {
    stdio: "inherit",
    windowsHide: true,
    ...options,
  });
  if (completed.error) {
    throw completed.error;
  }
  if (completed.status !== 0) {
    process.exit(completed.status || 1);
  }
}

main();
