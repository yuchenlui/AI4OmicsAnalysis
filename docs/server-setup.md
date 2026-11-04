# 服务器配置指南（组学分析建议）

> 为什么：DEG（DESeq2/limma）、Seurat、大矩阵 IO 在笔记本上又慢又吃内存——
> 一个 24 样本 RNA-seq 的 DEG + 富集，32GB 内存的本机要数十分钟，128GB 的服务器几十秒。
> ai4omics 的阶段脚本可以留在本地开发，`execution: ssh` 一键切到服务器执行，产物自动拉回。

## 1. 服务器最低配置建议

| 用途 | CPU | 内存 | 存储 | 说明 |
|---|---|---|---|---|
| 批量 RNA-seq DEG（≤50 样本） | 8 核 | 32 GB | 200 GB | DESeq2 峰值内存 ≈ 样本数 × 基因数 × 12B |
| 多数据集 DEG + 富集 + ChIP（本项目规模） | 16 核 | 64 GB | 500 GB | GEO/PRIDE 原始数据 ~GB 级/数据集 |
| 单细胞（Seurat/scanpy ≥10 万细胞） | 16 核 | 128 GB | 1 TB | 内存是第一瓶颈 |

软件：Linux x86_64 + [mambaforge](https://github.com/conda-forge/miniforge)；建一个 `omics` 环境装
`python=3.11 pandas numpy matplotlib pyyaml scipy statsmodels r-base r-deseq2 bioconductor-limma bioconductor-clusterprofiler`。

## 2. SSH 免密配置（本地一次性）

```bash
ssh-keygen -t ed25519 -C "ai4omics"            # 一路回车
ssh-copy-id user@server                        # 或手动追加到服务器 ~/.ssh/authorized_keys
```

`~/.ssh/config` 建别名（推荐，之后所有配置只写别名）：

```
Host sxycloud-x2
    HostName <服务器IP>
    User dsh
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
```

自检：

```bash
ssh sxycloud-x2 "nproc && free -g && df -h /data"   # 核数/内存/磁盘
python -m ai4omics doctor --pipeline pipeline.yaml  # 依赖 + SSH + 工作目录一键体检
```

## 3. 项目切换到远程执行

`pipeline.yaml` 三处改动：

```yaml
base: /data/omics/myproject          # 服务器上的项目根
python: /opt/mambaforge/envs/omics/bin/python
execution: ssh
remote:
  host: sxycloud-x2
  workdir: /data/omics/myproject
```

首次使用先把项目同步上去（rsync 增量，排除大结果目录）：

```bash
rsync -avz --exclude 'results/' --exclude 'figures/' ./ sxycloud-x2:/data/omics/myproject/
```

之后照常运行，产物自动 scp 拉回本地：

```bash
python -m ai4omics run --pipeline pipeline.yaml
```

> 注意：`execution: ssh` 时 expect/contract 检查的是**拉回后**的本地副本；
> 大文件（原始 fastq/counts）留在服务器，pipeline 里只把 results/ 列进 pull。

## 4. 长任务与断点

- 阶段有 `state.json` 断点：中断后直接重跑同一条命令，已完成阶段自动跳过。
- 单阶段超过 1 小时：给该阶段加 `timeout: 14400`，并建议在 tmux 里跑整条流水线。
- 限流型数据源（NCBI/EBI）失败属 transient 类，会自动退避重试，无需人工干预。
