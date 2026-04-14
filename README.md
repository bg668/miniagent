# paimonsdk

`paimonsdk` 是一个偏底层的 Python Agent Runtime SDK，用来构建可自定义的 agent loop。

仓库采用标准的 Python `src` 布局，适合被其他项目直接安装和依赖：

- `src/paimonsdk/`：正式发布的包代码
- `tests/`：SDK 回归测试
- `examples/`：最小示例与示例配置
- `scripts/`：本地 smoke 检查脚本
- `docs/`：功能说明、开发者参考与设计文档

推荐把它作为“内部包”提供给其他项目，而不是手工拷贝 `src/` 目录。

## 给其他项目使用

### 方式 1：本地路径 editable 安装

适合同机开发、联调多个项目：

```bash
pip install -e /path/to/paimonsdk
```

### 方式 2：Git 依赖

适合团队内部共享，且不发布到公开 PyPI：

```txt
paimonsdk @ git+ssh://git@your-git-server/your-team/paimonsdk.git@main
```

### 方式 3：安装构建产物

适合发固定版本给其他项目或部署环境：

```bash
uv build
pip install dist/paimonsdk-0.1.0-py3-none-any.whl
```

## 本仓库开发

常用命令：

```bash
uv run pytest -q
uv build
uv sync --extra examples
uv run python examples/chat_demo.py
```

示例程序依赖 `python-dotenv`，请先安装 `examples` 可选依赖，并将 [examples/.env.example](examples/.env.example) 复制为 `examples/.env` 后填入 `OPENAI_API_KEY`。

文档入口见 [docs/README.md](docs/README.md)。
