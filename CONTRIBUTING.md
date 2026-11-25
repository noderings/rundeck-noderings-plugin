# Contributing

Thanks for helping improve the NodeRings plugin for Rundeck.

1. Open an issue describing the bug or change before large pull requests.
2. Fork the repository and create a topic branch.
3. Run `pytest` and `ruff check . && ruff format --check .`; both must pass. The unit tests
   use the in-memory API in `tests/fakeapi.py`, so they need no token.
4. Add tests for new behaviour. A new setting goes in `plugin.yaml` and in the script that
   reads it; `tests/test_plugin_yaml.py` checks they match.
5. For changes that reach the API or Rundeck, run `tests/e2e/rundeck_e2e.py` (see the
   README); it orders a billed VM and removes everything afterwards.
6. Use [Conventional Commits](https://www.conventionalcommits.org/) and sign off each commit
   (`git commit -s`) to certify the [Developer Certificate of Origin](https://developercertificate.org/).

The `contents/nr_client.py`, `nr_compute.py`, `nr_dns.py` and `nr_marketplace.py` files are
the NodeRings API client shared with the NodeRings Salt extension and Libcloud drivers.
Please describe fixes to them in an issue so they are made everywhere.

Please report security problems privately as described in [SECURITY.md](SECURITY.md).
