# PostgreSQL 目录库与对象存储升级手册

本手册定义应用侧已经实现的升级边界。基础设施创建、数据库绑定、备份、恢复和生产切换必须继续通过远程 GitOps 执行；未获得明确授权时，不运行这些动作，也不在本机启动 Docker。

## 1. 数据边界

- PostgreSQL 保存身份、版本关系、采集运行、游标和处理队列。
- S3 兼容对象存储保存不可变原始正文及首次采集元数据；配置备份桶时，每次写入同时落主桶与备份桶。
- `raw_objects.body_path` 始终保存对象键，现有 `objects/<前缀>/<标识>.body` 不变。
- SQLite 和现有 `objects/` 在迁移及观察期内保持原样，是应用回滚源；升级代码不会删除它们。
- API 与采集器必须同时使用同一组目录库和对象存储配置，不能混合写入。

## 2. 后端配置

默认配置仍是现有基线，部署新代码不会自动切换或迁移：

```text
QSOU_CATALOG_BACKEND=sqlite
QSOU_OBJECT_STORAGE_BACKEND=file
```

PostgreSQL 与 S3 兼容对象存储准备好后，迁移进程需要以下配置：

```text
QSOU_CATALOG_BACKEND=postgres
DATABASE_URL=postgresql://...
QSOU_OBJECT_STORAGE_BACKEND=s3
QSOU_OBJECT_STORAGE_ENDPOINT=https://...
QSOU_OBJECT_STORAGE_REGION=us-east-1
QSOU_OBJECT_STORAGE_BUCKET=...
QSOU_OBJECT_BACKUP_BUCKET=...
QSOU_OBJECT_STORAGE_ACCESS_KEY=...
QSOU_OBJECT_STORAGE_SECRET_KEY=...
```

凭据只进入远程部署环境，不写入仓库、发布包或命令输出。

## 3. 迁移顺序

在 API 与采集器仍使用 SQLite/file 时，可以从带有目标后端配置的单次远程任务运行可重复回填：

```bash
python -m qsou_data.migrate backfill
```

回填会执行以下硬校验，任何一项失败都会使目录事务回滚：

1. 逐表幂等 upsert，并比较源/目标行数。
2. 按主键稳定排序后比较每张表的 SHA-256 摘要。
3. 逐个校验旧文件、目标对象和备份对象的正文 SHA-256。
4. 写入 `schema_migrations` 与 `migration_audits`，记录阶段、数量、摘要和结果。

目录库统一写入边界会把 PostgreSQL 不接受的文本 NUL 字节规范化为 Unicode
替代字符；SQLite 新写入、PostgreSQL 新写入、历史迁移和摘要校验使用同一规则。
迁移结果中的 `text_nul_bytes_normalized` 记录本次规范化数量，避免静默处理。

线上后端仍为 SQLite 时，回填失败会输出
`QSOU_DATABASE_MIGRATION_RESULT` 的 `status=failed` 结果并继续启动 API；自动发布不会
因为目标库或历史数据异常而中断现有服务。最终增量和生产验收仍然失败关闭，未通过时
不能切换到 PostgreSQL。

切换前停止 SQLite 写入，并只对最终增量任务设置写入冻结确认：

```bash
QSOU_SQLITE_WRITES_FROZEN=true python -m qsou_data.migrate final
```

最终增量还会检查运行期间 SQLite `data_version`；发现其他连接仍在写入时失败，不能进入切换。

## 4. 切换与回滚

只有回填和最终增量都得到 `status=verified` 后，才允许通过一次远程 GitOps 变更同时把 API 与采集器切到 `postgres/s3`。不得只切其中一个服务。

回滚不执行反向覆盖或删除：把 API 与采集器同时恢复为 `sqlite/file` 配置并重新发布，继续使用未改动的旧目录。切换前可在不依赖 PostgreSQL 可用性的情况下检查回滚源：

```bash
QSOU_DATA_ROOT=/var/lib/qsou python -m qsou_data.migrate rollback-check
```

只有输出 `status=rollback_ready` 且旧目录完整性、对象数量和正文哈希全部通过，回滚路径才成立。

## 5. 备份恢复与生产验收

数据库备份与恢复必须由 GitOps 管理的 PostgreSQL 能力完成，并恢复到隔离的验证目标；对象恢复同样使用新的空主桶或隔离前缀，不能覆盖现有证据。恢复后的应用验收至少包含：

1. PostgreSQL 可连接，外键关系无孤儿记录。
2. 主对象桶与备份桶都能读取，正文哈希与目录一致。
3. 迁移审计中的逐表行数和摘要与恢复目标一致。
4. API 健康检查、搜索、证据正文读取和 JSONL 导出成功。
5. 采集器新增一条真实证据，目录、主桶和备份桶均保存且可读取。
6. 在 2C/4G 总资源上观察 API、Web、采集器和存储连接，无重启、积压或错误。

恢复目标的目录关系、逐表摘要、主对象和备份对象可先运行统一硬校验：

```bash
python -m qsou_data.verify --require-backup
```

命令只有在所有孤儿记录为 0、每个正文对象与目录哈希一致且备份桶也逐一通过时，才输出 `status=verified`。

完成隔离恢复验证后再销毁临时目标；销毁属于基础设施动作，必须单独确认准确目标并遵守 GitOps 治理。
