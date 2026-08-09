# PostgreSQL 目录库与对象存储升级手册

本手册定义应用侧已经实现的升级边界。基础设施创建、数据库绑定、备份、恢复和生产切换必须继续通过远程 GitOps 执行；未获得明确授权时，不运行这些动作，也不在本机启动 Docker。

## 1. 数据边界

- PostgreSQL 保存身份、版本关系、采集运行、游标和处理队列。
- S3 兼容对象存储保存不可变原始正文及首次采集元数据；配置备份桶时，每次写入同时落主桶与备份桶。
- `raw_objects.body_path` 始终保存对象键，现有 `objects/<前缀>/<标识>.body` 不变。
- PostgreSQL 是 API、采集器和索引器唯一允许使用的运行目录库。
- 历史目录迁移已经完成；运行制品不再包含旧目录迁移器、文件探测或回退开关。
- API、采集器和索引器必须使用同一个 PostgreSQL 与对象存储配置，不能混合写入。

## 2. 后端配置

运行配置必须提供 PostgreSQL：

```text
DATABASE_URL=postgresql://...
QSOU_OBJECT_STORAGE_BACKEND=file
```

切换 S3 兼容对象存储时再增加：

```text
QSOU_OBJECT_STORAGE_BACKEND=s3
QSOU_OBJECT_STORAGE_ENDPOINT=https://...
QSOU_OBJECT_STORAGE_REGION=us-east-1
QSOU_OBJECT_STORAGE_BUCKET=...
QSOU_OBJECT_BACKUP_BUCKET=...
QSOU_OBJECT_STORAGE_ACCESS_KEY=...
QSOU_OBJECT_STORAGE_SECRET_KEY=...
```

凭据只进入远程部署环境，不写入仓库、发布包或命令输出。

## 3. 迁移入口终态

1. 通过 GitOps 数据库绑定为迁移服务注入 `DATABASE_URL`。
2. 从终态成功的 API 制品运行受治理的 `/app/deploy/database-migrate`，不得把迁移塞进 API 启动命令。
3. 入口执行 `alembic upgrade head`，保证 PostgreSQL schema 到达当前版本。
4. 对象后端为 S3 时，入口随后执行 `migrate_file_objects_to_s3.py`，逐个核对本地源、主桶、备份桶三方哈希；已完成的迁移根据 PostgreSQL 迁移标记直接跳过。
5. 运行 `python -m qsou_data.verify --require-backup`，核对外键孤儿、主备对象哈希、目录摘要和迁移版本。

## 4. 切换与回滚

只有迁移与统一验收都得到 `status=verified` 后，才允许恢复 API、采集器和索引器写入。Elasticsearch 首次同步完成前，API 健康检查保持不就绪。

采集器和索引器在制品内核对 Alembic 版本，以及 S3 模式下的对象迁移标记；标记不齐时只报告等待状态，不发起采集、目录写入或索引重建。该门禁不执行迁移，迁移仍由独立的受治理入口完成。

API 在迁移标记齐全前拒绝除登录外的写入和搜索 POST，请求只得到“数据升级正在完成”的 503，不暴露迁移实现细节；只读健康探针和受治理迁移入口不受影响。

GitOps 容器探针使用 `/live` 判断 API 进程是否已启动，使制品发布可以先得到终态；生产就绪与验收始终使用 `/health`，后者在迁移或 Elasticsearch 全量同步完成前返回 503。两者不得互换。

回滚不再切回 SQLite。回滚单元是切换前 PostgreSQL 备份、隔离恢复验证通过的对象备份，以及对应的上一版应用制品；恢复后仍然运行 PostgreSQL-only 架构。

## 5. 备份恢复与生产验收

数据库备份与恢复必须由 GitOps 管理的 PostgreSQL 能力完成，并恢复到隔离的验证目标；对象恢复同样使用新的空主桶或隔离前缀，不能覆盖现有证据。恢复后的应用验收至少包含：

1. PostgreSQL 可连接，外键关系无孤儿记录。
2. 主对象桶与备份桶都能读取，正文哈希与目录一致。
3. 迁移审计中的逐表行数和摘要与恢复目标一致。
4. Elasticsearch 可从恢复后的 PostgreSQL 全量重建，活动版本数与全文索引可见数一致。
5. API 健康检查、真实搜索、证据正文读取和 JSONL 导出成功。
6. 采集器新增一条真实证据，目录、主桶和备份桶均保存且可读取，索引器随后使其可搜索。
7. 在 2C/4G/512 总资源上观察 API、Web、采集器、索引器、Elasticsearch 和存储连接，无重启、积压或错误。

恢复目标的目录关系、逐表摘要、主对象和备份对象可先运行统一硬校验：

```bash
python -m qsou_data.verify --require-backup
```

命令只有在所有孤儿记录为 0、每个正文对象与目录哈希一致且备份桶也逐一通过时，才输出 `status=verified`。

完成 PostgreSQL 与对象存储隔离恢复验证后，先创建新的可读备份，再处理临时目标。任何临时目标或旧文件的删除都必须列出准确对象并单独确认，继续遵守 GitOps 治理。
