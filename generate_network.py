#!/usr/bin/env python3
"""
Ethereum PoA Network Generator
自动生成支持任意数量区块生产者和同步者的以太坊私有网络配置
"""

import os
import yaml
import json
import subprocess
import sys
from typing import List, Dict

class EthereumNetworkGenerator:
    def __init__(self, config_file: str = "config.yaml", output_dir: str = None):
        """初始化网络生成器"""
        self.config_file = config_file
        self.config = self.load_config()
        self.accounts = {}
        
        # 设置输出目录
        if output_dir:
            self.output_dir = output_dir
        else:
            # 使用网络名称或默认名称
            network_name = self.config.get('network', {}).get('name', 'ethereum-poa-network')
            self.output_dir = network_name
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
    def load_config(self) -> Dict:
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            print(f"错误: 配置文件 {self.config_file} 不存在")
            sys.exit(1)
            
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def create_directories(self):
        """创建节点目录"""
        print("创建节点目录...")
        producers = self.config.get('producers', [])
        synchers = self.config.get('synchers', [])
        
        for node in producers + synchers:
            node_dir = os.path.join(self.output_dir, f"node_{node['name']}")
            os.makedirs(node_dir, exist_ok=True)
            os.makedirs(f"{node_dir}/keystore", exist_ok=True)
            print(f"  ✓ {node_dir}")
    
    def create_password_files(self):
        """创建密码文件"""
        print("\n创建密码文件...")
        producers = self.config.get('producers', [])
        synchers = self.config.get('synchers', [])
        
        for node in producers + synchers:
            password_file = os.path.join(self.output_dir, f"node_{node['name']}_password.txt")
            with open(password_file, 'w') as f:
                f.write(node.get('password', 'password'))
            print(f"  ✓ {password_file}")
    
    def create_accounts(self):
        """为所有节点创建账户"""
        print("\n创建账户...")
        producers = self.config.get('producers', [])
        synchers = self.config.get('synchers', [])
        image = self.config.get('docker_image', 'ethereum/client-go:latest')
        
        for node in producers + synchers:
            node_name = node['name']
            node_dir = os.path.join(self.output_dir, f"node_{node_name}")
            password_file = os.path.join(self.output_dir, f"node_{node_name}_password.txt")
            keystore_dir = f"{node_dir}/keystore"
            
            # 首先检查是否已经有账户
            if os.path.exists(keystore_dir) and os.listdir(keystore_dir):
                # 从keystore文件中读取地址
                keystore_files = os.listdir(keystore_dir)
                if keystore_files:
                    keystore_file = keystore_files[0]
                    # 从文件名提取地址 (格式: UTC--timestamp--address)
                    if '--' in keystore_file:
                        address = '0x' + keystore_file.split('--')[-1]
                        self.accounts[node_name] = address
                        print(f"  ✓ {node_name}: {address} (已存在)")
                        continue
            
            # 创建新账户
            cmd = [
                'docker', 'run', '--rm',
                '-v', f"{os.path.abspath(node_dir)}:/root/.ethereum",
                '-v', f"{os.path.abspath(password_file)}:/password.txt",
                image,
                'account', 'new',
                '--password', '/password.txt'
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                # 从输出中提取地址 (尝试多种格式)
                address = None
                output = result.stderr + result.stdout
                
                for line in output.split('\n'):
                    # 格式1: Public address of the key:   0x...
                    if 'Public address of the key:' in line:
                        address = line.split(':')[-1].strip()
                        break
                    # 格式2: Address: {0x...}
                    elif 'Address:' in line and '0x' in line:
                        address = line.split('{')[-1].split('}')[0].strip()
                        break
                
                # 如果还是没找到，尝试从keystore文件名获取
                if not address:
                    keystore_files = os.listdir(keystore_dir)
                    if keystore_files:
                        keystore_file = keystore_files[0]
                        if '--' in keystore_file:
                            address = '0x' + keystore_file.split('--')[-1]
                
                if address:
                    self.accounts[node_name] = address
                    print(f"  ✓ {node_name}: {address}")
                else:
                    print(f"  ✗ 无法提取地址 ({node_name})")
                    print(f"  输出: {output}")
                    sys.exit(1)
                    
            except subprocess.CalledProcessError as e:
                print(f"  ✗ 创建账户失败 ({node_name}): {e}")
                print(f"  stderr: {e.stderr}")
                print(f"  stdout: {e.stdout}")
                sys.exit(1)
    
    def generate_genesis(self):
        """生成genesis.json文件"""
        print("\n生成genesis.json...")
        
        network_config = self.config.get('network', {})
        chain_id = network_config.get('chain_id', 123454321)
        block_period = network_config.get('block_period', 5)
        epoch = network_config.get('epoch', 30000)
        gas_limit = network_config.get('gas_limit', '800000000')
        initial_balance = network_config.get('initial_balance', '1000000000000000000')
        
        # 构建extradata (只包含区块生产者)
        producers = self.config.get('producers', [])
        validator_addresses = []
        for producer in producers:
            addr = self.accounts[producer['name']]
            if addr.startswith('0x'):
                addr = addr[2:]
            # 转换为小写
            validator_addresses.append(addr.lower())
        
        # extradata格式: 32字节前缀 + 验证者地址 + 65字节后缀
        extradata = '0x' + '0' * 64
        for addr in validator_addresses:
            extradata += addr
        extradata += '0' * 130
        
        # 构建alloc (所有节点都获得初始余额)
        alloc = {}
        all_nodes = producers + self.config.get('synchers', [])
        for node in all_nodes:
            addr = self.accounts[node['name']]
            if addr.startswith('0x'):
                addr = addr[2:]
            # 转换为小写
            alloc[addr.lower()] = {"balance": initial_balance}
        
        alloc_str = ',\n    '.join([f'"{addr}": {json.dumps(data)}' for addr, data in alloc.items()])
        
        # 读取模板
        template_path = 'genesis.json.template'
        if not os.path.exists(template_path):
            print(f"  ✗ 模板文件不存在: {template_path}")
            sys.exit(1)
            
        with open(template_path, 'r') as f:
            template = f.read()
        
        # 替换占位符
        genesis_content = template.replace('{{CHAIN_ID}}', str(chain_id))
        genesis_content = genesis_content.replace('{{BLOCK_PERIOD}}', str(block_period))
        genesis_content = genesis_content.replace('{{EPOCH}}', str(epoch))
        genesis_content = genesis_content.replace('{{GAS_LIMIT}}', gas_limit)
        genesis_content = genesis_content.replace('{{EXTRA_DATA}}', extradata)
        genesis_content = genesis_content.replace('{{ALLOC_ACCOUNTS}}', alloc_str)
        
        # 写入文件到输出目录
        genesis_path = os.path.join(self.output_dir, 'genesis.json')
        with open(genesis_path, 'w') as f:
            f.write(genesis_content)
        
        print(f"  ✓ {genesis_path} (验证者: {len(validator_addresses)}个)")
    
    def initialize_nodes(self):
        """初始化所有节点"""
        print("\n初始化节点...")
        producers = self.config.get('producers', [])
        synchers = self.config.get('synchers', [])
        image = self.config.get('docker_image', 'ethereum/client-go:latest')
        genesis_path = os.path.join(self.output_dir, 'genesis.json')
        
        for node in producers + synchers:
            node_name = node['name']
            node_dir = os.path.join(self.output_dir, f"node_{node_name}")
            
            cmd = [
                'docker', 'run', '--rm',
                '-v', f"{os.path.abspath(node_dir)}:/root/.ethereum",
                '-v', f"{os.path.abspath(genesis_path)}:/genesis.json",
                image,
                'init',
                '--datadir', '/root/.ethereum',
                '/genesis.json'
            ]
            
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                print(f"  ✓ {node_name}")
            except subprocess.CalledProcessError as e:
                print(f"  ✗ 初始化失败 ({node_name}): {e}")
                sys.exit(1)
    
    def get_enode_ids(self) -> Dict[str, str]:
        """获取所有区块生产者的enode ID"""
        print("\n获取区块生产者enode ID...")
        producers = self.config.get('producers', [])
        enode_ids = {}
        
        # 检查是否安装了必要的加密库
        try:
            from coincurve import PrivateKey
            has_coincurve = True
        except ImportError:
            has_coincurve = False
        
        for i, producer in enumerate(producers):
            node_name = producer['name']
            node_dir = os.path.join(self.output_dir, f"node_{node_name}")
            nodekey_path = os.path.join(node_dir, "geth/nodekey")
            
            # 检查nodekey文件是否存在
            if not os.path.exists(nodekey_path):
                print(f"  ✗ nodekey文件不存在 ({node_name})")
                print(f"  提示: 请确保节点已经正确初始化")
                sys.exit(1)
            
            # 读取nodekey（私钥）
            with open(nodekey_path, 'r') as f:
                nodekey_hex = f.read().strip()
            
            if has_coincurve:
                try:
                    # 使用coincurve库从私钥计算公钥
                    private_key_bytes = bytes.fromhex(nodekey_hex)
                    private_key = PrivateKey(private_key_bytes)
                    # 获取未压缩的公钥（去掉0x04前缀）
                    public_key_bytes = private_key.public_key.format(compressed=False)[1:]
                    enode_id = public_key_bytes.hex()
                    enode_ids[node_name] = enode_id
                    print(f"  ✓ {node_name}: {enode_id[:16]}...")
                    
                except Exception as e:
                    print(f"  ✗ 计算enode ID失败 ({node_name}): {e}")
                    sys.exit(1)
            else:
                # 如果没有安装coincurve，使用临时启动节点的方法
                print(f"  ! 未安装coincurve库，使用临时启动节点方法获取enode...")
                print(f"    (提示: 运行 'pip install coincurve' 可以加快这个过程)")
                enode_id = self._get_enode_from_running_node(node_name, i)
                if enode_id:
                    enode_ids[node_name] = enode_id
                    print(f"  ✓ {node_name}: {enode_id[:16]}...")
                else:
                    print(f"  ✗ 无法获取enode ID ({node_name})")
                    sys.exit(1)
        
        return enode_ids
    
    def _get_enode_from_running_node(self, node_name: str, index: int) -> str:
        """通过临时启动节点来获取enode ID（备用方法）"""
        import time
        
        node_dir = os.path.join(self.output_dir, f"node_{node_name}")
        password_file = os.path.join(self.output_dir, f"node_{node_name}_password.txt")
        port = 30306 + index
        image = self.config.get('docker_image', 'ethereum/client-go:latest')
        network_config = self.config.get('network', {})
        chain_id = network_config.get('chain_id', 123454321)
        
        # 临时启动节点
        cmd = [
            'docker', 'run', '--rm', '-d',
            '--name', f'temp-{node_name}',
            '-v', f"{os.path.abspath(node_dir)}:/root/.ethereum",
            image,
            '--datadir', '/root/.ethereum',
            '--port', str(port),
            '--networkid', str(chain_id),
            '--maxpeers', '0'  # 不连接其他节点
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            time.sleep(3)  # 等待节点启动
            
            # 读取日志获取enode
            logs_cmd = ['docker', 'logs', f'temp-{node_name}']
            result = subprocess.run(logs_cmd, capture_output=True, text=True)
            
            # 从日志中查找enode
            for line in result.stdout.split('\n') + result.stderr.split('\n'):
                if 'self=enode://' in line or 'enode://' in line:
                    # 提取enode ID
                    if 'enode://' in line:
                        enode_part = line.split('enode://')[1]
                        if '@' in enode_part:
                            enode_id = enode_part.split('@')[0]
                            return enode_id
            
            return None
            
        finally:
            # 停止容器
            subprocess.run(['docker', 'stop', f'temp-{node_name}'], 
                         capture_output=True, text=True)
    
    def generate_docker_compose(self, enode_ids: Dict[str, str]):
        """生成docker-compose.yml文件"""
        print("\n生成docker-compose.yml...")
        
        producers = self.config.get('producers', [])
        synchers = self.config.get('synchers', [])
        image = self.config.get('docker_image', 'ethereum/client-go:latest')
        network_config = self.config.get('network', {})
        chain_id = network_config.get('chain_id', 123454321)
        subnet = network_config.get('subnet', '172.20.0.0/16')
        base_ip = network_config.get('base_ip', '172.20.0.2')
        
        services = []
        ip_parts = base_ip.split('.')
        ip_counter = int(ip_parts[3])
        
        # 获取输出目录的绝对路径
        output_dir_abs = os.path.abspath(self.output_dir)
        
        # 生成区块生产者服务
        for i, producer in enumerate(producers):
            node_name = producer['name']
            node_dir = f"node_{node_name}"
            password_file = f"node_{node_name}_password.txt"
            p2p_port = 30306 + i
            rpc_port = 8545 + i
            node_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_counter}"
            ip_counter += 1
            
            address = self.accounts[node_name]
            
            # 构建bootnodes (第一个生产者不需要bootnodes，其他连接到第一个)
            bootnode_str = ''
            if i > 0:
                first_producer = producers[0]
                first_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{int(ip_parts[3])}"
                first_port = 30306
                first_enode = enode_ids[first_producer['name']]
                bootnode_str = f" --bootnodes enode://{first_enode}@{first_ip}:{first_port}"
            
            service = f"""  {node_name}:
    container_name: ethereum-{node_name}
    image: {image}
    volumes:
      - {output_dir_abs}/{node_dir}:/root/.ethereum
      - {output_dir_abs}/{password_file}:/password.txt
      - {output_dir_abs}/genesis.json:/genesis.json
    ports:
      - "{p2p_port}:{p2p_port}"
      - "{p2p_port}:{p2p_port}/udp"
      - "{rpc_port}:{rpc_port}"
    command: --datadir /root/.ethereum --port {p2p_port} --networkid {chain_id} --unlock {address} --password /password.txt --mine --miner.etherbase {address} --http --http.api eth,net,web3,personal,admin,clique --http.addr 0.0.0.0 --http.port {rpc_port} --http.corsdomain "*" --allow-insecure-unlock{bootnode_str}
    networks:
      ethnet:
        ipv4_address: {node_ip}"""
            
            services.append(service)
        
        # 生成同步节点服务
        # 构建所有生产者的bootnodes列表
        bootnode_list = []
        for i, producer in enumerate(producers):
            producer_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{int(ip_parts[3]) + i}"
            producer_port = 30306 + i
            producer_enode = enode_ids[producer['name']]
            bootnode_list.append(f"enode://{producer_enode}@{producer_ip}:{producer_port}")
        
        bootnodes = ','.join(bootnode_list)
        
        for i, syncher in enumerate(synchers):
            node_name = syncher['name']
            node_dir = f"node_{node_name}"
            password_file = f"node_{node_name}_password.txt"
            p2p_port = 30306 + len(producers) + i
            rpc_port = 8545 + len(producers) + i
            node_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_counter}"
            ip_counter += 1
            
            address = self.accounts[node_name]
            
            service = f"""  {node_name}:
    container_name: ethereum-{node_name}
    image: {image}
    depends_on:
      - {producers[0]['name']}
    volumes:
      - {output_dir_abs}/{node_dir}:/root/.ethereum
      - {output_dir_abs}/{password_file}:/password.txt
      - {output_dir_abs}/genesis.json:/genesis.json
    ports:
      - "{p2p_port}:{p2p_port}"
      - "{p2p_port}:{p2p_port}/udp"
      - "{rpc_port}:{rpc_port}"
    command: --datadir /root/.ethereum --port {p2p_port} --networkid {chain_id} --unlock {address} --password /password.txt --http --http.api eth,net,web3,personal,admin --http.addr 0.0.0.0 --http.port {rpc_port} --http.corsdomain "*" --allow-insecure-unlock --bootnodes {bootnodes}
    networks:
      ethnet:
        ipv4_address: {node_ip}"""
            
            services.append(service)
        
        # 读取模板并替换
        template_path = 'docker-compose.yml.template'
        if not os.path.exists(template_path):
            print(f"  ✗ 模板文件不存在: {template_path}")
            sys.exit(1)
            
        with open(template_path, 'r') as f:
            template = f.read()
        
        services_content = '\n\n'.join(services)
        docker_compose = template.replace('{{SERVICES}}', services_content)
        docker_compose = docker_compose.replace('{{SUBNET}}', subnet)
        
        # 写入文件到输出目录
        compose_path = os.path.join(self.output_dir, 'docker-compose.yml')
        with open(compose_path, 'w') as f:
            f.write(docker_compose)
        
        print(f"  ✓ {compose_path} ({len(producers)}个生产者, {len(synchers)}个同步者)")
    
    def save_node_info(self):
        """保存节点信息到文件"""
        print("\n保存节点信息...")
        
        info = {
            'network': self.config.get('network'),
            'output_directory': os.path.abspath(self.output_dir),
            'producers': [],
            'synchers': []
        }
        
        producers = self.config.get('producers', [])
        for i, producer in enumerate(producers):
            info['producers'].append({
                'name': producer['name'],
                'address': self.accounts[producer['name']],
                'rpc_port': 8545 + i,
                'p2p_port': 30306 + i,
                'rpc_url': f"http://localhost:{8545 + i}"
            })
        
        synchers = self.config.get('synchers', [])
        for i, syncher in enumerate(synchers):
            info['synchers'].append({
                'name': syncher['name'],
                'address': self.accounts[syncher['name']],
                'rpc_port': 8545 + len(producers) + i,
                'p2p_port': 30306 + len(producers) + i,
                'rpc_url': f"http://localhost:{8545 + len(producers) + i}"
            })
        
        info_path = os.path.join(self.output_dir, 'node_info.json')
        with open(info_path, 'w') as f:
            json.dump(info, f, indent=2)
        
        print(f"  ✓ {info_path}")
    
    def generate(self):
        """执行完整的生成流程"""
        print("=" * 60)
        print("以太坊PoA私有网络配置生成器")
        print("=" * 60)
        print(f"\n输出目录: {os.path.abspath(self.output_dir)}\n")
        
        self.create_directories()
        self.create_password_files()
        self.create_accounts()
        self.generate_genesis()
        self.initialize_nodes()
        enode_ids = self.get_enode_ids()
        self.generate_docker_compose(enode_ids)
        self.save_node_info()
        
        print("\n" + "=" * 60)
        print("✓ 配置生成完成!")
        print("=" * 60)
        print(f"\n所有文件已生成到: {os.path.abspath(self.output_dir)}")
        print("\n下一步:")
        print(f"  1. cd {self.output_dir}")
        print(f"  2. 运行: docker-compose up -d")
        print(f"  3. 查看节点信息: cat node_info.json")
        print("")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='生成以太坊PoA私有网络配置',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                                # 使用默认config.yaml
  %(prog)s -o output                      # 指定输出目录名称
  %(prog)s network_config.yaml            # 使用指定配置文件
  %(prog)s network_config.yaml -o output  # 同时指定配置文件和输出目录
        """
    )
    
    parser.add_argument(
        'config',
        nargs='?',
        default='config.yaml',
        help='配置文件路径 (默认: config.yaml)'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='output_dir',
        help='输出目录名称 (默认: 从配置文件读取network.name)'
    )
    
    args = parser.parse_args()
    
    generator = EthereumNetworkGenerator(args.config, args.output_dir)
    generator.generate()

if __name__ == "__main__":
    main()
