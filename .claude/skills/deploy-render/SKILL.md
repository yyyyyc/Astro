---
name: deploy-render
description: Deploy this repository to Render - bump the version, commit, push main to GitHub (Render auto-deploys from it), optionally fire the Render deploy hook, then poll the live site until the new version is served.
disable-model-invocation: true
argument-hint: "[patch|minor|major] [commit message]"
---

# Deploy to Render

Render builds the web service from `https://github.com/yyyyyc/Astro` branch `main`.
A deploy = getting the wanted commit onto `origin/main`, then confirming the live
site serves it. The main page renders `v<version>` from `version.json`
(`templates/index.html`, `.version-tag`), which is how a deploy is verified.

Arguments: `$ARGUMENTS` — optional bump level (`patch` default, `minor`, `major`)
followed by an optional commit message.

## Config (in `.env`, which is gitignored — never commit these)

- `RENDER_SITE_URL` — public URL of the service: `https://tertiary-progression.onrender.com`. Required for verification.
- `RENDER_SERVICE_ID` — `srv-d8l70apo3t8c73aniiag`. Dashboard (build logs/events):
  `https://dashboard.render.com/web/srv-d8l70apo3t8c73aniiag` — include this link in the report.
- `RENDER_DEPLOY_HOOK_URL` — Render dashboard → service → Settings → Deploy Hook. Fired on every deploy (step 7).
  It is a secret: never print it, never put it in a commit or command output.

Read them without echoing secrets:

```bash
cd /c/Python/Astro
SITE=$(grep -E '^RENDER_SITE_URL=' .env | cut -d= -f2- | tr -d '"\r')
HOOK=$(grep -E '^RENDER_DEPLOY_HOOK_URL=' .env | cut -d= -f2- | tr -d '"\r')
```

If `RENDER_SITE_URL` is missing, ask the user for it and offer to add it to `.env`.

## Steps

1. **Check state.** `git status`, `git branch --show-current`, `git log origin/main..HEAD --oneline`.
   - Must be on `main`. If not, stop and ask.
   - Show the user what will ship (uncommitted changes + unpushed commits). If there
     is nothing to ship, say so and stop (unless they just want to re-trigger via the hook).
   - Don't stage `.env`, `venv/`, `flask_*.txt`, or `.claude/settings.local.json`.

2. **Docs.** Per CLAUDE.md: if calculation/forecast/validation logic, a route, or a
   business rule changed, `docs/PROJECT_LOGIC.md` (English + Hebrew) must be updated in
   the same commit. If it's stale, say so before deploying.

3. **Smoke test locally** (catches import errors before Render does):
   ```bash
   python -c "import app" && echo OK
   ```

4. **Bump the version** (required before every push):
   ```bash
   python bump_version.py ${LEVEL:-patch}
   NEW=$(python -c "import json;print(json.load(open('version.json'))['version'])")
   ```

5. **Commit** the changes together with `version.json`. Message style follows the
   repo history: `<summary> (v$NEW)`, ending with the Co-Authored-By trailer.
   Stage specific files, not `git add -A`.

6. **Push:** `git push origin main`. If rejected (remote ahead), `git pull --rebase origin main`,
   resolve, re-run step 4 only if `version.json` conflicts, and push again. Never force-push.

7. **Trigger** the deploy hook (if `HOOK` is missing from `.env`, say so and rely on Auto-Deploy):
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -X POST "$HOOK"
   ```
   Expect `200`/`201`. If the hook is set *and* Auto-Deploy is on, Render may build twice — harmless.

8. **Verify.** Render builds take a few minutes; a free instance may also need ~1 min to wake.
   Poll up to ~10 minutes (use a Monitor/background until-loop rather than foreground sleep):
   ```bash
   until curl -s "$SITE/" | grep -q "v$NEW"; do sleep 20; done
   ```
   Then smoke the other pages:
   ```bash
   # Print the path separately: in Git Bash, a -w value starting with "/" gets rewritten as a Windows path
   for p in / /lp/moon; do printf '%s ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "$SITE$p"; done
   ```

9. **Report:** version, commit hash, live URL, and HTTP results. If verification
   timed out, say so plainly — the push succeeded but the deploy is unconfirmed; point
   the user to the Render dashboard → Events/Logs for the build output.
