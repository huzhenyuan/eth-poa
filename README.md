# 以太坊 Clique PoA 私有网络

本项目提供了一套完整的工具和脚本，用于快速搭建基于 Clique PoA (Proof of Authority) 共识机制的以太坊私有网络。通过自动化脚本，您可以轻松创建任意数量的区块生产者和同步节点。

[English](./README.md) | [中文](./README.zh-TW.md)

---

## 目录

1. [Clique 运作机制概述](#1-clique-运作机制概述)
   - [1.1 区块生成流程](#11-区块生成流程)
   - [1.2 genesis.json 中的 Clique 配置](#12-genesisjson-中的-clique-配置)
   - [1.3 extradata 字段内容解析](#13-extradata-字段内容解析)
   - [1.4 投票与治理机制](#14-投票与治理机制)
   - [1.5 使用 Python 进行投票](#15-使用-python-进行投票)
   - [1.6 使用 Geth 控制台进行投票](#16-使用-geth-控制台进行投票)
2. [使用 generate_network.py 创建私有网络](#2-使用-generate_networkpy-创建私有网络)
   - [2.1 脚本原理详解](#21-脚本原理详解)
   - [2.2 修改配置和运行脚本](#22-修改配置和运行脚本)
   - [2.3 如何运行网络](#23-如何运行网络)
   - [2.4 连接到节点控制台](#24-连接到节点控制台)

---

## 1. Clique 运作机制概述

### 1.1 区块生成流程

Clique 是以太坊的权威证明 (Proof of Authority) 共识机制，专为私有链和联盟链设计。与传统的工作量证明 (PoW) 不同，Clique 不需要大量算力，而是依靠预先授权的验证者 (validators) 轮流产生区块。

**区块生成的完整流程：**

1. **验证者选择**
   - 系统根据区块高度和验证者集合，使用确定性算法选择当前轮次的出块者
   - 算法确保每个验证者都有公平的出块机会
   - 验证者按照其地址的字典序进行排序

2. **区块创建**
   - 被选中的验证者从交易池中选择待打包的交易
   - 执行交易并更新状态树
   - 计算区块头中的各个字段 (状态根、交易根、收据根等)

3. **区块签名**
   - 验证者使用私钥对区块头进行签名
   - 签名结果 (65字节) 被添加到区块头的 `extradata` 字段末尾
   - 签名包含 r、s、v 三个组件，可用于恢复签名者地址

4. **区块广播**
   - 已签名的区块被广播到网络中的其他节点
   - 其他节点验证区块的有效性

5. **区块验证**
   - 接收节点验证区块签名的有效性
   - 检查签名者是否在当前验证者集合中
   - 验证区块间隔是否符合配置的 `period` 参数
   - 检查区块高度是否连续

6. **区块确认**
   - 验证通过后，区块被添加到本地链上
   - 区块中的交易被标记为已确认
   - 状态数据库被更新

**出块时序规则：**

- **正常出块**：验证者在指定时间点 (`parent.time + period`) 产生区块
- **延迟出块**：如果轮到的验证者未能及时出块，下一个验证者可以接替
- **防止分叉**：通过签名机制和严格的时间规则，最小化分叉可能性

### 1.2 genesis.json 中的 Clique 配置

在创世块配置文件 `genesis.json` 中，Clique 共识相关的配置位于 `config.clique` 部分：

```json
{
  "config": {
    "chainId": 123454321,
    "homesteadBlock": 0,
    "eip150Block": 0,
    "eip155Block": 0,
    "eip158Block": 0,
    "byzantiumBlock": 0,
    "constantinopleBlock": 0,
    "petersburgBlock": 0,
    "istanbulBlock": 0,
    "muirGlacierBlock": 0,
    "berlinBlock": 0,
    "londonBlock": 0,
    "arrowGlacierBlock": 0,
    "grayGlacierBlock": 0,
    "clique": {
      "period": 5,
      "epoch": 30000
    }
  },
  "difficulty": "1",
  "gasLimit": "800000000",
  "extradata": "0x0000...0000[VALIDATOR_ADDRESSES]0000...0000",
  "alloc": {
    "address1": { "balance": "1000000000000000000" },
    "address2": { "balance": "1000000000000000000" }
  }
}
```

**关键配置参数说明：**

| 参数 | 说明 | 默认值 | 推荐范围 |
|------|------|--------|----------|
| `chainId` | 链 ID，用于防止重放攻击 | 123454321 | 任意唯一整数 |
| `period` | 区块生成间隔 (秒) | 5 | 3-15秒 |
| `epoch` | 治理周期 (区块数) | 30000 | 10000-50000 |
| `gasLimit` | 区块 Gas 上限 | 800000000 | 根据需求调整 |
| `difficulty` | 固定难度值 | "1" | 通常为"1"或"2" |

**参数详解：**

- **period（出块间隔）**
  - 控制区块生成的时间间隔
  - 更短的间隔意味着更快的交易确认，但会增加网络负担
  - 推荐值：开发环境 3-5 秒，生产环境 10-15 秒

- **epoch（治理周期）**
  - 定义一个完整治理周期包含的区块数量
  - 在每个 epoch 边界 (`blockNumber % epoch == 0`) 时：
    - 系统处理并结算累积的所有投票
    - 根据投票结果更新验证者集合
    - 清除未达成共识的投票
    - 重新计算区块签名顺序
  - 更长的 epoch 意味着更稳定但反应较慢的治理机制

- **difficulty（难度值）**
  - 在 Clique 中，难度值是固定的
  - `1` 表示轮到自己的验证者
  - `2` 表示不在自己轮次的验证者（作为备选）

### 1.3 extradata 字段内容解析

`extradata` 是区块头中的一个特殊字段，在 Clique 共识中用于存储验证者信息和区块签名。

**创世块中的 extradata 格式：**

```
总长度 = 32 + (20 * N) + 65 字节

结构：
[32字节前缀] + [验证者地址列表] + [65字节后缀]
```

**详细组成：**

1. **32 字节前缀 (Vanity)**
   - 用途：自定义数据区域
   - 内容：通常填充为 0，也可以包含网络标识等信息
   - 示例：`0x0000000000000000000000000000000000000000000000000000000000000000`

2. **验证者地址列表**
   - 长度：20 字节 × 验证者数量
   - 格式：连续排列的以太坊地址（不含 `0x` 前缀）
   - 顺序：按地址字典序排列
   - 示例（2个验证者）：
     ```
     c0a55ae58fb8e26f7874e865ee143f033d445927
     8c59707ccf4c996bdb6163a3a759baadf82dae6a
     ```

3. **65 字节后缀 (Seal)**
   - 在创世块中：填充为 0
   - 在普通区块中：包含区块签名 (r + s + v 组件)
   - 示例：`0x0000...0000` (65 字节)

**完整示例（2个验证者）：**

```
0x
0000000000000000000000000000000000000000000000000000000000000000  ← 32字节前缀
c0a55ae58fb8e26f7874e865ee143f033d445927                        ← 验证者1
8c59707ccf4c996bdb6163a3a759baadf82dae6a                        ← 验证者2
00000000000000000000000000000000000000000000000000000000000000  ← 65字节后缀
0000000000000000000000000000000000000000000000000000000000000000
00
```

**普通区块中的 extradata 格式：**

在已挖出的区块中，extradata 的结构略有不同：

```
[32字节前缀] + [65字节签名]
```

- 前 32 字节：Vanity（可选的自定义数据）
- 后 65 字节：区块生产者的签名
  - r (32 字节)：签名的 r 组件
  - s (32 字节)：签名的 s 组件  
  - v (1 字节)：恢复 ID

通过签名，可以使用 `ecrecover` 算法恢复出签名者的地址，从而验证区块的有效性。

**验证者集合的快照机制：**

Clique 使用快照 (snapshot) 机制来跟踪验证者集合：

- 每个 epoch 边界会创建一个快照
- 快照包含当前的验证者集合和投票状态
- 节点可以从任意快照重建当前的验证者状态
- 这使得轻客户端无需下载完整链即可验证区块

### 1.4 投票与治理机制

Clique 采用链上投票机制来动态调整验证者集合，实现去中心化治理。

**投票规则：**

1. **投票权重**
   - 每个现有验证者拥有一票
   - 投票权重平等，不受质押或其他因素影响

2. **提案类型**
   - **添加验证者**：提议将新地址加入验证者集合
   - **移除验证者**：提议将现有地址从验证者集合中移除

3. **投票通过条件**
   - 需要超过半数 (> 50%) 的现有验证者支持
   - 例如：3 个验证者需要 2 票，4 个验证者需要 3 票

4. **投票限制**
   - 验证者不能投票支持自己加入
   - 验证者不能投票反对自己被移除
   - 每个验证者在同一 epoch 内对同一地址只能投一次票

5. **投票有效期**
   - 投票在下一个 epoch 结束时结算
   - 未达成多数的投票会被丢弃
   - 已通过的投票立即生效

**投票流程：**

```
1. 验证者发起提案
   ↓
2. 其他验证者投票支持或反对
   ↓
3. 投票被记录在区块中
   ↓
4. 到达 epoch 边界时统计投票
   ↓
5. 如果达到多数，更新验证者集合
   ↓
6. 清除已处理的投票
```

**投票的链上表示：**

投票信息通过区块头的特定字段传递：

- `coinbase`：被提议的地址
- `nonce`：投票类型
  - `0xffffffffffffffff`：支持添加该地址
  - `0x0000000000000000`：支持移除该地址

### 1.5 使用 Python 进行投票

使用 Web3.py 库可以程序化地进行 Clique 投票操作。

**安装依赖：**

```bash
pip install web3
```

**Python 投票脚本示例：**

```python
from web3 import Web3
import json

# 连接到以太坊节点
web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))

# 检查连接
if not web3.is_connected():
    print("无法连接到以太坊节点")
    exit(1)

print(f"已连接到节点，链ID: {web3.eth.chain_id}")

# 验证者账户配置
validator_address = "0xC0A55ae58fb8E26f7874E865eE143f033D445927"
password = "password1"

class CliqueGovernance:
    """Clique 治理操作类"""
    
    def __init__(self, web3_instance, validator_address, password):
        self.web3 = web3_instance
        self.validator = validator_address
        self.password = password
    
    def propose_add_validator(self, new_validator_address):
        """提议添加新验证者"""
        try:
            # 解锁账户
            self.web3.geth.personal.unlock_account(
                self.validator, 
                self.password, 
                600  # 解锁600秒
            )
            
            # 发送提案
            result = self.web3.provider.make_request(
                'clique_propose',
                [new_validator_address, True]
            )
            
            print(f"✓ 已提议添加验证者: {new_validator_address}")
            return result
            
        except Exception as e:
            print(f"✗ 提议失败: {e}")
            return None
    
    def propose_remove_validator(self, validator_address):
        """提议移除验证者"""
        try:
            # 解锁账户
            self.web3.geth.personal.unlock_account(
                self.validator, 
                self.password, 
                600
            )
            
            # 发送提案
            result = self.web3.provider.make_request(
                'clique_propose',
                [validator_address, False]
            )
            
            print(f"✓ 已提议移除验证者: {validator_address}")
            return result
            
        except Exception as e:
            print(f"✗ 提议失败: {e}")
            return None
    
    def get_proposals(self):
        """查看当前所有提案"""
        try:
            result = self.web3.provider.make_request(
                'clique_proposals',
                []
            )
            
            proposals = result.get('result', {})
            
            print("\n当前提案:")
            if not proposals:
                print("  (无)")
            else:
                for address, vote in proposals.items():
                    vote_type = "添加" if vote else "移除"
                    print(f"  {address}: {vote_type}")
            
            return proposals
            
        except Exception as e:
            print(f"✗ 获取提案失败: {e}")
            return None
    
    def get_signers(self):
        """查看当前验证者集合"""
        try:
            result = self.web3.provider.make_request(
                'clique_getSigners',
                []
            )
            
            signers = result.get('result', [])
            
            print("\n当前验证者:")
            for i, signer in enumerate(signers, 1):
                print(f"  {i}. {signer}")
            
            return signers
            
        except Exception as e:
            print(f"✗ 获取验证者失败: {e}")
            return None
    
    def get_snapshot(self, block_number='latest'):
        """查看特定区块的验证者快照"""
        try:
            if block_number == 'latest':
                block_number = hex(self.web3.eth.block_number)
            elif isinstance(block_number, int):
                block_number = hex(block_number)
            
            result = self.web3.provider.make_request(
                'clique_getSnapshot',
                [block_number]
            )
            
            snapshot = result.get('result', {})
            
            print(f"\n区块 {block_number} 的快照:")
            print(f"  区块哈希: {snapshot.get('hash', 'N/A')}")
            print(f"  区块高度: {int(snapshot.get('number', '0x0'), 16)}")
            print(f"  验证者数量: {len(snapshot.get('signers', {}))}")
            print(f"  投票数量: {len(snapshot.get('votes', []))}")
            
            return snapshot
            
        except Exception as e:
            print(f"✗ 获取快照失败: {e}")
            return None
    
    def discard_proposal(self, address):
        """撤销对某地址的提案"""
        try:
            # 解锁账户
            self.web3.geth.personal.unlock_account(
                self.validator, 
                self.password, 
                600
            )
            
            # 撤销提案
            result = self.web3.provider.make_request(
                'clique_discard',
                [address]
            )
            
            print(f"✓ 已撤销对 {address} 的提案")
            return result
            
        except Exception as e:
            print(f"✗ 撤销失败: {e}")
            return None

# 使用示例
def main():
    # 创建治理实例
    governance = CliqueGovernance(web3, validator_address, password)
    
    # 1. 查看当前验证者
    print("=" * 60)
    print("查看当前验证者集合")
    print("=" * 60)
    governance.get_signers()
    
    # 2. 查看当前提案
    print("\n" + "=" * 60)
    print("查看当前提案")
    print("=" * 60)
    governance.get_proposals()
    
    # 3. 提议添加新验证者
    print("\n" + "=" * 60)
    print("提议添加新验证者")
    print("=" * 60)
    new_validator = "0x8c59707CcF4c996bDB6163A3a759baADf82dAe6A"
    governance.propose_add_validator(new_validator)
    
    # 4. 再次查看提案（应该能看到新提案）
    print("\n" + "=" * 60)
    print("确认提案已提交")
    print("=" * 60)
    governance.get_proposals()
    
    # 5. 查看快照
    print("\n" + "=" * 60)
    print("查看当前快照")
    print("=" * 60)
    governance.get_snapshot('latest')
    
    # 6. 撤销提案（可选）
    # governance.discard_proposal(new_validator)

if __name__ == "__main__":
    main()
```

**监听验证者变更事件：**

```python
import time
from web3 import Web3

web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))

class ValidatorMonitor:
    """验证者变更监控类"""
    
    def __init__(self, web3_instance, epoch_length):
        self.web3 = web3_instance
        self.epoch = epoch_length
        self.known_signers = set()
        self.update_signers()
    
    def update_signers(self):
        """更新已知验证者集合"""
        result = self.web3.provider.make_request('clique_getSigners', [])
        new_signers = set(result.get('result', []))
        
        # 检测新增的验证者
        added = new_signers - self.known_signers
        for signer in added:
            print(f"➕ 新增验证者: {signer}")
        
        # 检测移除的验证者
        removed = self.known_signers - new_signers
        for signer in removed:
            print(f"➖ 移除验证者: {signer}")
        
        self.known_signers = new_signers
        return new_signers
    
    def is_epoch_boundary(self, block_number):
        """检查是否为 epoch 边界"""
        return block_number % self.epoch == 0
    
    def monitor(self):
        """持续监控验证者变更"""
        print(f"开始监控验证者变更 (epoch = {self.epoch} 区块)")
        print(f"当前验证者: {len(self.known_signers)} 个\n")
        
        block_filter = self.web3.eth.filter('latest')
        
        try:
            while True:
                for block_hash in block_filter.get_new_entries():
                    block = self.web3.eth.get_block(block_hash)
                    block_number = block['number']
                    
                    print(f"新区块 #{block_number}")
                    
                    # 在 epoch 边界检查验证者变更
                    if self.is_epoch_boundary(block_number):
                        print(f"\n🔔 到达 epoch 边界 (区块 #{block_number})")
                        self.update_signers()
                        print()
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n监控已停止")

# 使用示例
if __name__ == "__main__":
    monitor = ValidatorMonitor(web3, epoch_length=30000)
    monitor.monitor()
```

### 1.6 使用 Geth 控制台进行投票

Geth 控制台提供了直接的 JavaScript 接口来进行 Clique 治理操作。

**连接到 Geth 控制台：**

```bash
# 通过 IPC 连接
docker exec -it ethereum-producer1 geth attach /root/.ethereum/geth.ipc

# 或通过 RPC 连接
geth attach http://localhost:8545
```

**1. 提议添加新验证者：**

```javascript
// 提议添加新验证者
> clique.propose("0x8c59707CcF4c996bDB6163A3a759baADf82dAe6A", true)
null

// 命令说明：
// - 第一个参数：要添加的验证者地址
// - 第二个参数：true 表示添加，false 表示移除
```

**2. 提议移除现有验证者：**

```javascript
// 提议移除验证者
> clique.propose("0xC0A55ae58fb8E26f7874E865eE143f033D445927", false)
null

// 注意：验证者不能投票移除自己
```

**3. 查看当前所有提案：**

```javascript
> clique.proposals()
{
  0x8c59707ccf4c996bdb6163a3a759baadf82dae6a: true,   // 提议添加此地址
  0xc0a55ae58fb8e26f7874e865ee143f033d445927: false   // 提议移除此地址
}

// 输出说明：
// - key: 被提议的地址
// - value: true (添加) 或 false (移除)
```

**4. 查看当前验证者集合：**

```javascript
> clique.getSigners()
[
  "0xc0a55ae58fb8e26f7874e865ee143f033d445927",
  "0x8c59707ccf4c996bdb6163a3a759baadf82dae6a"
]

// 返回所有当前活跃的验证者地址
// 地址按字典序排列
```

**5. 查看特定区块的验证者快照：**

```javascript
> clique.getSnapshot()
{
  hash: "0x6e3a93a...",              // 快照对应的区块哈希
  number: 100,                        // 区块高度
  recents: {                          // 最近出块的验证者
    98: "0xc0a55ae...",
    99: "0x8c59707...",
    100: "0xc0a55ae..."
  },
  signers: {                          // 当前验证者集合
    "0x8c59707ccf4c996bdb6163a3a759baadf82dae6a": {},
    "0xc0a55ae58fb8e26f7874e865ee143f033d445927": {}
  },
  votes: [                            // 当前投票列表
    {
      address: "0x...",
      authorize: true,
      signer: "0x..."
    }
  ],
  tally: {                            // 投票统计
    "0x...": 1
  }
}

// 还可以查看特定区块的快照
> clique.getSnapshot(1000)           // 查看第1000个区块的快照
> clique.getSnapshot("latest")       // 查看最新区块的快照
```

**6. 撤销提案：**

```javascript
// 撤销对某地址的提案
> clique.discard("0x8c59707CcF4c996bDB6163A3a759baADf82dAe6A")
null

// 再次查看提案，应该已经移除
> clique.proposals()
{}
```

**7. 查看验证者状态（高级）：**

```javascript
// 获取指定区块号的快照
> snapshot = clique.getSnapshot(30000)

// 查看验证者数量
> Object.keys(snapshot.signers).length
2

// 查看投票数量
> snapshot.votes.length
0

// 查看投票统计
> snapshot.tally
{
  0x8c59707ccf4c996bdb6163a3a759baadf82dae6a: 1
}
```

**完整治理流程示例：**

```javascript
// ========================================
// 场景：添加新验证者到网络
// ========================================

// 步骤1: 查看当前验证者（假设有2个）
> clique.getSigners()
["0xaddr1", "0xaddr2"]

// 步骤2: 验证者1提议添加新验证者
> clique.propose("0xaddr3", true)
null

// 步骤3: 查看提案状态
> clique.proposals()
{ 0xaddr3: true }

// 步骤4: 验证者2也投票支持（在另一个节点的控制台）
> clique.propose("0xaddr3", true)
null

// 步骤5: 等待下一个 epoch 边界（例如30000的倍数区块）
> eth.blockNumber
30050  // 已经过了30000边界

// 步骤6: 检查验证者集合是否更新
> clique.getSigners()
["0xaddr1", "0xaddr2", "0xaddr3"]  // 新验证者已加入

// 步骤7: 确认提案已清除
> clique.proposals()
{}  // 已通过的提案被清除
```

**监控投票和验证者变更：**

```javascript
// 创建一个简单的监控器
var lastEpoch = 0;
var currentSigners = new Set(clique.getSigners());

// 订阅新区块
eth.filter("latest").watch(function(error, blockHash) {
    if (error) {
        console.log("错误:", error);
        return;
    }
    
    var block = eth.getBlock(blockHash);
    var blockNumber = block.number;
    
    // 检查是否到达新的 epoch
    var epoch = Math.floor(blockNumber / 30000);
    if (epoch > lastEpoch) {
        console.log("\n🔔 到达新的 epoch:", epoch);
        console.log("区块高度:", blockNumber);
        
        // 检查验证者变更
        var newSigners = new Set(clique.getSigners());
        
        // 检测新增
        for (var signer of newSigners) {
            if (!currentSigners.has(signer)) {
                console.log("➕ 新增验证者:", signer);
            }
        }
        
        // 检测移除
        for (var signer of currentSigners) {
            if (!newSigners.has(signer)) {
                console.log("➖ 移除验证者:", signer);
            }
        }
        
        currentSigners = newSigners;
        lastEpoch = epoch;
        
        // 显示当前提案
        console.log("当前提案:", clique.proposals());
    }
});

console.log("监控器已启动");
```

---

## 2. 使用 generate_network.py 创建私有网络

本项目提供的 `generate_network.py` 脚本可以自动化创建和配置以太坊 Clique PoA 私有网络，支持任意数量的区块生产者和同步节点。

### 2.1 脚本原理详解

#### 2.1.1 整体架构

`generate_network.py` 脚本采用模块化设计，通过 `EthereumNetworkGenerator` 类封装了所有网络生成逻辑：

```
配置文件 (config.yaml)
        ↓
   加载并解析配置
        ↓
   创建节点目录结构
        ↓
   生成账户和密钥
        ↓
   生成 genesis.json
        ↓
   初始化所有节点
        ↓
   获取 enode ID
        ↓
   生成 docker-compose.yml
        ↓
   保存节点信息
```

#### 2.1.2 核心功能模块

**1. 配置加载模块 (`load_config`)**

```python
def load_config(self) -> Dict:
    """加载 YAML 配置文件"""
    with open(self.config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
```

- 读取 YAML 格式的配置文件
- 解析网络参数、节点定义等配置
- 验证配置文件的存在性和格式正确性

**2. 目录创建模块 (`create_directories`)**

```python
def create_directories(self):
    """为每个节点创建独立的数据目录"""
    for node in producers + synchers:
        node_dir = os.path.join(self.output_dir, f"node_{node['name']}")
        os.makedirs(node_dir, exist_ok=True)
        os.makedirs(f"{node_dir}/keystore", exist_ok=True)
```

目录结构：
```
output_dir/
├── node_producer1/
│   └── keystore/          # 存储加密的私钥文件
├── node_producer2/
│   └── keystore/
├── node_syncher1/
│   └── keystore/
└── ...
```

**3. 账户创建模块 (`create_accounts`)**

```python
def create_accounts(self):
    """使用 Docker 运行 geth account new 为每个节点创建账户"""
    cmd = [
        'docker', 'run', '--rm',
        '-v', f"{node_dir}:/root/.ethereum",
        '-v', f"{password_file}:/password.txt",
        image,
        'account', 'new',
        '--password', '/password.txt'
    ]
```

工作流程：
1. 为每个节点启动临时 Docker 容器
2. 运行 `geth account new` 命令
3. 使用预设密码自动创建账户
4. 从输出中提取账户地址
5. 将地址存储到 `self.accounts` 字典中

**4. Genesis 生成模块 (`generate_genesis`)**

这是最核心的模块之一，负责生成创世块配置。

```python
def generate_genesis(self):
    # 构建 extradata
    extradata = '0x' + '0' * 64  # 32字节前缀
    for addr in validator_addresses:
        extradata += addr  # 添加验证者地址
    extradata += '0' * 130  # 65字节后缀
    
    # 构建 alloc (初始余额分配)
    alloc = {}
    for node in all_nodes:
        addr = self.accounts[node['name']]
        alloc[addr] = {"balance": initial_balance}
```

extradata 构建详解：
- **32 字节前缀**：`'0' * 64` (64 个十六进制字符 = 32 字节)
- **验证者地址**：每个地址 40 个十六进制字符 (20 字节)
- **65 字节后缀**：`'0' * 130` (130 个十六进制字符 = 65 字节)

**5. 节点初始化模块 (`initialize_nodes`)**

```python
def initialize_nodes(self):
    """使用 genesis.json 初始化每个节点的区块链数据"""
    cmd = [
        'docker', 'run', '--rm',
        '-v', f"{node_dir}:/root/.ethereum",
        '-v', f"{genesis_path}:/genesis.json",
        image,
        'init',
        '--datadir', '/root/.ethereum',
        '/genesis.json'
    ]
```

初始化过程：
1. 读取 genesis.json
2. 创建创世块
3. 初始化状态数据库 (LevelDB)
4. 生成节点密钥 (nodekey)
5. 设置初始余额

**6. Enode ID 获取模块 (`get_enode_ids`)**

Enode ID 是节点的网络标识符，用于 P2P 网络通信。脚本提供两种获取方式：

**方式一：使用 coincurve 库计算（推荐）**

```python
from coincurve import PrivateKey

# 从 nodekey 文件读取私钥
with open(nodekey_path, 'r') as f:
    nodekey_hex = f.read().strip()

# 计算公钥
private_key_bytes = bytes.fromhex(nodekey_hex)
private_key = PrivateKey(private_key_bytes)
public_key_bytes = private_key.public_key.format(compressed=False)[1:]
enode_id = public_key_bytes.hex()
```

优点：
- 快速，无需启动节点
- 纯计算，无副作用

**方式二：临时启动节点获取（备用）**

```python
def _get_enode_from_running_node(self, node_name, index):
    # 启动临时容器
    subprocess.run(['docker', 'run', '-d', '--name', f'temp-{node_name}', ...])
    
    # 等待启动
    time.sleep(3)
    
    # 从日志中提取 enode
    logs = subprocess.run(['docker', 'logs', f'temp-{node_name}'])
    # 解析 "enode://..." 字符串
```

**Enode 格式说明：**

完整格式：`enode://[node_id]@[ip]:[port]`

示例：
```
enode://67cbdce9f4d0a82cfb76053f948bb467d5acb96175a31330b99df0907e65a046
       8946f2ba2680a850e72a00ab92bbed53d417765b0e32e7afb3523453399edd45
       @172.20.0.2:30306
       
组成部分：
- node_id: 128 个十六进制字符 (64 字节)，即节点的公钥
- ip: 节点的 IP 地址
- port: P2P 监听端口
```

**7. Docker Compose 生成模块 (`generate_docker_compose`)**

该模块负责生成 `docker-compose.yml` 文件，定义所有节点的容器配置。

**网络地址分配策略：**

```python
# 从配置读取基础IP (例如 172.20.0.2)
base_ip = "172.20.0.2"
ip_parts = base_ip.split('.')  # ['172', '20', '0', '2']
ip_counter = int(ip_parts[3])  # 2

# 为每个节点分配连续的IP
for i, node in enumerate(nodes):
    node_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_counter}"
    ip_counter += 1
```

分配示例：
```
producer1: 172.20.0.2
producer2: 172.20.0.3
producer3: 172.20.0.4
syncher1:  172.20.0.5
syncher2:  172.20.0.6
```

**端口分配策略：**

```python
# P2P 端口：从 30306 开始
p2p_port = 30306 + node_index

# RPC 端口：从 8545 开始
rpc_port = 8545 + node_index
```

分配示例：
```
节点          P2P端口    RPC端口
producer1    30306     8545
producer2    30307     8546
producer3    30308     8547
syncher1     30309     8548
syncher2     30310     8549
```

**区块生产者配置：**

```yaml
producer1:
  container_name: ethereum-producer1
  image: layer1:latest
  volumes:
    - ./node_producer1:/root/.ethereum
    - ./node_producer1_password.txt:/password.txt
    - ./genesis.json:/genesis.json
  ports:
    - "30306:30306"
    - "30306:30306/udp"
    - "8545:8545"
  command: >
    --datadir /root/.ethereum
    --port 30306
    --networkid 123454321
    --unlock 0xADDRESS
    --password /password.txt
    --mine                          # 启用挖矿
    --miner.etherbase 0xADDRESS     # 设置挖矿奖励地址
    --http
    --http.api eth,net,web3,personal,admin,clique
    --http.addr 0.0.0.0
    --http.port 8545
    --http.corsdomain "*"
    --allow-insecure-unlock
  networks:
    ethnet:
      ipv4_address: 172.20.0.2
```

**同步节点配置：**

```yaml
syncher1:
  container_name: ethereum-syncher1
  image: layer1:latest
  depends_on:
    - producer1                     # 依赖第一个生产者
  volumes:
    - ./node_syncher1:/root/.ethereum
    - ./node_syncher1_password.txt:/password.txt
    - ./genesis.json:/genesis.json
  ports:
    - "30309:30309"
    - "30309:30309/udp"
    - "8548:8548"
  command: >
    --datadir /root/.ethereum
    --port 30309
    --networkid 123454321
    --unlock 0xADDRESS
    --password /password.txt
    --http
    --http.api eth,net,web3,personal,admin
    --http.addr 0.0.0.0
    --http.port 8548
    --http.corsdomain "*"
    --allow-insecure-unlock
    --bootnodes enode://NODE1@172.20.0.2:30306,enode://NODE2@172.20.0.3:30307
  networks:
    ethnet:
      ipv4_address: 172.20.0.5
```

**Bootnode 配置策略：**

- **第一个生产者**：不需要 bootnode（作为种子节点）
- **其他生产者**：连接到第一个生产者
- **同步节点**：连接到所有生产者

```python
# 构建 bootnode 列表
bootnode_list = []
for i, producer in enumerate(producers):
    producer_ip = f"172.20.0.{base_ip_last_octet + i}"
    producer_port = 30306 + i
    producer_enode = enode_ids[producer['name']]
    bootnode_list.append(f"enode://{producer_enode}@{producer_ip}:{producer_port}")

bootnodes = ','.join(bootnode_list)
```

**8. 节点信息保存模块 (`save_node_info`)**

```python
def save_node_info(self):
    """将节点信息保存为 JSON 文件，方便后续查询"""
    info = {
        'network': {
            'chain_id': 123454321,
            'block_period': 5,
            'epoch': 30000
        },
        'producers': [
            {
                'name': 'producer1',
                'address': '0x...',
                'rpc_port': 8545,
                'rpc_url': 'http://localhost:8545'
            }
        ],
        'synchers': [...]
    }
```

生成的 `node_info.json` 示例：
```json
{
  "network": {
    "name": "ethereum-poa-network",
    "chain_id": 123454321,
    "block_period": 5,
    "epoch": 30000,
    "gas_limit": "800000000"
  },
  "output_directory": "/path/to/ethereum-poa-network",
  "producers": [
    {
      "name": "producer1",
      "address": "0xc0a55ae58fb8e26f7874e865ee143f033d445927",
      "rpc_port": 8545,
      "p2p_port": 30306,
      "rpc_url": "http://localhost:8545"
    },
    {
      "name": "producer2",
      "address": "0x8c59707ccf4c996bdb6163a3a759baadf82dae6a",
      "rpc_port": 8546,
      "p2p_port": 30307,
      "rpc_url": "http://localhost:8546"
    }
  ],
  "synchers": [
    {
      "name": "syncher1",
      "address": "0x1234567890abcdef1234567890abcdef12345678",
      "rpc_port": 8548,
      "p2p_port": 30309,
      "rpc_url": "http://localhost:8548"
    }
  ]
}
```

### 2.2 修改配置和运行脚本

#### 2.2.1 配置文件详解

`config.yaml` 是网络的核心配置文件，定义了所有网络参数和节点信息。

**完整配置示例：**

```yaml
# Docker 镜像配置
docker_image: "layer1:latest"  # 或 "ethereum/client-go:latest"

# 网络参数配置
network:
  name: "ethereum-poa-network"      # 网络名称（也是输出目录名）
  chain_id: 123454321               # 链 ID
  block_period: 5                   # 区块间隔（秒）
  epoch: 30000                      # 治理周期（区块数）
  gas_limit: "800000000"            # Gas 上限
  initial_balance: "1000000000000000000"  # 初始余额（Wei）
  subnet: "172.20.0.0/16"           # Docker 网络子网
  base_ip: "172.20.0.2"             # 起始 IP 地址

# 区块生产者配置
producers:
  - name: producer1
    password: "password"
  
  - name: producer2
    password: "password"
  
  - name: producer3
    password: "password"
  
  - name: producer4
    password: "password"

# 同步节点配置
synchers:
  - name: syncher1
    password: "password_sync1"
  
  - name: syncher2
    password: "password_sync2"
```

**配置参数说明：**

| 参数分类 | 参数名 | 说明 | 推荐值 |
|---------|--------|------|--------|
| **镜像** | `docker_image` | Geth Docker 镜像 | `layer1:latest` 或 `ethereum/client-go:latest` |
| **网络名称** | `network.name` | 网络标识，输出目录名 | 任意字符串 |
| **链 ID** | `network.chain_id` | 区块链 ID，防止重放攻击 | 唯一整数 |
| **出块间隔** | `network.block_period` | 秒为单位 | 3-15 秒 |
| **治理周期** | `network.epoch` | 区块数 | 10000-50000 |
| **Gas 上限** | `network.gas_limit` | 字符串格式 | "800000000" |
| **初始余额** | `network.initial_balance` | Wei 为单位 | "1000000000000000000" (1 ETH) |
| **子网** | `network.subnet` | CIDR 格式 | "172.20.0.0/16" |
| **起始 IP** | `network.base_ip` | IPv4 地址 | "172.20.0.2" |
| **生产者** | `producers` | 列表，每项包含 name 和 password | 至少 1 个 |
| **同步者** | `synchers` | 列表，每项包含 name 和 password | 可选 |

#### 2.2.2 修改配置文件

**场景一：创建 4 个生产者、2 个同步节点的网络**

```yaml
network:
  name: "my-ethereum-network"
  chain_id: 888888
  block_period: 3
  epoch: 10000

producers:
  - name: validator1
    password: "secure_pass_1"
  - name: validator2
    password: "secure_pass_2"
  - name: validator3
    password: "secure_pass_3"
  - name: validator4
    password: "secure_pass_4"

synchers:
  - name: observer1
    password: "observer_pass_1"
  - name: observer2
    password: "observer_pass_2"
```

**场景二：创建高性能开发网络（快速出块）**

```yaml
network:
  name: "dev-network"
  chain_id: 999999
  block_period: 1              # 1秒出块
  epoch: 3000                  # 较短的治理周期
  gas_limit: "1000000000"      # 更高的 Gas 上限

producers:
  - name: dev1
    password: "dev"
  - name: dev2
    password: "dev"
```

**场景三：创建生产环境网络（更安全）**

```yaml
network:
  name: "production-network"
  chain_id: 123456789
  block_period: 15             # 较长的出块间隔
  epoch: 50000                 # 较长的治理周期
  gas_limit: "800000000"

producers:
  - name: prod_validator_1
    password: "STRONG_PASSWORD_1"
  - name: prod_validator_2
    password: "STRONG_PASSWORD_2"
  - name: prod_validator_3
    password: "STRONG_PASSWORD_3"
  - name: prod_validator_4
    password: "STRONG_PASSWORD_4"
  - name: prod_validator_5
    password: "STRONG_PASSWORD_5"

synchers:
  - name: backup_node_1
    password: "BACKUP_PASS_1"
  - name: backup_node_2
    password: "BACKUP_PASS_2"
```

#### 2.2.3 运行脚本

**前置要求：**

1. **安装 Python 3.6+**
   ```bash
   python3 --version
   ```

2. **安装依赖**
   ```bash
   pip install pyyaml
   
   # 可选：安装 coincurve 以加快 enode ID 生成
   pip install coincurve
   ```

3. **安装 Docker 和 Docker Compose**
   ```bash
   docker --version
   docker-compose --version
   ```

4. **准备 Geth Docker 镜像**
   ```bash
   # 方式一：使用官方镜像
   docker pull ethereum/client-go:latest
   
   # 方式二：使用自定义镜像
   # 确保 config.yaml 中的 docker_image 设置正确
   ```

**运行步骤：**

**1. 克隆仓库（或下载文件）**

```bash
git clone https://github.com/huzhenyuan/eth-poa.git
cd eth-poa
```

**2. 创建配置文件**

```bash
# 复制示例配置
cp config.yaml my_network.yaml

# 编辑配置文件
vim my_network.yaml  # 或使用其他编辑器
```

**3. 运行生成脚本**

```bash
# 给脚本添加执行权限
chmod +x generate_network.py

# 使用默认配置 (config.yaml)
python3 generate_network.py

# 或使用自定义配置文件
python3 generate_network.py my_network.yaml

# 指定输出目录
python3 generate_network.py my_network.yaml -o my_output_dir
```

**脚本输出示例：**

```
============================================================
以太坊PoA私有网络配置生成器
============================================================

输出目录: /path/to/ethereum-poa-network

创建节点目录...
  ✓ ethereum-poa-network/node_producer1
  ✓ ethereum-poa-network/node_producer2
  ✓ ethereum-poa-network/node_producer3
  ✓ ethereum-poa-network/node_syncher1

创建密码文件...
  ✓ ethereum-poa-network/node_producer1_password.txt
  ✓ ethereum-poa-network/node_producer2_password.txt
  ✓ ethereum-poa-network/node_producer3_password.txt
  ✓ ethereum-poa-network/node_syncher1_password.txt

创建账户...
  ✓ producer1: 0xc0a55ae58fb8e26f7874e865ee143f033d445927
  ✓ producer2: 0x8c59707ccf4c996bdb6163a3a759baadf82dae6a
  ✓ producer3: 0x1234567890abcdef1234567890abcdef12345678
  ✓ syncher1: 0xabcdef1234567890abcdef1234567890abcdef12

生成genesis.json...
  ✓ ethereum-poa-network/genesis.json (验证者: 3个)

初始化节点...
  ✓ producer1
  ✓ producer2
  ✓ producer3
  ✓ syncher1

获取区块生产者enode ID...
  ✓ producer1: 67cbdce9f4d0a82c...
  ✓ producer2: aa6c5c109f9cd6c4...
  ✓ producer3: 8ffcf8ba02dc25d1...

生成docker-compose.yml...
  ✓ ethereum-poa-network/docker-compose.yml (3个生产者, 1个同步者)

保存节点信息...
  ✓ ethereum-poa-network/node_info.json

============================================================
✓ 配置生成完成!
============================================================

所有文件已生成到: /path/to/ethereum-poa-network

下一步:
  1. cd ethereum-poa-network
  2. 运行: docker-compose up -d
  3. 查看节点信息: cat node_info.json
```

**4. 验证生成的文件**

```bash
cd ethereum-poa-network
ls -la
```

应该看到以下文件结构：
```
ethereum-poa-network/
├── docker-compose.yml           # Docker Compose 配置
├── genesis.json                 # 创世块配置
├── node_info.json               # 节点信息汇总
├── node_producer1/              # 生产者1数据目录
│   ├── geth/
│   │   └── nodekey
│   └── keystore/
│       └── UTC--2024-...
├── node_producer1_password.txt  # 生产者1密码
├── node_producer2/
├── node_producer2_password.txt
├── node_producer3/
├── node_producer3_password.txt
├── node_syncher1/
└── node_syncher1_password.txt
```

### 2.3 如何运行网络

生成配置文件后，使用 Docker Compose 启动网络非常简单。

#### 2.3.1 启动网络

**进入输出目录：**

```bash
cd ethereum-poa-network
```

**启动所有节点（前台运行）：**

```bash
docker-compose up
```

这将在前台启动所有容器，您可以看到实时日志输出：
```
Attaching to ethereum-producer1, ethereum-producer2, ethereum-producer3, ethereum-syncher1
producer1    | INFO [03-15|12:00:00.000] Starting Geth on Ethereum testnet...
producer1    | INFO [03-15|12:00:00.100] Maximum peer count                       ETH=50 LES=0 total=50
producer2    | INFO [03-15|12:00:00.200] Starting peer-to-peer node               instance=Geth/v1.13.14
producer3    | INFO [03-15|12:00:01.000] Block synchronisation started
syncher1     | INFO [03-15|12:00:01.500] Imported new chain segment               blocks=1 txs=0
...
```

**启动所有节点（后台运行）：**

```bash
docker-compose up -d
```

后台启动后，可以使用以下命令查看状态：

```bash
# 查看容器状态
docker-compose ps

# 输出示例：
         Name                       Command              State                    Ports
-------------------------------------------------------------------------------------------------------------
ethereum-producer1   geth --datadir /root/.ethe ...   Up      0.0.0.0:30306->30306/tcp, 0.0.0.0:8545->8545/tcp
ethereum-producer2   geth --datadir /root/.ethe ...   Up      0.0.0.0:30307->30307/tcp, 0.0.0.0:8546->8546/tcp
ethereum-producer3   geth --datadir /root/.ethe ...   Up      0.0.0.0:30308->30308/tcp, 0.0.0.0:8547->8547/tcp
ethereum-syncher1    geth --datadir /root/.ethe ...   Up      0.0.0.0:30309->30309/tcp, 0.0.0.0:8548->8548/tcp
```

#### 2.3.2 查看日志

**查看所有容器的日志：**

```bash
docker-compose logs -f
```

**查看特定节点的日志：**

```bash
# 查看 producer1 的日志
docker-compose logs -f producer1

# 查看最近100行
docker-compose logs --tail=100 producer1

# 只查看错误信息
docker-compose logs producer1 | grep ERROR
```

**日志示例（正常运行）：**

```
producer1    | INFO [03-15|12:00:05.000] Imported new chain segment               blocks=1  txs=0  mgas=0.000  elapsed=2.000ms  mgasps=0.000  number=1  hash=0x1234..
producer1    | INFO [03-15|12:00:10.000] Successfully sealed new block            number=2  hash=0x5678..  elapsed=1.500s
producer2    | INFO [03-15|12:00:10.100] Block synchronisation started
producer2    | INFO [03-15|12:00:10.200] Imported new chain segment               blocks=2  txs=0
syncher1     | INFO [03-15|12:00:10.300] Syncing blockchain                       downloaded=2  imported=2  remaining=0
```

#### 2.3.3 停止网络

**优雅停止所有节点：**

```bash
docker-compose down
```

这将停止并删除所有容器，但保留数据卷（区块链数据不会丢失）。

**停止但不删除容器：**

```bash
docker-compose stop
```

稍后可以使用 `docker-compose start` 重新启动。

**完全清理（包括数据）：**

```bash
# 停止并删除容器、网络
docker-compose down

# 删除所有节点数据（谨慎使用！）
rm -rf node_*
rm genesis.json docker-compose.yml node_info.json
```

#### 2.3.4 验证网络运行状态

**方法一：使用 curl 检查 RPC 接口**

```bash
# 检查 producer1 (端口 8545)
curl -X POST --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  -H "Content-Type: application/json" \
  http://localhost:8545

# 预期输出（区块高度会持续增长）：
{"jsonrpc":"2.0","id":1,"result":"0x64"}  # 0x64 = 100 区块

# 检查节点对等连接数
curl -X POST --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' \
  -H "Content-Type: application/json" \
  http://localhost:8545

# 预期输出：
{"jsonrpc":"2.0","id":1,"result":"0x3"}  # 连接了 3 个对等节点
```

**方法二：使用 geth attach 连接控制台**

```bash
# 连接到 producer1
docker exec -it ethereum-producer1 geth attach /root/.ethereum/geth.ipc

# 在控制台中检查
> eth.blockNumber
150

> net.peerCount
3

> admin.peers.length
3
```

**方法三：检查区块生成**

```bash
# 监控区块增长
watch -n 2 'curl -s -X POST --data "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}" -H "Content-Type: application/json" http://localhost:8545 | jq -r ".result" | xargs printf "%d\n"'

# 输出会每2秒刷新，显示当前区块高度
100
105
110
115
...
```

#### 2.3.5 网络管理常用命令

**重启特定节点：**

```bash
# 重启 producer1
docker-compose restart producer1

# 重启所有生产者
docker-compose restart producer1 producer2 producer3
```

**查看资源使用情况：**

```bash
# 查看 CPU 和内存使用
docker stats

# 输出示例：
CONTAINER ID   NAME                  CPU %   MEM USAGE / LIMIT     MEM %
abc123         ethereum-producer1    5.20%   256MiB / 2GiB        12.50%
def456         ethereum-producer2    4.80%   245MiB / 2GiB        12.00%
ghi789         ethereum-producer3    5.10%   251MiB / 2GiB        12.30%
jkl012         ethereum-syncher1     2.50%   180MiB / 2GiB        8.80%
```

**扩展网络：**

如果需要添加新节点：

```bash
# 1. 编辑 config.yaml，添加新节点
vim config.yaml

# 2. 重新运行生成脚本
python3 generate_network.py config.yaml

# 3. 重启网络
docker-compose down
docker-compose up -d
```

### 2.4 连接到节点控制台

连接到节点控制台后，您可以执行各种以太坊操作，包括查询状态、发送交易、管理账户等。

#### 2.4.1 连接方式

**方式一：通过 IPC 连接（推荐，最快）**

```bash
# 连接到 producer1
docker exec -it ethereum-producer1 geth attach /root/.ethereum/geth.ipc

# 连接到 producer2
docker exec -it ethereum-producer2 geth attach /root/.ethereum/geth.ipc

# 连接到 syncher1
docker exec -it ethereum-syncher1 geth attach /root/.ethereum/geth.ipc
```

**方式二：通过 HTTP RPC 连接**

```bash
# 从主机连接（需要先安装 geth）
geth attach http://localhost:8545   # producer1
geth attach http://localhost:8546   # producer2
geth attach http://localhost:8547   # producer3
geth attach http://localhost:8548   # syncher1
```

**方式三：通过 WebSocket 连接**

如果启用了 WebSocket（需要在 docker-compose.yml 中添加 `--ws` 参数）：

```bash
geth attach ws://localhost:8546
```

**连接成功示例：**

```
Welcome to the Geth JavaScript console!

instance: Geth/v1.13.14-stable-2bd6bd01/linux-amd64/go1.21.7
coinbase: 0xc0a55ae58fb8e26f7874e865ee143f033d445927
at block: 245 (Sat Nov 09 2025 03:01:15 GMT+0000 (UTC))
 datadir: /root/.ethereum
 modules: admin:1.0 clique:1.0 debug:1.0 eth:1.0 miner:1.0 net:1.0 
          personal:1.0 rpc:1.0 txpool:1.0 web3:1.0

To exit, press ctrl-d or type exit
>
```

#### 2.4.2 常用控制台命令

以下是在 Geth JavaScript 控制台中常用的命令列表。

**1. 基础信息查询**

```javascript
// 查看当前区块高度
> eth.blockNumber
245

// 查看同步状态
> eth.syncing
false  // false 表示已同步，如果在同步中会显示同步进度

// 查看网络 ID
> net.version
"123454321"

// 查看节点信息
> admin.nodeInfo
{
  enode: "enode://67cbd...",
  enr: "enr:-...",
  id: "67cbd...",
  ip: "172.20.0.2",
  listenAddr: "[::]:30306",
  name: "Geth/v1.13.14-stable/linux-amd64/go1.21.7",
  ports: {
    discovery: 30306,
    listener: 30306
  },
  protocols: {
    eth: {...},
    snap: {...}
  }
}

// 查看客户端版本
> web3.clientVersion
"Geth/v1.13.14-stable-2bd6bd01/linux-amd64/go1.21.7"

// 查看当前 Gas 价格
> eth.gasPrice
1000000000  // Wei，即 1 Gwei
```

**2. 账户管理**

```javascript
// 列出所有账户
> eth.accounts
["0xc0a55ae58fb8e26f7874e865ee143f033d445927"]

// 查看账户余额（返回 Wei）
> eth.getBalance(eth.accounts[0])
1000000000000000000  // 1 ETH

// 转换为 Ether
> web3.fromWei(eth.getBalance(eth.accounts[0]), "ether")
"1"

// 查看账户交易计数（nonce）
> eth.getTransactionCount(eth.accounts[0])
0

// 创建新账户
> personal.newAccount("new_password")
"0x1234567890abcdef1234567890abcdef12345678"

// 解锁账户（300秒）
> personal.unlockAccount(eth.accounts[0], "password", 300)
true

// 锁定账户
> personal.lockAccount(eth.accounts[0])
true

// 列出所有账户（包括密钥库路径）
> personal.listAccounts
["0xc0a55ae58fb8e26f7874e865ee143f033d445927"]
```

**3. 网络和对等节点管理**

```javascript
// 查看对等节点数量
> net.peerCount
3

// 查看是否在监听
> net.listening
true

// 查看所有对等节点详情
> admin.peers
[{
    caps: ["eth/68", "snap/1"],
    enode: "enode://aa6c5c...",
    id: "4f674866...",
    name: "Geth/v1.13.14-stable",
    network: {
      inbound: false,
      localAddress: "172.20.0.2:30306",
      remoteAddress: "172.20.0.3:45978",
      static: false,
      trusted: false
    },
    protocols: {
      eth: {
        difficulty: 100,
        head: "0x1234...",
        version: 68
      }
    }
}]

// 添加对等节点
> admin.addPeer("enode://node_id@ip:port")
true

// 移除对等节点
> admin.removePeer("enode://node_id@ip:port")
true

// 查看信任的对等节点
> admin.peers.filter(p => p.network.trusted)
[]
```

**4. 区块查询**

```javascript
// 获取最新区块
> eth.getBlock("latest")
{
  difficulty: 2,
  extraData: "0xd883010e0...",
  gasLimit: 800000000,
  gasUsed: 0,
  hash: "0x669ca01...",
  miner: "0xc0a55ae58fb8e26f7874e865ee143f033d445927",
  number: 245,
  parentHash: "0x123abc...",
  receiptsRoot: "0x56dde...",
  size: 622,
  stateRoot: "0x789def...",
  timestamp: 1731121275,
  transactions: [],
  transactionsRoot: "0x56dde..."
}

// 获取指定高度的区块
> eth.getBlock(100)

// 获取指定哈希的区块
> eth.getBlock("0x669ca01...")

// 只获取区块头（不含交易详情）
> eth.getBlock(100, false)

// 获取包含完整交易的区块
> eth.getBlock(100, true)

// 获取创世块
> eth.getBlock(0)
```

**5. 交易操作**

```javascript
// 发送交易
> eth.sendTransaction({
    from: eth.accounts[0],
    to: "0x8c59707CcF4c996bDB6163A3a759baADf82dAe6A",
    value: web3.toWei(0.1, "ether"),
    gas: 21000,
    gasPrice: web3.toWei(20, "gwei")
})
"0x58b6458922733da50d6230560cd033d147532beb64107e75dc246853cdb6a8ec"

// 查看交易详情
> eth.getTransaction("0x58b64589...")
{
  blockHash: "0x669ca015...",
  blockNumber: 246,
  from: "0xc0a55ae58fb8e26f7874e865ee143f033d445927",
  gas: 21000,
  gasPrice: 20000000000,
  hash: "0x58b64589...",
  input: "0x",
  nonce: 0,
  to: "0x8c59707ccf4c996bdb6163a3a759baadf82dae6a",
  transactionIndex: 0,
  value: 100000000000000000,
  v: "0x1",
  r: "0x1d2bb3ce...",
  s: "0x28209c4b..."
}

// 查看交易回执（确认交易已执行）
> eth.getTransactionReceipt("0x58b64589...")
{
  blockHash: "0x669ca015...",
  blockNumber: 246,
  contractAddress: null,
  cumulativeGasUsed: 21000,
  from: "0xc0a55ae58fb8e26f7874e865ee143f033d445927",
  gasUsed: 21000,
  logs: [],
  logsBloom: "0x00000000...",
  status: "0x1",  // 0x1 = 成功, 0x0 = 失败
  to: "0x8c59707ccf4c996bdb6163a3a759baadf82dae6a",
  transactionHash: "0x58b64589...",
  transactionIndex: 0,
  type: "0x2"
}

// 查看待处理交易
> eth.pendingTransactions
[]

// 估算交易 Gas
> eth.estimateGas({
    from: eth.accounts[0],
    to: "0x8c59707CcF4c996bDB6163A3a759baADf82dAe6A",
    value: web3.toWei(0.1, "ether")
})
21000
```

**6. 挖矿控制**

```javascript
// 检查是否在挖矿
> eth.mining
true

// 开始挖矿
> miner.start()
null

// 停止挖矿
> miner.stop()
null

// 查看挖矿算力
> eth.hashrate
0  // Clique PoA 不需要算力

// 设置挖矿收益地址
> miner.setEtherbase(eth.accounts[0])
true

// 查看当前挖矿地址
> eth.coinbase
"0xc0a55ae58fb8e26f7874e865ee143f033d445927"
```

**7. Clique 治理命令**

```javascript
// 查看当前验证者
> clique.getSigners()
[
  "0xc0a55ae58fb8e26f7874e865ee143f033d445927",
  "0x8c59707ccf4c996bdb6163a3a759baadf82dae6a",
  "0x1234567890abcdef1234567890abcdef12345678"
]

// 提议添加验证者
> clique.propose("0xabcdef1234567890abcdef1234567890abcdef12", true)
null

// 提议移除验证者
> clique.propose("0x1234567890abcdef1234567890abcdef12345678", false)
null

// 查看所有提案
> clique.proposals()
{
  0xabcdef1234567890abcdef1234567890abcdef12: true,
  0x1234567890abcdef1234567890abcdef12345678: false
}

// 撤销提案
> clique.discard("0xabcdef1234567890abcdef1234567890abcdef12")
null

// 查看快照
> clique.getSnapshot()
{
  hash: "0x669ca015...",
  number: 246,
  recents: {...},
  signers: {
    "0x1234567890abcdef1234567890abcdef12345678": {},
    "0x8c59707ccf4c996bdb6163a3a759baadf82dae6a": {},
    "0xc0a55ae58fb8e26f7874e865ee143f033d445927": {}
  },
  tally: {
    "0xabcdef1234567890abcdef1234567890abcdef12": 1
  },
  votes: [...]
}

// 查看指定区块的快照
> clique.getSnapshot(30000)
```

**8. 交易池管理**

```javascript
// 查看交易池状态
> txpool.status
{
  pending: 5,  // 待处理的交易数
  queued: 2    // 排队的交易数
}

// 查看交易池内容
> txpool.content
{
  pending: {
    0xc0a55ae58fb8e26f7874e865ee143f033d445927: {
      0: {...},  // nonce 0 的交易
      1: {...}   // nonce 1 的交易
    }
  },
  queued: {}
}

// 查看交易池详细信息
> txpool.inspect
{
  pending: {
    0xc0a55ae58fb8e26f7874e865ee143f033d445927: {
      0: "0x8c59707... value: 100000000000000000 wei + 21000 gas × 1000000000 wei",
      1: "0xabcdef... value: 50000000000000000 wei + 21000 gas × 1000000000 wei"
    }
  },
  queued: {}
}
```

**9. 调试和诊断**

```javascript
// 获取区块的 RLP 编码
> debug.getBlockRlp(100)
"0xf90217f90212..."

// 打印区块信息
> debug.printBlock(100)

// 追踪交易执行
> debug.traceTransaction("0x58b64589...")
{
  gas: 21000,
  returnValue: "",
  structLogs: [...]
}

// 查看虚拟机追踪（详细）
> debug.traceTransaction("0x58b64589...", {tracer: "callTracer"})

// 获取坏区块
> debug.getBadBlocks()
[]

// 设置日志级别
> debug.verbosity(4)  // 0-5，数字越大越详细

// 查看内存统计
> debug.memStats()
{
  Alloc: 12345678,
  TotalAlloc: 98765432,
  ...
}
```

**10. Web3 实用工具**

```javascript
// SHA3 哈希
> web3.sha3("Hello World")
"0x592fa743..."

// 单位转换
> web3.toWei(1, "ether")
"1000000000000000000"

> web3.fromWei("1000000000000000000", "ether")
"1"

> web3.toHex(255)
"0xff"

> web3.toAscii("0x48656c6c6f")
"Hello"

> web3.fromAscii("Hello")
"0x48656c6c6f"

// 地址校验
> web3.isAddress("0xc0a55ae58fb8e26f7874e865ee143f033d445927")
true

> web3.isAddress("invalid_address")
false

// 检查校验和地址
> web3.toChecksumAddress("0xc0a55ae58fb8e26f7874e865ee143f033d445927")
"0xC0A55ae58fb8E26f7874E865eE143f033D445927"
```

**11. 事件监听和过滤器**

```javascript
// 监听新区块
> var filter = eth.filter("latest")
> filter.watch(function(error, blockHash) {
    if (!error) {
        console.log("新区块:", blockHash);
    }
})

// 监听待处理交易
> var pendingFilter = eth.filter("pending")
> pendingFilter.watch(function(error, txHash) {
    if (!error) {
        console.log("新交易:", txHash);
    }
})

// 停止监听
> filter.stopWatching()

// 创建日志过滤器（智能合约事件）
> var logFilter = eth.filter({
    fromBlock: 0,
    toBlock: "latest",
    address: "0xContractAddress",
    topics: ["0xEventSignature"]
})

> logFilter.get(function(error, logs) {
    console.log(logs);
})
```

**12. 批量操作和脚本**

```javascript
// 批量查询余额
> eth.accounts.forEach(function(addr) {
    console.log(addr + ": " + web3.fromWei(eth.getBalance(addr), "ether") + " ETH");
})

// 等待区块达到特定高度
> function waitForBlock(targetBlock) {
    var interval = setInterval(function() {
        var current = eth.blockNumber;
        console.log("当前区块:", current);
        if (current >= targetBlock) {
            console.log("已达到目标区块:", targetBlock);
            clearInterval(interval);
        }
    }, 5000);  // 每5秒检查一次
}
> waitForBlock(1000)

// 监控特定地址的余额变化
> function monitorBalance(address) {
    var lastBalance = eth.getBalance(address);
    var filter = eth.filter("latest");
    filter.watch(function() {
        var currentBalance = eth.getBalance(address);
        if (!currentBalance.equals(lastBalance)) {
            console.log("余额变化:", web3.fromWei(currentBalance, "ether"), "ETH");
            lastBalance = currentBalance;
        }
    });
}
> monitorBalance(eth.accounts[0])
```

#### 2.4.3 退出控制台

```javascript
// 方法一：输入 exit
> exit

// 方法二：按 Ctrl+D
```

---

## 3. 故障排除

### 3.1 常见问题

**问题1：节点无法相互连接**

**症状：**
```bash
> net.peerCount
0
```

**解决方案：**

1. **检查网络配置**
   ```bash
   docker network ls
   docker network inspect ethereum-poa-network_ethnet
   ```

2. **验证 bootnode 配置**
   ```bash
   # 检查 docker-compose.yml 中的 bootnode 参数
   grep "bootnodes" docker-compose.yml
   ```

3. **检查防火墙设置**
   ```bash
   # 确保 P2P 端口未被阻止
   sudo ufw allow 30306/tcp
   sudo ufw allow 30306/udp
   ```

4. **重启网络**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

**问题2：节点不出块**

**症状：**
```bash
> eth.blockNumber
0  # 长时间保持为 0
```

**解决方案：**

1. **检查挖矿状态**
   ```javascript
   > eth.mining
   false  // 应该为 true
   
   > miner.start()  // 手动启动
   ```

2. **检查账户解锁**
   ```bash
   # 查看日志
   docker-compose logs producer1 | grep "unlock"
   ```

3. **验证验证者地址**
   ```javascript
   > clique.getSigners()
   // 应包含当前节点地址
   ```

**问题3：交易一直处于 pending 状态**

**解决方案：**

1. **检查 Gas 价格**
   ```javascript
   > eth.gasPrice  // 确保交易 gas 价格 >= 网络 gas 价格
   ```

2. **检查 nonce**
   ```javascript
   > eth.getTransactionCount(eth.accounts[0])
   // 确保交易 nonce 正确
   ```

3. **查看交易池**
   ```javascript
   > txpool.status
   > txpool.content
   ```

**问题4：Docker 容器频繁重启**

**解决方案：**

1. **查看容器日志**
   ```bash
   docker-compose logs --tail=100 producer1
   ```

2. **检查资源限制**
   ```bash
   docker stats
   # 确保有足够的 CPU 和内存
   ```

3. **检查磁盘空间**
   ```bash
   df -h
   ```

**问题5：RPC 连接被拒绝**

**症状：**
```bash
curl: (7) Failed to connect to localhost port 8545: Connection refused
```

**解决方案：**

1. **检查端口映射**
   ```bash
   docker-compose ps
   # 确保端口正确映射
   ```

2. **检查 RPC 配置**
   ```bash
   docker-compose logs producer1 | grep "HTTP endpoint"
   # 应显示: HTTP endpoint opened url=http://0.0.0.0:8545
   ```

3. **测试内部连接**
   ```bash
   docker exec ethereum-producer1 geth attach /root/.ethereum/geth.ipc
   ```

### 3.2 性能优化建议

**1. 调整区块 Gas 上限**

```yaml
# config.yaml
network:
  gas_limit: "1000000000"  # 增加以支持更多交易
```

**2. 减少出块时间（开发环境）**

```yaml
network:
  block_period: 1  # 1秒出块，更快的交易确认
```

**3. 增加缓存大小**

在 docker-compose.yml 中添加：
```yaml
command: >
  ...
  --cache 4096
  --cache.database 50
  --cache.trie 15
```

**4. 启用快照同步**

```yaml
command: >
  ...
  --snapshot
```

---

## 4. 高级用途

### 4.1 智能合约部署

**使用 Remix IDE 部署：**

1. 打开 [Remix IDE](https://remix.ethereum.org/)
2. 编写智能合约
3. 编译合约
4. 在 "Deploy & Run Transactions" 中：
   - Environment: 选择 "Injected Web3" 或 "Web3 Provider"
   - 输入 RPC URL: `http://localhost:8545`
   - 部署合约

**使用控制台部署：**

```javascript
// 简单的存储合约示例
var contractCode = "0x608060405234801561001057600080fd5b50..."

// 部署
var tx = eth.sendTransaction({
    from: eth.accounts[0],
    data: contractCode,
    gas: 1000000
})

// 获取合约地址
var receipt = eth.getTransactionReceipt(tx)
var contractAddress = receipt.contractAddress
console.log("合约地址:", contractAddress)
```

### 4.2 与其他工具集成

**Hardhat 配置：**

```javascript
// hardhat.config.js
module.exports = {
  networks: {
    localhost: {
      url: "http://localhost:8545",
      accounts: ["0xPRIVATE_KEY"]
    }
  }
};
```

**Truffle 配置：**

```javascript
// truffle-config.js
module.exports = {
  networks: {
    development: {
      host: "127.0.0.1",
      port: 8545,
      network_id: "123454321"
    }
  }
};
```

---

## 5. 注意事项

⚠️ **安全警告：**

1. **仅用于开发和测试**：本配置不适合生产环境
2. **密码管理**：生产环境应使用硬件钱包或 KMS
3. **RPC 暴露**：不要将 RPC 端口暴露到公网
4. **私钥安全**：永远不要分享或提交私钥到版本控制

⚠️ **性能注意：**

1. 过短的 `block_period` 会增加网络负担
2. 建议生产环境至少 3-5 个验证者
3. 定期备份节点数据目录

---

## 6. 参考资源

### 官方文档

- [Geth 官方文档](https://geth.ethereum.org/docs/)
- [Ethereum 官方文档](https://ethereum.org/developers/)
- [Clique PoA 规范 (EIP-225)](https://eips.ethereum.org/EIPS/eip-225)
- [Go Ethereum GitHub](https://github.com/ethereum/go-ethereum)

### 相关工具

- [Remix IDE](https://remix.ethereum.org/) - 智能合约开发 IDE
- [Hardhat](https://hardhat.org/) - 以太坊开发环境
- [Truffle](https://trufflesuite.com/) - 开发框架
- [Web3.js](https://web3js.readthedocs.io/) - JavaScript 库
- [Ethers.js](https://docs.ethers.io/) - 轻量级 JavaScript 库

### 社区资源

- [Ethereum Stack Exchange](https://ethereum.stackexchange.com/)
- [Geth Discord](https://discord.gg/ethereum)
- [/r/ethereum](https://reddit.com/r/ethereum)

---

## 7. 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 8. 贡献

欢迎提交 Issue 和 Pull Request！

**贡献指南：**

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 9. 更新日志

### v1.0.0 (2025-11-09)
- ✨ 初始版本发布
- ✨ 支持自动化网络生成
- ✨ 支持任意数量的生产者和同步节点
- 📝 完整的中文文档

---

**作者：** huzhenyuan  
**最后更新：** 2025-11-09