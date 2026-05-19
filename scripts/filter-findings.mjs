import { readFileSync } from "fs";
const r = JSON.parse(readFileSync("data/security-audit-report.json", "utf8"));
const real = r.findings.filter(f => 
  !f.file.includes("test") && 
  !f.file.includes("security-audit") && 
  !f.file.includes("services/rust") && 
  !f.file.includes("services/go") &&
  !f.file.includes("scripts/")
);
console.log("Real findings:", real.length);
real.forEach(f => console.log(`  ${f.severity} | ${f.file}:${f.line} | ${f.description}`));
