# cache-status（查看缓存状态）

请指导用户查看本仓库的本地缓存状态（按 dev/prod 隔离），并解释输出字段含义。

命令：

```bash
python scripts/cache_status.py --env dev
python scripts/cache_status.py --env prod
```

说明：

- 缓存目录：`cache/<env>/`
- 缓存由 `scripts/cache_refresh.py` 生成/刷新
