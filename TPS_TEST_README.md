# TPS 性能测试工具使用说明

## 简介

`tps_test.py` 是一个用于测试以太坊 PoA 网络 TPS（每秒交易数）性能的脚本。

## 功能特性

- ✅ 创建 2000 个以太坊子账号（私钥和地址）
- ✅ 从 producer1 账号读取余额并平均分配到所有子账号
- ✅ 使用前 1000 个子账号作为发送方，后 1000 个子账号作为接收方
- ✅ 不断循环发起小额转账（默认 0.001 ETH）
- ✅ 记录和显示 TPS 性能指标（总交易数、总耗时、平均 TPS、成功/失败数）
- ✅ 支持多线程或异步方式提高交易发送效率
- ✅ 灵活的配置选项（RPC 地址、私钥、转账金额、并发数）
- ✅ 完善的错误处理和重试机制
- ✅ 清晰的进度和统计信息输出

## 安装依赖

```bash
# 安装必需的 Python 包
pip install -r requirements.txt

# 或者手动安装
pip install web3 eth-account pyyaml
```

## 使用方法

### 1. 配置

有两种方式配置测试参数：

#### 方式一：使用环境变量

```bash
export ETH_RPC_URL="http://localhost:8545"
export PRODUCER_PRIVATE_KEY="0x你的私钥"
export TRANSFER_AMOUNT="0.001"
export DISTRIBUTION_AMOUNT="0.1"
export CONCURRENCY="50"
export GAS_PRICE_GWEI="20"
```

#### 方式二：使用命令行参数

直接在命令行中指定参数（会覆盖环境变量）。

### 2. 创建测试账号

```bash
python3 tps_test.py --rpc http://localhost:8545 --key 0x你的私钥 --create
```

此命令会：
- 创建 2000 个以太坊账号
- 将账号信息保存到 `test_accounts.json` 文件

### 3. 分配余额

```bash
python3 tps_test.py --rpc http://localhost:8545 --key 0x你的私钥 --distribute
```

此命令会：
- 从 producer 账号向所有 2000 个子账号转账
- 每个账号默认接收 0.1 ETH（可通过 `--distribution` 参数调整）

### 4. 运行 TPS 测试

```bash
# 运行 60 秒的测试（多线程模式）
python3 tps_test.py --rpc http://localhost:8545 --test 60

# 运行 60 秒的测试（异步模式）
python3 tps_test.py --rpc http://localhost:8545 --test 60 --async

# 指定并发数
python3 tps_test.py --rpc http://localhost:8545 --test 60 --concurrency 100
```

### 5. 完整工作流程

一次性完成所有步骤：

```bash
python3 tps_test.py \
  --rpc http://localhost:8545 \
  --key 0x你的私钥 \
  --create \
  --distribute \
  --test 60
```

### 6. 验证账号余额

检查子账号是否有足够的余额：

```bash
python3 tps_test.py --rpc http://localhost:8545 --verify
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--rpc RPC` | RPC 节点地址 | `http://localhost:8545` |
| `--key KEY` | Producer 私钥（用于分配余额） | 环境变量 `PRODUCER_PRIVATE_KEY` |
| `--transfer TRANSFER` | 单次转账金额（ETH） | `0.001` |
| `--distribution DISTRIBUTION` | 分配给每个子账号的金额（ETH） | `0.1` |
| `--concurrency CONCURRENCY` | 并发数 | `50` |
| `--gas-price GAS_PRICE` | Gas 价格（Gwei） | `20` |
| `--create` | 创建子账号 | - |
| `--distribute` | 分配余额到子账号 | - |
| `--test SECONDS` | 运行 TPS 测试（指定持续秒数） | - |
| `--async` | 使用异步模式（默认使用多线程） | - |
| `--verify` | 验证账号余额 | - |

## 输出示例

### 测试运行中

```
开始 TPS 测试（多线程模式，持续 60 秒）...
并发数: 50
转账金额: 0.001 ETH

获取发送方账号 nonce...
  已获取 200/1000 个账号的 nonce...
  已获取 400/1000 个账号的 nonce...
  ...

开始发送交易...

  已提交 100 笔交易 | 当前 TPS: 45.23 | 剩余时间: 57 秒
  已提交 200 笔交易 | 当前 TPS: 48.67 | 剩余时间: 55 秒
  ...
```

### 测试结果

```
============================================================
TPS 测试统计结果
============================================================
总交易数:       3000
成功交易数:     2985
失败交易数:     15
总耗时:         60.12 秒
平均 TPS:       49.65 交易/秒
成功率:         99.50%
============================================================
```

## 注意事项

1. **Producer 账号余额**
   - 确保 producer 账号有足够的 ETH 用于分配
   - 所需金额 = (分配金额 × 2000) + (gas 费用 × 2000)
   - 例如：分配 0.1 ETH/账号，约需 200+ ETH

2. **网络性能**
   - TPS 取决于网络配置（出块时间、gas 限制等）
   - 建议先使用较小的测试时长（如 30 秒）测试

3. **并发数设置**
   - 并发数过高可能导致节点负载过大
   - 建议从 50 开始，逐步调整

4. **账号文件**
   - 创建的账号保存在 `test_accounts.json`
   - 请妥善保管此文件，包含私钥信息
   - 可以重复使用已创建的账号（无需每次都创建）

5. **Gas 价格**
   - 根据网络情况调整 gas 价格
   - 过低可能导致交易长时间未确认
   - 过高会增加测试成本

## 故障排除

### 问题 1: 连接失败

```
错误: 无法连接到以太坊节点
```

**解决方案：**
- 检查 RPC 地址是否正确
- 确保节点正在运行
- 检查防火墙设置

### 问题 2: 余额不足

```
错误: Producer 余额不足！
```

**解决方案：**
- 检查 producer 账号余额
- 减少分配金额或账号数量
- 向 producer 账号转入更多 ETH

### 问题 3: 交易失败率高

**可能原因：**
- Gas 价格过低
- 网络拥堵
- 并发数过高

**解决方案：**
- 增加 `--gas-price` 参数值
- 减少 `--concurrency` 参数值
- 等待网络恢复正常

## 高级用法

### 自定义测试参数

```bash
# 使用更大的转账金额和更高的并发
python3 tps_test.py \
  --rpc http://localhost:8545 \
  --test 120 \
  --transfer 0.01 \
  --concurrency 100 \
  --gas-price 50
```

### 使用异步模式进行更高性能测试

```bash
python3 tps_test.py \
  --rpc http://localhost:8545 \
  --test 60 \
  --async \
  --concurrency 200
```

### 连接到远程节点

```bash
python3 tps_test.py \
  --rpc http://your-node-ip:8545 \
  --key 0x你的私钥 \
  --create \
  --distribute \
  --test 60
```

## 与 PoA 网络集成

如果您使用本项目的 `generate_network.py` 创建了 PoA 网络：

```bash
# 1. 启动网络
cd ethereum-poa-network
docker-compose up -d

# 2. 获取 producer1 的私钥
# 私钥在 node_producer1/keystore/ 目录下的 UTC 文件中

# 3. 运行 TPS 测试
cd ..
python3 tps_test.py \
  --rpc http://localhost:8545 \
  --key 0xPRODUCER1_PRIVATE_KEY \
  --create \
  --distribute \
  --test 60
```

## 性能优化建议

1. **网络层面**
   - 减少 `block_period`（出块间隔）以提高 TPS
   - 增加 `gas_limit` 允许更多交易进入区块
   - 增加验证者数量提高网络吞吐量

2. **测试层面**
   - 使用异步模式 (`--async`) 获得更高并发
   - 适当增加并发数 (`--concurrency`)
   - 使用较低的转账金额减少 gas 消耗

3. **节点层面**
   - 使用 SSD 硬盘提高 I/O 性能
   - 分配足够的 CPU 和内存资源
   - 启用 geth 性能优化选项

## 许可证

本工具遵循项目主许可证（MIT License）。
