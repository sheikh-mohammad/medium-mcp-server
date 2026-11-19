# Contributing to Medium MCP Server

Thanks for your interest in improving this project. The server is still in its early stages, so there is plenty of room for help with documentation, client setup guides, tests, and implementation.

## Before you start

- Read the [README](README.md) for the project's goals and status.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Search existing issues before opening a new one.
- For a large change, open an issue first so we can agree on the approach.
- Never include Medium tokens or other credentials in issues, pull requests, or commits.

## Ways to contribute

- **Bug reports** — describe what happened, your MCP host, and how to reproduce it.
- **Feature proposals** — explain the use case and how it fits the server's scope.
- **Client guides** — document setup for Claude Desktop, Claude Code, ChatGPT connectors, Gemini, Cursor, VS Code, terminal agents, and other MCP hosts.
- **Documentation** — improve the README, add examples, and clarify tool behaviour.
- **Code** — help with the Python server, API client, packaging, and tests as implementation proceeds.

## Development workflow

1. Fork the repository and clone your fork.
2. Create a focused branch, for example `docs/claude-desktop-setup`.
3. Work in a Python virtual environment (Python 3.11+). Install dependencies from the project's dependency files once they are added.
4. Keep changes focused and update documentation when behaviour changes.
5. Run the available tests and linters before opening a pull request. Exact commands will be added here as the project tooling is established.
6. Push your branch and open a pull request against `main`.

## Pull request guidelines

- Link the related issue in the description.
- Explain **what** changed and **why**.
- Keep the diff small and reviewable; split unrelated changes into separate PRs.
- Confirm that no secrets, tokens, or personal data are included.
- Respond to review feedback — stalled PRs may be closed after a period of inactivity.

## Commit messages

Use a short imperative subject line and, when helpful, a body explaining the reasoning:

```text
Add Claude Desktop setup guide

Explains stdio configuration and where to store the Medium token.
```

## Security issues

Do not open a public issue for a security problem. Follow [SECURITY.md](SECURITY.md) instead.

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
