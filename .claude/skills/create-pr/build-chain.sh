#!/usr/bin/env bash
# build-chain.sh
# Walks from the current branch up to main, outputting the branch chain as JSON.
# Each entry has {branch, base} where base is what the branch should be rebased onto.
#
# Output (stdout): JSON array, e.g.:
#   [{"branch":"feature-a","base":"main"},{"branch":"feature-b","base":"feature-a"}]
#
# Exit codes:
#   0 - success
#   1 - error (on main, or could not determine chain)
#
# Optional env var PR_BASE_MAP: JSON object mapping branch -> base, precomputed
# by the caller via mcp__github__list_pull_requests (head filter) since this
# script has no GitHub API access of its own. Falls back to git tracking
# config, then "main".

set -euo pipefail

pr_base_map="${PR_BASE_MAP:-{}}"

current_branch=$(git branch --show-current)

if [ "$current_branch" = "main" ]; then
    echo '{"error":"on_main","message":"Currently on main branch"}' >&2
    exit 1
fi

chain='[]'
branch="$current_branch"

while [ "$branch" != "main" ]; do
    # Try to get base from the precomputed PR base map
    base=$(echo "$pr_base_map" | jq -r --arg b "$branch" '.[$b] // empty')

    # Fallback to git tracking config
    if [ -z "$base" ]; then
        tracking=$(git config "branch.$branch.merge" 2>/dev/null || true)
        if [ -n "$tracking" ]; then
            base=$(echo "$tracking" | sed 's|refs/heads/||')
        fi
    fi

    # Fallback to main
    if [ -z "$base" ]; then
        base="main"
    fi

    # Prepend to chain (we want closest-to-main first)
    chain=$(echo "$chain" | jq --arg b "$branch" --arg base "$base" '. = [{"branch":$b,"base":$base}] + .')

    if [ "$base" = "main" ]; then
        break
    fi

    # Check we're not in a loop
    if echo "$chain" | jq -e --arg b "$base" '[.[].branch] | index($b) != null' > /dev/null 2>&1; then
        echo "{\"error\":\"loop\",\"message\":\"Cycle detected at branch $base\"}" >&2
        exit 1
    fi

    branch="$base"
done

echo "$chain"
