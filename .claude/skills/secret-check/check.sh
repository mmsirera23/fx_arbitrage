#!/usr/bin/env bash
# Busca secretos guardados por Claude Code en .claude/settings*.json
set -u
PAT='(AKIA[0-9A-Z]{16}|sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY|[a-z]+://[^:/ "]+:[^@/ "]+@|(pass(word|wd)?|pwd|secret|token|api[_-]?key|PGPASSWORD|MYSQL_PWD)[A-Za-z_]*[=: ]+["'"'"']?[^ "'"'"'$]{6,}|Bearer [A-Za-z0-9._-]{15,}|-p[^ "]{6,})'
mask() { sed -E 's/([A-Za-z0-9_+\/.-]{4})[A-Za-z0-9_+\/.-]{4,}/\1****/g'; }
found=0

scan() { # $1=label, stdin=content
  local hits; hits=$(grep -nEi "$PAT" || true)
  if [ -n "$hits" ]; then echo "🚨 $1"; echo "$hits" | mask | cut -c1-200 | sed 's/^/    /'; found=1; fi
}

echo "== Archivos actuales =="
for f in .claude/settings.local.json .claude/settings.json "$HOME/.claude/settings.json" "$HOME/.claude/settings.local.json"; do
  [ -f "$f" ] || continue
  before=$found; scan "$f" < "$f"; [ $found = $before ] && echo "✅ $f sin secretos"
done

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "== Git =="
  if git check-ignore -q .claude/settings.local.json; then echo "✅ settings.local.json está en .gitignore"
  else echo "⚠️  .claude/settings.local.json NO está en .gitignore"; found=$((found|2)); fi
  tracked=$(git ls-files '.claude/settings*.json')
  [ -n "$tracked" ] && echo "⚠️  Commiteado hoy: $tracked"
  commits=$(git log --all --oneline -- '.claude/settings*.json' | wc -l)
  if [ "$commits" -gt 0 ]; then
    echo "⚠️  $commits commit(s) tocaron .claude/settings*.json"
    git log --all -p -- '.claude/settings*.json' | grep '^+' | scan "Secretos en el historial de git (rotalos aunque ya no estén)"
  else echo "✅ Nunca se commiteó .claude/settings*.json"; fi
fi

echo "=="
if [ $((found&1)) = 1 ]; then echo "RESULTADO: 🚨 secretos encontrados → ROTARLOS primero"; exit 1
elif [ $found -ne 0 ]; then echo "RESULTADO: ⚠️ riesgo (sin secretos visibles)"; exit 0
else echo "RESULTADO: ✅ limpio"; fi
