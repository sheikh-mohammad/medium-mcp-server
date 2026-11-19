# Security Policy

## Supported versions

The project is pre-release. Security fixes are applied to the latest code on `main`.

| Version | Supported |
| --- | --- |
| `main` (unreleased) | Yes |
| Older snapshots | No |

## Reporting a vulnerability

Please report security issues privately:

1. Open the repository's **Security** tab on GitHub.
2. Choose **Report a vulnerability** and submit the details.
3. Include affected code or commits, reproduction steps, and the potential impact.

Do **not** open a public issue for an unpatched vulnerability, and do not include real Medium access tokens in a report.

You should receive an acknowledgement within seven days. We will keep you informed as the issue is investigated and a fix is prepared, and will credit you in the release notes if you wish.

## Handling your Medium token

- Store your Medium integration token in an environment variable or your MCP host's secret store — never in source code or committed configuration.
- Use a token with only the permissions the server needs.
- Revoke and rotate the token immediately if you believe it was exposed.
- Review tool calls before allowing your AI assistant to publish content; the server acts with the permissions of the account whose token it uses.

## Responsible disclosure

Please give maintainers a reasonable opportunity to release a fix before publicly discussing a vulnerability. Once a fix is available, we will publish details in the [changelog](CHANGELOG.md).
