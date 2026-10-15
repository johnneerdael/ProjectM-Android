#!/usr/bin/env python3
"""Trusted controller for reviewed PR validation; run only from main."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote

CONTEXT = "Reviewed PR builds"
WORKFLOW = "pr-builds.yml"
CODEX = "chatgpt-codex-connector[bot]"
CLAUDE = "claude[bot]"
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}


def writer(api, login):
    return api.get(f"collaborators/{quote(login, safe='')}/permission")["permission"] in {"admin", "maintain", "write"}


def claude_result(review):
    user = review["user"]
    if user["login"] not in {CLAUDE, "github-actions[bot]"} or user.get("type") != "Bot":
        return None
    body = review.get("body") or ""
    marker = re.search(r"^\*\*Reviewed commit:\*\* `([0-9a-f]{40})`$", body, re.M)
    result = re.search(r"^\*\*Result:\*\* (RUNNING|APPROVED|FINDINGS|INCOMPLETE)$", body, re.M)
    run = re.search(r"^\*\*Workflow run:\*\* ([1-9][0-9]*)$", body, re.M)
    if (not body.startswith("## Claude Review\n") or not marker or not result or not run
            or marker[1] != review.get("commit_id") or not review.get("submitted_at")):
        return None
    # The trusted publisher signs off with a native approval, authenticated below
    # against its dedicated workflow run rather than the marker alone.
    if result[1] == "APPROVED" and review["state"] != "APPROVED":
        return None
    if review["state"] == "DISMISSED":
        return None
    return result[1], run[1]


def reviewed_commit_matches(record, written, head):
    if not re.fullmatch(r"[0-9a-f]{7,40}", written):
        return False
    resolved = record.get("_reviewed_commits", {}).get(written, written if len(written) == 40 else None)
    return (isinstance(resolved, str) and re.fullmatch(r"[0-9a-f]{40}", resolved)
            and resolved.startswith(written) and resolved == head)


def eligibility(pr, reviews, comments, threads, reactions=()):
    if pr["state"] != "open" or pr["draft"] or pr["base"]["ref"] != "main":
        return False, "Waiting for an open, ready PR targeting main"
    if pr.get("requested_reviewers") or pr.get("requested_teams"):
        return False, "Waiting for requested reviews"
    if any(not thread["isResolved"] for thread in threads):
        return False, "Waiting for all review threads to be resolved"
    # GitHub hides other users' private drafts. Outstanding review requests above
    # are the observable blocking signal; also reject any draft the API does expose.
    if any(review["state"] == "PENDING" for review in reviews):
        return False, "Waiting for a visible pending review"
    # A comment-only follow-up does not revoke a request for changes.
    decisions = {}
    for review in reviews:
        if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            decisions[review["user"]["login"]] = review["state"]
    if "CHANGES_REQUESTED" in decisions.values():
        return False, "Waiting for requested changes to be accepted"
    head = pr["head"]["sha"]
    completed = False
    requests, completions = {}, {}
    claude_completed = None
    codex_running = []

    def completed_at(kind, value):
        if value:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(microsecond=0)
            completions[kind] = max(timestamp, completions.get(kind, timestamp))

    for comment in comments:
        user = comment["user"]["login"]
        trusted = (user == pr["user"]["login"] or comment.get("author_association") in TRUSTED
                   or comment.get("_claude_authorized") is True)
        request = re.match(r"^@(codex|claude)\s+(security\s+)?review\b", (comment.get("body") or "").strip(), re.I)
        requested_at = comment.get("updated_at") or comment.get("created_at")
        if trusted and request and requested_at:
            provider = request[1].lower()
            if provider == "claude" and (request[2] or not re.fullmatch(r"@claude\s+review", (comment.get("body") or "").strip(), re.I)):
                continue
            if provider == "claude" and comment.get("_claude_authorized") is not True:
                continue
            kind = "security" if request[2] else "code"
            timestamp = datetime.fromisoformat(requested_at.replace("Z", "+00:00")).replace(microsecond=0)
            previous = requests.get(kind)
            if previous is None or timestamp > previous[1]:
                requests[kind] = (provider, timestamp)
            elif timestamp == previous[1] and provider != previous[0]:
                return False, "Review commands are ambiguous; request one reviewer again"
    for comment in comments:
        if comment["user"]["login"] != CODEX or comment["user"].get("type") != "Bot":
            continue
        body = comment.get("body") or ""
        if "<!-- codex-pull-request-review-summary -->" in body:
            for row in body.splitlines():
                if "**Code Review**" not in row and "**Security Review**" not in row:
                    continue
                commit = re.search(r"`([0-9a-f]{7,40})`", row)
                if commit and reviewed_commit_matches(comment, commit[1], head) and "**Completed**" in row:
                    kind = "security" if "**Security Review**" in row else "code"
                    date = re.search(r'datetime="([^"]+)"', row)
                    completed_at(kind, date[1] if date else None)
                elif "**Completed**" not in row and (not commit or reviewed_commit_matches(comment, commit[1], head)):
                    # Defer until the latest manual provider selection is known.
                    date = re.search(r'datetime="([^"]+)"', row)
                    started = date[1] if date else comment.get("updated_at") or comment.get("created_at")
                    codex_running.append(("security" if "**Security Review**" in row else "code", started))
        else:
            commit = re.search(r"\*\*Reviewed commit:\*\*\s*`([0-9a-f]{7,40})`", body)
            if commit and reviewed_commit_matches(comment, commit[1], head) and re.search(r"\bCodex(?: Security)? Review\b", body):
                kind = "security" if re.search(r"Codex Security Review", body, re.I) else "code"
                completed_at(kind, comment.get("created_at"))
    claude_runs = {}
    claude_findings = None
    for review in reviews:
        receipt = claude_result(review)
        if receipt and review["commit_id"] == head and review.get("_workflow_verified") is True:
            result, run = receipt
            claude_runs[run] = review
            if result == "RUNNING" and review.get("_workflow_event") == "workflow_dispatch":
                timestamp = datetime.fromisoformat(review["_workflow_started_at"].replace("Z", "+00:00")).replace(microsecond=0)
                previous = requests.get("code")
                if previous is None or timestamp > previous[1]:
                    requests["code"] = ("claude", timestamp)
                elif timestamp == previous[1] and previous[0] != "claude":
                    return False, "Review commands are ambiguous; request one reviewer again"
            if result == "APPROVED" and not review.get("_workflow_active", False):
                timestamp = datetime.fromisoformat(review["submitted_at"].replace("Z", "+00:00")).replace(microsecond=0)
                claude_completed = max(timestamp, claude_completed or timestamp)
            elif result == "FINDINGS":
                timestamp = datetime.fromisoformat(review["submitted_at"].replace("Z", "+00:00")).replace(microsecond=0)
                claude_findings = max(timestamp, claude_findings or timestamp)
        user = review["user"]
        # Bot replies can create empty COMMENTED review records at the new head
        # even when their inline reply concerns an older commit. Require an actual
        # Codex review body and the API's full commit ID as completion evidence.
        codex_review = (user["login"] == CODEX and user.get("type") == "Bot"
                        and re.search(r"\bCodex(?: Security)? Review\b", review.get("body") or "")
                        and re.fullmatch(r"[0-9a-f]{40}", review.get("commit_id") or ""))
        marker = re.search(r"\*\*Reviewed commit:\*\*\s*`([0-9a-f]{7,40})`", review.get("body") or "")
        if marker:
            codex_review = codex_review and review.get("commit_id", "").startswith(marker[1])
        trusted = codex_review or (
            user.get("type") == "User" and user["login"] not in {CODEX, CLAUDE, "github-actions[bot]", pr["user"]["login"]}
            and review.get("author_association") in TRUSTED)
        if (codex_review and review["commit_id"] == head and review.get("submitted_at")
                and review["state"] in {"APPROVED", "COMMENTED"}):
            kind = "security" if re.search(r"Codex Security Review", review.get("body") or "", re.I) else "code"
            completed_at(kind, review["submitted_at"])
        if (trusted and not codex_review and review.get("submitted_at") and review["commit_id"] == head
                and review["state"] in {"APPROVED", "COMMENTED"}):
            completed = True
    # The PR reaction is Codex's approval signal. Completion text/reviews identify
    # the revision and time only; they cannot approve a PR without its thumbs-up.
    # GitHub's reactions endpoint represents this bot as type=User, so authenticate
    # its reserved connector login rather than relying on that inconsistent field.
    thumbs = [datetime.fromisoformat(reaction["created_at"].replace("Z", "+00:00")).replace(microsecond=0)
              for reaction in reactions if reaction["user"]["login"] == CODEX
              and reaction.get("content") == "+1" and reaction.get("created_at")]
    codex_approved = (bool(completions) and any(thumb >= max(completions.values()) for thumb in thumbs))
    if claude_findings is not None:
        if claude_completed is None or claude_completed <= claude_findings:
            claude_completed = None
        if completions.get("code") is None or completions["code"] <= claude_findings:
            codex_approved = False
        if not claude_completed and not codex_approved:
            return False, "Waiting for a clean review after Claude findings"
    completed = completed or codex_approved or claude_completed is not None
    for kind, started in codex_running:
        switched = requests.get("code")
        timestamp = datetime.fromisoformat(started.replace("Z", "+00:00")).replace(microsecond=0) if started else None
        if kind == "security" or not switched or switched[0] != "claude" or timestamp is None or switched[1] <= timestamp:
            return False, "Waiting for Codex review to finish"
    for review in claude_runs.values():
        if review.get("_workflow_active", claude_result(review)[0] == "RUNNING"):
            switched = requests.get("code")
            started = datetime.fromisoformat(review.get("_workflow_started_at", review["submitted_at"]).replace("Z", "+00:00")).replace(microsecond=0)
            if not switched or switched[0] != "codex" or switched[1] <= started:
                return False, "Waiting for Claude review to finish"
    for kind, (provider, timestamp) in requests.items():
        if provider == "claude":
            fulfilled = claude_completed is not None and claude_completed > timestamp
        else:
            fulfilled = codex_approved and kind in completions and completions[kind] > timestamp
        if not fulfilled:
            return False, f"Waiting for requested {provider.title()} {kind} review to finish"
    if not completed:
        return False, "Waiting for current Claude/Codex approval or a qualified review"
    if pr.get("mergeable") is not True or not pr.get("merge_commit_sha"):
        return False, "Waiting for a mergeable PR and its test merge commit"
    return True, "Review complete; no outstanding findings"


def matches(pr, head, base, merge):
    return (pr["head"]["sha"], pr["base"]["sha"], pr.get("merge_commit_sha")) == (head, base, merge)


def builds_passed(results):
    return set(results) == {"android", "presets", "docs"} and all(value == "success" for value in results.values())


class GitHub:
    def __init__(self, repo):
        self.repo = repo

    def request(self, endpoint, data=None, paginate=False):
        command = ["gh", "api", endpoint]
        if data is not None:
            command += ["--method", "POST", "--input", "-"]
        if paginate:
            command += ["--paginate", "--slurp"]
        try:
            result = subprocess.run(command, input=json.dumps(data) if data is not None else None,
                                    text=True, capture_output=True, check=True)
        except subprocess.CalledProcessError as err:
            stderr = (err.stderr or "").strip()
            stdout = (err.stdout or "").strip()
            raise RuntimeError(f"gh api failed with exit {err.returncode}: {stderr or stdout}") from err
        return json.loads(result.stdout) if result.stdout.strip() else None

    def get(self, path):
        return self.request(f"repos/{self.repo}/{path}")

    def post(self, path, data):
        return self.request(f"repos/{self.repo}/{path}", data)

    def pages(self, path, key=None):
        pages = self.request(f"repos/{self.repo}/{path}", paginate=True)
        return [item for page in pages for item in (page[key] if key else page)]

    def resolve_review_commit(self, written):
        if not re.fullmatch(r"[0-9a-f]{7,40}", written):
            return None
        if len(written) == 40:
            return written
        # The commits endpoint also accepts ref names. Reject hex-named refs so
        # it resolves a commit abbreviation rather than a mutable branch/tag alias.
        for namespace in ("heads", "tags"):
            refs = self.get(f"git/matching-refs/{namespace}/{written}")
            if any(ref["ref"] == f"refs/{namespace}/{written}" for ref in refs):
                return None
        resolved = self.get(f"commits/{written}")["sha"]
        if not isinstance(resolved, str) or not re.fullmatch(r"[0-9a-f]{40}", resolved) or not resolved.startswith(written):
            raise RuntimeError("GitHub did not resolve the reviewed commit abbreviation")
        return resolved

    def snapshot(self, number):
        pr = self.get(f"pulls/{number}")
        # PR base.sha can lag behind the actual branch ref after a main push.
        pr["base"]["sha"] = self.get("git/ref/heads/main")["object"]["sha"]
        reviews = self.pages(f"pulls/{number}/reviews?per_page=100")
        comments = self.pages(f"issues/{number}/comments?per_page=100")
        claude_permissions = {}
        for comment in comments:
            if not re.fullmatch(r"@claude\s+review", (comment.get("body") or "").strip(), re.I):
                continue
            user = comment["user"]
            if user.get("type") != "User":
                comment["_claude_authorized"] = False
                continue
            if user["login"] not in claude_permissions:
                claude_permissions[user["login"]] = writer(self, user["login"])
            comment["_claude_authorized"] = claude_permissions[user["login"]]
        reactions = self.pages(f"issues/{number}/reactions?per_page=100")
        claude_workflows = {}
        for review in reviews:
            receipt = claude_result(review)
            if not receipt or review["commit_id"] != pr["head"]["sha"]:
                continue
            if receipt[1] not in claude_workflows:
                claude_workflows[receipt[1]] = self.get(f"actions/runs/{receipt[1]}")
            run = claude_workflows[receipt[1]]
            target = (run.get("event") == "pull_request_target"
                      and any(item["number"] == number and item["base"]["ref"] == "main"
                              and item["head"]["sha"] == review["commit_id"]
                              for item in run.get("pull_requests", [])))
            manual = run.get("event") in {"issue_comment", "workflow_dispatch"} and run.get("head_branch") == "main"
            review["_workflow_active"] = run["status"] != "completed"
            review["_workflow_started_at"] = run["created_at"]
            review["_workflow_event"] = run.get("event")
            submitted = datetime.fromisoformat(review["submitted_at"].replace("Z", "+00:00"))
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            updated = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
            review["_workflow_verified"] = (run.get("path", "").split("@")[0] == ".github/workflows/claude-code-review.yml"
                                            and (target or manual) and created <= submitted
                                            and (review["_workflow_active"] or submitted <= updated))
            if receipt[0] == "APPROVED":
                started = any(claude_result(item) == ("RUNNING", receipt[1])
                              and item["user"]["login"] == "github-actions[bot]"
                              and item["commit_id"] == review["commit_id"]
                              and created <= datetime.fromisoformat(item["submitted_at"].replace("Z", "+00:00")) <= submitted
                              for item in reviews)
                review["_workflow_verified"] = (review["_workflow_verified"] and started
                                                and run.get("conclusion") == "success" and not review["_workflow_active"])
        resolved = {}
        for record in comments:
            if record["user"]["login"] != CODEX or record["user"].get("type") != "Bot":
                continue
            written = [token for token in re.findall(r"`([0-9a-f]{7,40})`", record.get("body") or "")
                       if pr["head"]["sha"].startswith(token)]
            for token in written:
                if token not in resolved:
                    resolved[token] = self.resolve_review_commit(token)
            record["_reviewed_commits"] = {token: resolved[token] for token in written}
        owner, name = self.repo.split("/")
        threads, cursor = [], None
        while True:
            data = self.request("graphql", dict(query="""
              query($owner:String!, $name:String!, $number:Int!, $cursor:String) {
                repository(owner:$owner,name:$name) {
                  pullRequest(number:$number) {
                    reviewThreads(first:100,after:$cursor) {
                      nodes { isResolved }
                      pageInfo { hasNextPage endCursor }
                    }
                  }
                }
              }""", variables=dict(owner=owner, name=name, number=number, cursor=cursor)))
            if data.get("errors"):
                raise RuntimeError(f"Cannot read review threads: {data['errors']}")
            connection = data["data"]["repository"]["pullRequest"]["reviewThreads"]
            threads.extend(connection["nodes"])
            if not connection["pageInfo"]["hasNextPage"]:
                break
            cursor = connection["pageInfo"]["endCursor"]
        # Re-read to reject a snapshot collected across a push or base change.
        current = self.get(f"pulls/{number}")
        current["base"]["sha"] = self.get("git/ref/heads/main")["object"]["sha"]
        if not matches(current, pr["head"]["sha"], pr["base"]["sha"], pr.get("merge_commit_sha")):
            return current, (False, "PR changed while reading reviews; recheck required")
        ready, reason = eligibility(current, reviews, comments, threads, reactions)
        if ready:
            parents = self.get(f"git/commits/{current['merge_commit_sha']}")["parents"]
            if [parent["sha"] for parent in parents] != [current["base"]["sha"], current["head"]["sha"]]:
                return current, (False, "Waiting for the test merge of current head and main")
        return current, (ready, reason)

    def status(self, head, state, description, url=None):
        previous = next((s for s in self.pages(f"commits/{head}/statuses?per_page=100")
                         if s["context"] == CONTEXT), None)
        if previous and (previous["state"], previous["description"]) == (state, description):
            return
        payload = dict(state=state, context=CONTEXT, description=description[:140])
        if url:
            payload["target_url"] = url
        self.post(f"statuses/{head}", payload)


def title(pr):
    return f"Reviewed PR #{pr['number']} @ {pr['head']['sha']} + {pr['base']['sha']}"


def reconcile(api, number, retry=False):
    pr, (ready, reason) = api.snapshot(number)
    try:
        all_runs = [run for run in api.pages(f"actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=100", "workflow_runs")
                    if run["head_branch"] == "main" and run["display_title"].startswith(f"Reviewed PR #{number} @ ")]
    except (RuntimeError, subprocess.CalledProcessError, KeyError, ValueError, TypeError) as error:
        print(f"Unable to list workflow runs for {WORKFLOW}; continuing without run history: {error}", file=sys.stderr)
        all_runs = []
    for run in all_runs:
        if run["status"] != "completed" and (run["display_title"] != title(pr) or pr["state"] != "open"):
            api.post(f"actions/runs/{run['id']}/cancel", {})
    if pr["state"] != "open" or pr["base"]["ref"] != "main":
        return
    head = pr["head"]["sha"]
    runs = [run for run in all_runs if run["display_title"] == title(pr)]
    runs.sort(key=lambda run: run["id"], reverse=True)
    active = [run for run in runs if run["status"] != "completed"]
    if not ready:
        api.status(head, "pending", reason)
        for run in active:
            api.post(f"actions/runs/{run['id']}/cancel", {})
        return
    if active:
        api.status(head, "pending", "Reviewed; full validation is running", active[0]["html_url"])
        return
    previous = next((s for s in api.pages(f"commits/{head}/statuses?per_page=100") if s["context"] == CONTEXT), None)
    passed = f"Passed all builds against main {pr['base']['sha']}"
    if previous and previous["state"] == "success" and previous["description"] == passed:
        return
    # Success without a still-valid passing status needs fresh validation after
    # review eligibility recovers. Actual failures require an explicit retry.
    if runs and not retry:
        last = runs[0]
        if last["conclusion"] not in {"success", "cancelled", "skipped"}:
            api.status(head, "failure", "Validation did not pass; fix the PR or rerun validation", last["html_url"])
            return
    # Dispatch reservations prevent duplicate runs while GitHub queues a new workflow.
    reservation = f"Queued builds against main {pr['base']['sha']}"
    if previous and previous["state"] == "pending" and previous["description"] == reservation:
        created = datetime.fromisoformat(previous["created_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - created < timedelta(minutes=20):
            return
    api.status(head, "pending", reservation)
    api.post(f"actions/workflows/{WORKFLOW}/dispatches", dict(ref="main", inputs=dict(
        pr_number=str(number), head_sha=head, base_sha=pr["base"]["sha"], merge_sha=pr["merge_commit_sha"])))


def snapshot_safely(api, number, expected_head=None):
    try:
        return api.snapshot(number)
    except (RuntimeError, subprocess.CalledProcessError, KeyError, ValueError, TypeError):
        pr = api.get(f"pulls/{number}")
        if (pr["state"] == "open" and pr["base"]["ref"] == "main"
                and (expected_head is None or pr["head"]["sha"] == expected_head)):
            api.status(pr["head"]["sha"], "pending", "Unable to verify review state; recheck required")
        raise


def reconcile_safely(api, numbers, retry=False):
    errors = []
    for number in numbers:
        try:
            reconcile(api, number, retry)
        except (RuntimeError, subprocess.CalledProcessError, KeyError, ValueError, TypeError) as error:
            # Fail closed if review reads fail after a previously successful build.
            try:
                pr = api.get(f"pulls/{number}")
                if pr["state"] == "open" and pr["base"]["ref"] == "main":
                    api.status(pr["head"]["sha"], "pending", "Unable to verify review state; recheck required")
            except (RuntimeError, subprocess.CalledProcessError, KeyError, ValueError, TypeError) as status_error:
                errors.append(f"PR #{number}: cannot invalidate status: {status_error}")
            errors.append(f"PR #{number}: {error}")
    if errors:
        raise RuntimeError("; ".join(errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["reconcile", "preflight", "finish", "inspect"])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), required=not os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int, default=0)
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()
    api = GitHub(args.repo)
    if args.mode == "inspect":
        if args.pr <= 0:
            raise ValueError("A positive PR number is required")
        pr, (ready, reason) = api.snapshot(args.pr)
        print(json.dumps(dict(pr=args.pr, head=pr["head"]["sha"], base=pr["base"]["sha"],
                              merge=pr.get("merge_commit_sha"), eligible=ready, reason=reason)))
        return
    if args.mode == "reconcile":
        numbers = [args.pr] if args.pr else [pr["number"] for pr in api.pages("pulls?state=open&base=main&per_page=100")]
        reconcile_safely(api, numbers, args.retry)
        return
    head, base, merge = (os.environ[name] for name in ["PR_HEAD", "PR_BASE", "PR_MERGE"])
    if any(not re.fullmatch(r"[0-9a-f]{40}", sha) for sha in [head, base, merge]):
        raise ValueError("Full commit SHAs are required")
    if args.mode == "preflight":
        pr, (ready, reason) = snapshot_safely(api, args.pr, head)
        ready = ready and matches(pr, head, base, merge)
        if not ready:
            raise RuntimeError(f"PR is not eligible or its revision changed: {reason}")
        api.status(head, "pending", "Preflight verified; full validation is starting")
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            output.write(f"merge_sha={merge}\n")
        return
    results = json.loads(os.environ["BUILD_RESULTS"])
    preflight = os.environ.get("PREFLIGHT_RESULT", "success")
    url = f"https://github.com/{args.repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    finish_validation(api, args.pr, head, base, merge, results, preflight, url)


def finish_validation(api, number, head, base, merge, results, preflight, url):
    no_builds_started = (set(results) == {"android", "presets", "docs"}
                         and all(value == "skipped" for value in results.values()))
    retryable = builds_passed(results) or (preflight != "success" and no_builds_started)
    try:
        pr, (ready, _) = snapshot_safely(api, number, head)
        # Never mutate the new head's status from an old validation run.
        if pr["head"]["sha"] != head:
            return
        ready = ready and matches(pr, head, base, merge)
        if preflight != "success" and no_builds_started:
            api.status(head, "pending", "Preflight did not start builds; fresh validation required", url)
        elif not ready:
            api.status(head, "pending", "Review or base changed; fresh validation required", url)
        elif builds_passed(results):
            api.status(head, "success", f"Passed all builds against main {base}", url)
        else:
            api.status(head, "failure", "Validation failed, was cancelled, or skipped a required build", url)
            raise RuntimeError(f"Required builds did not pass: {results}")
    except (RuntimeError, subprocess.CalledProcessError, KeyError, ValueError, TypeError) as error:
        if not retryable:
            raise
        # A reporter outage must not turn successful builds into an actual build
        # failure. Return success while leaving the required gate pending; the
        # controller rechecks eligibility before dispatching fresh validation.
        try:
            api.status(head, "pending", "Final reporting unavailable; fresh validation required", url)
        except (RuntimeError, subprocess.CalledProcessError, KeyError, ValueError, TypeError) as status_error:
            print(f"Cannot mark reporter outage pending: {status_error}", file=sys.stderr)
        print(f"Final reporting will be retried: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
