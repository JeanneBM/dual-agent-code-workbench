"""Read a single PR snapshot; fixed GitHub API origin, no writes or shell."""
import re
import httpx


class GitHubError(Exception):
    pass


def load_pr(url, token="", client=None):
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)/?", url.strip())
    if not match:
        raise GitHubError("Use https://github.com/owner/repo/pull/123")
    owner, repo, number = match.groups()
    if client is None:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            return load_pr(url, token, client)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    endpoint = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"

    def get(suffix="", accept=None):
        try:
            response = client.get(endpoint + suffix, headers={**headers, **({"Accept": accept} if accept else {})})
            response.raise_for_status()
            if len(response.content) > 2_000_000:
                raise GitHubError("PR is too large; paste a smaller diff")
            return response
        except httpx.HTTPError:
            raise GitHubError("GitHub read failed; check URL, token permissions and rate limits") from None

    try:
        before = get().json()
        files = get("/files?per_page=100").json()
        if before.get("changed_files", 0) > 100:
            raise GitHubError("More than 100 changed files; paste a smaller diff")
        if len(files) != before.get("changed_files"):
            raise GitHubError("File list is incomplete")
        if any(not f.get("patch") or f.get("status") == "renamed" for f in files):
            raise GitHubError("Binary, empty-patch or renamed files require manually supplied context")
        diff = get(accept="application/vnd.github.diff").text
        after = get().json()
        if before["head"]["sha"] != after["head"]["sha"] or before["base"]["sha"] != after["base"]["sha"]:
            raise GitHubError("PR changed during import; retry")
        if "diff --git " not in diff:
            raise GitHubError("PR diff is empty or unavailable")
        context = (f"Repository: {owner}/{repo}\nPR: {number}\nHead: {before['head']['sha']}\n"
                   f"Base: {before['base']['sha']}\nTitle: {before['title']}\n"
                   f"Description: {before.get('body') or ''}\n\n{diff}")
        if len(context) > 40_000:
            raise GitHubError("PR exceeds 40000 characters; supply focused context")
        return context
    except (KeyError, ValueError, TypeError):
        raise GitHubError("Invalid GitHub response") from None
