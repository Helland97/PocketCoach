#!/usr/bin/env node
const { execSync } = require("child_process");
const fs = require("fs");

let raw = "";
try {
  raw = fs.readFileSync(0, "utf8");
} catch {
  process.exit(0);
}

let input;
try {
  input = JSON.parse(raw);
} catch {
  process.exit(0);
}

const filePath = input?.tool_input?.file_path || "";
if (!/\.py$/i.test(filePath)) process.exit(0);
if (!/(^|[\\/])AI[\\/]/.test(filePath)) process.exit(0);

function hasRuff() {
  try {
    execSync("ruff --version", { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

try {
  if (hasRuff()) {
    execSync(`ruff check "${filePath}"`, { stdio: "inherit" });
  } else {
    execSync(`python -m py_compile "${filePath}"`, { stdio: "inherit" });
  }
} catch {
  console.error(
    `\nPython check failed for ${filePath}. Fix before continuing.`
  );
  process.exit(2);
}
