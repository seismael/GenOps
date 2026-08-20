# Distribution

GenOps is a **native, in-repo tool** — the engine, skills, templates, and scaffolds live inside each project (`.agents/`) and are driven by the agent locally. There is **no daemon, no network service, and no required package manager**.

This document lists how to obtain GenOps and how maintainers publish a release.

## Obtaining GenOps (users)

| Channel | Command / action | Best for |
|---|---|---|
| **GitHub template (primary)** | Click **"Use this template"** on the repo | Starting a new project pre-wired with GenOps |
| **GitHub Release** | Download the tagged source/artifact from Releases | Pinning a specific version; offline use |
| **Git clone** | `git clone https://github.com/seismael/GenOps.git` | Vendoring the latest in an existing repo |
| **In-repo copy** | Copy `.agents/` + `genops.yaml` into a project, then `python .agents/scripts/genops.py init --agent all` | Zero network; full control |

After obtaining it, verify with:

```bash
python .agents/scripts/genops.py doctor
```

## Why no npm / PyPI runtime package

GenOps's value is that the engine is **versioned together with the project** it governs. A globally-installed package would decouple the tool from the specs it generates (version drift) and contradict the zero-dependency, vendored-in-repo design. A registry could only ever be a thin `genops init` bootstrap shim — not the delivery of the engine itself — so it is intentionally omitted.

## Publishing a release (maintainers)

1. **Bump the version** in `.agents/scripts/genops.py` (`__version__`) and `CHANGELOG.md`.
2. **Verify**: `python .agents/scripts/genops.py doctor` and the example suites (`examples-gate` in CI).
3. **Commit & tag**:
   ```bash
   git add -A
   git commit -m "feat: release GenOps vX.Y.Z - <summary>"
   git tag -a vX.Y.Z -m "GenOps vX.Y.Z"
   git push origin <branch> --tags
   ```
4. **Cut a GitHub Release** at the tag — paste the matching `docs/releases/vX.Y.Z.md` as the description and attach the `.agents/` bundle (or just the source tarball).
5. **Keep "Template repository" enabled** in GitHub → Settings → General → *Template repository*, so users get the one-click "Use this template" flow.

## Release notes

- [v3.1.0](releases/v3.1.0.md)
