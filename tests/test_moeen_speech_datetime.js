const fs = require("fs");

const source = fs.readFileSync("static/moeen_exec/app.js", "utf8");
const start = source.indexOf("function localDateTimeValue");
const end = source.indexOf("function updateSchedulePreview");
if (start < 0 || end < 0) throw new Error("Speech date parser functions were not found");

const buildParser = new Function(`${source.slice(start, end)}; return extractArabicDateTime;`);
const parse = buildParser();
const now = new Date();
const cases = [
  ["\u0627\u062c\u062a\u0645\u0627\u0639 \u063a\u062f\u0627 \u0627\u0644\u0633\u0627\u0639\u0629 \u0627\u0644\u0639\u0627\u0634\u0631\u0629 \u0635\u0628\u0627\u062d\u0627", date => date.getDate() !== now.getDate() && date.getHours() === 10],
  ["\u0630\u0643\u0631\u0646\u064a \u0628\u0639\u062f \u0633\u0627\u0639\u062a\u064a\u0646", date => Math.abs((date - now) / 60000 - 120) < 1],
  ["\u0627\u062a\u0635\u0644 \u0628\u0623\u062d\u0645\u062f \u0628\u0639\u062f \u0646\u0635\u0641 \u0633\u0627\u0639\u0629", date => Math.abs((date - now) / 60000 - 30) < 1],
  ["\u0645\u062a\u0627\u0628\u0639\u0629 \u0628\u0643\u0631\u0629 \u0627\u0644\u0633\u0627\u0639\u0629 \u0627\u0644\u062e\u0627\u0645\u0633\u0629 \u0645\u0633\u0627\u0621", date => date.getHours() === 17],
  ["\u0645\u0648\u0639\u062f \u0628\u0639\u062f \u062b\u0644\u0627\u062b\u0629 \u0627\u064a\u0627\u0645", date => Math.abs((date - now) / 86400000 - 3) < 0.01],
  ["\u0627\u062c\u062a\u0645\u0627\u0639 \u0643\u0645\u0627\u0646 \u062b\u0644\u0627\u062b \u0627\u064a\u0627\u0645 \u0645\u0646 \u0627\u0644\u064a\u0648\u0645 \u0641\u064a \u0645\u0642\u0631 \u0627\u0644\u0643\u0631\u0645\u0644 \u0627\u0644\u0633\u0627\u0639\u0629 10:00 \u0635\u0628\u0627\u062d\u0627", date => Math.round((date - now) / 86400000) === 3 && date.getHours() === 10 && date.getMinutes() === 0],
  ["\u0627\u062c\u062a\u0645\u0627\u0639 \u0627\u0644\u064a\u0648\u0645 \u0627\u0644\u0633\u0627\u0639\u0629 \u0627\u0644\u062b\u0627\u0646\u064a\u0629 \u0639\u0634\u0631\u0629", date => date.getHours() === 12],
];

let failed = 0;
for (const [phrase, check] of cases) {
  const result = parse(phrase);
  const ok = Boolean(result && check(result));
  console.log(ok ? "PASS" : "FAIL", JSON.stringify(phrase), result?.toISOString());
  if (!ok) failed += 1;
}
if (failed) process.exit(1);
