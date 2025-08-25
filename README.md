# Real-Time Social Media Sentiment Feed for Trading Platforms

> Monorepo for the project. **Do not push directly to `main`.** Use branches and Pull Requests (PRs).  

⚠️ **Please read the information below on how to contribute to the repo.**  

---

## Workflow

1. **Create a branch** from `main`:
   - `feature/<short-name>` – new features
   - `fix/<short-name>` – bug fixes
   - `refactor/<short-name>` – code restructuring (no behavior change)
   - `docs/<short-name>` – documentation only
   - `chore/<short-name>` – tooling, deps, CI
   - (optional) `hotfix/<short-name>` – urgent fix
2. **Commit & push** your work to your branch:
   ```bash
   git checkout -b feature/<short-name>
   git push -u origin feature/<short-name>
3. **Open a Pull Request** (PR) into main.
4. **Review & merge:**
  - Another contributor reviews the PR (or review by yourself incase of urgency).  
  - Address comments, then squash & merge (preferred) into main.  
ℹ️ Branch protection on main is expected: no direct pushes.

## Repo Structure
This is the mother repo. Avoid starting projects in the root.  
Create subfolders and keep each component isolated:  
```
/frontend/     # web app(s)
/backend/      # services, APIs
/model/        # AI/ML models, notebooks, training code
/infra/        # IaC, deployment, CI/CD workflows
/docs/         # design docs, specs, ADRs
```
- Each subfolder can have its own README.md, .env.example, and tooling.
- Use separate package managers/virtual envs inside each subproject.

## Quick Commands
```
# update local main
git checkout main
git pull origin main

# create a feature branch
git checkout -b feature/<short-name>

# work, commit, and push
git add .
git commit -m "feat: <message>"
git push -u origin feature/<short-name>
```

## PR Checklist
- Scope limited to one logical change
- **Please updated docs/README in the affected subfolder during the PR push (does not have to be finalized documentation, but provide enough info to avoid potential breaks due to introduced changes in the future**

## Notes
- Keep secrets out of the repo. Provide .env.example files instead.
- Prefer conventional commits (feat, fix, chore, docs, refactor, test).
- Discuss breaking changes in the PR description.
