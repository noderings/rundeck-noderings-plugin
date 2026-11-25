# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-25

### Added

- Node source **NodeRings**: the organization's VMs as Rundeck nodes, with tags,
  `noderings-*` attributes and an optional SSH key from Key Storage.
- Workflow steps **Create VM** (idempotent order, outputs the IP as job data), **Power**,
  **Delete VM** and **DNS record**.
- The API token is read from Rundeck Key Storage.
