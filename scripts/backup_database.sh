"""
数据库自动备份脚本
"""

#!/bin/bash

# CryptoQuant 数据库备份脚本
# 用法：./backup.sh [backup_dir]

set -e

# 配置
BACKUP_DIR="${1:-./backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3307}"
DB_USER="${DB_USER:-cryptoquant}"
DB_PASSWORD="${DB_PASSWORD}"
DB_NAME="${DB_NAME:-crypto_quant}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "开始备份数据库：$DB_NAME"
echo "备份文件：$BACKUP_FILE"

# 执行备份
mysqldump \
  -h "$DB_HOST" \
  -P "$DB_PORT" \
  -u "$DB_USER" \
  -p"$DB_PASSWORD" \
  --single-transaction \
  --quick \
  --lock-tables=false \
  "$DB_NAME" | gzip > "$BACKUP_FILE"

# 检查备份是否成功
if [ $? -eq 0 ]; then
  BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
  echo "✅ 备份成功：$BACKUP_SIZE"
else
  echo "❌ 备份失败"
  exit 1
fi

# 清理旧备份
echo "清理 ${RETENTION_DAYS} 天前的备份..."
find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete

# 列出当前备份
echo ""
echo "当前备份文件:"
ls -lh "$BACKUP_DIR"/*.sql.gz

echo ""
echo "备份完成!"
