# 变更说明

## 2024-01-21: 简化后端设计

### 变更内容

**移除的功能：**
- ❌ 查询词扩展（QueryExpander）
- ❌ 中文到英文的自动转换
- ❌ 预定义术语映射表

**变更原因：**
后端应该专注于执行搜索，查询词扩展由调用者（脚本/大模型）负责。这样可以：
1. 后端更简单，职责单一
2. 调用者可以更灵活地控制查询策略
3. 大模型本身就擅长生成同义词和扩展查询

### 新的 API 设计

**旧方式（后端扩展）：**
```bash
python main.py --keywords="硅基负极"
# 后端内部扩展为: ["silicon anode", "Si anode", ...]
```

**新方式（调用者提供）：**
```bash
python main.py \
  --queries="silicon anode" \
  --queries="Si anode" \
  --queries="Si-C anode"
# 后端直接执行这些查询
```

### 参数变更

| 旧参数 | 新参数 | 说明 |
|--------|--------|------|
| `--keywords` | `--queries` | 现在接受列表，可多次指定 |
| (无) | `--providers` | 可选择数据源（可选） |

### 调用示例

**Python 脚本：**
```python
# 调用者自己扩展查询词（可以使用 LLM）
expanded_queries = expand_with_llm("硅基负极")
# -> ["silicon anode", "Si anode", "Si-C anode", ...]

# 直接传递给后端
result = search_papers(
    queries=expanded_queries,
    start_date="2020-01-01"
)
```

### 文件变更

**修改：**
- `src/paper_router/main.py` - 移除 QueryExpander，改为接收查询列表

**更新文档：**
- `API_USAGE.md` - 更新 API 文档
- `BACKEND_README.md` - 更新快速开始
- `example_usage.py` - 更新示例脚本
- `test_cli.py` - 更新测试（移除 query expansion 测试）

### 优势

1. **职责分离**：后端只执行，调用者决定策略
2. **更灵活**：调用者可以用 LLM、规则、数据库等各种方式扩展查询
3. **更简单**：后端代码减少约 50 行，更容易维护
4. **更清晰**：接口语义明确，输入什么就搜索什么
