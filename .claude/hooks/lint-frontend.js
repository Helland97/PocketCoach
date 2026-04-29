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
const isFrontend = /(^|[\\/])frontend[\\/]/.test(filePath);
if (!isFrontend) process.exit(0);

const lintable = /\.(ts|tsx|js|jsx|mjs|cjs)$/i.test(filePath);
if (!lintable) process.exit(0);

try {
  execSync("npm run lint", { cwd: "frontend", stdio: "inherit" });
} catch {
  console.error(
    `\nESLint failed after edit to ${filePath}. Fix lint errors before continuing.`
  );
  process.exit(2);
}
