#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const skillsDir = path.join(root, "skills");
const llmsPath = path.join(skillsDir, "llms.txt");
const errors = [];

function fail(message) {
  errors.push(message);
}

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function parseFrontmatter(content, skillPath) {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) {
    fail(`${skillPath}: missing YAML frontmatter`);
    return null;
  }

  const data = {};
  for (const line of match[1].split(/\r?\n/)) {
    if (!line.trim()) continue;
    const field = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!field) {
      fail(`${skillPath}: unsupported frontmatter line: ${line}`);
      continue;
    }
    const [, key, rawValue] = field;
    let value = rawValue.trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    data[key] = value;
  }

  return data;
}

if (!fs.existsSync(skillsDir)) {
  fail("missing skills/ directory");
}

if (!fs.existsSync(llmsPath)) {
  fail("missing skills/llms.txt");
}

const llmsText = fs.existsSync(llmsPath) ? readText(llmsPath) : "";
const seenNames = new Map();

const entries = fs.existsSync(skillsDir)
  ? fs.readdirSync(skillsDir, { withFileTypes: true })
  : [];

for (const entry of entries) {
  if (!entry.isDirectory()) continue;

  const folder = entry.name;
  const skillDir = path.join(skillsDir, folder);
  const skillPath = path.join(skillDir, "SKILL.md");
  const relativeSkillPath = path.relative(root, skillPath);

  if (!fs.existsSync(skillPath)) {
    fail(`skills/${folder}: missing SKILL.md`);
    continue;
  }

  for (const banned of ["README.md", "INSTALL.md", "QUICKSTART.md", "CHANGELOG.md"]) {
    if (fs.existsSync(path.join(skillDir, banned))) {
      fail(`skills/${folder}: move ${banned} to the repository root or examples/`);
    }
  }

  const frontmatter = parseFrontmatter(readText(skillPath), relativeSkillPath);
  if (!frontmatter) continue;

  const keys = Object.keys(frontmatter).sort();
  const extraKeys = keys.filter((key) => !["description", "name"].includes(key));
  if (extraKeys.length > 0) {
    fail(`${relativeSkillPath}: unsupported frontmatter keys: ${extraKeys.join(", ")}`);
  }

  const name = frontmatter.name;
  const description = frontmatter.description;

  if (!name) {
    fail(`${relativeSkillPath}: missing name`);
  } else {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) {
      fail(`${relativeSkillPath}: name must use lowercase-hyphen format`);
    }
    if (name.length > 63) {
      fail(`${relativeSkillPath}: name must be 63 characters or fewer`);
    }
    if (name !== folder) {
      fail(`${relativeSkillPath}: folder name must match frontmatter name (${name})`);
    }
    if (seenNames.has(name)) {
      fail(`${relativeSkillPath}: duplicate skill name also used by ${seenNames.get(name)}`);
    } else {
      seenNames.set(name, relativeSkillPath);
    }
    if (!llmsText.includes(`${name}:`)) {
      fail(`skills/llms.txt: missing entry for ${name}`);
    }
  }

  if (!description || description.length < 25) {
    fail(`${relativeSkillPath}: description must be at least 25 characters`);
  }

  if (!fs.existsSync(path.join(skillDir, "agents", "openai.yaml"))) {
    fail(`skills/${folder}: missing agents/openai.yaml`);
  }
}

if (seenNames.size === 0) {
  fail("no skills found under skills/");
}

if (errors.length > 0) {
  console.error("Skill validation failed:");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log(`Validated ${seenNames.size} skill${seenNames.size === 1 ? "" : "s"}.`);
