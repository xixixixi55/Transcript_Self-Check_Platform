/**
 * 仓库资产卫生检查
 * 验证 Git 当前跟踪文件中不存在禁止路径或文件模式。
 * 运行: npx tsx scripts/check-repository-assets.ts
 *
 * 跨平台：Windows / Linux / macOS。
 * 仅读取 Git 跟踪文件（不扫描磁盘目录）。
 */
import { execSync } from 'node:child_process';

function run(cmd: string): string {
  try {
    return execSync(cmd, {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
      maxBuffer: 10 * 1024 * 1024,
    });
  } catch (err: any) {
    console.error(`Git 命令失败: ${cmd}`);
    console.error(err.stderr || err.message);
    process.exit(2);
  }
}

/** 禁止的路径模式（子串匹配，已规范化为 / 的路径） */
const FORBIDDEN_PATTERNS = [
  { pattern: '.idea/', rule: 'IDE 目录不得被 Git 跟踪', fix: '确认已在 .gitignore 中忽略' },
  { pattern: '/output/', rule: '生成输出目录不得被 Git 跟踪', fix: '确认已在 .gitignore 中忽略；仅本地保存' },
];

/** 禁止的文件 glob（小写，git fnmatch 区分大小写） */
const FORBIDDEN_GLOBS_LOWER = [
  { glob: '~$*.doc', rule: 'Word 临时锁文件 (.doc)', fix: '删除文件；已由 .gitignore 忽略' },
  { glob: '~$*.docx', rule: 'Word 临时锁文件 (.docx)', fix: '删除文件；已由 .gitignore 忽略' },
  { glob: '*.rar', rule: 'RAR 归档不得被 Git 跟踪', fix: '删除文件；已由 .gitignore 忽略' },
  { glob: '*.zip', rule: 'ZIP 归档不得被 Git 跟踪', fix: '删除文件；已由 .gitignore 忽略' },
  { glob: '*.tmp', rule: '临时文件 (.tmp) 不得被 Git 跟踪', fix: '删除文件；已由 .gitignore 忽略' },
  { glob: '*.temp', rule: '临时文件 (.temp) 不得被 Git 跟踪', fix: '删除文件；已由 .gitignore 忽略' },
];

/** 大写后缀变体（git fnmatch 无法匹配的） */
const FORBIDDEN_SUFFIXES = [
  { suffix: '.RAR', rule: 'RAR 归档不得被 Git 跟踪', fix: '删除文件；已由 .gitignore 忽略' },
  { suffix: '.ZIP', rule: 'ZIP 归档不得被 Git 跟踪', fix: '删除文件；已由 .gitignore 忽略' },
  { suffix: '.TMP', rule: '临时文件 (.TMP) 不得被 Git 跟踪', fix: '删除文件；已由 .gitignore 忽略' },
  { suffix: '.TEMP', rule: '临时文件 (.TEMP) 不得被 Git 跟踪', fix: '删除文件；已由 .gitignore 忽略' },
];

/** 明确允许的资产（不应被上述规则误报） */
const ALLOWED_ASSETS = new Set([
  'word_templates/template.docx',
  'word_templates/template-v1.0.0.docx',
  'word_templates/template-v1.0.1.docx',
  'word_templates/template-v1.0.2.docx',
]);

// 使用 NUL 分隔符读取跟踪文件（安全处理所有字符）
const trackedRaw = run('git ls-files -z');

// 空输出保护
if (!trackedRaw || trackedRaw.length === 0) {
  console.error('错误: git ls-files 返回空输出，无法验证资产。');
  process.exit(2);
}

const trackedFiles = trackedRaw
  .split('\0')
  .filter(Boolean)
  .map((f) => f.replace(/\\/g, '/'));

if (trackedFiles.length === 0) {
  console.error('错误: 未找到任何跟踪文件，无法验证资产。');
  process.exit(2);
}

let violations = 0;

function report(file: string, rule: string, fix: string) {
  console.log(`[违规] ${file}`);
  console.log(`  规则: ${rule}`);
  console.log(`  修复: ${fix}`);
  console.log('');
  violations++;
}

for (const file of trackedFiles) {
  // 跳过明确允许的资产
  if (ALLOWED_ASSETS.has(file)) continue;

  // 检查禁止的路径模式
  for (const fp of FORBIDDEN_PATTERNS) {
    if (file.includes(fp.pattern)) {
      report(file, fp.rule, fp.fix);
    }
  }

  // 检查大写后缀变体
  for (const fs of FORBIDDEN_SUFFIXES) {
    if (file.endsWith(fs.suffix)) {
      report(file, fs.rule, fs.fix);
    }
  }
}

// 检查禁止的小写 glob（通过 git ls-files 匹配）
for (const fg of FORBIDDEN_GLOBS_LOWER) {
  try {
    const matches = run(`git ls-files -z "${fg.glob}"`);
    if (matches && matches.length > 0) {
      for (const file of matches.split('\0').filter(Boolean)) {
        const normalized = file.replace(/\\/g, '/');
        if (ALLOWED_ASSETS.has(normalized)) continue;
        report(normalized, fg.rule, fg.fix);
      }
    }
  } catch {
    // 无匹配 — 正常
  }
}

if (violations > 0) {
  console.log(`发现 ${violations} 项资产卫生违规。`);
  console.log('请在提交前解决全部违规。');
  process.exit(1);
} else {
  console.log('仓库资产卫生检查: 通过');
  console.log(`跟踪文件数: ${trackedFiles.length}`);
  process.exit(0);
}
