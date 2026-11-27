# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.1](https://github.com/noderings/rundeck-noderings-plugin/compare/v0.2.0...v0.2.1) (2026-11-27)


### Documentation

* link the official Go SDK in the README ([#5](https://github.com/noderings/rundeck-noderings-plugin/issues/5)) ([7142064](https://github.com/noderings/rundeck-noderings-plugin/commit/71420648ffa9ad3538f3f06abfdb60583140711c))

## [0.2.0](https://github.com/noderings/rundeck-noderings-plugin/compare/v0.1.0...v0.2.0) (2026-11-26)


### Features

* choose the provider when creating a VM ([#3](https://github.com/noderings/rundeck-noderings-plugin/issues/3)) ([4757807](https://github.com/noderings/rundeck-noderings-plugin/commit/4757807fe2b490116dd49d56db707cd24ceb2613))

## [Unreleased]

## [0.1.0] - 2026-11-25

### Added

- Node source **NodeRings**: the organization's VMs as Rundeck nodes, with tags,
  `noderings-*` attributes and an optional SSH key from Key Storage.
- Workflow steps **Create VM** (idempotent order, outputs the IP as job data), **Power**,
  **Delete VM** and **DNS record**.
- The API token is read from Rundeck Key Storage.
