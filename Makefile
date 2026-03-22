.PHONY: lint check fix build publish clean test dev install install-hooks

# 默认任务：运行所有质量检查
check: lint 

# 巅峰一键安装流程 (Python 隔离环境)
install:
	@echo "🛠️  Initializing isolated Python virtual environment..."
	@uv venv
	@echo "📦 Syncing dependencies (powered by UV)..."
	@uv sync --all-extras
	@echo "✅ Setup complete! You can now run 'make test' or 'make dev'"

# 静态分析 (Lint & Format)
fix:
	uv run ruff check . --fix
	uv run ruff format .

# 运行静态分析（Ruff）和类型检查（MyPy）
lint:
	@echo "🔍 Running Ruff checks..."
	uv run ruff check .
	@echo "🔍 Running MyPy checks..."
	uv run mypy src/agent_tools

# 启动本地开发 MCP 服务器
dev:
	uv run src/agent_tools/server.py

# 清理构建缓存与隔离环境
clean:
	@echo "🧹 Cleaning up environments and artifacts..."
	rm -rf dist/ build/ *.egg-info .venv .mypy_cache .ruff_cache .pytest_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} +

# 构建与发布
build: clean
	uv run python -m build

publish: build
	uv run twine upload dist/*

# 本地运行测试
test:
	uv run pytest tests/

# 安装项目 Git 钩子 (软链接)
install-hooks:
	chmod +x scripts/git-hooks/pre-commit
	ln -sf ../../scripts/git-hooks/pre-commit .git/hooks/pre-commit
	@echo "✅ Project hooks installed successfully (Local -> .git/hooks Symlink)"
