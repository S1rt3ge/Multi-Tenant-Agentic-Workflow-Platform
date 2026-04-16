# Release Process

This repository uses a lightweight git-based release process.

## Version Source of Truth

- Backend application version: `backend/app/core/version.py`
- Frontend package version: `frontend/package.json`
- CLI package version: `cli/package.json`
- Changelog: `CHANGELOG.md`

Keep these aligned for each release.

## Release Checklist

1. Ensure `main` is green in both workflows:
   - `CI`
   - `Smoke`
2. Run local verification if needed:
   - backend tests
   - frontend build
   - smoke script
3. Update version values:
   - `backend/app/core/version.py`
   - `frontend/package.json`
   - `cli/package.json`
4. Update `CHANGELOG.md`
5. Commit release metadata changes
6. Create a git tag
7. Push commit and tag
8. Confirm the `Release` workflow created the GitHub Release for the tag
9. Confirm the `Publish Images` workflow pushed backend/frontend images for the tag
10. Confirm the `Publish CLI` workflow published the `graphpilot` npm package for the tag

## Required Publishing Secrets

- `NPM_TOKEN` — required for the `Publish CLI` workflow

GHCR image publishing uses the built-in `GITHUB_TOKEN` and does not require a separate registry token.

## Validation

Before tagging, validate release metadata locally:

```bash
python scripts/validate-release.py
```

To validate against a specific tag:

```bash
python scripts/validate-release.py v0.1.0
```

## Suggested Commands

```bash
git checkout main
git pull

# after updating version files + changelog
git add backend/app/core/version.py frontend/package.json frontend/package-lock.json cli/package.json CHANGELOG.md
git commit -m "release: cut v0.1.1"
python scripts/validate-release.py v0.1.1
git tag v0.1.1
git push origin main
git push origin v0.1.1
```

## Post-Release

After a release tag:

1. Verify GitHub Actions completed successfully
2. Deploy using `DEPLOYMENT.md`
3. Record deployment notes if production behavior differs from staging/local

## Notes

- Avoid releasing from a dirty worktree
- Prefer small release commits that only contain version/changelog metadata
- If production deployment requires a rollback, redeploy the previous known-good tag
