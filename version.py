# Single source of truth for the app version.
# When you want to ship an update:
#   1. Bump this string (e.g. "1.0.1")
#   2. Commit and push a matching git tag:  git tag v1.0.1 && git push origin v1.0.1
#   3. GitHub Actions will automatically build and publish the new release.

__version__ = "1.0.3"
