# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Email **partners@noderings.com** with:

- a description of the issue and its impact
- steps to reproduce, or a proof of concept
- the plugin version and the Rundeck version

We acknowledge reports within three working days and keep you updated until the issue is fixed. Credit is given in the release notes unless you ask us not to.

## Supported versions

Security fixes are made for the latest minor release.

## Handling credentials

The plugin reads the NodeRings service account token from Rundeck Key Storage, so it never appears in job definitions or project settings. Restrict who can read that Key Storage path with Rundeck's access control policies, and give the service account the narrowest NodeRings role that covers what the jobs do. Root passwords for new VMs are read from Key Storage too. The SSH key setting stores only a Key Storage path; Rundeck's SSH executor reads the key itself.
