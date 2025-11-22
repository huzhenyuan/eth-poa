#!/usr/bin/env python3
"""
以太坊 PoA 网络 TPS 性能测试脚本

功能：
1. 创建 2000 个以太坊子账号
2. 从 producer1 账号分配余额到所有子账号
3. 使用前 1000 个账号作为发送方，后 1000 个作为接收方进行交易
4. 记录和显示 TPS 性能指标
5. 支持多线程或异步方式提高效率
"""

import os
import sys
import time
import json
import asyncio
from typing import List, Dict, Tuple
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from web3 import Web3
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # For web3.py v6+
    from web3.middleware import ExtraDataToPOAMiddleware as geth_poa_middleware
from eth_account import Account


@dataclass
class TestConfig:
    """测试配置"""
    rpc_url: str
    producer_private_key: str
    transfer_amount: str  # 单次转账金额（ETH）
    distribution_amount: str  # 分配给每个子账号的金额（ETH）
    concurrency: int  # 并发数
    num_accounts: int = 2000  # 子账号数量
    gas_limit: int = 21000  # 基础转账gas限制
    gas_price_gwei: int = 20  # Gas价格（Gwei）
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 1.0  # 重试延迟（秒）


@dataclass
class TransactionStats:
    """交易统计信息"""
    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    start_time: float = 0
    end_time: float = 0
    
    def get_duration(self) -> float:
        """获取总耗时（秒）"""
        if self.end_time == 0:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    def get_tps(self) -> float:
        """获取平均TPS"""
        duration = self.get_duration()
        if duration <= 0:
            return 0
        return self.successful_transactions / duration
    
    def display(self):
        """显示统计信息"""
        duration = self.get_duration()
        tps = self.get_tps()
        
        print("\n" + "=" * 60)
        print("TPS 测试统计结果")
        print("=" * 60)
        print(f"总交易数:       {self.total_transactions}")
        print(f"成功交易数:     {self.successful_transactions}")
        print(f"失败交易数:     {self.failed_transactions}")
        print(f"总耗时:         {duration:.2f} 秒")
        print(f"平均 TPS:       {tps:.2f} 交易/秒")
        print(f"成功率:         {(self.successful_transactions / self.total_transactions * 100) if self.total_transactions > 0 else 0:.2f}%")
        print("=" * 60)


class TPSTest:
    """TPS 性能测试类"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.w3 = self._init_web3()
        self.producer_account = Account.from_key(config.producer_private_key)
        self.sub_accounts: List[Account] = []
        self.stats = TransactionStats()
        
    def _init_web3(self) -> Web3:
        """初始化 Web3 连接"""
        print(f"连接到以太坊节点: {self.config.rpc_url}")
        w3 = Web3(Web3.HTTPProvider(self.config.rpc_url))
        
        # 添加 PoA 中间件
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not w3.is_connected():
            raise Exception("无法连接到以太坊节点")
        
        print(f"✓ 成功连接到节点")
        print(f"  链 ID: {w3.eth.chain_id}")
        print(f"  区块高度: {w3.eth.block_number}")
        
        return w3
    
    def create_accounts(self):
        """创建子账号"""
        print(f"\n创建 {self.config.num_accounts} 个子账号...")
        
        self.sub_accounts = []
        for i in range(self.config.num_accounts):
            account = Account.create()
            self.sub_accounts.append(account)
            
            if (i + 1) % 500 == 0:
                print(f"  已创建 {i + 1} 个账号...")
        
        print(f"✓ 成功创建 {len(self.sub_accounts)} 个子账号")
        
        # 保存账号信息到文件
        accounts_data = [
            {
                'index': i,
                'address': account.address,
                'private_key': account.key.hex()
            }
            for i, account in enumerate(self.sub_accounts)
        ]
        
        with open('test_accounts.json', 'w') as f:
            json.dump(accounts_data, f, indent=2)
        
        print(f"✓ 账号信息已保存到 test_accounts.json")
    
    def load_accounts(self):
        """从文件加载账号"""
        if not os.path.exists('test_accounts.json'):
            return False
        
        print("\n从文件加载已有账号...")
        
        try:
            with open('test_accounts.json', 'r') as f:
                accounts_data = json.load(f)
            
            if len(accounts_data) != self.config.num_accounts:
                print(f"  账号数量不匹配（期望 {self.config.num_accounts}，实际 {len(accounts_data)}）")
                return False
            
            self.sub_accounts = []
            for data in accounts_data:
                account = Account.from_key(data['private_key'])
                self.sub_accounts.append(account)
            
            print(f"✓ 成功加载 {len(self.sub_accounts)} 个账号")
            return True
            
        except Exception as e:
            print(f"  加载失败: {e}")
            return False
    
    def distribute_balance(self):
        """从 producer 账号分配余额到所有子账号"""
        print("\n开始分配余额...")
        
        # 检查 producer 余额
        producer_balance = self.w3.eth.get_balance(self.producer_account.address)
        producer_balance_eth = Decimal(self.w3.from_wei(producer_balance, 'ether'))
        print(f"Producer 余额: {producer_balance_eth} ETH")
        
        # 计算需要的总金额
        distribution_amount_wei = self.w3.to_wei(self.config.distribution_amount, 'ether')
        total_needed = distribution_amount_wei * self.config.num_accounts
        gas_price = self.w3.to_wei(self.config.gas_price_gwei, 'gwei')
        total_gas_cost = gas_price * self.config.gas_limit * self.config.num_accounts
        total_needed_with_gas = total_needed + total_gas_cost
        
        total_needed_eth = Decimal(self.w3.from_wei(total_needed_with_gas, 'ether'))
        print(f"需要分配的总金额（含 gas）: {total_needed_eth} ETH")
        
        if producer_balance < total_needed_with_gas:
            raise Exception(f"Producer 余额不足！需要 {total_needed_eth} ETH，但只有 {producer_balance_eth} ETH")
        
        # 获取当前 nonce
        nonce = self.w3.eth.get_transaction_count(self.producer_account.address)
        print(f"起始 nonce: {nonce}")
        
        # 分批发送交易
        batch_size = 100
        successful = 0
        failed = 0
        
        print(f"\n开始分配（批次大小: {batch_size}）...")
        
        for i in range(0, len(self.sub_accounts), batch_size):
            batch = self.sub_accounts[i:i+batch_size]
            batch_start = i
            batch_end = min(i + batch_size, len(self.sub_accounts))
            
            print(f"\n处理批次 {batch_start + 1}-{batch_end}...")
            
            # 发送批次中的所有交易
            tx_hashes = []
            for j, account in enumerate(batch):
                try:
                    tx = {
                        'from': self.producer_account.address,
                        'to': account.address,
                        'value': distribution_amount_wei,
                        'gas': self.config.gas_limit,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'chainId': self.w3.eth.chain_id
                    }
                    
                    signed_tx = self.w3.eth.account.sign_transaction(tx, self.producer_account.key)
                    tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                    tx_hashes.append(tx_hash)
                    nonce += 1
                    
                except Exception as e:
                    print(f"  ✗ 账号 {batch_start + j + 1} 发送失败: {e}")
                    failed += 1
                    nonce += 1  # 仍然增加 nonce
                    continue
            
            # 等待批次中的交易确认
            print(f"  等待 {len(tx_hashes)} 笔交易确认...")
            for k, tx_hash in enumerate(tx_hashes):
                try:
                    receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt['status'] == 1:
                        successful += 1
                    else:
                        failed += 1
                    
                    if (k + 1) % 20 == 0:
                        print(f"    已确认 {k + 1}/{len(tx_hashes)} 笔交易...")
                        
                except Exception as e:
                    print(f"  ✗ 交易 {batch_start + k + 1} 确认失败: {e}")
                    failed += 1
            
            print(f"  批次完成: 成功 {successful}, 失败 {failed}")
        
        print(f"\n✓ 余额分配完成")
        print(f"  成功: {successful} 笔")
        print(f"  失败: {failed} 笔")
        
        if failed > 0:
            print(f"\n⚠️  警告: {failed} 笔交易失败，可能影响后续测试")
    
    def verify_balances(self) -> Tuple[int, int]:
        """验证子账号余额"""
        print("\n验证账号余额...")
        
        ready_count = 0
        empty_count = 0
        min_balance = self.w3.to_wei(self.config.transfer_amount, 'ether') * 10  # 至少能发送10笔交易
        
        for i, account in enumerate(self.sub_accounts):
            balance = self.w3.eth.get_balance(account.address)
            if balance >= min_balance:
                ready_count += 1
            else:
                empty_count += 1
            
            if (i + 1) % 500 == 0:
                print(f"  已检查 {i + 1} 个账号...")
        
        print(f"\n账号余额验证结果:")
        print(f"  准备就绪: {ready_count} 个")
        print(f"  余额不足: {empty_count} 个")
        
        return ready_count, empty_count
    
    def _send_transaction(self, sender: Account, receiver: Account, nonce: int) -> bool:
        """
        发送单笔交易（不等待确认）
        
        注意：返回 True 表示交易成功提交到交易池，不代表交易已被确认
        """
        try:
            transfer_amount_wei = self.w3.to_wei(self.config.transfer_amount, 'ether')
            gas_price = self.w3.to_wei(self.config.gas_price_gwei, 'gwei')
            
            tx = {
                'from': sender.address,
                'to': receiver.address,
                'value': transfer_amount_wei,
                'gas': self.config.gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            }
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, sender.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            return True
            
        except Exception as e:
            # 静默处理错误以避免输出过多，常见错误包括 nonce 冲突、余额不足等
            return False
    
    async def send_transaction_async(self, sender: Account, receiver: Account, nonce: int) -> bool:
        """
        异步发送单笔交易（包装器）
        
        注意：当前 web3.py 的操作是同步的，此方法为异步接口的包装
        """
        return self._send_transaction(sender, receiver, nonce)
    
    def send_transaction_sync(self, sender: Account, receiver: Account, nonce: int) -> bool:
        """同步发送单笔交易（包装器）"""
        return self._send_transaction(sender, receiver, nonce)
    
    def run_test_threaded(self, duration_seconds: int = 60):
        """使用多线程运行 TPS 测试"""
        print(f"\n开始 TPS 测试（多线程模式，持续 {duration_seconds} 秒）...")
        print(f"并发数: {self.config.concurrency}")
        print(f"转账金额: {self.config.transfer_amount} ETH")
        
        # 分组：前 1000 个作为发送方，后 1000 个作为接收方
        senders = self.sub_accounts[:1000]
        receivers = self.sub_accounts[1000:]
        
        # 获取每个发送方的初始 nonce
        sender_nonces = {}
        print("\n获取发送方账号 nonce...")
        for i, sender in enumerate(senders):
            sender_nonces[sender.address] = self.w3.eth.get_transaction_count(sender.address)
            if (i + 1) % 200 == 0:
                print(f"  已获取 {i + 1}/1000 个账号的 nonce...")
        
        # 初始化统计
        self.stats = TransactionStats()
        self.stats.start_time = time.time()
        
        # 使用线程池发送交易
        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            futures = []
            test_end_time = time.time() + duration_seconds
            current_sender_idx = 0
            
            print("\n开始发送交易...\n")
            
            # 持续提交任务直到时间结束
            while time.time() < test_end_time:
                # 选择发送方和接收方
                sender = senders[current_sender_idx % len(senders)]
                receiver = receivers[current_sender_idx % len(receivers)]
                
                # 获取并增加 nonce
                nonce = sender_nonces[sender.address]
                sender_nonces[sender.address] += 1
                
                # 提交任务
                future = executor.submit(self.send_transaction_sync, sender, receiver, nonce)
                futures.append(future)
                
                current_sender_idx += 1
                self.stats.total_transactions += 1
                
                # 显示进度
                if self.stats.total_transactions % 100 == 0:
                    elapsed = time.time() - self.stats.start_time
                    current_tps = self.stats.total_transactions / elapsed if elapsed > 0 else 0
                    print(f"  已提交 {self.stats.total_transactions} 笔交易 | 当前 TPS: {current_tps:.2f} | "
                          f"剩余时间: {int(test_end_time - time.time())} 秒")
                
                # 限制未完成的futures数量，避免内存溢出
                if len(futures) > self.config.concurrency * 10:
                    # 等待一些 futures 完成
                    done, futures = self._wait_for_some_futures(futures, self.config.concurrency * 5)
                    for future in done:
                        if future.result():
                            self.stats.successful_transactions += 1
                        else:
                            self.stats.failed_transactions += 1
            
            # 等待所有剩余任务完成
            print("\n等待剩余交易完成...")
            for future in as_completed(futures):
                try:
                    if future.result():
                        self.stats.successful_transactions += 1
                    else:
                        self.stats.failed_transactions += 1
                except Exception:
                    self.stats.failed_transactions += 1
        
        self.stats.end_time = time.time()
        
        # 显示统计结果
        self.stats.display()
    
    def _wait_for_some_futures(self, futures, count):
        """等待部分 futures 完成"""
        done = []
        pending = list(futures)
        
        for future in as_completed(futures):
            done.append(future)
            pending.remove(future)
            if len(done) >= count:
                break
        
        return done, pending
    
    async def run_test_async(self, duration_seconds: int = 60):
        """使用异步方式运行 TPS 测试"""
        print(f"\n开始 TPS 测试（异步模式，持续 {duration_seconds} 秒）...")
        print(f"并发数: {self.config.concurrency}")
        print(f"转账金额: {self.config.transfer_amount} ETH")
        
        # 分组：前 1000 个作为发送方，后 1000 个作为接收方
        senders = self.sub_accounts[:1000]
        receivers = self.sub_accounts[1000:]
        
        # 获取每个发送方的初始 nonce
        sender_nonces = {}
        print("\n获取发送方账号 nonce...")
        for i, sender in enumerate(senders):
            sender_nonces[sender.address] = self.w3.eth.get_transaction_count(sender.address)
            if (i + 1) % 200 == 0:
                print(f"  已获取 {i + 1}/1000 个账号的 nonce...")
        
        # 初始化统计
        self.stats = TransactionStats()
        self.stats.start_time = time.time()
        
        print("\n开始发送交易...\n")
        
        test_end_time = time.time() + duration_seconds
        current_sender_idx = 0
        tasks = []
        
        # 持续发送交易直到时间结束
        while time.time() < test_end_time:
            # 选择发送方和接收方
            sender = senders[current_sender_idx % len(senders)]
            receiver = receivers[current_sender_idx % len(receivers)]
            
            # 获取并增加 nonce
            nonce = sender_nonces[sender.address]
            sender_nonces[sender.address] += 1
            
            # 创建任务
            task = asyncio.create_task(self.send_transaction_async(sender, receiver, nonce))
            tasks.append(task)
            
            current_sender_idx += 1
            self.stats.total_transactions += 1
            
            # 显示进度
            if self.stats.total_transactions % 100 == 0:
                elapsed = time.time() - self.stats.start_time
                current_tps = self.stats.total_transactions / elapsed if elapsed > 0 else 0
                print(f"  已提交 {self.stats.total_transactions} 笔交易 | 当前 TPS: {current_tps:.2f} | "
                      f"剩余时间: {int(test_end_time - time.time())} 秒")
            
            # 限制并发任务数量
            if len(tasks) >= self.config.concurrency * 10:
                # 等待一些任务完成
                done, tasks = await self._wait_for_some_tasks(tasks, self.config.concurrency * 5)
                for task in done:
                    if task.result():
                        self.stats.successful_transactions += 1
                    else:
                        self.stats.failed_transactions += 1
            
            # 短暂休眠以避免过度占用 CPU
            await asyncio.sleep(0.001)
        
        # 等待所有剩余任务完成
        print("\n等待剩余交易完成...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, bool) and result:
                self.stats.successful_transactions += 1
            else:
                self.stats.failed_transactions += 1
        
        self.stats.end_time = time.time()
        
        # 显示统计结果
        self.stats.display()
    
    async def _wait_for_some_tasks(self, tasks, count):
        """等待部分任务完成"""
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # 继续等待直到达到指定数量
        while len(done) < count and pending:
            more_done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            done.update(more_done)
        
        return list(done), list(pending)


def load_config_from_env() -> TestConfig:
    """从环境变量加载配置"""
    return TestConfig(
        rpc_url=os.getenv('ETH_RPC_URL', 'http://localhost:8545'),
        producer_private_key=os.getenv('PRODUCER_PRIVATE_KEY', ''),
        transfer_amount=os.getenv('TRANSFER_AMOUNT', '0.001'),
        distribution_amount=os.getenv('DISTRIBUTION_AMOUNT', '0.1'),
        concurrency=int(os.getenv('CONCURRENCY', '50')),
        gas_price_gwei=int(os.getenv('GAS_PRICE_GWEI', '20'))
    )


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='以太坊 PoA 网络 TPS 性能测试工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用环境变量配置
  export ETH_RPC_URL="http://localhost:8545"
  export PRODUCER_PRIVATE_KEY="0x..."
  %(prog)s --create --distribute --test 60
  
  # 使用命令行参数
  %(prog)s --rpc http://localhost:8545 --key 0x... --create --distribute --test 60
  
  # 仅运行测试（假设账号已创建和分配）
  %(prog)s --test 60
  
  # 使用异步模式
  %(prog)s --test 60 --async
        """
    )
    
    parser.add_argument('--rpc', help='RPC 节点地址')
    parser.add_argument('--key', help='Producer 私钥')
    parser.add_argument('--transfer', default='0.001', help='单次转账金额（ETH，默认 0.001）')
    parser.add_argument('--distribution', default='0.1', help='分配给每个子账号的金额（ETH，默认 0.1）')
    parser.add_argument('--concurrency', type=int, default=50, help='并发数（默认 50）')
    parser.add_argument('--gas-price', type=int, default=20, help='Gas 价格（Gwei，默认 20）')
    
    parser.add_argument('--create', action='store_true', help='创建子账号')
    parser.add_argument('--distribute', action='store_true', help='分配余额到子账号')
    parser.add_argument('--test', type=int, metavar='SECONDS', help='运行 TPS 测试（指定持续秒数）')
    parser.add_argument('--async', dest='use_async', action='store_true', help='使用异步模式（默认使用多线程）')
    parser.add_argument('--verify', action='store_true', help='验证账号余额')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config_from_env()
    
    # 命令行参数覆盖环境变量
    if args.rpc:
        config.rpc_url = args.rpc
    if args.key:
        config.producer_private_key = args.key
    if args.transfer:
        config.transfer_amount = args.transfer
    if args.distribution:
        config.distribution_amount = args.distribution
    if args.concurrency:
        config.concurrency = args.concurrency
    if args.gas_price:
        config.gas_price_gwei = args.gas_price
    
    # 验证配置
    if not config.rpc_url:
        print("错误: 必须提供 RPC 节点地址（通过 --rpc 或环境变量 ETH_RPC_URL）")
        sys.exit(1)
    
    if (args.create or args.distribute) and not config.producer_private_key:
        print("错误: 创建账号或分配余额需要提供 Producer 私钥（通过 --key 或环境变量 PRODUCER_PRIVATE_KEY）")
        sys.exit(1)
    
    # 显示配置信息
    print("=" * 60)
    print("以太坊 PoA 网络 TPS 性能测试")
    print("=" * 60)
    print(f"RPC 节点: {config.rpc_url}")
    print(f"转账金额: {config.transfer_amount} ETH")
    print(f"分配金额: {config.distribution_amount} ETH")
    print(f"并发数: {config.concurrency}")
    print(f"Gas 价格: {config.gas_price_gwei} Gwei")
    print("=" * 60)
    
    tps_test = None
    try:
        # 创建测试实例
        tps_test = TPSTest(config)
        
        # 执行操作
        if args.create:
            tps_test.create_accounts()
        else:
            # 尝试加载已有账号
            if not tps_test.load_accounts():
                print("\n未找到已有账号文件，正在创建新账号...")
                tps_test.create_accounts()
        
        if args.verify:
            tps_test.verify_balances()
        
        if args.distribute:
            tps_test.distribute_balance()
            print("\n建议等待几秒让交易确认后再运行测试...")
            time.sleep(5)
        
        if args.test:
            if args.use_async:
                asyncio.run(tps_test.run_test_async(args.test))
            else:
                tps_test.run_test_threaded(args.test)
        
        if not (args.create or args.distribute or args.test or args.verify):
            parser.print_help()
            print("\n提示: 至少需要指定一个操作（--create, --distribute, --test, --verify）")
            
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        if tps_test and hasattr(tps_test, 'stats') and tps_test.stats.start_time > 0:
            tps_test.stats.end_time = time.time()
            tps_test.stats.display()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
