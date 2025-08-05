# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Initial project structure alignment and refactoring.
- Implemented custom FastAPI RPC Gateway for database communication, replacing `SimpleSupabaseGateway`.
- Documented lessons learned from RPC Gateway implementation and troubleshooting (`docs/archived/Læringsnotat Implementering av RPC Gateway.md`).

### Changed
- Replaced `fastmcp` library with custom FastAPI implementation for RPC Gateway.
- Updated import paths across the codebase to reflect new directory structure.

### Fixed
- Resolved `ConnectError` by ensuring RPC Gateway is running.
