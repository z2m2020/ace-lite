# `.aceignore` Cookbook

`.aceignore` uses gitignore-like glob patterns (matched against repo-relative POSIX paths) to exclude low-signal files from indexing.

## Go (protobuf + generated + vendor)

```gitignore
*.pb.go
*_generated.go
*_gen.go
mock_*.go
*_mock.go
vendor/
testdata/
pkg/contract/
```

## Node / TypeScript (deps + build)

```gitignore
node_modules/
dist/
build/
.next/
.turbo/
coverage/
```

## Solidity Monorepo (Foundry or hybrid Hardhat/Foundry)

```gitignore
artifacts/
broadcast/
cache/
coverage/
out/
typechain/
lib/**
!lib/**/*.sol
node_modules/**
!node_modules/**/*.sol
```

## Java (build + deps)

```gitignore
target/
.gradle/
build/
```

## Rust (build)

```gitignore
target/
```

## Python (venv + caches)

```gitignore
.venv/
venv/
__pycache__/
.pytest_cache/
```
