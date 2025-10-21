"""
实时监控消息处理
"""
import time
import os

def monitor_log():
    log_file = "logs/xianyu_2025-10-21.log"
    
    print("🔍 实时监控消息处理...")
    print("=" * 80)
    print("等待新消息...\n")
    
    # 获取当前文件大小
    try:
        current_size = os.path.getsize(log_file)
    except:
        print("❌ 日志文件不存在")
        return
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            # 跳到文件末尾
            f.seek(current_size)
            
            while True:
                line = f.readline()
                if line:
                    # 只显示相关的日志
                    if any(keyword in line for keyword in [
                        "收到】", "发出】", "跳过重复", "新消息已标记", 
                        "⏭️", "✅", "关键词匹配", "默认回复"
                    ]):
                        # 提取时间和内容
                        if "收到】" in line:
                            print(f"📥 {line.strip()}")
                        elif "发出】" in line:
                            print(f"📤 {line.strip()}")
                        elif "跳过重复" in line or "⏭️" in line:
                            print(f"⏭️  {line.strip()}")
                        elif "新消息已标记" in line or "✅" in line:
                            print(f"✅ {line.strip()}")
                        else:
                            print(f"ℹ️  {line.strip()}")
                else:
                    time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\n监控已停止")
    except Exception as e:
        print(f"\n❌ 监控出错: {e}")

if __name__ == "__main__":
    monitor_log()
