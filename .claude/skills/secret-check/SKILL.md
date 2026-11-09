---
name: secret-check
description: Revisa si Claude Code guardó contraseñas, tokens o API keys en .claude/settings*.json (por el botón "Yes, and don't ask again") y si esos archivos están o estuvieron commiteados en git. Usar antes de commitear o pushear, al abrir un repo, o cuando el usuario pida revisar secretos o permisos guardados.
---

# secret-check

Corré el script desde la raíz del repo:

```bash
bash .claude/skills/secret-check/check.sh
```

Revisa:
1. `.claude/settings.local.json` y `.claude/settings.json` (proyecto) y `~/.claude/settings*.json` (usuario) en busca de secretos.
2. Si `.claude/settings.local.json` está en `.gitignore`.
3. Si algún `.claude/settings*.json` fue commiteado alguna vez (todo el historial), y si ese historial tiene secretos.

## Cómo reportar
- Respondé en español, corto: ✅ limpio / ⚠️ riesgo / 🚨 secreto encontrado.
- **Nunca muestres el valor del secreto completo.** El script ya los enmascara; no los reconstruyas.
- Si hay 🚨: el primer paso es **rotar el secreto** (borrarlo no alcanza si estuvo en git). Después, sacar la línea del archivo y agregar `.claude/settings.local.json` al `.gitignore`.
- No reescribas el historial de git ni hagas force-push sin el OK explícito del usuario.
