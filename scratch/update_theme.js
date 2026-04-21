const fs = require('fs');
const path = require('path');

const pagesDir = path.join(__dirname, '../frontend/src/pages');

const _map = [
  { s: 'bg-[#0f1117]', r: 'bg-slate-50 dark:bg-[#0f1117]' },
  { s: 'bg-[#06080F]', r: 'bg-slate-100 dark:bg-[#06080F]' },
  { s: 'bg-[#1a1d27]', r: 'bg-white dark:bg-[#1a1d27]' },
  { s: 'text-slate-200', r: 'text-slate-800 dark:text-slate-200' },
  { s: 'text-slate-300', r: 'text-slate-700 dark:text-slate-300' },
  { s: 'text-slate-400', r: 'text-slate-600 dark:text-slate-400' },
  { s: 'text-white', r: 'text-slate-900 dark:text-white' },
  { s: 'hover:text-white', r: 'hover:text-slate-900 dark:hover:text-white' },
  { s: 'hover:text-slate-200', r: 'hover:text-slate-800 dark:hover:text-slate-200' },
  { s: 'hover:bg-white/5', r: 'hover:bg-slate-100 dark:hover:bg-white/5' },
  { s: 'hover:bg-white/10', r: 'hover:bg-slate-200 dark:hover:bg-white/10' },
  { s: 'hover:bg-white/20', r: 'hover:bg-slate-300 dark:hover:bg-white/20' },
  { s: 'hover:bg-white/[0.07]', r: 'hover:bg-slate-100 dark:hover:bg-white/[0.07]' },
  { s: 'bg-white/5', r: 'bg-white dark:bg-white/5' },
  { s: 'bg-white/10', r: 'bg-slate-200 dark:bg-white/10' },
  { s: 'bg-white/[0.07]', r: 'bg-slate-50 dark:bg-white/[0.07]' },
  { s: 'bg-black/20', r: 'bg-white dark:bg-black/20' },
  { s: 'bg-black/30', r: 'bg-slate-100 dark:bg-black/30' },
  { s: 'bg-black/40', r: 'bg-slate-50 dark:bg-black/40' },
  { s: 'bg-black/50', r: 'bg-slate-200 dark:bg-black/50' },
  { s: 'bg-black/10', r: 'bg-slate-50 dark:bg-black/10' },
  { s: 'border-white/5', r: 'border-slate-200 dark:border-white/5' },
  { s: 'border-white/10', r: 'border-slate-300 dark:border-white/10' },
  { s: 'border-white/20', r: 'border-slate-400 dark:border-white/20' },
  { s: 'hover:bg-black/20', r: 'hover:bg-slate-100 dark:hover:bg-black/20' },
  { s: 'hover:bg-black/40', r: 'hover:bg-slate-200 dark:hover:bg-black/40' },
  { s: 'placeholder:text-slate-600', r: 'placeholder:text-slate-400 dark:placeholder:text-slate-600' }
];

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function processFiles() {
  const files = fs.readdirSync(pagesDir).filter(file => file.endsWith('.jsx'));

  files.forEach(file => {
    const filePath = path.join(pagesDir, file);
    let content = fs.readFileSync(filePath, 'utf8');

    _map.forEach(({ s, r }) => {
      const pattern = new RegExp(`(?<=[\\s"'\\\`])${escapeRegExp(s)}(?=[\\s"'\\\`])`, 'g');
      content = content.replace(pattern, r);
    });

    fs.writeFileSync(filePath, content);
    console.log(`Updated ${file}`);
  });
}

processFiles();
