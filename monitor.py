import requests
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

# 配置区域（更新RPC节点列表）
RPC_NODES = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.gateway.pokt.network",
    "https://rpc.ankr.com/solana",
    "https://ssc-dao.genesysgo.net"
]
TELEGRAM_BOT_TOKEN = "7911654236:AAF9lXDllNVG9gtDUe54XV0GpUW9CUa7-GM"
TELEGRAM_CHAT_ID = "2078609125"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

def get_rpc_node():
    """获取可用RPC节点（带响应时间测试）"""
    working_nodes = []
    for node in RPC_NODES:
        try:
            start = time.time()
            response = requests.post(node, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBlockHeight"
            }, timeout=5)
            if response.status_code == 200:
                latency = (time.time() - start) * 1000
                working_nodes.append( (node, latency) )
        except:
            continue
    
    if not working_nodes:
        raise Exception("所有RPC节点不可用")
    
    # 选择延迟最低的节点
    return min(working_nodes, key=lambda x: x[1])[0]

def get_recent_blockhash(rpc_url):
    """获取最新区块hash（兼容新版API）"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getLatestBlockhash",
        "params": [{
            "commitment": "finalized"
        }]
    }
    
    try:
        response = requests.post(rpc_url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                return data['result']['value']['blockhash']
        print(f"区块hash响应异常：{response.text}")
    except Exception as e:
        print(f"区块hash请求失败：{str(e)}")
    return None

def get_new_tokens():
    """获取新代币数量（优化版）"""
    try:
        current_rpc = get_rpc_node()
        print(f"当前使用节点：{current_rpc}")
        
        blockhash = get_recent_blockhash(current_rpc)
        if not blockhash:
            print("⚠️ 无法获取有效区块hash")
            return 0

        # 获取当前时间戳（UTC）
        current_time = int(datetime.utcnow().timestamp())
        since_time = current_time - 60

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                TOKEN_PROGRAM_ID,
                {
                    "limit": 100,
                    "before": blockhash,
                    "commitment": "confirmed",
                    "filters": [
                        {
                            "memcmp": {
                                "offset": 0,
                                "bytes": "3Q3Lh6"  # InitializeMint的base58编码前缀
                            }
                        }
                    ]
                }
            ]
        }

        response = requests.post(current_rpc, json=payload, timeout=20).json()
        
        if "error" in response:
            print(f"RPC错误：{response['error']}")
            return 0
            
        valid_tokens = 0
        for sig in response.get("result", []):
            if sig.get("blockTime", 0) >= since_time:
                # 验证交易有效性
                tx_info = requests.post(current_rpc, json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [sig["signature"], "json"]
                }, timeout=15).json()
                
                if tx_info.get("result"):
                    valid_tokens += 1
        return valid_tokens

    except Exception as e:
        print(f"主流程异常：{str(e)}")
        return 0

# ...（保持send_telegram_message和job函数不变）

if __name__ == "__main__":
    try:
        print("🚀 初始化监控系统...")
        print(f"首选节点：{get_rpc_node()}")
        
        # 初始化调度器
        scheduler = BlockingScheduler()
        scheduler.add_job(job, 'interval', minutes=1, misfire_grace_time=60)
        
        # 立即执行并启动
        job()
        print("✅ 监控服务正常运行中")
        scheduler.start()
        
    except Exception as e:
        print(f"❌ 启动失败：{str(e)}")
        send_telegram_message(f"监控服务启动失败：{str(e)}")
